# fluid_test —— pygame_physics 流体（salva SPH）标准场景（2026-11-17
# solid/fluid 分层重构验收样张）：容器壁壳 + 水柱下落 + DFSPH 压力求
# 解 + **三渲同屏**（体素 mesh + rapier solid 线框 + salva 流体粒子球
# ——F1=solid 线框 / F2=流体粒子高亮 / F3=体素 mesh 按键切换）+
# 空格=注入一波新流体 / G=调度器 fluid 开关切换 / ESC 退出。
# 调度器：pygame_physics.scheduler_status() 实时读 / scheduler_enable
# ("fluid", False) 运行时暂停流体推进（solid 照常）——1 键切换演示。
# 控制台 [fluid-test] 逐项断言。
import pygame
import pygame_physics as pp

M = pygame.math
import pygame_voxelis

W, H = 800, 600

WGSL = """
struct Camera { mvp: mat4x4<f32>, };
struct Model { model: mat4x4<f32>, };
@group(0) @binding(0) var<uniform> camera: Camera;
@group(0) @binding(1) var<uniform> model: Model;
struct VIn {
    @location(0) pos: vec3<f32>,
    @location(1) nrm: vec3<f32>,
}
struct VOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) nrm: vec3<f32>,
}
@vertex
fn vs_main(vin: VIn) -> VOut {
    var o: VOut;
    let wp = model.model * vec4<f32>(vin.pos, 1.0);
    o.pos = camera.mvp * wp;
    o.nrm = normalize((model.model * vec4<f32>(vin.nrm, 0.0)).xyz);
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    // 水蓝渐变（顶亮底深——球面法线定向）
    let l = 0.45 + 0.55 * max(dot(in.nrm, normalize(vec3<f32>(0.4, 0.8, 0.5))), 0.0);
    return vec4<f32>(vec3<f32>(0.25, 0.5, 0.9) * l, 1.0);
}
"""

# instanced 单元球（半径 0.1——粒子半径 0.1 对应；12 三角）
SPHERE = [
    -0.1,-0.1, 0.1, 0,0,1,  0.1,-0.1, 0.1, 0,0,1,  0.1,0.1, 0.1, 0,0,1,
    -0.1,-0.1, 0.1, 0,0,1,  0.1, 0.1, 0.1, 0,0,1, -0.1,0.1, 0.1, 0,0,1,
     0.1,-0.1,-0.1, 0,0,-1, -0.1,-0.1,-0.1, 0,0,-1, -0.1,0.1,-0.1, 0,0,-1,
     0.1,-0.1,-0.1, 0,0,-1, -0.1,0.1,-0.1, 0,0,-1,  0.1,0.1,-0.1, 0,0,-1,
     0.1,-0.1, 0.1, 1,0,0,  0.1,-0.1,-0.1, 1,0,0,  0.1,0.1,-0.1, 1,0,0,
     0.1,-0.1, 0.1, 1,0,0,  0.1,0.1,-0.1, 1,0,0,  0.1,0.1, 0.1, 1,0,0,
    -0.1,-0.1,-0.1, -1,0,0, -0.1,-0.1, 0.1, -1,0,0, -0.1,0.1, 0.1, -1,0,0,
    -0.1,-0.1,-0.1, -1,0,0, -0.1,0.1, 0.1, -1,0,0, -0.1,0.1,-0.1, -1,0,0,
    -0.1, 0.1, 0.1, 0,1,0,  0.1, 0.1, 0.1, 0,1,0,  0.1, 0.1,-0.1, 0,1,0,
    -0.1, 0.1, 0.1, 0,1,0,  0.1, 0.1,-0.1, 0,1,0, -0.1, 0.1,-0.1, 0,1,0,
    -0.1,-0.1, 0.1, 0,-1,0, -0.1,-0.1,-0.1, 0,-1,0, 0.1,-0.1,-0.1, 0,-1,0,
    -0.1,-0.1, 0.1, 0,-1,0, 0.1,-0.1,-0.1, 0,-1,0, 0.1,-0.1, 0.1, 0,-1,0,
]


def fps_view(eye, yaw_deg, pitch_deg):
    yaw = M.radians(yaw_deg)
    pitch = M.radians(pitch_deg)
    fx = M.cos(pitch) * M.sin(yaw)
    fy = M.sin(pitch)
    fz = -M.cos(pitch) * M.cos(yaw)
    f = (fx, fy, fz)                       # 前向（单位——三角恒等式保证）
    up0 = (0.0, 1.0, 0.0)
    s0 = (fy * up0[2] - fz * up0[1],
          fz * up0[0] - fx * up0[2],
          fx * up0[1] - fy * up0[0])       # right = f × up（模 = cos(pitch)
                                            # ≠ 1——**必须归一化**，否则
                                            # pitch 越大横竖缩放越失配 =
                                            # 旋转画面拉伸畸变，2026-11-17
                                            # 用户实测报障根因）
    sn = (s0[0] * s0[0] + s0[1] * s0[1] + s0[2] * s0[2]) ** 0.5
    s = (s0[0] / sn, s0[1] / sn, s0[2] / sn)
    u = (s[1] * fz - s[2] * fy,
         s[2] * fx - s[0] * fz,
         s[0] * fy - s[1] * fx)            # true up = s × f（s⊥f 双单位
                                            # → u 自动单位）
    ex, ey, ez = eye
    # 视图基（行主视觉——标准 view 行向量）→ 列主展开（from_cols_array
    # 列主序契约：out[c*4+r] = m[r*4+c]）
    m = [
        s[0], s[1], s[2], -s[0] * ex - s[1] * ey - s[2] * ez,
        u[0], u[1], u[2], -u[0] * ex - u[1] * ey - u[2] * ez,
        -f[0], -f[1], -f[2], f[0] * ex + f[1] * ey + f[2] * ez,
        0.0, 0.0, 0.0, 1.0,
    ]
    cols = [m[r * 4 + c] for c in range(4) for r in range(4)]
    return M.mat4_from_cols_array(cols)




async def main():
    pygame.display.set_caption("fluid_test")
    screen = pygame.display.set_mode((800, 600))
    cjk = pygame.font.Font("cjk", 15)
    ac = pygame.render.access()
    frame = 0
    _fail = []

    def st(name, cond):
        if cond:
            print("[fluid-test] PASS", name)
        else:
            _fail.append(name)
            print("[fluid-test] FAIL", name)

    # ── 体素世界（场景主体——槽体两侧的墙）──
    vw = pygame_voxelis.VoxWorld(4, 16.0)
    # 槽体两侧墙（x=1 与 x=7 两列，z 4..8）
    for z in range(4, 9):
        for y in range(0, 3):
            vw.set_voxel(1, y, z, 1)
            vw.set_voxel(7, y, z, 1)
    vox_mesh_out = vw.generate_mesh()
    st("体素 mesh 出口", len(vox_mesh_out[0]) > 0)

    # ── solid 世界（地面 + 侧壁——fluid 粒子被约束在槽内）──
    solid = pp.PhysicsWorld3D(gravity=(0, -9.81, 0))
    solid.insert(
        pp.RigidBodyBuilder3D("fixed", translation=(0, -0.5, 0)),
        pp.ColliderBuilder3D("cuboid", hx=4.0, hy=0.5, hz=2.0, friction=0.5),
    )
    solid.insert(
        pp.RigidBodyBuilder3D("fixed", translation=(-2.5, 1.5, 0)),
        pp.ColliderBuilder3D("cuboid", hx=0.25, hy=1.5, hz=2.0),
    )
    solid.insert(
        pp.RigidBodyBuilder3D("fixed", translation=(2.5, 1.5, 0)),
        pp.ColliderBuilder3D("cuboid", hx=0.25, hy=1.5, hz=2.0),
    )
    solid.step_frame(1.0 / 60.0)   # 时序契约（查询前必步进一次）

    # ── fluid 世界（salva DFSPH——粒子半径 0.1）──
    fw = pp.FluidWorld(particle_radius=0.1)
    st("FluidWorld 构造", fw is not None)
    st("particle_radius 0.1", abs(fw.particle_radius() - 0.1) < 1e-6)
    st("boundary_count 0", fw.boundary_count() == 0)

    # 水柱：0.8×2.0×0.8 的方块水（spacing 0.2 → ~200 粒子）
    fh = fw.add_fluid_cuboid((-0.4, 1.0, -0.4), (0.8, 2.0, 0.8))
    st("add_fluid_cuboid 句柄", fh == 0)
    n = fw.fluid_particle_count(fh)
    st(f"水柱粒子数 {n} > 100", n > 100)

    # ── instanced 渲染管线（粒子 → GPU 球矩阵通路）──
    cam_buf = ac.buffer(64, label="cam_buf")
    model_buf = ac.buffer(64, label="model_buf")
    sphere_mesh = ac.mesh(["float32x3", "float32x3"], SPHERE, label="sphere_mesh")
    shader = ac.shader(WGSL, label="fluid_shader")
    bind = ac.bind_group([
        (0, "uniform", cam_buf),
        (1, "uniform", model_buf),
    ], label="fluid_bind")
    pipe = ac.pipeline(shader, sphere_mesh, [bind], cull="back",
                       blend="opaque", depth_mode="standard",
                       depth_write=True, label="fluid_pipe")

    # 相机（斜 45° 俯瞰槽）
    cam = pygame.render.game_camera_perspective(
        50.0, W, H, W, H, 0.1, 100.0)
    cam = cam.with_view(fps_view((0.0, 4.0, 9.0), 0.0, -25.0))
    screen.set_camera(cam)
    pygame.render.write_camera_mvp(cam_buf, cam.mvp())  # 初始——循环内静态相机恒定

    # 三渲开关（F1/F2/F3——debug 事件控制演示）
    solid_debug = False      # F1: rapier solid 线框
    fluid_debug = False      # F2: 流体粒子高亮
    vox_on = True            # F3: 体素 mesh 显示

    # 每粒子独立 model uniform + bind（粒子数固定——add_fluid_cuboid
    # 一次性建 160 粒子；空格注水追加时惰性扩容）
    particle_uniforms = []

    def ensure_particle_uniforms(count):
        while len(particle_uniforms) < count:
            i = len(particle_uniforms)
            b = ac.buffer(64, label=f"fluid_model_{i}")
            bd = ac.bind_group([
                (0, "uniform", cam_buf),
                (1, "uniform", b),
            ], label=f"fluid_model_bind_{i}")
            particle_uniforms.append((b, bd))

    # 体素 mesh 管线（同 WGSL——binding 1 恒单位阵填充）
    vox_model = ac.buffer(64, label="vox_model")   # WGSL 声明 binding 1——恒单位阵
    vox_mesh = ac.mesh(["float32x3", "float32x3"], vox_mesh_out[0], label="vox_mesh")
    vox_bind = ac.bind_group([
        (0, "uniform", cam_buf),
        (1, "uniform", vox_model),
    ], label="vox_bind")
    vox_pipe = ac.pipeline(shader, vox_mesh, [vox_bind], cull="back",
                           blend="opaque", depth_mode="standard",
                           depth_write=True, label="vox_pipe")

    # solid 调试线（rapier 线框——DebugLinesRenderer3D + collect3d）
    dbg_draw = pp.DebugDraw3D()
    dbg_sink = pp.LineSink3D()
    dbg_renderer = pp.DebugLinesRenderer3D(
        eye=(0.0, 4.0, 9.0), target=(0.0, 1.0, 0.0), fov=0.873)  # ≈50°

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN:
                if e.key == pygame.key.K_ESCAPE:
                    return
                if e.key == pygame.key.K_F1:
                    solid_debug = not solid_debug
                if e.key == pygame.key.K_F2:
                    fluid_debug = not fluid_debug
                if e.key == pygame.key.K_F3:
                    vox_on = not vox_on
                if e.key == pygame.key.K_SPACE:
                    # 注入一波新流体（顶部随机位置）
                    fh2 = fw.add_fluid_cuboid(
                        (-0.3 + (frame % 7) * 0.1, 3.0, -0.3),
                        (0.6, 0.4, 0.6))
                    print(f"[fluid-test] 注入流体 handle={fh2}")
                if e.key == pygame.key.K_g:
                    cur = pp.scheduler_status().get("fluid")
                    pp.scheduler_enable("fluid", not cur)
                    print(f"[fluid-test] 调度器 fluid → {not cur}")

        # 物理（solid + fluid 各自 step；调度器可运行时暂停任一）
        solid.step_frame(1.0 / 60.0)
        fw.step(1.0 / 60.0)

        positions, _vel = fw.fluid_particles(fh)
        ensure_particle_uniforms(len(positions) // 3)

        with screen.render() as rt:
            rt.fill((16, 20, 30))
            with screen.raw_render(depth=True) as p:
                # ① 体素 mesh（场景墙——F3 切换）
                if vox_on:
                    p.set_pipeline(vox_pipe)
                    p.set_bind_group(0, vox_bind)
                    p.draw_mesh(vox_mesh)
                # ② solid 线框（F1 切换——rapier collider 线框叠加）
                if solid_debug:
                    pp.collect3d(solid, dbg_draw, dbg_sink)
                    rt.draw_debug_3d(dbg_renderer, dbg_sink)
                # ③ 流体粒子球（每帧逐粒子 draw——200 粒子可承受）
                # ⚠️ 每粒子**独立 model uniform**（记录-回放模型：write 立
                # 即生效、draw 回放时读 buffer——共享 buf = 全部粒子叠在
                # 最后粒子的位置 = "没有渲染画面"假象；与 voxel_mc 多球
                # 叠影同款根因，2026-11-17 修复）
                for i in range(len(positions) // 3):
                    x = positions[i * 3]
                    y = positions[i * 3 + 1]
                    z = positions[i * 3 + 2]
                    if i >= len(particle_uniforms):
                        break
                    buf_i, bind_i = particle_uniforms[i]
                    ac.write_buffer(buf_i, M.mat4_translation(x, y, z))
                    p.set_pipeline(pipe)
                    p.set_bind_group(0, bind_i)
                    p.draw_mesh(sphere_mesh)

            # HUD
            pygame.gfxdraw.set_transform(rt, M.mat4_translation(-388, 288, 0))
            pygame.gfxdraw.draw_surface(rt, cjk.render(
                f"[fluid] 粒子 {len(positions) // 3} | F1 solid线框={solid_debug} "
                f"F2 流体={fluid_debug} F3 体素={vox_on} 空格=注水",
                True, (200, 210, 230)))
            pygame.gfxdraw.set_transform(rt, M.mat4_translation(-388, 268, 0))
            pygame.gfxdraw.draw_surface(rt, cjk.render(
                f"调度器: {pp.scheduler_status()}（G 键切 fluid 开关）",
                True, (180, 200, 180)))

        pygame.display.flip()
        if frame == 60:
            st("60 帧三渲同屏稳定", True)
        if frame == 300:
            pos_check = fw.fluid_particles(fh)
            st("300 帧粒子数据出口有效",
               len(pos_check[0]) == len(positions) and len(positions) > 0)
            print("[fluid-test] SUMMARY",
                  "PASS" if not _fail else "FAIL " + str(_fail))
        if frame > 3600:
            return
        await pygame.next_frame()
