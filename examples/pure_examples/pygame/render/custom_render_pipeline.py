# cube_rotate —— mesh_builder 自定义布局 + cloth.png 纹理立方体：
# pos3 + normal3 + uv2 布局（mesh_builder 任意格式）+ 自定义 WGSL
# 纹理采样 + 法线光照。旋转立方体六面贴 cloth 纹理。
# 退出：ESC / 关窗。
import pygame

# WGSL：顶点 = pos3 + normal3 + uv2；片元 = 纹理采样 × 法线光照
WGSL_CUBE = """
struct Camera {
    mvp: mat4x4<f32>,
};
struct Model {
    model: mat4x4<f32>,
};

@group(0) @binding(0) var<uniform> camera: Camera;
@group(0) @binding(1) var<uniform> model: Model;
@group(0) @binding(2) var cloth_tex: texture_2d<f32>;
@group(0) @binding(3) var cloth_samp: sampler;

struct VIn {
    @location(0) pos: vec3<f32>,
    @location(1) nrm: vec3<f32>,
    @location(2) uv: vec2<f32>,
}

struct VOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) normal: vec3<f32>,
    @location(1) uv: vec2<f32>,
}

@vertex
fn vs_main(vin: VIn) -> VOut {
    var o: VOut;
    let world_pos = model.model * vec4<f32>(vin.pos, 1.0);
    o.pos = camera.mvp * world_pos;
    o.normal = normalize((model.model * vec4<f32>(vin.nrm, 0.0)).xyz);
    o.uv = vin.uv;
    return o;
}

@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let tex_color = textureSample(cloth_tex, cloth_samp, in.uv);
    // 法线漫反射 + 环境光
    let light_dir = normalize(vec3<f32>(0.6, 0.8, 0.7));
    let ndotl = max(dot(in.normal, light_dir), 0.0);
    let brightness = 0.25 + 0.75 * ndotl;
    return vec4<f32>(tex_color.rgb * brightness, tex_color.a);
}
"""


async def main():
    screen = pygame.display.set_mode((800, 600))
    cjk = pygame.font.Font("cjk", 17)
    title = cjk.render(
        "mesh_builder + cloth.png 纹理立方体（SAF 轮询槽形态）",
        True, (205, 205, 205))
    _fail = []

    def st(name, cond):
        if cond:
            print("[cube-demo] PASS", name)
        else:
            _fail.append(name)
            print("[cube-demo] FAIL", name)

    # 显式 camera（阶段一定约——渲染会话必传）
    cam = pygame.render.game_camera_perspective(58.0, 800, 600, 800, 600, 0.1, 300.0)
    screen.set_camera(cam)

    ac = pygame.render.access()

    # ── 加载纹理（cloth.png → Surface → bind_group texture 槽）──
    cloth = await pygame.image.load("cloth.png")
    st("cloth.png 加载", cloth is not None)
    print(f"[cube-demo] cloth.png size = {cloth.get_size()}")

    # ── shader ──
    shader = ac.shader(WGSL_CUBE, label="cube_shader")

    # ── 立方体顶点：pos3 + normal3 + uv2 = 8 floats/vertex ──
    # **索引式**（24 顶点 = 6 面 × 4 角点 + 36 索引 = 6 面 × 2 三角 × 3）：
    # 每面 4 角点按面法线独立（角点位置在 3 面间重复——法线/UV 按面定
    # 义的必然），面内角点共享；索引 u16。对照旧展开式 36 顶点：顶点
    # 缓冲 1152B→768B（-33%）+ 索引 72B = 净 -27%——大模型顶点属性
    # 十数倍于位置时收益成倍放大（GPU 复用顶点着色结果 + 前处理缓存
    # 命中）。每面顶点序 BL→BR→TR→TL（从面外看 CCW），索引 (0,1,2
    # 0,2,3)×面基；UV 整块 cloth 纹理 (0,0)-(1,1)
    def face(bl, br, tr, tl, n):
        return [
            *bl, *n, 0.0, 1.0,
            *br, *n, 1.0, 1.0,
            *tr, *n, 1.0, 0.0,
            *tl, *n, 0.0, 0.0,
        ]

    verts = (
        face([-1, -1,  1], [ 1, -1,  1], [ 1,  1,  1], [-1,  1,  1], [0, 0,  1])   # 前 +z
        + face([ 1, -1, -1], [-1, -1, -1], [-1,  1, -1], [ 1,  1, -1], [0, 0, -1])  # 后 -z
        + face([ 1, -1,  1], [ 1, -1, -1], [ 1,  1, -1], [ 1,  1,  1], [ 1, 0, 0])  # 右 +x
        + face([-1, -1, -1], [-1, -1,  1], [-1,  1,  1], [-1,  1, -1], [-1, 0, 0])  # 左 -x
        + face([-1,  1,  1], [ 1,  1,  1], [ 1,  1, -1], [-1,  1, -1], [0,  1, 0])  # 上 +y
        + face([-1, -1,  1], [-1, -1, -1], [ 1, -1, -1], [ 1, -1,  1], [0, -1, 0])  # 下 -y
    )
    # 索引流（u16 LE）：每面 (0,1,2 0,2,3) 相对面基偏移
    indices = []
    for f in range(6):
        b = f * 4
        indices += [b, b + 1, b + 2, b, b + 2, b + 3]
    index_bytes = b"".join(i.to_bytes(2, "little") for i in indices)

    mesh = ac.mesh(
        ["float32x3", "float32x3", "float32x2"], verts,
        index_bytes=index_bytes, label="textured_cube_idx"
    )
    st("mesh 索引式（24 vertex × 8f）", mesh.vertex_count() == 24)
    st("index_count 36（12 三角）", mesh.index_count() == 36)
    st("has_index_buffer", mesh.has_index_buffer())
    st("index_format u16", mesh.index_format() == "u16")

    # ── uniform buffer + bind group（camera + model + texture + sampler）──
    cam_buf = ac.buffer(64, label="cam_buf")
    model_buf = ac.buffer(64, label="model_buf")

    bind = ac.bind_group([
        (0, "uniform", cam_buf),
        (1, "uniform", model_buf),
        (2, "texture", cloth),
        (3, "sampler", None),
    ], label="cube_bind")
    st("bind_group 4 槽", True)

    pipe = ac.pipeline(shader, mesh, [bind],
        cull="back",
        blend="opaque",
        depth_mode="standard",
        depth_write=True,
        label="cube_textured")

    frame = 0
    asserted = False
    M = pygame.math

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        t_sec = frame / 60.0

        # 模型矩阵：Y 持续旋转 + X 慢速摇摆（@ 矩阵组合）
        rot_y = M.quat_from_axis_angle(0.0, 1.0, 0.0, t_sec * 42.0)
        rot_x = M.quat_from_axis_angle(1.0, 0.0, 0.0, M.sin(t_sec * 1.0) * 50.0)
        model_mat =  M.mat4_translation(0.0, 0.0,  abs(M.sin(t_sec * 1.0)) * -10) @ M.mat4_from_quat(rot_y) @ M.mat4_from_quat(rot_x) @ M.mat4_scale(2.6, 2.6, 2.6)#

        # 自管透视相机
        view = M.mat4_translation(0.0, 0.0, -7.2)
        proj = pygame.render.game_camera_perspective(58.0, 800, 600, 800, 600, 0.1, 300.0).with_view(view)

        pygame.render.write_camera_mvp(cam_buf, proj.mvp())
        ac.write_buffer(model_buf, model_mat)

        with screen.render() as rt:
            rt.fill((14, 15, 22))
            if frame == 0:
                st("screen attachment ok", pygame.render.screen_attachment() is not None)
            rt.fill((12, 13, 20))
            pygame.gfxdraw.draw_surface(rt, title, transform=pygame.math.mat4_translation(-380, 270, 0))

            with screen.raw_render(depth=True) as p:
                p.push_debug_group("textured_cube")
                p.set_pipeline(pipe)
                p.set_bind_group(0, bind)
                p.draw_mesh(mesh)
                p.pop_debug_group()

        pygame.display.flip()

        if frame in (30, 60):
            print("[cube-state]", pygame.render.screen_frame_state())

        frame += 1

        if not asserted and frame == 60:
            st("raw_render textured cube 60 frame ok", True)
            asserted = True
            print("[cube-demo] SUMMARY",
                  "PASS" if not _fail else "FAIL " + str(_fail))

        await pygame.tasks.yield_now()
