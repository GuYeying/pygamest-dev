# update_mesh 协程内失效探针（挂账③取证）
# async-main 形态：协程体内 update_mesh 原地挪 quad（左半屏→右半屏），
# screen_probe 前后对照——右半屏点从背景色变为 quad 色 = 生效。
import pygame

WGSL = """
struct VIn { @location(0) pos: vec2<f32>, @location(1) col: vec4<f32> }
struct VOut { @builtin(position) pos: vec4<f32>, @location(0) col: vec4<f32> }
@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    o.pos = vec4<f32>(v.pos, 0.0, 1.0);
    o.col = v.col;
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    return in.col;
}
"""

def quad(x0, x1):
    # 4 顶点 × (pos2 + rgba4)；红 255
    col = [1.0, 0.0, 0.0, 1.0]
    vs = []
    for x, y in [(x0, -1.0), (x1, -1.0), (x1, 1.0), (x0, 1.0)]:
        vs += [x, y] + col
    return vs

LEFT = quad(-1.0, 0.0)
RIGHT = quad(0.0, 1.0)


async def main():
    pygame.display.set_caption("mesh_update_probe")
    screen = pygame.display.set_mode((128, 128))
    ac = pygame.render.access()

    mesh = ac.mesh(["float32x2", "float32x4"], LEFT,
                   index_bytes=bytes([0, 0, 1, 0, 2, 0, 0, 0, 2, 0, 3, 0]),
                   label="upd_mesh")
    shader = ac.shader(WGSL, label="upd_shader")
    pipe = ac.pipeline(shader, mesh, [], cull="none", blend="opaque",
                       label="upd_pipe")

    probes = []
    for f in range(120):
        if f == 30:
            ac.update_mesh(mesh, RIGHT)   # ⬅ 协程内原地更新（挂账③正体）
        if f == 15:
            probes.append(("before", pygame.render.screen_probe()))
        if f == 90:
            probes.append(("after", pygame.render.screen_probe()))
        with screen.render() as rt:
            with screen.raw_render() as p:
                p.set_pipeline(pipe)
                p.draw_mesh(mesh)
        pygame.display.flip()
        await pygame.tasks.yield_now()

    def px(plist, fx, fy):
        if not plist:
            return None
        x, y = fx * 127, fy * 127
        return min(plist, key=lambda pt: (pt[0] - x) ** 2 + (pt[1] - y) ** 2)

    def red_cx(plist):
        reds = [p for p in plist if p[2] > 200]
        return sum(p[0] for p in reds) / len(reds) if reds else None

    domain = max(p[0] for p in probes[0][1])
    bc, ac_ = red_cx(probes[0][1]), red_cx(probes[1][1])
    print(f"[mesh-update] red_cx before={bc} after={ac_} domain={domain}")
    if bc is not None and ac_ is not None and bc < domain * 0.45 and ac_ > domain * 0.55:
        print("[mesh-update] ROOT-OK (协程内 update_mesh 生效——质心左→右)")
    else:
        print("[mesh-update] STALE (原地更新失效)")
