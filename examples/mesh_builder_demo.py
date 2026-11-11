# mesh_builder_demo —— 任意顶点布局验证（自定义 WGSL 管线直绘）：
# pos3 + color4 + normal3 + uv2 预设里**不存在**的组合——mesh_builder
# 突破 6 种预设字符串限制，任意 WGSL struct 布局可达。
# ① mesh_builder 创建自定义布局 mesh
# ② 自定义 WGSL 管线（顶点色 × 法线光照 × UV 采样）
# ③ raw_render 直绘到屏幕
# 退出：ESC / 关窗。
import pygame

WGSL = """
struct Camera { mvp: mat4x4<f32> };
@group(0) @binding(0) var<uniform> camera: Camera;

struct VIn {
    @location(0) pos: vec3<f32>,
    @location(1) color: vec4<f32>,
    @location(2) normal: vec3<f32>,
    @location(3) uv: vec2<f32>,
};
struct VOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) color: vec4<f32>,
    @location(1) uv: vec2<f32>,
    @location(2) brightness: f32,
};

@vertex
fn vs_main(vin: VIn) -> VOut {
    var out: VOut;
    out.pos = camera.mvp * vec4<f32>(vin.pos, 1.0);
    out.color = vin.color;
    out.uv = vin.uv;
    // 简易方向光照——normal 真的参与了着色（预设里没有 normal 字段）
    let light_dir = normalize(vec3<f32>(0.5, 0.8, 0.6));
    out.brightness = 0.4 + 0.6 * max(dot(normalize(vin.normal), light_dir), 0.0);
    return out;
}

@fragment
fn fs_main(fin: VOut) -> @location(0) vec4<f32> {
    // UV 格子纹理（程序化——免资产依赖）
    let gx = floor(fin.uv.x * 4.0) % 2.0;
    let gy = floor(fin.uv.y * 4.0) % 2.0;
    let checker = select(0.7, 0.3, gx == gy);
    let base = vec3<f32>(checker);
    let lit = base * fin.brightness;
    return vec4<f32>(lit * fin.color.rgb, fin.color.a);
}
"""


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 22)
    ac = pygame.render.access()

    # ── ① mesh_builder：自定义四字段布局（预设里不存在）──
    layout = ["float32x3", "float32x4", "float32x3", "float32x2"]
    stride = 12  # 3+4+3+2 floats

    # 立方体 6 面各两三角形（彩色 + 法线各面朝向不同——光照可辨）
    # 每顶点: x, y, z, r, g, b, a, nx, ny, nz, u, v
    faces = [
        # +Z front (红)
        [[-1, -1, 1, 1, 0.2, 0.2, 1, 0, 0, 1, 0, 0],
         [1, -1, 1, 1, 0.2, 0.2, 1, 0, 0, 1, 1, 0],
         [1, 1, 1, 1, 0.6, 0.2, 1, 0, 0, 1, 1, 1],
         [-1, 1, 1, 1, 0.6, 0.2, 1, 0, 0, 1, 0, 1]],
        # -Z back (蓝)
        [[1, -1, -1, 0.2, 0.2, 1, 1, 0, 0, -1, 0, 0],
         [-1, -1, -1, 0.2, 0.2, 1, 1, 0, 0, -1, 1, 0],
         [-1, 1, -1, 0.2, 0.6, 1, 1, 0, 0, -1, 1, 1],
         [1, 1, -1, 0.2, 0.6, 1, 1, 0, 0, -1, 0, 1]],
        # +X right (绿)
        [[1, -1, 1, 0.2, 1, 0.2, 1, 1, 0, 0, 0, 0],
         [1, -1, -1, 0.2, 1, 0.2, 1, 1, 0, 0, 1, 0],
         [1, 1, -1, 0.2, 1, 0.6, 1, 1, 0, 0, 1, 1],
         [1, 1, 1, 0.2, 1, 0.6, 1, 1, 0, 0, 0, 1]],
        # -X left (黄)
        [[-1, -1, -1, 1, 1, 0.2, 1, -1, 0, 0, 0, 0],
         [-1, -1, 1, 1, 1, 0.2, 1, -1, 0, 0, 1, 0],
         [-1, 1, 1, 1, 1, 0.6, 1, -1, 0, 0, 1, 1],
         [-1, 1, -1, 1, 1, 0.6, 1, -1, 0, 0, 0, 1]],
        # +Y top (白)
        [[-1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0],
         [1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 1, 0],
         [1, 1, -1, 1, 1, 1, 1, 0, 1, 0, 1, 1],
         [-1, 1, -1, 1, 1, 1, 1, 0, 1, 0, 0, 1]],
        # -Y bottom (紫)
        [[-1, -1, -1, 0.8, 0.2, 1, 1, 0, -1, 0, 0, 0],
         [1, -1, -1, 0.8, 0.2, 1, 1, 0, -1, 0, 1, 0],
         [1, -1, 1, 0.8, 0.2, 1, 1, 0, -1, 0, 1, 1],
         [-1, -1, 1, 0.8, 0.2, 1, 1, 0, -1, 0, 0, 1]],
    ]
    indices = []
    vi = 0
    verts = []
    for face in faces:
        for v in face:
            verts.extend(v)
        indices.extend([vi, vi + 1, vi + 2, vi, vi + 2, vi + 3])
        vi += 4

    mesh = ac.mesh(layout, verts, indices=indices, label="cube_mesh")
    print("[OK] mesh_builder: 12 格式字段 × 24 顶点 × 36 索引")

    # ── ② 管线（引用 mesh 布局的 WGSL）──
    shader = ac.shader(WGSL, label="mesh_builder_shader")

    cam_buf = ac.buffer(64, label="cam_buf")
    time_buf = ac.buffer(4, label="time_buf")

    # bind_group slot 0 = uniform(camera)
    # 但 WGSL 只有 @binding(0) camera——够用
    bind = ac.bind_group([(0, "uniform", cam_buf)], label="cam_bind")

    pipeline = ac.pipeline(shader, mesh, [bind], label="cube_pipeline")

    # ── ③ 渲染循环（旋转立方体 + 心跳文本）──
    import time as _time
    angle = 0.0
    t0 = _time.time()

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        angle += 0.01
        # 模型旋转（列主序 Mat4 链——pygame.math 定约；旧手写行主序
        # 矩阵列主序上传 = 转置错位，立方体被裁剪出屏，2026-11-12 修正）
        model = pygame.math.mat4_from_quat(
            pygame.math.quat_from_axis_angle(0.0, 1.0, 0.0, angle))
        view = pygame.math.mat4_translation(0.0, 0.0, -4.0)
        cam = pygame.render.camera_perspective(60.0, 800 / 600, 0.1, 100.0).with_view(view)
        mvp = cam.mvp().mul_mat4(model)

        # 双参形态 = 引擎自动左乘 present_fit 收进画布（裸 write_buffer
        # 直写无 letterbox 拟合——非 4:3 表面横向拉伸，2026-11-12 修正）
        pygame.render.write_camera_mvp(cam_buf, mvp)

        with screen.render() as r:
            r.fill((18, 18, 28))
            # raw_render 自定义管线直绘（2026-11-12 目标级扁平化：
            # screen.raw_render——旧 4 位置参形态被现行签名静默丢弃，
            # 本案例自迁移起 cube 才真正上屏）
            with screen.raw_render() as p:
                p.set_pipeline(pipeline)
                p.set_bind_group(0, bind)
                p.draw_mesh(mesh)

            # HUD
            lines = [
                f"mesh_builder: 4 fields × 24 verts (custom layout)",
                f"angle = {angle:.1f}rad",
            ]
            y = 20
            for line in lines:
                s = font.render(line, True, (180, 220, 180))
                pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(-380, y - 280, 0))
                pygame.gfxdraw.draw_surface(r, s)
                y += 26

        pygame.display.flip()
        await pygame.next_frame()
