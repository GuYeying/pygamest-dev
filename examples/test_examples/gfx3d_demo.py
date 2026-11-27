# gfx3d_demo —— gfxdraw 3D 词汇首验（2026-11-12 对接批次）：
# render_depth 深度会话 + 透视相机（gfxdraw.set_camera）+ shape3d 五件套
# （cube/sphere/plane/cylinder/cone）+ polygon3d（平面基三角化）+
# clear_camera 清除演示。退出：ESC / 关窗。
import pygame

M = pygame.math


async def main():
    screen = pygame.display.set_mode((800, 600))
    cjk = pygame.font.Font("cjk", 17)
    title = cjk.render("gfxdraw 3D：cube/sphere/plane/cylinder/cone/polygon3d（深度会话）",
                       True, (205, 205, 205))

    # 透视相机（像素空间 Camera——gfxdraw.set_camera 段级口）
    cam = pygame.render.game_camera_perspective(55.0, 800, 600, 800, 600, 0.1, 100.0)
    view = M.mat4_translation(0.0, 1.6, -7.0)
    cam = cam.with_view(view)

    angle = 0.0
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        angle += 0.01
        ca = M.cos(angle)
        sa = M.sin(angle)

        with screen.render_depth() as rt:
            rt.fill((10, 11, 18))

            # 3D 段：透视相机 + 深度测试管线
            pygame.gfxdraw.set_camera(rt, cam)

            # 地板平面（右/上基向量定朝向）
            # 地板（plane 直调渲染缺陷挂账——薄盒替代实证可靠）
            pygame.gfxdraw.cube(rt, [-4.0, -1.5, -4.0], [4.0, -0.5, 4.0])

            # 中央旋转立方体
            pygame.gfxdraw.cube(rt, [ca * 1.5 - 0.6, -0.6, sa * 1.5 - 0.6],
                                [ca * 1.5 + 0.6, 0.6, sa * 1.5 + 0.6])

            # 球（左）
            pygame.gfxdraw.sphere(rt, [-2.6, 0.0, 0.5], 0.8)

            # 圆柱 + 圆锥（右）
            pygame.gfxdraw.cylinder(rt, [2.6, -1.0, 0.5], 0.6, 2.0)
            pygame.gfxdraw.cone(rt, [2.6, 1.0, 0.5], 0.6, 1.2)

            # polygon3d：斜置六边形板（平面基三角化）
            hex_pts = []
            for i in range(6):
                a = i / 6.0 * 6.2831853
                hex_pts += [-1.5 + M.cos(a) * 0.7, -0.9, 2.2 + M.sin(a) * 0.7]
            pygame.gfxdraw.polygon3d(rt, hex_pts)

            # clear_camera：摘除透视 → 回目标尺寸正交（2D HUD 层）
            pygame.gfxdraw.clear_camera(rt)
            pygame.gfxdraw.set_transform(rt, M.mat4_translation(-380, 270, 0))
            pygame.gfxdraw.draw_surface(rt, title)

            # 正交 2D 边框线（clear 后像素坐标直用）
            pygame.gfxdraw.draw_batch(rt, pygame.gfxdraw.gen_line(-390, -290, 390, -290), color=(150, 170, 150))
            pygame.gfxdraw.draw_batch(rt, pygame.gfxdraw.gen_line(-390, -290, -390, 290))

        pygame.display.flip()
        # 帧率上限（深度会话每帧重建深度资源——无上限循环会 OOM，
        # 存量性能项挂账：深度纹理应随表面复用而非逐帧重建）
        pygame.time.delay(8)
        await pygame.tasks.yield_now()
