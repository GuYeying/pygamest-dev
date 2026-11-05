# camera_kit_demo —— 多文件工程最小模板（开发者对照样例）。
#
# 布局：本文件（主脚本）+ modules/rsdev_kit.py（相机封装）
#       + modules/rsdev_log.py（本地日志）——`import modules.xxx` 即达
#       （模块根 = 主脚本所在目录，引擎自动装载模块表）。
# 演示：自定义相机三件套——上半 2D 正交（blit_transform 旋转卡片）、
#       下半 3D 透视 + 深度会话（近大远小）、帧内回切 2D 画文字；
#       Android 窗口化 letterbox 与桌面同一份代码（引擎统一呈现映射）。
# 退出：ESC / 返回键 / 600 帧自动（≈10s，日志写 DONE 便于取证）。
import pygame

import modules.rsdev_kit as kit
import modules.rsdev_log as rlog


async def main():
    rlog.clear()                                    # 一轮运行一个日志文件
    screen = pygame.display.set_mode((800, 600))
    w, h = screen.get_size()
    rlog.log("set_mode =", (w, h), "| get_size 一致:", (w, h) == (800, 600))
    rlog.log("日志落点 =", rlog.path())

    font = pygame.font.Font(None, 26)               # 内嵌默认字体（拉丁）
    try:
        cjk = pygame.font.Font("cjk", 20)           # 宿主预载 CJK（缺则回退）
    except (ValueError, TypeError):
        cjk = font

    # 静态面创建一次、循环内只 blit（性能定约——勿每帧新建 GPU 表面）
    title = cjk.render(
        "camera_kit_demo：上半 2D 正交 / 下半 3D 透视", True, (220, 220, 230))
    card = pygame.Surface((120, 90))
    with card.render() as t:
        t.fill((30, 34, 48))
        pygame.gfxdraw.rectangle(t, (6, 6, 108, 78), (80, 200, 90))  # 原 width=2 描边（gfxdraw 恒 1px）
        pygame.gfxdraw.filled_circle(t, 34, 45, 16, (230, 70, 70))

    cam2d = kit.Camera2D(w, h)                      # 相机只建一次
    cam3d = kit.Camera3D(w, h, fov=45.0)
    k = 0.5 / 120.0                                 # 卡片像素 → 3D 世界单位（宽≈0.5）

    frame = 0
    while frame < 600:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        x = 100 + (frame * 3) % (w - 220)           # 匀速巡游（帧推进自证）

        # ── 上半：2D 正交（会话级 set_camera）+ draw_surface 矩阵链 ──
        with screen.render() as t:
            cam2d.use(t)
            t.fill((16, 17, 24))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(14, 10, 0)); pygame.gfxdraw.draw_surface(t, title)
            pygame.gfxdraw.set_transform(t, 
                kit.chain(kit.pos(x, 180), kit.rot_z(frame % 360)))
            pygame.gfxdraw.draw_surface(t, card)
            pygame.gfxdraw.box(t, (0, h // 2, w, 3), (70, 74, 92))

        # ── 下半：3D 透视 + 深度会话（y 向上右手系，看向 -Z）──
        with screen.render_depth() as t:
            cam3d.use(t)
            pygame.gfxdraw.set_transform(t, 
                kit.chain(kit.pos(-0.5, 0.4, -2.2), kit.scale(k)))
            pygame.gfxdraw.draw_surface(t, card)
            pygame.gfxdraw.set_transform(t, 
                kit.chain(kit.pos(0.5, 0.6, -3.4), kit.scale(k)))
            pygame.gfxdraw.draw_surface(t, card)

        # 回 2D 画文字/描边（新会话开始即 Auto 重置——中心系坐标）
        with screen.render() as t:
            cam2d.use(t)
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(14, h // 2 - 8, 0))
            pygame.gfxdraw.draw_surface(t, cjk.render("下半：render_depth + 透视（近大远小）",
                              True, (150, 160, 180)))
            pygame.gfxdraw.rectangle(t, (20 - w // 2, -(h // 2 - 40), w - 40, h // 2 - 60), (120, 60, 60))

        pygame.display.flip()
        frame += 1
        if frame == 30:
            rlog.log("[selftest] 帧空档相机 = manual:", hasattr(pygame.render.camera_mvp(), "mul_mat4"))
        await pygame.next_frame()

    rlog.log("DONE 600 帧渲染收口")
