# dispatch 二维根修探针——dispatch(8, 8) 是否丢 y 维（挂账①取证）
# 正典复刻（compute_chain_probe 结构）：cs 把 gid 编码进 storage → FS
# 热图上屏 → screen_probe() CPU 读像素判覆盖率。y 维丢失 = 行组只有
# 2 个非零值；健在 = 行组 0..7 全出现。
import pygame

# cs：每格写 (y*8+x+1)/64 —— FS 解码出 (x/8, y/8, 0.25)
WGSL_CS = """
@group(0) @binding(0) var<storage, read_write> buf: array<f32>;

@compute @workgroup_size(1, 1)
fn cs_main(@builtin(global_invocation_id) gid: vec3<u32>) {
    buf[gid.y * 8u + gid.x] = f32(gid.y * 8u + gid.x + 1u) / 64.0;
}
"""

WGSL_QUAD = """
struct Camera { mvp: mat4x4<f32> };
@group(0) @binding(0) var<uniform> camera: Camera;
@group(0) @binding(1) var<storage, read> buf: array<f32>;
struct VIn { @location(0) pos: vec2<f32>, @location(1) uv: vec2<f32> }
struct VOut { @builtin(position) pos: vec4<f32>, @location(0) uv: vec2<f32> }
@vertex
fn vs_main(vin: VIn) -> VOut {
    var o: VOut;
    o.pos = camera.mvp * vec4<f32>(vin.pos, 0.0, 1.0);
    o.uv = vin.uv;
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let uv = clamp(in.uv, vec2<f32>(0.0), vec2<f32>(0.99999));
    let cell = vec2<u32>(uv * 8.0);
    let idx = cell.y * 8u + cell.x;
    let packed = u32(buf[idx] * 64.0) - 1u;
    let cy = packed / 8u;
    let cx = packed - cy * 8u;
    return vec4<f32>(f32(cx) / 8.0, f32(cy) / 8.0, 0.25, 1.0);
}
"""


async def main():
    pygame.display.set_caption("2d_dispatch_probe")
    screen = pygame.display.set_mode((256, 256))
    ac = pygame.render.access()

    buf = ac.buffer(64 * 4, usage="storage", label="gid_buf")
    bg = ac.bind_group([(0, "storage_rw", buf)], label="gid_bg")
    cs_shader = ac.shader(WGSL_CS, label="probe_cs")
    cs_pipe = ac.compute_pipeline(cs_shader, [bg], label="probe_cs_pipe")

    quad = ac.mesh(["float32x2", "float32x2"],
                   [-1.0, -1.0, 0.0, 0.0, 1.0, -1.0, 1.0, 0.0,
                    1.0, 1.0, 1.0, 1.0, -1.0, 1.0, 0.0, 1.0],
                   index_bytes=bytes([0, 0, 1, 0, 2, 0, 0, 0, 2, 0, 3, 0]),
                   label="quad")
    cam_buf = ac.buffer(64, label="cam")
    bind = ac.bind_group([(0, "uniform", cam_buf), (1, "storage", buf)],
                         label="quad_bg")
    shader = ac.shader(WGSL_QUAD, label="probe_quad_fs")
    pipe = ac.pipeline(shader, quad, [bind], cull="none", blend="opaque",
                       label="probe_pipe")

    frame = 0
    while frame < 120:
        pygame.render.write_camera_mvp(cam_buf, pygame.math.mat4_identity())
        with screen.render() as rt:
            with screen.raw_compute() as cp:
                cp.set_pipeline(cs_pipe)
                cp.set_bind_group(0, bg)
                cp.dispatch(8, 8)          # ⬅ 二维派发正体
            with screen.raw_render() as p:
                p.set_pipeline(pipe)
                p.set_bind_group(0, bind)
                p.draw_mesh(quad)
        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1

    probe = pygame.render.screen_probe()   # 元组序 (x, y, r, g, b, a)，色 0-255
    # FS 编码：r = cx/8，g = cy/8；屏幕 y 向上 → cy = 7 - y//32
    def expect(px, py):
        cx = min(int(px / 256 * 8), 7)
        cy = min(int((1.0 - py / 256) * 8), 7)
        return cx / 8 * 255, cy / 8 * 255

    ok = all(abs(p[2] - expect(p[0], p[1])[0]) < 8
             and abs(p[3] - expect(p[0], p[1])[1]) < 8
             for p in probe)
    rows = sorted({min(int((1.0 - p[1] / 256) * 8), 7) for p in probe})
    print(f"[2d-dispatch] rows(y)={rows}")
    if ok and len(rows) >= 5:
        print("[2d-dispatch] ROOT-OK (dispatch(8,8) 二维全覆盖——y 维从未丢失)")
    else:
        print("[2d-dispatch] Y-DIM-LOST")
