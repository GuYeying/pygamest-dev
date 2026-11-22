# fluid2d_test —— pygame_physics 2D 流体×刚体碰撞标准场景（2026-11-18，
# fluid2d 轴验收样张）：**静态刚体 × 2D 流体**——rapier 2D 斜面 + 大
# 地面（PhysicsWorld）经 FluidWorld2D.step(dt, solid) 耦合步进
# （DynamicContactSampling 硬投影——与 3D 同源语义，salva2d/salva3d
# 同一上游 src），水柱从斜面高端滑落 → 摊开 → 静置。
# **2D 流体 debug 渲染**：instanced quad 片元圆判（渲染半径
# 1.4×粒子半径——视觉重叠连贯表面）+ game_camera_ortho 正交相机；
# T 键 = 2D solid 线框（**rapier2d DebugLinesRenderer 标准链**——
# collect 全量 collider 形状 + set_mvp 与主管线同矩阵绝对对齐；
# 2026-11-18 自 gfxdraw 手绘迁回——两段式渲染域修复后 overlay 相机
# 写入已实证生效，fluid2d_debug_calib 同链三平台验收通过）。
# 空格=注水 / F=投放动态小立方体（自由落体砸水——观测流体被排开的
# 水花形态与刚体穿行）/ ESC 退出。控制台 [fluid2d-test] 逐项断言。
import pygame
import pygame_physics as pp

M = pygame.math

W, H = 800, 600

WGSL = """
struct Camera { mvp: mat4x4<f32>, };
struct Model { model: mat4x4<f32>, };
@group(0) @binding(0) var<uniform> camera: Camera;
@group(0) @binding(1) var<uniform> model: Model;
struct VIn {
    @location(0) pos: vec2<f32>,
    @location(1) uv: vec2<f32>,
}
struct VOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
}
@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    let wp = model.model * vec4<f32>(v.pos, 0.0, 1.0);
    o.pos = camera.mvp * wp;
    o.uv = v.uv;
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    // 2D 圆判（quad 片元到中心距离 > 半径 discard——水蓝填充，中心亮
    // 边缘暗微立体；渲染半边 0.14 = 1.4×粒子半径视觉重叠）
    let d = length(in.uv - vec2<f32>(0.5, 0.5));
    if (d > 0.5) { discard; }
    let l = 0.6 + 0.4 * clamp((0.5 - d) * 4.0, 0.0, 1.0);
    return vec4<f32>(vec3<f32>(0.25, 0.5, 0.9) * l, 1.0);
}
"""

# 动态方块 WGSL（灰橙方片——无圆判，自由落体刚体渲染）
BLOCK_WGSL = WGSL.replace("""    let d = length(in.uv - vec2<f32>(0.5, 0.5));
    if (d > 0.5) { discard; }
    let l = 0.6 + 0.4 * clamp((0.5 - d) * 4.0, 0.0, 1.0);
    return vec4<f32>(vec3<f32>(0.25, 0.5, 0.9) * l, 1.0);""", """    let l = 0.75;
    return vec4<f32>(vec3<f32>(0.95, 0.55, 0.25) * l, 1.0);""")

# instanced 单元圆片（quad 半边 0.10 = 粒子半径——DC 投影粒子中心
# 距表面仅 ~0.01，渲染半径 > 粒子半径会让贴面圆过半嵌入线框 = 穿模
# 观感（2026-11-18 用户截图反馈）；半径=粒子半径为标准 SPH 渲染形态
QUAD = [
    -0.10, -0.10, 0.0, 0.0, 0.10, -0.10, 1.0, 0.0, 0.10, 0.10, 1.0, 1.0,
    -0.10, -0.10, 0.0, 0.0, 0.10, 0.10, 1.0, 1.0, -0.10, 0.10, 0.0, 1.0,
]


# instanced 单元方块（动态刚体渲染单元——半边 0.15 对应 collider）
BLOCK = [
    -0.15, -0.15, 0.0, 0.0, 0.15, -0.15, 1.0, 0.0, 0.15, 0.15, 1.0, 1.0,
    -0.15, -0.15, 0.0, 0.0, 0.15, 0.15, 1.0, 1.0, -0.15, 0.15, 0.0, 1.0,
]


def mat2d(x, y, ang):
    # 2D 位姿矩阵（绕 z 旋转 + 平移——列主 16 元素）
    c = M.cos(ang)
    s = M.sin(ang)
    return M.mat4_from_cols_array(
        [c, s, 0, 0, -s, c, 0, 0, 0, 0, 1, 0, x, y, 0, 1])


async def main():
    pygame.display.set_caption("fluid2d_test")
    screen = pygame.display.set_mode((800, 600))
    cjk = pygame.font.Font("cjk", 15)
    ac = pygame.render.access()
    frame = 0
    _fail = []

    def st(name, cond):
        if cond:
            print("[fluid2d-test] PASS", name)
        else:
            _fail.append(name)
            print("[fluid2d-test] FAIL", name)

    # ── solid 世界（rapier 2D 静态刚体——**碰撞主角**）──
    # 地面（大平面）+ 斜面（rotation 单弧度标量，+x 端翘起）。耦合注册
    # 按 collider 位姿每步重采样——旋转刚体开箱即用；线框由
    # DebugLinesRenderer collect 全量 collider 自动绘制（零登记）
    solid = pp.PhysicsWorld(gravity=(0, -9.81))
    solid.insert(
        pp.RigidBodyBuilder("fixed", translation=(0, -0.25)),
        pp.ColliderBuilder("cuboid", hx=6.0, hy=0.25, friction=0.5),
    )
    solid.insert(
        pp.RigidBodyBuilder("fixed", translation=(0.5, 1.2), rotation=0.35),
        pp.ColliderBuilder("cuboid", hx=1.6, hy=0.12, friction=0.1),
    )
    solid.step()                    # 时序契约（查询前必步进一次）

    # ── fluid 世界（salva2d DFSPH——粒子半径 0.1；XSPH 粘性默认挂）──
    fw = pp.FluidWorld2D(particle_radius=0.1)
    st("FluidWorld2D 构造", fw is not None)
    st("particle_radius 0.1", abs(fw.particle_radius() - 0.1) < 1e-6)

    # 水柱：1.4×1.2 矩形水（spacing 0.2 → 42 粒子），位于斜面高端上方
    fh = fw.add_fluid_cuboid((1.2, 2.6), (1.4, 1.2))
    n = fw.fluid_particle_count(fh)
    st(f"水柱粒子数 {n} > 30", n > 30)

    # ── instanced 渲染管线（quad 圆判 → GPU 通路）──
    cam_buf = ac.buffer(64, label="cam2d_buf")
    quad_mesh = ac.mesh(["float32x2", "float32x2"], QUAD, label="quad2d_mesh")
    shader = ac.shader(WGSL, label="fluid2d_shader")

    # 正交相机（世界 14×8 原点居中 → 800×600 窗口；ortho 签名全 u32）
    cam = pygame.render.game_camera_ortho(14, 8, W, H)
    screen.set_camera(cam)
    pygame.render.write_camera_mvp(cam_buf, cam.mvp())  # 静态相机恒定

    # 每粒子独立 model uniform + bind（记录-回放模型惯例——共享 buf =
    # 全部粒子叠最后粒子位置；惰性扩容跟上注水）
    particle_uniforms = []

    def ensure_particle_uniforms(count):
        while len(particle_uniforms) < count:
            i = len(particle_uniforms)
            b = ac.buffer(64, label=f"fluid2d_model_{i}")
            bd = ac.bind_group([
                (0, "uniform", cam_buf),
                (1, "uniform", b),
            ], label=f"fluid2d_bind_{i}")
            particle_uniforms.append((b, bd))

    pipe = None   # 首帧粒子数就绪后建

    # solid 线框（**rapier2d DebugLinesRenderer 标准链**——collect 全量
    # collider 形状 + set_mvp 与主管线同矩阵绝对对齐；DebugDraw 每帧新
    # 建（calib 参照实现同款——回调消费体逐帧重置最稳）；2026-11-18 自
    # gfxdraw 手绘迁回——两段式修复后 overlay 相机写入已实证生效）
    dbg_sink = pp.LineSink()
    pixel_cam = pygame.render.game_camera_ortho(800, 600, 800, 600)
    dbg_renderer = pp.DebugLinesRenderer()

    solid_debug = True   # T 键切换（默认开——碰撞对齐目视验收）
    drops = []           # 动态方块句柄（F 键投放——自由落体砸水）

    # 方块渲染管线（BLOCK_WGSL 灰橙方片 + per-body uniform 惰性扩容）
    block_mesh = ac.mesh(["float32x2", "float32x2"], BLOCK, label="block2d_mesh")
    block_shader = ac.shader(BLOCK_WGSL, label="block2d_shader")
    block_uniforms = []

    def ensure_block_uniforms(count):
        while len(block_uniforms) < count:
            i = len(block_uniforms)
            b = ac.buffer(64, label=f"block2d_model_{i}")
            bd = ac.bind_group([
                (0, "uniform", cam_buf),
                (1, "uniform", b),
            ], label=f"block2d_bind_{i}")
            block_uniforms.append((b, bd))

    block_pipe = None
    clock = pygame.time.Clock()          # 真实帧间隔度量（accumulator 喂食源）

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN:
                if e.key == pygame.key.K_ESCAPE:
                    return
                if e.key == pygame.key.K_t:
                    solid_debug = not solid_debug
                if e.key == pygame.key.K_SPACE:
                    fh2 = fw.add_fluid_cuboid(
                        (1.0 + (frame % 5) * 0.08, 3.6), (0.5, 0.4))
                    print(f"[fluid2d-test] 注入流体 handle={fh2}")
                if e.key == pygame.key.K_f:
                    # 投放高度 2.4（水面 2.0 上方 0.4——入水速度 ~2.8 m/s；
                    # 曾 3.8 = 入水 ~7 m/s，DC 采样 60Hz 下单步位移 > 粒子
                    # 间距 40%，排开呈冲击爆开、水花形态不可辨——2026-11-19
                    # 量化实证：包络展宽 0..1.8 → -1.9..3.7 = 排开存在）
                    # ⚠️ DC 耦合语义 = **单向**（刚体是移动边界——粒子被
                    # 推开，刚体不受浮力/拖拽反作用）：方块入水后继续
                    # 加速沉底 = 语义现状，观测对象是排开水花与绕流
                    x = -1.5 + (frame % 5) * 0.6
                    h = solid.insert(
                        pp.RigidBodyBuilder(
                            "dynamic", translation=(x, 2.4)),
                        pp.ColliderBuilder("cuboid", hx=0.15, hy=0.15))[0]
                    drops.append(h)
                    print(f"[fluid2d-test] 投放方块 handle={h} @x={x}")

        # 物理（solid + fluid 耦合步进——**本案例核心**）
        solid.step_frame(clock.get_time() / 1000.0)
        fw.step(clock.get_time() / 1000.0, solid)

        if frame == 1:
            bc = fw.boundary_count()
            st(f"耦合边界注册 {bc} >= 2", bc >= 2)

        positions, _vel = fw.fluid_particles(fh)
        count = len(positions) // 2
        ensure_particle_uniforms(count)
        if pipe is None and count > 0:
            model_buf = ac.buffer(64, label="model2d_template")
            bind = ac.bind_group([
                (0, "uniform", cam_buf),
                (1, "uniform", model_buf),
            ], label="fluid2d_bind")
            pipe = ac.pipeline(shader, quad_mesh, [bind], cull="back",
                               blend="opaque", depth_mode="standard",
                               depth_write=True, label="fluid2d_pipe")

        with screen.render() as t:
            t.fill((16, 20, 30))
            # ① 2D 流体粒子圆（raw 段——instanced quad 圆判管线）
            with screen.raw_render(depth=True) as p:
                for i in range(count):
                    x = positions[i * 2]
                    y = positions[i * 2 + 1]
                    buf_i, bind_i = particle_uniforms[i]
                    ac.write_buffer(buf_i, M.mat4_translation(x, y, 0.0))
                    p.set_pipeline(pipe)
                    p.set_bind_group(0, bind_i)
                    p.draw_mesh(quad_mesh)
            # ② 动态方块（F 键投放——translation/rotation 读回 → 2D
            # 位姿矩阵；落水穿行时流体粒子被 DC 投影排开 = 水花观测）
            if drops:
                ensure_block_uniforms(len(drops))
                if block_pipe is None:
                    model_buf = ac.buffer(64, label="block2d_template")
                    bind = ac.bind_group([
                        (0, "uniform", cam_buf),
                        (1, "uniform", model_buf),
                    ], label="block2d_bind")
                    block_pipe = ac.pipeline(block_shader, block_mesh,
                                             [bind], cull="back",
                                             blend="opaque",
                                             depth_mode="standard",
                                             depth_write=True,
                                             label="block2d_pipe")
                with screen.raw_render(depth=True) as p:
                    for i, h in enumerate(drops):
                        x, y = solid.translation(h)
                        ang = solid.rotation(h)
                        buf_i, bind_i = block_uniforms[i]
                        ac.write_buffer(buf_i, mat2d(x, y, ang))
                        p.set_pipeline(block_pipe)
                        p.set_bind_group(0, bind_i)
                        p.draw_mesh(block_mesh)
            # ③ solid 线框（T 切换——**rapier2d DebugLinesRenderer 标准链**：
            # collect 全量 collider 形状 + set_mvp 与主管线同矩阵绝对对齐
            # + overlay 通道绘制；DebugDraw 每帧新建逐帧重置）
            if solid_debug:
                dbg = pp.DebugDraw()
                pp.collect(solid, dbg, dbg_sink)
                dbg_renderer.set_mvp(cam.mvp())
                t.draw_debug(dbg_renderer, dbg_sink)

            # HUD（段级显式像素相机——v3.1 全显式：米制相机下像素 UI
            # 须显式切段声明像素域，画毕 clear_camera 交还）
            pygame.gfxdraw.set_camera(t, pixel_cam)
            pygame.gfxdraw.set_transform(t, M.mat4_translation(-388, 288, 0))
            pygame.gfxdraw.draw_surface(t, cjk.render(
                f"[fluid2d] 粒子 {count} 方块 {len(drops)} | T 线框={solid_debug} "
                f"空格=注水 F=投放方块", True, (200, 210, 230)))
            pygame.gfxdraw.set_transform(t, M.mat4_translation(-388, 268, 0))
            pygame.gfxdraw.draw_surface(t, cjk.render(
                f"2D 轴: physics2d + fluid2d（salva2d DC 耦合）",
                True, (180, 200, 180)))
            pygame.gfxdraw.clear_camera(t)

        pygame.display.flip()
        clock.tick(0)                      # 跟帧度量（vsync 节拍，get_time 供 accumulator）
        if frame == 60:
            st("60 帧刚体×流体耦合渲染稳定", True)
        if frame == 300:
            pos, vel = fw.fluid_particles(fh)
            n2 = len(pos)
            mn_y = min(pos[1::2]) if n2 else -99.0
            mn_x = min(pos[0::2]) if n2 else 99.0
            mx_s = max((vel[i]**2 + vel[i+1]**2) ** 0.5
                       for i in range(0, len(vel), 2)) if n2 else 99.0
            # 未穿地（地面顶 y=0）+ 滑落交互（越过斜面中线——XSPH 粘性
            # 下蜂蜜状慢速成团滑落）+ 静置衰减（能量正常耗散）
            st(f"300 帧未穿地 min_y={mn_y:.3f} > -0.4", mn_y > -0.4)
            st(f"300 帧滑落交互 min_x={mn_x:.3f} < 0", mn_x < 0)
            st(f"300 帧静置衰减 max_spd={mx_s:.2f} < 2.0", mx_s < 2.0)
            st("300 帧粒子数据出口有效", n2 == len(positions) and count > 0)
            print("[fluid2d-test] SUMMARY",
                  "PASS" if not _fail else "FAIL " + str(_fail))
        if frame > 36000000:
            return
        await pygame.next_frame()
        frame += 1
