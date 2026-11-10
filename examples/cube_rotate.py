# custom_pipeline_demo_cube：自建 WGSL 管线 + raw_render
# 3D 旋转立方体，同架构：自管相机、独立 uniform buffer、自定义管线
import pygame



def sin(x: float, eps: float = 1e-10) -> float:
    """
    手搓 sin，泰勒级数逼近
    :param x: 弧度
    :param eps: 精度
    :return: sin(x)
    """
    pi = 3.1415926535
    x = x % (2 * pi)
    if x > pi:
        x -= 2 * pi

    res = 0.0
    term = x  # n=0 第一项
    n = 0

    while abs(term) > eps:
        res += term
        n += 1
        # 递推计算下一项
        term *= (-1) * x * x / ((2 * n) * (2 * n + 1))
    return res

WGSL_CUBE = """
struct Camera {
    mvp: mat4x4<f32>;
};

struct Model {
    model: mat4x4<f32>;
};

@group(0) @binding(0) var<uniform> camera: Camera;
@group(0) @binding(1) var<uniform> model: Model;

struct VIn {
    @location(0) pos: vec3<f32>;
    @location(1) col: vec3<f32>;
    @location(2) nrm: vec3<f32>;
};

struct VOut {
    @builtin(position) pos: vec4<f32>;
    @location(0) color: vec3<f32>;
    @location(1) normal: vec3<f32>;
};

@vertex
fn vs_main(in: VIn) -> VOut {
    var o: VOut;
    let world_pos = model.model * vec4<f32>(in.pos, 1.0);
    o.pos = camera.mvp * world_pos;
    o.color = in.col;
    o.normal = normalize((model.model * vec4<f32>(in.nrm, 0.0)).xyz);
    return o;
}

@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    // 简单漫反射
    let light_dir = normalize(vec3<f32>(0.6, 0.8, 0.7));
    let ndotl = max(dot(in.normal, light_dir), 0.0);
    let ambient = 0.22;
    let diffuse = 0.78 * ndotl;
    let final_rgb = in.color * (ambient + diffuse);
    return vec4<f32>(final_rgb, 1.0);
}
"""


async def main():
    screen = pygame.display.set_mode((800, 600))
    cjk = pygame.font.Font("cjk", 17)
    title = cjk.render(
        "RawRender 自建管线：3D 旋转立方体，自管透视相机",
        True, (205, 205, 205))
    _fail = []

    def st(name, cond):
        if cond:
            print("[cube-demo] PASS", name)
        else:
            _fail.append(name)
            print("[cube-demo] FAIL", name)

    ac = pygame.render.access()
    shader = ac.shader(WGSL_CUBE, label="cube_shader")

    # 立方体顶点：pos3, color3, normal3
    # 一个中心在原点、边长 2 的立方体（-1 ~ +1）
    verts = [
        # 前面 +z
        -1.0, -1.0,  1.0,   1.0, 0.3, 0.3,   0.0, 0.0,  1.0,
         1.0, -1.0,  1.0,   0.3, 1.0, 0.3,   0.0, 0.0,  1.0,
         1.0,  1.0,  1.0,   0.3, 0.3, 1.0,   0.0, 0.0,  1.0,
        -1.0, -1.0,  1.0,   1.0, 0.3, 0.3,   0.0, 0.0,  1.0,
         1.0,  1.0,  1.0,   0.3, 0.3, 1.0,   0.0, 0.0,  1.0,
        -1.0,  1.0,  1.0,   0.9, 0.9, 0.3,   0.0, 0.0,  1.0,

        # 后面 -z
        -1.0, -1.0, -1.0,   1.0, 0.3, 1.0,   0.0, 0.0, -1.0,
         1.0, -1.0, -1.0,   0.3, 1.0, 1.0,   0.0, 0.0, -1.0,
         1.0,  1.0, -1.0,   1.0, 1.0, 0.3,   0.0, 0.0, -1.0,
        -1.0, -1.0, -1.0,   1.0, 0.3, 1.0,   0.0, 0.0, -1.0,
         1.0,  1.0, -1.0,   1.0, 1.0, 0.3,   0.0, 0.0, -1.0,
        -1.0,  1.0, -1.0,   0.3, 0.6, 0.9,   0.0, 0.0, -1.0,

        # 右面 +x
         1.0, -1.0, -1.0,   0.2, 0.8, 0.8,   1.0, 0.0,  0.0,
         1.0, -1.0,  1.0,   0.8, 0.2, 0.8,   1.0, 0.0,  0.0,
         1.0,  1.0,  1.0,   0.8, 0.8, 0.2,   1.0, 0.0,  0.0,
         1.0, -1.0, -1.0,   0.2, 0.8, 0.8,   1.0, 0.0,  0.0,
         1.0,  1.0,  1.0,   0.8, 0.8, 0.2,   1.0, 0.0,  0.0,
         1.0,  1.0, -1.0,   0.4, 0.7, 0.6,   1.0, 0.0,  0.0,

        # 左面 -x
        -1.0, -1.0, -1.0,   0.7, 0.4, 0.8,  -1.0, 0.0,  0.0,
        -1.0, -1.0,  1.0,   0.4, 0.8, 0.7,  -1.0, 0.0,  0.0,
        -1.0,  1.0,  1.0,   0.8, 0.7, 0.4,  -1.0, 0.0,  0.0,
        -1.0, -1.0, -1.0,   0.7, 0.4, 0.8,  -1.0, 0.0,  0.0,
        -1.0,  1.0,  1.0,   0.8, 0.7, 0.4,  -1.0, 0.0,  0.0,
        -1.0,  1.0, -1.0,   0.6, 0.5, 0.8,  -1.0, 0.0,  0.0,

        # 上面 +y
        -1.0,  1.0, -1.0,   0.5, 0.9, 0.5,   0.0,  1.0, 0.0,
         1.0,  1.0, -1.0,   0.9, 0.5, 0.5,   0.0,  1.0, 0.0,
         1.0,  1.0,  1.0,   0.5, 0.5, 0.9,   0.0,  1.0, 0.0,
        -1.0,  1.0, -1.0,   0.5, 0.9, 0.5,   0.0,  1.0, 0.0,
         1.0,  1.0,  1.0,   0.5, 0.5, 0.9,   0.0,  1.0, 0.0,
        -1.0,  1.0,  1.0,   0.9, 0.9, 0.5,   0.0,  1.0, 0.0,

        # 下面 -y
        -1.0, -1.0, -1.0,   0.9, 0.6, 0.3,   0.0, -1.0, 0.0,
         1.0, -1.0, -1.0,   0.6, 0.9, 0.3,   0.0, -1.0, 0.0,
         1.0, -1.0,  1.0,   0.3, 0.9, 0.6,   0.0, -1.0, 0.0,
        -1.0, -1.0, -1.0,   0.9, 0.6, 0.3,   0.0, -1.0, 0.0,
         1.0, -1.0,  1.0,   0.3, 0.9, 0.6,   0.0, -1.0, 0.0,
        -1.0, -1.0,  1.0,   0.3, 0.6, 0.9,   0.0, -1.0, 0.0,
    ]
    mesh = ac.mesh(["float32x3","float32x3","float32x3"], verts, label="cube_mesh")

    # 两个 uniform buffer：相机 mvp + 模型矩阵
    cam_buf = ac.buffer(64, label="cube_cam_buf")
    model_buf = ac.buffer(64, label="cube_model_buf")

    bind = ac.bind_group([
        (0, "uniform", cam_buf),
        (1, "uniform", model_buf),
    ], label="cube_bind")

    pipe = ac.pipeline(shader, mesh, [bind], label="cube")

    st("cube mesh vertex count", mesh.vertex_count() == 36)
    st("cube mesh no index", mesh.index_count() == 0)

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

        # 模型矩阵：Y 持续旋转 + X 慢速摇摆
        rot_y = M.quat_from_axis_angle(0.0, 1.0, 0.0, t_sec * 42.0)
        rot_x = M.quat_from_axis_angle(1.0, 0.0, 0.0, sin(t_sec * 1.8) * 28.0)
        model_mat = (
            M.mat4_from_quat(rot_y)
            .mul_mat4(M.mat4_from_quat(rot_x))
            .mul_mat4(M.mat4_scale(2.6, 2.6, 2.6))
        )

        # 自管透视相机，固定在后方斜角
        view = M.mat4_translation(0.0, 0.0, -7.2)
        proj = pygame.render.camera_perspective(
            58.0, 800 / 600, 0.1, 300.0
        ).with_view(view)

        ac.update_mesh(mesh, verts)
        pygame.render.write_camera_mvp(cam_buf, proj.mvp())
        ac.write_buffer(model_buf, model_mat)

        with screen.render() as rt:
            if frame == 0:
                st("screen attachment ok", pygame.render.screen_attachment() is not None)
            rt.fill((12, 13, 20))
            pygame.gfxdraw.set_transform(rt, M.mat4_translation(-380, 270, 0))
            pygame.gfxdraw.draw_surface(rt, title)

            with rt.raw_render() as p:
                p.push_debug_group("rotating_cube")
                p.set_pipeline(pipe)
                p.set_bind_group(0, bind)
                # 如果你的管线需要开启深度测试，在这里加上
                # p.set_depth_state(...)
                p.draw_mesh(mesh)
                p.pop_debug_group()

        pygame.display.flip()

        if frame in (30, 60):
            print("[cube-state]", pygame.render.screen_frame_state())

        frame += 1

        if not asserted and frame == 60:
            st("raw_render cube 60 frame ok", True)
            _mvp = pygame.render.camera_mvp()
            st("no set_camera, auto camera hold", hasattr(_mvp, "mul_mat4"))
            asserted = True
            print("[cube-demo] SUMMARY",
                  "PASS" if not _fail else "FAIL " + str(_fail))

        await pygame.next_frame()
