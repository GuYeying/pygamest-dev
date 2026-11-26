# voxel_spin_probe —— 水平旋转歪斜自动化取证（2026-11-17）：
# 静止球置于视线中轴（pitch=0 正前方），yaw=±θ 时球像素质心 x 应
# 相对于画面中心对称偏移；任何"旋转歪"都会破坏该对称。同时打
# view/MVP 矩阵数值。纯自动 12 秒跑完。
import pygame

M = pygame.math

WGSL = """
struct Camera { mvp: mat4x4<f32>, };
@group(0) @binding(0) var<uniform> camera: Camera;
struct VIn {
    @location(0) pos: vec3<f32>,
    @location(1) nrm: vec3<f32>,
}
struct VOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) nrm: vec3<f32>,
}
@vertex
fn vs_main(vin: VIn) -> VOut {
    var o: VOut;
    let wp = vin.pos + vec3<f32>(8.0, 6.0, 14.0);  // 静止球平移直入顶点
    o.pos = camera.mvp * vec4<f32>(wp, 1.0);
    o.nrm = vin.nrm;
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let l = 0.4 + 0.6 * max(dot(in.nrm, normalize(vec3<f32>(0.5, 0.9, 0.35))), 0.0);
    return vec4<f32>(vec3<f32>(1.0, 0.647, 0.176) * l, 1.0);
}
"""

CUBE = [
    -0.5,-0.5, 0.5, 0,0,1,  0.5,-0.5, 0.5, 0,0,1,  0.5,0.5, 0.5, 0,0,1,
    -0.5,-0.5, 0.5, 0,0,1,  0.5, 0.5, 0.5, 0,0,1, -0.5,0.5, 0.5, 0,0,1,
     0.5,-0.5,-0.5, 0,0,-1, -0.5,-0.5,-0.5, 0,0,-1, -0.5,0.5,-0.5, 0,0,-1,
     0.5,-0.5,-0.5, 0,0,-1, -0.5,0.5,-0.5, 0,0,-1,  0.5,0.5,-0.5, 0,0,-1,
     0.5,-0.5, 0.5, 1,0,0,  0.5,-0.5,-0.5, 1,0,0,  0.5,0.5,-0.5, 1,0,0,
     0.5,-0.5, 0.5, 1,0,0,  0.5,0.5,-0.5, 1,0,0,  0.5,0.5, 0.5, 1,0,0,
    -0.5,-0.5,-0.5, -1,0,0, -0.5,-0.5, 0.5, -1,0,0, -0.5,0.5, 0.5, -1,0,0,
    -0.5,-0.5,-0.5, -1,0,0, -0.5,0.5, 0.5, -1,0,0, -0.5,0.5,-0.5, -1,0,0,
    -0.5, 0.5, 0.5, 0,1,0,  0.5, 0.5, 0.5, 0,1,0,  0.5, 0.5,-0.5, 0,1,0,
    -0.5, 0.5, 0.5, 0,1,0,  0.5, 0.5,-0.5, 0,1,0, -0.5, 0.5,-0.5, 0,1,0,
    -0.5,-0.5, 0.5, 0,-1,0, -0.5,-0.5,-0.5, 0,-1,0,  0.5,-0.5,-0.5, 0,-1,0,
    -0.5,-0.5, 0.5, 0,-1,0,  0.5,-0.5,-0.5, 0,-1,0,  0.5,-0.5, 0.5, 0,-1,0,
]


def fps_view(eye, yaw_deg, pitch_deg):
    yaw = M.radians(yaw_deg)
    pitch = M.radians(pitch_deg)
    fx = M.cos(pitch) * M.sin(yaw)
    fy = M.sin(pitch)
    fz = -M.cos(pitch) * M.cos(yaw)
    f = (fx, fy, fz)
    up0 = (0.0, 1.0, 0.0)
    s0 = (fy * up0[2] - fz * up0[1],
          fz * up0[0] - fx * up0[2],
          fx * up0[1] - fy * up0[0])
    sn = (s0[0] * s0[0] + s0[1] * s0[1] + s0[2] * s0[2]) ** 0.5
    s = (s0[0] / sn, s0[1] / sn, s0[2] / sn)
    u = (s[1] * fz - s[2] * fy,
         s[2] * fx - s[0] * fz,
         s[0] * fy - s[1] * fx)
    ex, ey, ez = eye
    m = [
        s[0], s[1], s[2], -s[0] * ex - s[1] * ey - s[2] * ez,
        u[0], u[1], u[2], -u[0] * ex - u[1] * ey - u[2] * ez,
        -f[0], -f[1], -f[2], f[0] * ex + f[1] * ey + f[2] * ez,
        0.0, 0.0, 0.0, 1.0,
    ]
    return [m[r * 4 + c] for c in range(4) for r in range(4)]


async def main():
    pygame.display.set_caption("spin_probe")
    W, H = 800, 600
    screen = pygame.display.set_mode((W, H))
    ac = pygame.render.access()
    cam0 = pygame.render.game_camera_perspective(
        48.0, W, H, W, H, 0.1, 300.0)
    screen.set_camera(cam0)

    cam_buf = ac.buffer(64, label="cam_buf")
    ball_mesh = ac.mesh(["float32x3", "float32x3"], CUBE, label="probe_cube")
    shader = ac.shader(WGSL, label="probe_shader")
    bind = ac.bind_group([(0, "uniform", cam_buf)], label="probe_bind")
    pipe = ac.pipeline(shader, ball_mesh, [bind], cull="back",
                       blend="opaque", depth_mode="standard",
                       depth_write=True, label="probe_pipe")

    eye = (8.0, 6.0, 22.0)          # 与球同高（pitch=0 平视）

    def centroid_yaw(yaw_deg, pitch_deg=0.0):
        cam = cam0.with_view(M.mat4_from_cols_array(
            fps_view(eye, yaw_deg, pitch_deg)))
        pygame.render.write_camera_mvp(cam_buf, cam.mvp())
        probe = None
        with screen.render() as rt:
            rt.fill((10, 12, 18))
            with screen.raw_render(depth=True) as p:
                p.set_pipeline(pipe)
                p.set_bind_group(0, bind)
                p.draw_mesh(ball_mesh)
            # screen_probe 须 flip 前调（读当前交换链真实内容）
            probe = pygame.render.screen_probe()
        pygame.display.flip()
        n = 0
        sx = sy = 0.0
        for s2 in probe:
            x, y, r, g, bb, _a = s2
            if r > 140 and 80 < g < 210 and bb < 95:
                sx += x
                sy += y
                n += 1
        return (sx / n, sy / n, n) if n else (None, None, 0)

    for yaw_d in (0, 90):
        v = fps_view(eye, yaw_d, 0.0)
        print(f"[spin] view(yaw={yaw_d}) = "
              + " ".join(f"{x:+.3f}" for x in v))
    m0 = cam0.with_view(M.mat4_from_cols_array(fps_view(eye, 0, 0))).mvp()
    print("[spin] mvp(yaw=0)  = "
          + " ".join(f"{x:+.2f}" for x in m0.to_cols_array()))

    print(f"[spin] 球 (8,6,14) eye={eye} 画面 {W}x{H} 中轴 x={W // 2}")
    results = {}
    for yaw_d in (0, 15, -15, 30, -30):
        for _ in range(30):
            await pygame.tasks.yield_now()
        cx, cy, n = centroid_yaw(yaw_d)
        results[yaw_d] = cx
        if cx is not None:
            print(f"  yaw={yaw_d:+3d}: 质心=({cx:.1f}, {cy:.1f}) 像素={n}")
        else:
            print(f"  yaw={yaw_d:+3d}: 未找到球像素")

    ok = True
    for d in (15, 30):
        a, b2 = results.get(d), results.get(-d)
        if a is None or b2 is None:
            print(f"[spin] yaw=±{d}: 缺数据")
            ok = False
            continue
        off_a = a - W / 2
        off_b = b2 - W / 2
        sym = abs(off_a + off_b) < 8
        print(f"[spin] yaw=±{d}: 偏移(+{d})={off_a:+.0f}px 偏移(-{d})={off_b:+.0f}px "
              f"和={off_a + off_b:+.1f}（应≈0）→ " + ("对称 ✓" if sym else "不对称 ✗"))
        ok = ok and sym
    c0 = results.get(0)
    if c0 is not None:
        ctr = abs(c0 - W / 2) < 8
        print(f"[spin] yaw=0 中轴偏移={c0 - W / 2:+.0f}px（应≈0）→ "
              + ("居中 ✓" if ctr else "偏心 ✗"))
        ok = ok and ctr
    print("[spin] " + ("PASS 水平旋转对称（渲染无歪斜）" if ok
                       else "FAIL 不对称（渲染歪斜——矩阵见上）"))
    return
