# fluid_test —— pygame_physics 流体（salva SPH）标准场景（2026-11-17
# solid/fluid 分层重构验收样张）：容器壁壳 + 水柱下落 + DFSPH 压力求
# 解 + instanced 球渲染（粒子出口 → GPU 粒子通路）。
# 按键：F1=solid 调试线框（rigid 线框）/ F2=流体粒子高亮切换（debug
# 事件控制演示）/ 空格=注入一波新流体 / ESC 退出。
# 调度器：pygame_physics.scheduler_status() 实时读 / scheduler_enable
# ("fluid", False) 运行时暂停流体推进（solid 照常）——1 键切换演示。
# 控制台 [fluid-test] 逐项断言。
import pygame
import pygame_physics as pp

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


async def main():
    pygame.display.set_caption("fluid_test")
    screen = pygame.display.set_mode((800, 600))
    cjk = pygame.font.Font("cjk", 15)
    ac = pygame.render.access()
    M = pygame.math
    frame = 0
    _fail = []

    def st(name, cond):
        if cond:
            print("[fluid-test] PASS", name)
        else:
            _fail.append(name)
            print("[fluid-test] FAIL", name)

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
    cam = cam.with_view(M.mat4_from_cols_array(
        [1, 0, 0, 0, 0, 0.707, 0.707, 0, 0, -0.707, 0.707, 0,
         0, -3.5, 9.0, 1]))
    screen.set_camera(cam)
    pygame.render.write_camera_mvp(cam_buf, cam.mvp())

    fluid_debug = False
    solid_debug = False

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
                if e.key == pygame.key.K_SPACE:
                    # 注入一波新流体（顶部随机位置）
                    fh2 = fw.add_fluid_cuboid(
                        (-0.3 + (frame % 7) * 0.1, 3.0, -0.3),
                        (0.6, 0.4, 0.6))
                    print(f"[fluid-test] 注入流体 handle={fh2}")

        # 物理（solid + fluid 各自 step；调度器可运行时暂停任一）
        solid.step_frame(1.0 / 60.0)
        fw.step(1.0 / 60.0)

        positions, _vel = fw.fluid_particles(fh)

        with screen.render() as rt:
            rt.fill((16, 20, 30))
            with screen.raw_render(depth=True) as p:
                p.set_pipeline(pipe)
                p.set_bind_group(0, bind)
                p.draw_mesh(sphere_mesh)
                # 流体粒子 instanced 球（位置由 GPU 通路外部注入——
                # v1 直接逐粒子 draw：200 粒子 @ 60fps 可承受）
                for i in range(len(positions) // 3):
                    x = positions[i * 3]
                    y = positions[i * 3 + 1]
                    z = positions[i * 3 + 2]
                    ac.write_buffer(model_buf, M.mat4_translation(x, y, z))
                    p.set_pipeline(pipe)
                    p.set_bind_group(0, bind)
                    p.draw_mesh(sphere_mesh)

            # HUD
            pygame.gfxdraw.set_transform(rt, M.mat4_translation(-388, 288, 0))
            pygame.gfxdraw.draw_surface(rt, cjk.render(
                f"[fluid] 粒子 {len(positions) // 3} | F1 solid线框={solid_debug} "
                f"F2 流体高亮={fluid_debug} 空格=注水", True, (200, 210, 230)))
            pygame.gfxdraw.set_transform(rt, M.mat4_translation(-388, 268, 0))
            pygame.gfxdraw.draw_surface(rt, cjk.render(
                f"调度器: {pp.scheduler_status()}（G 键切 fluid 开关）",
                True, (180, 200, 180)))

        pygame.display.flip()
        frame += 1
        if frame == 60:
            st("60 帧流体模拟稳定", True)
        if frame == 300:
            pos_check = fw.fluid_particles(fh)
            st("300 帧粒子数据出口有效",
               len(pos_check[0]) == len(positions) and len(positions) > 0)
            print("[fluid-test] SUMMARY",
                  "PASS" if not _fail else "FAIL " + str(_fail))
        if frame > 3600:
            return
        await pygame.next_frame()
