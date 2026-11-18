# fluid2d_debug_calib —— DebugLinesRenderer 偏移场标定案例（2026-11-18，
# rapier2d debug 渲染偏移 debug 专用）：**无重力空间** + **九宫格方块**——
# 中心 (0,0) / 四轴 (±3,0)(0,±2) / 四象限 (±3,±2) 各放一个 fixed
# cuboid (hx=hy=0.3)，三点对照：
#   橙片 = GPU 管线（mat2d 位姿，流体/方块同款渲染链）
#   白/彩线框 = DebugLinesRenderer（rapier 原生 debug 渲染）
#   绿点 = 画布中心原点参照 (0,0)
# 每格橙片与线框重合 = 该位零偏移；分离形态（方向/量级随位置变化）
# = 偏移场直接可视化——反解两相机矩阵的差异语义
# （平移/缩放/旋转/非均匀）。无重力 = 方块恒静止（排除物理干扰）。
# ESC 退出。
import pygame
import pygame_physics as pp

M = pygame.math

W, H = 800, 600

# 方块位姿表（九宫格——世界坐标：米）
SPOTS = [
    (0.0, 0.0),                # 中心
    (3.0, 0.0), (-3.0, 0.0),   # x 轴两端
    (0.0, 2.0), (0.0, -2.0),   # y 轴两端
    (3.0, 2.0), (-3.0, 2.0),   # 四象限
    (3.0, -2.0), (-3.0, -2.0),
]

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
}
@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    o.pos = camera.mvp * (model.model * vec4<f32>(v.pos, 0.0, 1.0));
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    return vec4<f32>(0.95, 0.55, 0.25, 1.0);
}
"""

BLOCK = [
    -0.3, -0.3, 0.0, 0.0, 0.3, -0.3, 1.0, 0.0, 0.3, 0.3, 1.0, 1.0,
    -0.3, -0.3, 0.0, 0.0, 0.3, 0.3, 1.0, 1.0, -0.3, 0.3, 0.0, 1.0,
]


def mat2d(x, y):
    return M.mat4_from_cols_array(
        [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, 0, 1])


async def main():
    pygame.display.set_caption("fluid2d_debug_calib")
    screen = pygame.display.set_mode((800, 600))
    ac = pygame.render.access()

    # 无重力空间——方块恒静止（位姿全程已知）
    solid = pp.PhysicsWorld(gravity=(0, 0))
    handles = []
    for sx, sy in SPOTS:
        h = solid.insert(
            pp.RigidBodyBuilder("fixed", translation=(sx, sy)),
            pp.ColliderBuilder("cuboid", hx=0.3, hy=0.3),
        )[0]
        handles.append((h, sx, sy))
    solid.step_frame(1.0 / 60.0)

    cam = pygame.render.game_camera_ortho(14, 8, 800, 600)
    screen.set_camera(cam)

    cam_buf = ac.buffer(64)
    pygame.render.write_camera_mvp(cam_buf, cam.mvp())
    mesh = ac.mesh(["float32x2", "float32x2"], BLOCK)
    shader = ac.shader(WGSL)
    # 每方块独立 model uniform（九个片同管线异 model）
    binds = []
    for i, (h, sx, sy) in enumerate(handles):
        b = ac.buffer(64)
        ac.write_buffer(b, mat2d(sx, sy))
        binds.append(ac.bind_group([
            (0, "uniform", cam_buf), (1, "uniform", b),
        ]))
    pipe = ac.pipeline(shader, mesh, [binds[0]], cull="back", blend="opaque",
                       depth_mode="standard", depth_write=True)
    _ = binds

    dbg_draw = pp.DebugDraw()
    dbg_sink = pp.LineSink()
    dbg_renderer = pp.DebugLinesRenderer(ppm=60.0)

    green = pygame.Surface((20, 20))
    green.fill((0, 255, 0))

    frame = 0
    while frame < 3600:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        solid.step_frame(1.0 / 60.0)

        with screen.render() as t:
            t.fill((16, 20, 30))
            with screen.raw_render(depth=True) as p:
                p.set_pipeline(pipe)
                for bd in binds:
                    p.set_bind_group(0, bd)
                    p.draw_mesh(mesh)
            # 画布中心原点参照（绿点）
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_identity())
            pygame.gfxdraw.draw_surface(t, green)
            # rapier 原生 debug 线框（白/彩——与橙片逐格对照）
            dbg = pp.DebugDraw()
            pp.collect(solid, dbg, dbg_sink)
            dbg_renderer.set_mvp(cam.mvp())
            t.draw_debug(dbg_renderer, dbg_sink)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
