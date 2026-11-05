# y 方向判定探针（一锤定音）：中心系 (0, +200)（上半）画白圆，
# screen_probe 帧缓冲回读——白像素落在物理帧上半 = y 向上正确；
# 落在下半 = 渲染 y 反转。同时画顶部/底部文字条辅助目视。
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 24)
    top = font.render("THIS TEXT WAS DRAWN AT +Y (expect TOP)", True, (120, 255, 120))
    #bot = font.render("this text was drawn at -Y (expect BOTTOM)", True, (255, 160, 120))

    frame = 0
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return

        with screen.render() as f:
            f.fill((16, 16, 28))
            pygame.gfxdraw.filled_circle(f, 0, 200, 70, (255, 255, 255))      # 中心系上半白圆
            pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(-390, 250, 0)); pygame.gfxdraw.draw_surface(f, top)     # +Y 文字（期望顶部）
            #pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(-390, -270, 0)); pygame.gfxdraw.draw_surface(f, bot)    # -Y 文字（期望底部）
        pygame.display.flip()

        if frame == 3:
            pts = pygame.render.screen_probe()
            white_top = sum(1 for x, y, r, g, b, a in pts if y < 300 and r > 200 and g > 200)
            white_bot = sum(1 for x, y, r, g, b, a in pts if y >= 300 and r > 200 and g > 200)
            print("[ycheck] probe 网格点数 =", len(pts))
            print("[ycheck] 上半白像素 =", white_top, " 下半白像素 =", white_bot)
            print("[ycheck] 结论:", "y 向上正确（+Y → 屏幕上方）" if white_top > white_bot
                  else "渲染 y 反转！（+Y → 屏幕下方）")
        frame += 1
        await pygame.next_frame()
