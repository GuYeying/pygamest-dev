# min_probe —— 内容层最小对照（fill + gfxdraw 文字，无物理/无 raw）：
# probe 与 PrintWindow 双取证——帧缓冲回读与窗口截图对账，定位"内容层
# pass 被 GPU 丢弃"的真伪与范围（2026-11-20 MC 案例 HUD 消失排查）。
import pygame


async def main():
    pygame.display.set_caption("min_probe")
    pygame.render.set_fb_dump(True)   # BMP 像素真值（STARFISH_FB_BMP 落盘）
    screen = pygame.display.set_mode((400, 300))
    screen.set_camera(pygame.render.game_camera_ortho(400, 300, 400, 300))
    cjk = pygame.font.Font("cjk", 15)
    frame = 0
    while True:
        with screen.render() as rt:
            rt.fill((28, 34, 46))   # 自然顺序（fill 最先——背景语义）
            pygame.gfxdraw.set_transform(rt, pygame.math.mat4_translation(-150, 120, 0))
            pygame.gfxdraw.draw_surface(rt, cjk.render("MIN PROBE TEST", True, (255, 255, 255)))
            pygame.gfxdraw.draw_batch(rt, pygame.gfxdraw.gen_rect(20, 2), color=(240, 240, 240))
            pygame.gfxdraw.draw_batch(rt, pygame.gfxdraw.gen_rect(2, 20), color=(240, 240, 240))
        if frame == 200:
            for s in pygame.render.screen_probe()[:6]:
                print("[probe]", s, flush=True)
        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1
        if frame > 300:
            return
