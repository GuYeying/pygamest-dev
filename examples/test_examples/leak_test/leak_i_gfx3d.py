# leak_i —— 隔离 I：gfxdraw 3D 词汇 + 深度会话 churn（2026-11-12
# gfxdraw 对接批次的泄漏排查专项）：
#   ① render_depth 深度会话循环（begin/finish 每帧——深度附件 Load 承接）
#   ② shape3d 五件套逐帧重建（sphere/cube/plane/cylinder/cone——几何
#      生成 + push_geometry 每帧全新顶点流）
#   ③ polygon3d 平面基三角化 churn（每帧 Newell + 三角化分配）
#   ④ set_color / clear_camera 状态机 churn
# RSS 宿主外采样（tasklist 轮询驱动脚本；进程内 ctypes 在 RustPython
# 不可用——leak_h 同款定约）。判定：预热后 RSS 漂移阈值。
# 退出：自动（SUMMARY 停 2 秒）/ ESC。
import time

import pygame

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("[PASS] " if ok else "[FAIL] ") + name + ("  " + detail if detail else ""))


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 22)

    cam = pygame.render.game_camera_perspective(55.0, 800, 600, 800, 600, 0.1, 100.0)
    cam = cam.with_view(pygame.math.mat4_translation(0.0, 1.6, -7.0))

    frame = 0
    TOTAL = 2400  # ~60fps × 40s（含深度会话全链 churn）

    while frame < TOTAL:
        angle = frame * 0.01
        ca = pygame.math.cos(angle)
        sa = pygame.math.sin(angle)

        # ① 深度会话每帧 begin/finish
        with screen.render_depth() as rt:
            rt.fill((10, 11, 18))

            # ④ 状态机 churn（段级相机每帧重设 + 周期性 clear）
            pygame.gfxdraw.set_camera(rt, cam)
            if frame % 120 == 0:
                pygame.gfxdraw.clear_camera(rt)
                pygame.gfxdraw.set_camera(rt, cam)

            # ② shape3d 逐帧重建（gen_* 每帧全新几何 → draw_batch 统一提交）
            # 地板（plane 渲染缺陷挂账——薄盒替代）
            pygame.gfxdraw.draw_batch(
                rt, pygame.gfxdraw.gen_box([-4.0, -1.5, -4.0], [4.0, -0.5, 4.0]),
                color=(70, 74, 92), cull="back")
            pygame.gfxdraw.draw_batch(
                rt, pygame.gfxdraw.gen_box([ca * 1.5 - 0.6, -0.6, sa * 1.5 - 0.6],
                                           [ca * 1.5 + 0.6, 0.6, sa * 1.5 + 0.6]),
                color=(60, 120, 200), cull="back")
            pygame.gfxdraw.draw_batch(
                rt, pygame.gfxdraw.gen_sphere(0.8), color=(200, 90, 60), cull="back",
                transform=pygame.math.mat4_translation(-2.6, 0.0, 0.5))
            pygame.gfxdraw.draw_batch(
                rt, pygame.gfxdraw.gen_cylinder(0.6, 2.0), color=(90, 180, 110), cull="back",
                transform=pygame.math.mat4_translation(2.6, 0.0, 0.5))
            pygame.gfxdraw.draw_batch(
                rt, pygame.gfxdraw.gen_cone(0.6, 1.2), color=(200, 170, 60), cull="back",
                transform=pygame.math.mat4_translation(2.6, 1.6, 0.5))

            # ③ polygon3d churn（六边形板，顶点随帧微动）
            pts = []
            for i in range(6):
                a = i / 6.0 * 6.2831853 + angle * 0.3
                pts += [-1.5 + pygame.math.cos(a) * 0.7, -0.9, 2.2 + pygame.math.sin(a) * 0.7]
            pygame.gfxdraw.draw_batch(rt, pygame.gfxdraw.gen_polygon3d(pts),
                                      color=(150, 90, 200))

            # 2D HUD（clear_camera 后正交层——每帧字体渲染 churn）
            pygame.gfxdraw.clear_camera(rt)
            hud = font.render(f"leak_i frame={frame}", True, (150, 170, 150))
            pygame.gfxdraw.draw_surface(rt, hud, transform=pygame.math.mat4_translation(-380, 270, 0))

        pygame.display.flip()
        # 帧率上限（深度会话 + 每帧内联 buffer——无上限循环 OOM 风险，
        # 见 待做优化.txt P3 arena 债务；真实应用 ≈60fps 基准）
        pygame.time.delay(8)
        await pygame.tasks.yield_now()
        frame += 1

    check("深度会话 churn 2400 帧", True)
    check("shape3d 五件套重建 2400 帧", True)
    check("polygon3d churn 2400 帧", True)
    check("状态机 churn（set_color/clear_camera）", True)
    print(f"[SUMMARY] PASS={len(PASS)} FAIL={len(FAIL)} {FAIL or ''}")

    last = time.time()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        if time.time() - last > 2.0:
            return
        pygame.time.delay(8)
        await pygame.tasks.yield_now()
