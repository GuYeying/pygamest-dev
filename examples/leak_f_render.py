# leak_f —— 隔离 F：C + 渲染通路（pipeline + set_mesh + draw_indirect）
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

RS = """
struct Camera { mvp: mat4x4<f32> };
@group(0) @binding(0) var<uniform> camera: Camera;
struct VOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) color: vec3<f32>,
};
const CORNERS = array<vec2<f32>, 3>(
    vec2<f32>(-2.0, -2.0), vec2<f32>(2.0, -2.0), vec2<f32>(0.0, 2.0));
@vertex
fn vs_main(@location(0) pos: vec2<f32>,
           @builtin(vertex_index) vi: u32,
           @builtin(instance_index) ii: u32) -> VOut {
    var o: VOut;
    o.pos = camera.mvp * vec4<f32>(pos + CORNERS[vi], 0.0, 1.0);
    o.color = vec3<f32>(1.0, 0.5, 0.3);
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    return vec4<f32>(in.color, 1.0);
}
"""


async def main():
    screen = pygame.display.set_mode((400, 300))
    ac = pygame.render.access()
    shader = ac.shader(CS, label="diag_cs")
    rshader = ac.shader(RS, label="diag_rs")
    n = 2048
    pos_out = ac.buffer(n * 8, usage="storage", label="diag_pos")
    mesh = ac.mesh_builder(["float32x2"], floats=n * 2, label="diag_mesh")
    cfg_buf = ac.buffer(16, label="diag_cfg")
    cam_buf = ac.buffer(64, label="diag_cam")
    ind_buf = ac.buffer(16, usage="indirect", label="diag_ind")
    sbind = ac.bind_group([(0, "storage_rw", pos_out), (1, "uniform", cfg_buf)],
                          label="diag_bind")
    rbind = ac.bind_group([(0, "uniform", cam_buf)], label="diag_rbind")
    cpipe = ac.compute_pipeline(shader, [sbind], label="diag_pipe")
    rpipe = ac.pipeline(rshader, mesh, [rbind], label="diag_rpipe")
    cam = pygame.render.camera_ortho(400.0, 300.0)
    ac.write_buffer_u32(cfg_buf, [n, 0, 16, 0])
    ac.write_buffer_u32(ind_buf, [3, n, 0, 0])
    frame = 0
    while frame < 9000:
        with screen.render() as t:
            t.fill((6, 8, 14))
            with t.raw_compute() as p:
                p.set_pipeline(cpipe)
                p.set_bind_group(0, sbind)
                p.dispatch(n // 64, 1, 1)
                p.copy_mesh_vertices(mesh, pos_out, n * 8)
            with t.raw_render() as p:
                p.set_pipeline(rpipe)
                p.set_bind_group(0, rbind)
                p.set_mesh(mesh)
                p.draw_indirect(ind_buf, 0)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
