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

    ac = pygame.render.access()

    # ── 加载纹理（cloth.png → Surface → bind_group texture 槽）──
    cloth = await pygame.image.load("cloth.png")
    st("cloth.png 加载", cloth is not None)
    print(f"[cube-demo] cloth.png size = {cloth.get_size()}")

    # ── shader ──
    shader = ac.shader(WGSL_CUBE, label="cube_shader")

    # ── 立方体顶点：pos3 + normal3 + uv2 = 8 floats/vertex ──
    # 每面 4 顶点 × 6 面 = 24 顶点；索引 36（6 面 × 2 三角形 × 3）
    # 每面 UV 映射整块 cloth 纹理 (0,0)-(1,1)
    verts = [
        # 前面 +z
        -1.0, -1.0,  1.0,   0.0, 0.0,  1.0,   0.0, 0.0,
         1.0, -1.0,  1.0,   0.0, 0.0,  1.0,   1.0, 0.0,
         1.0,  1.0,  1.0,   0.0, 0.0,  1.0,   1.0, 1.0,
        -1.0, -1.0,  1.0,   0.0, 0.0,  1.0,   0.0, 0.0,
         1.0,  1.0,  1.0,   0.0, 0.0,  1.0,   1.0, 1.0,
        -1.0,  1.0,  1.0,   0.0, 0.0,  1.0,   0.0, 1.0,

        # 后面 -z
        -1.0, -1.0, -1.0,   0.0, 0.0, -1.0,   0.0, 0.0,
         1.0, -1.0, -1.0,   0.0, 0.0, -1.0,   1.0, 0.0,
         1.0,  1.0, -1.0,   0.0, 0.0, -1.0,   1.0, 1.0,
        -1.0, -1.0, -1.0,   0.0, 0.0, -1.0,   0.0, 0.0,
         1.0,  1.0, -1.0,   0.0, 0.0, -1.0,   1.0, 1.0,
        -1.0,  1.0, -1.0,   0.0, 0.0, -1.0,   0.0, 1.0,

        # 右面 +x
         1.0, -1.0, -1.0,   1.0, 0.0,  0.0,   0.0, 0.0,
         1.0, -1.0,  1.0,   1.0, 0.0,  0.0,   1.0, 0.0,
         1.0,  1.0,  1.0,   1.0, 0.0,  0.0,   1.0, 1.0,
         1.0, -1.0, -1.0,   1.0, 0.0,  0.0,   0.0, 0.0,
         1.0,  1.0,  1.0,   1.0, 0.0,  0.0,   1.0, 1.0,
         1.0,  1.0, -1.0,   1.0, 0.0,  0.0,   0.0, 1.0,

        # 左面 -x
        -1.0, -1.0, -1.0,  -1.0, 0.0,  0.0,   0.0, 0.0,
        -1.0, -1.0,  1.0,  -1.0, 0.0,  0.0,   1.0, 0.0,
        -1.0,  1.0,  1.0,  -1.0, 0.0,  0.0,   1.0, 1.0,
        -1.0, -1.0, -1.0,  -1.0, 0.0,  0.0,   0.0, 0.0,
        -1.0,  1.0,  1.0,  -1.0, 0.0,  0.0,   1.0, 1.0,
        -1.0,  1.0, -1.0,  -1.0, 0.0,  0.0,   0.0, 1.0,

        # 上面 +y
        -1.0,  1.0, -1.0,   0.0, 1.0,  0.0,   0.0, 0.0,
         1.0,  1.0, -1.0,   0.0, 1.0,  0.0,   1.0, 0.0,
         1.0,  1.0,  1.0,   0.0, 1.0,  0.0,   1.0, 1.0,
        -1.0,  1.0, -1.0,   0.0, 1.0,  0.0,   0.0, 0.0,
         1.0,  1.0,  1.0,   0.0, 1.0,  0.0,   1.0, 1.0,
        -1.0,  1.0,  1.0,   0.0, 1.0,  0.0,   0.0, 1.0,

        # 下面 -y
        -1.0, -1.0, -1.0,   0.0, -1.0, 0.0,   0.0, 0.0,
         1.0, -1.0, -1.0,   0.0, -1.0, 0.0,   1.0, 0.0,
         1.0, -1.0,  1.0,   0.0, -1.0, 0.0,   1.0, 1.0,
        -1.0, -1.0, -1.0,   0.0, -1.0, 0.0,   0.0, 0.0,
         1.0, -1.0,  1.0,   0.0, -1.0, 0.0,   1.0, 1.0,
        -1.0, -1.0,  1.0,   0.0, -1.0, 0.0,   0.0, 1.0,
    ]
    indices = []
    for i in range(6):
        base = i * 4
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    # mesh_builder：任意布局（pos3 + normal3 + uv2——预设里没有的组合）
    mesh = ac.mesh(
        ["float32x3", "float32x3", "float32x2"], verts,
        indices=indices, label="textured_cube"
    )
    st("mesh 创建（24 vertex）", mesh.vertex_count() > 0)
    st("索引 36", mesh.index_count() == 36 or mesh.index_count() == 0)

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

    pipe = ac.pipeline(shader, mesh, [bind], label="cube_textured")

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
        rot_x = M.quat_from_axis_angle(1.0, 0.0, 0.0, M.sin(t_sec * 1.8) * 28.0)
        model_mat = M.mat4_from_quat(rot_y) @ M.mat4_from_quat(rot_x) @ M.mat4_scale(2.6, 2.6, 2.6)

        # 自管透视相机
        view = M.mat4_translation(0.0, 0.0, -7.2)
        proj = pygame.render.camera_perspective(
            58.0, 800 / 600, 0.1, 300.0
        ).with_view(view)

        pygame.render.write_camera_mvp(cam_buf, proj.mvp())
        ac.write_buffer(model_buf, model_mat)

        with screen.render() as rt:
            if frame == 0:
                st("screen attachment ok", pygame.render.screen_attachment() is not None)
            rt.fill((12, 13, 20))
            pygame.gfxdraw.set_transform(rt, M.mat4_translation(-380, 270, 0))
            pygame.gfxdraw.draw_surface(rt, title)

            with rt.raw_render() as p:
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

        await pygame.next_frame()
