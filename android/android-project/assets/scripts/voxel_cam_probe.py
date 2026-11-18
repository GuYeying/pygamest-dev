# voxel_cam_probe —— 相机 MVP 的 yaw 对称性纯数学验证（用户报障
# "向左转正常、向右转畸变"取证）：取正前方世界点，yaw=±θ 的 NDC_x
# 应严格互为相反数（对称）；投影管线任何方向性 bug 都会破坏该对称。
# 纯计算（无渲染依赖），3 秒跑完退出。
import pygame

M = pygame.math


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


def ndc(mvp_cols, p):
    """列主 16 → 手动乘 vec4 → NDC (x/w, y/w)。"""
    x, y, z = p
    # 列主：col c = cols[c*4 .. c*4+3]；clip = MVP @ (x,y,z,1)
    cx = mvp_cols[0] * x + mvp_cols[4] * y + mvp_cols[8] * z + mvp_cols[12]
    cy = mvp_cols[1] * x + mvp_cols[5] * y + mvp_cols[9] * z + mvp_cols[13]
    cz = mvp_cols[2] * x + mvp_cols[6] * y + mvp_cols[10] * z + mvp_cols[14]
    cw = mvp_cols[3] * x + mvp_cols[7] * y + mvp_cols[11] * z + mvp_cols[15]
    return (cx / cw, cy / cw, cz / cw)


async def main():
    screen = pygame.display.set_mode((400, 300))
    cam0 = pygame.render.game_camera_perspective(
        48.0, 400, 300, 400, 300, 0.1, 300.0)
    screen.set_camera(cam0)

    eye = (8.0, 9.0, 22.0)
    # 镜像点对（关于相机中平面 x=8 对称——yaw=±θ 时 A/B 的 NDC 应
    # 互为镜像：ndc_x(A,+θ) == -ndc_x(B,-θ)，ndc_y 相等）
    pairs = [((8.0, 4.0, 15.0), (8.0, 4.0, 15.0)),     # 中轴点自镜像
             ((5.0, 4.0, 12.0), (11.0, 4.0, 12.0)),    # 左右镜像对（同 y）
             ((4.0, 6.0, 16.0), (12.0, 6.0, 16.0))]

    print("[cam-probe] 镜像点对 yaw 对称（ndc_x(A,+θ)+ndc_x(B,-θ) 应 = 0）")
    worst = 0.0
    for pa, pb in pairs:
        for deg in (15, 30, 45):
            cam_p = cam0.with_view(M.mat4_from_cols_array(fps_view(eye, deg, -12.0)))
            cam_m = cam0.with_view(M.mat4_from_cols_array(fps_view(eye, -deg, -12.0)))
            xa = ndc(cam_p.mvp().to_cols_array(), pa)
            xb = ndc(cam_m.mvp().to_cols_array(), pb)
            asym = abs(xa[0] + xb[0])
            ydiff = abs(xa[1] - xb[1])
            worst = max(worst, asym, ydiff)
            print(f"  A{pa} B{pb} θ={deg}: x和={xa[0] + xb[0]:+.5f} y差={ydiff:.5f}")

    # 基线归一性：单位世界向量在 NDC 的模（yaw=0 正前方点应在中心）
    vp0 = fps_view(eye, 0.0, -12.0)
    cam_c = cam0.with_view(M.mat4_from_cols_array(vp0))
    xc = ndc(cam_c.mvp().to_cols_array(), (8.0, 6.03, 15.02))  # 视线中轴近似点
    print(f"[cam-probe] 中轴点 NDC ≈ (0, 0)：({xc[0]:+.4f}, {xc[1]:+.4f})")

    verdict = "PASS 对称（渲染数学无方向性 bug）" if worst < 0.02 else \
              f"FAIL 不对称（worst={worst:.4f}——view/proj 方向性 bug 实锤）"
    print(f"[cam-probe] {verdict}")
    return
