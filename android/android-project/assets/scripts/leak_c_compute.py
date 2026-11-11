# leak_c —— 隔离 C：仅 compute dispatch + copy_mesh_vertices（无 egui/无文本）
import pygame

CS = """
struct Config { n: u32, mode: u32, dt_ms: u32, pad1: u32 };
@group(0) @binding(0) var<storage, read_write> out_pos: array<vec2<f32>>;
@group(0) @binding(1) var<uniform> cfg: Config;
@compute @workgroup_size(64)
fn cs_main(@builtin(global_invocation_id) gid: vec3<u32>) {
    if (gid.x >= cfg.n) { return; }
    out_pos[gid.x] = vec2<f32>(f32(gid.x), f32(cfg.dt_ms));
}
"""


async def main():
    screen = pygame.display.set_mode((400, 300))
    ac = pygame.render.access()
    shader = ac.shader(CS, label="diag_cs")
    n = 2048
    pos_out = ac.buffer(n * 8, usage="storage", label="diag_pos")
    mesh = ac.mesh(["float32x2"], floats=n * 2, label="diag_mesh")
    cfg_buf = ac.buffer(16, label="diag_cfg")
    sbind = ac.bind_group([(0, "storage_rw", pos_out), (1, "uniform", cfg_buf)],
                          label="diag_bind")
    cpipe = ac.compute_pipeline(shader, [sbind], label="diag_pipe")
    ac.write_buffer_u32(cfg_buf, [n, 0, 16, 0])
    frame = 0
    while frame < 9000:
        with screen.render() as t:
            t.fill((6, 8, 14))
            with screen.raw_compute() as p:
                p.set_pipeline(cpipe)
                p.set_bind_group(0, sbind)
                p.dispatch(n // 64, 1, 1)
                p.copy_mesh_vertices(mesh, pos_out, n * 8)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
