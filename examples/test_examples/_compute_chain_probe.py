# compute_chain_probe E —— 1D 完整波方程 + wake（SebLague 路线终验）
# 双缓冲 ping-pong（两会话）+ 1D dispatch + wake uniform（16B 精确）
# 判据：热图 = 中心持续扩散波环 = GPU 波场完全可行
import pygame
M = pygame.math

WGSL_CS = """
struct Wake { amp: f32, pad0: f32, pad1: f32, pad2: f32 };
@group(0) @binding(0) var<storage, read_write> cur: array<vec2<f32>>;
@group(0) @binding(1) var<storage, read> prev: array<vec2<f32>>;
@group(0) @binding(2) var<uniform> wake: Wake;
@compute @workgroup_size(64, 1, 1)
fn cs_main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let i = gid.x;
    let x = i % 64;
    let z = i / 64;
    let hc = prev[i].x;
    let vc = prev[i].y;
    var lap = 0.0;
    if (x > 0) { lap += prev[i - 1].x; } else { lap += hc; }
    if (x < 63) { lap += prev[i + 1].x; } else { lap += hc; }
    if (z > 0) { lap += prev[i - 64].x; } else { lap += hc; }
    if (z < 63) { lap += prev[i + 64].x; } else { lap += hc; }
    lap -= 4.0 * hc;
    var v = (vc + lap * 0.42) * 0.9965;
    var h = hc + v;
    // wake（中心持续注入）
    let dx = f32(x) - 31.5;
    let dz = f32(z) - 31.5;
    let t = max(0.0, 1.0 - (dx * dx + dz * dz) / 25.0);
    v = v + wake.amp * t * t;
    let edge = min(min(x, 63 - x), min(z, 63 - z));
    if (edge < 2) {
        v = v * 0.90;
        h = h * 0.95;
    }
    cur[i] = vec2<f32>(h, v);
}
"""

WGSL_QUAD = """
struct Cam { mvp: mat4x4<f32> };
@group(0) @binding(0) var<uniform> cam: Cam;
@group(0) @binding(1) var<storage, read> buf: array<vec2<f32>>;
struct VIn { @location(0) pos: vec2<f32>, @location(1) uv: vec2<f32> }
struct VOut { @builtin(position) pos: vec4<f32>, @location(0) uv: vec2<f32> }
@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    o.pos = vec4<f32>(v.pos, 0.0, 1.0);
    o.uv = v.uv;
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    // h 热图（红 = h×30+0.5）
    let g = vec2<i32>(in.uv * 63.0 + vec2<f32>(0.5));
    let cx = clamp(g.x, 0, 63);
    let cz = clamp(g.y, 0, 63);
    let h = buf[u32(cx + cz * 64)].x;
    return vec4<f32>(clamp(h * 30.0 + 0.5, 0.0, 1.0), 0.25, 0.25, 1.0);
}
"""


async def main():
    pygame.display.set_caption("compute_chain_probe_E")
    screen = pygame.display.set_mode((256, 256)); pygame.render.set_fb_dump(True)
    ac = pygame.render.access()

    wave_a = ac.buffer(64 * 64 * 8, usage="storage", label="wave_a")
    wave_b = ac.buffer(64 * 64 * 8, usage="storage", label="wave_b")
    wake_buf = ac.buffer(16, label="wake_buf")

    def pump_wake(frame):
        # **零均值注入**（纯正向 = 平均水位持续泵升淹没波纹——逐帧交替
        # 正负 = 波纹可见）
        a = 0.03 if frame % 2 == 0 else -0.03
        ac.write_buffer(wake_buf, [a, 0.0, 0.0, 0.0])

    cs_shader = ac.shader(WGSL_CS, label="probe_cs")
    bg_a = ac.bind_group([(0, "storage_rw", wave_a),
                          (1, "storage", wave_b),
                          (2, "uniform", wake_buf)], label="bg_a")
    bg_b = ac.bind_group([(0, "storage_rw", wave_b),
                          (1, "storage", wave_a),
                          (2, "uniform", wake_buf)], label="bg_b")
    cs_pipe = ac.compute_pipeline(cs_shader, [bg_a], label="probe_cs_pipe")

    quad = ac.mesh(["float32x2", "float32x2"],
                   [-1.0, -1.0, 0.0, 0.0, 1.0, -1.0, 1.0, 0.0,
                    1.0, 1.0, 1.0, 1.0, -1.0, 1.0, 0.0, 1.0],
                   index_bytes=bytes([0,0, 1,0, 2,0, 0,0, 2,0, 3,0]), label="quad")
    cam_buf = ac.buffer(64, label="cam")
    bind = ac.bind_group([(0, "uniform", cam_buf),
                          (1, "storage", wave_b)], label="quad_bg")
    shader = ac.shader(WGSL_QUAD, label="probe_quad")
    pipe = ac.pipeline(shader, quad, [bind], cull="none", blend="opaque",
                       label="probe_pipe")

    frame = 0
    while frame < 600:
        pump_wake(frame)
        pygame.render.write_camera_mvp(cam_buf, M.mat4_identity())
        with screen.render() as rt:
            with screen.raw_render() as p:
                p.set_pipeline(pipe)
                p.set_bind_group(0, bind)
                p.draw_mesh(quad)
            # ping-pong = 两条独立 compute 会话（各 auto-index 0）
            with screen.raw_compute() as cp:
                cp.set_pipeline(cs_pipe)
                cp.set_bind_group(0, bg_a)
                cp.dispatch(64, 1, 1)
            with screen.raw_compute() as cp:
                cp.set_pipeline(cs_pipe)
                cp.set_bind_group(0, bg_b)
                cp.dispatch(64, 1, 1)
        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1
