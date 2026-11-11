# math_test —— pygame.math 专项案例（含 2026-11-12 新增面）：
#   三角函数八字 / Mat4 平移缩放 / @矩阵组合（列向量约定：t@s = s 先行）/
#   *标量逐元素 / quat 轴角旋转 / mat4_identity。纯断言 + 三轴环可视化。
#   （transform_point3(Vector3) = 3D 点变换口；to_cols_array = 列主序 16f）
import pygame

M = pygame.math
PASS = []
FAIL = []


def check(name, ok):
    (PASS if ok else FAIL).append(name)


def close(a, b, eps=1e-4):
    return all(abs(x - y) < eps for x, y in zip(a, b))


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 20)

    # ── 三角函数八字（2026-11-12 新增）──
    check("sin/cos 值域", close([M.sin(0.0), M.cos(0.0)], [0.0, 1.0])
          and abs(M.sin(M.radians(30)) - 0.5) < 1e-4)
    check("tan/radians/degrees", abs(M.tan(M.radians(45)) - 1.0) < 1e-4
          and abs(M.degrees(M.asin(0.5)) - 30.0) < 1e-3)

    # ── Mat4 构造族 ──
    t = M.mat4_translation(2.0, 3.0, 4.0)
    s = M.mat4_scale(2.0, 2.0, 2.0)
    check("translation/scale 构造", t is not None and s is not None)

    # ── @ 矩阵组合（列向量约定：(t@s)·v = t·(s·v)——s 先行）──
    combo = t @ s
    p = combo.transform_point3(pygame.math.Vector3(1.0, 1.0, 1.0))
    # s·v = (2,2,2) → t·(2,2,2) = (2+2, 3+2, 4+2) = (4,5,6)
    check("@ 矩阵组合 t@s（s 先行）", close([p.x, p.y, p.z], [4.0, 5.0, 6.0], 1e-3))

    # ── * 标量逐元素（与 @ 分离——numpy 定约）──
    scaled = t * 0.5
    q = scaled.transform_point3(pygame.math.Vector3(1.0, 1.0, 1.0))
    # t(1,1,1) = (3,4,5) → ×0.5 = (1.5, 2.0, 2.5)
    check("* 标量逐元素缩放", close([q.x, q.y, q.z], [1.5, 2.0, 2.5], 1e-3))

    # ── quat：轴角 → mat4 → 3D 点变换 ──
    quat = M.quat_from_axis_angle(0.0, 1.0, 0.0, 90.0)
    rot = M.mat4_from_quat(quat)
    p = rot.transform_point3(pygame.math.Vector3(1.0, 0.0, 0.0))
    # 绕 Y 轴 +90°：(1,0,0) → (0,0,-1)
    check("quat 轴角旋转 Y+90°", close([p.x, p.y, p.z], [0.0, 0.0, -1.0], 1e-3))

    # ── identity 恒等 ──
    back = (t @ M.mat4_identity()).transform_point3(pygame.math.Vector3(1.0, 2.0, 3.0))
    check("t @ identity = t", close([back.x, back.y, back.z], [3.0, 5.0, 7.0], 1e-3))

    # ── 渲染：三轴环（mat4_from_quat 实时旋转验证）──
    frame = 0
    angle = 0.0
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        angle += 0.01
        with screen.render() as rt:
            rt.fill((14, 16, 24))
            cam = pygame.render.camera_perspective(55.0, 800 / 600, 0.1, 100.0)
            cam = cam.with_view(M.mat4_translation(0.0, 1.0, -5.0))
            pygame.gfxdraw.set_camera(rt, cam)

            for axis, col in ((0.0, (255, 90, 90)), (1.0, (90, 255, 90)),
                              (2.0, (90, 120, 255))):
                quat = M.quat_from_axis_angle(axis, axis, axis, angle)
                rot = M.mat4_from_quat(quat)
                pts = []
                for i in range(24):
                    a = i / 24.0 * 6.2831853
                    v = rot.transform_point3(
                        pygame.math.Vector3(M.cos(a) * 1.5, M.sin(a) * 1.5, 0.0))
                    pts += [v.x, v.y, v.z]
                pygame.gfxdraw.set_color(rt, col)
                pygame.gfxdraw.polygon3d(rt, pts)

            pygame.gfxdraw.clear_camera(rt)
            yy = 270
            for line in PASS + FAIL:
                s = font.render(line, True,
                                (140, 220, 140) if line in PASS else (230, 120, 120))
                pygame.gfxdraw.set_transform(rt, M.mat4_translation(-380, yy, 0))
                pygame.gfxdraw.draw_surface(rt, s)
                yy -= 22

        pygame.display.flip()
        frame += 1
        if frame == 30:
            print(f"[math-test] SUMMARY {'PASS' if not FAIL else 'FAIL ' + str(FAIL)} "
                  f"({len(PASS)} 项)")
        if frame > 60:
            return
        pygame.time.delay(8)
        await pygame.next_frame()
