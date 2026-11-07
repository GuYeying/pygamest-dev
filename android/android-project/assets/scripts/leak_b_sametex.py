# leak_b —— 最小化隔离 B（对照组）：同一 Surface 复用（纹理只建一次）
# 判据：live 曲线平 = 复用路径无泄漏 → A/B 差异锁定"每帧新纹理"链路
import pygame


async def main():
    screen = pygame.display.set_mode((400, 300))
    font = pygame.font.Font("cjk", 16)
    surf = font.render("fixed surface reuse", True, (200, 200, 200))
    frame = 0
    while frame < 3600:
        with screen.render() as r:
            r.fill((20, 20, 30))
            pygame.gfxdraw.draw_surface(r, surf)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
