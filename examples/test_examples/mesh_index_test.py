# mesh_index_test —— mesh index 接口补齐冒烟（2026-11-16 批次）：
# ① u32 原始字节索引构建（index_bytes + index_format="u32"——大 mesh
# 通路）② index_format()/index_buffer_size() 查询 ③ update_mesh_index_
# bytes 原始字节更新 ④ raw_render draw 渲染验证 ⑤ compute copy_mesh_
# indices（GPU→GPU 动态索引——会话排程须在 render 块内）。30 帧自动
# 退；[mesh-index] 逐项断言。
import pygame


def u32pack(vals):
    """u32 LE 字节（struct 模块被裁——手拼）。"""
    out = bytearray()
    for v in vals:
        out += bytes((v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255))
    return bytes(out)


def u16pack(vals):
    """u16 LE 字节。"""
    out = bytearray()
    for v in vals:
        out += bytes((v & 255, (v >> 8) & 255))
    return bytes(out)


async def main():
    pygame.display.set_caption("mesh_index_test")
    screen = pygame.display.set_mode((400, 300))
    ac = pygame.render.access()
    frame = 0
    _fail = []

    def st(name, cond):
        if cond:
            print("[mesh-index] PASS", name)
        else:
            _fail.append(name)
            print("[mesh-index] FAIL", name)

    # quad 顶点（pos2 全屏域——4 顶点；索引 6 段两三角；色走 VS 程序化）
    verts = [0.0, 0.0,  1.0, 0.0,  1.0, 1.0,  0.0, 1.0]
    idx32 = [0, 1, 2, 0, 2, 3]

    mesh = ac.mesh(
        ["float32x2"], verts,
        index_bytes=u32pack(idx32),               # u32 LE 24B
        index_format="u32",
        label="idx32_mesh",
    )
    st("u32 index_bytes 构建", mesh.has_index_buffer())
    st("index_format() = u32", mesh.index_format() == "u32")
    st("index_count = 6", mesh.index_count() == 6)
    st("vertex_count = 4", mesh.vertex_count() == 4)
    st("index_buffer_size = 24B", mesh.index_buffer_size() == 24)
    st("vertex_buffer_size = 32B", mesh.vertex_buffer_size() == 32)

    # 原始字节索引更新（u32 格式匹配路径——access 口）
    new_idx = [0, 2, 1, 0, 3, 2]                  # 绕序翻转（内容变）
    ac.update_mesh_index_bytes(mesh, u32pack(new_idx), "u32")
    st("update_mesh_index_bytes u32", mesh.index_count() == 6)

    # 格式不匹配守卫（mesh u32 传 u16 = ValueError）
    try:
        ac.update_mesh_index_bytes(mesh, u16pack((0, 1, 2)), None)
        st("格式不匹配守卫", False)
    except ValueError:
        st("格式不匹配守卫", True)

    # shader（pos 程序化染色）+ pipeline
    cam_buf = ac.buffer(64, label="cam_buf")
    src_buf = ac.buffer(24, usage="storage", label="idx_src")       # compute 拷贝源
    ac.write_buffer_u32(src_buf, [0, 2, 1, 0, 3, 2])

    WGSL = """
    struct Camera { mvp: mat4x4<f32>, };
    @group(0) @binding(0) var<uniform> camera: Camera;
    struct VIn {
        @location(0) pos: vec2<f32>,
    }
    struct VOut {
        @builtin(position) pos: vec4<f32>,
        @location(0) tint: vec3<f32>,
    }
    @vertex
    fn vs_main(vin: VIn) -> VOut {
        var o: VOut;
        o.pos = vec4<f32>(vin.pos.x * 2.0 - 1.0, 1.0 - vin.pos.y * 2.0, 0.0, 1.0);
        o.tint = vec3<f32>(vin.pos.x, vin.pos.y, 0.5);
        return o;
    }
    @fragment
    fn fs_main(in: VOut) -> @location(0) vec4<f32> {
        return vec4<f32>(in.tint, 1.0);
    }
    """
    shader = ac.shader(WGSL, label="idx_shader")
    bind = ac.bind_group([(0, "uniform", cam_buf)], label="idx_bind")
    pipe = ac.pipeline(shader, mesh, [bind], cull="none",
                       blend="opaque", depth_mode="disabled",
                       label="idx_pipe")
    st("pipeline 构建", pipe is not None)

    # 无索引 mesh（copy 跳过路径——回放期告警不崩；更新 = ValueError 守卫）
    mesh_ni = ac.mesh(["float32x2"], verts, label="no_idx_mesh")
    st("无索引 mesh index_format None", mesh_ni.index_format() is None)
    st("无索引 size 0", mesh_ni.index_buffer_size() == 0)
    try:
        ac.update_mesh_index_bytes(mesh_ni, u16pack((0, 1, 2)), None)
        st("无索引更新守卫", False)
    except ValueError:
        st("无索引更新守卫", True)

    cam = pygame.render.game_camera_ortho(400, 300, 400, 300)
    screen.set_camera(cam)
    pygame.render.write_camera_mvp(cam_buf, cam.mvp())

    def draw_hud(rt):
        M = pygame.math
        pygame.gfxdraw.set_transform(rt, M.mat4_translation(-190, 138, 0))
        pygame.gfxdraw.draw_surface(rt, pygame.font.Font(
            "cjk", 13).render("mesh index 补齐冒烟：u32 构建/查询/更新/compute 拷贝",
                              True, (220, 224, 232)))

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        # compute 会话（GPU→GPU 索引直搬——排程须在 render 块内）
        with screen.render() as rt:
            with screen.raw_compute() as p:
                p.copy_mesh_indices(mesh, src_buf, 24)
            rt.fill((24, 28, 38))
            with screen.raw_render(depth=False) as p:
                p.set_pipeline(pipe)
                p.set_bind_group(0, bind)
                p.draw_mesh(mesh)          # u32 索引 draw（验证层）
            draw_hud(rt)
        pygame.display.flip()
        frame += 1
        if frame == 30:
            st("30 帧渲染稳定", True)
            print("[mesh-index] SUMMARY",
                  "PASS" if not _fail else "FAIL " + str(_fail))
        if frame > 600:
            return
        await pygame.tasks.yield_now()
