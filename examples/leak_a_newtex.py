# leak_a —— 最小化隔离 A：每帧新 Surface（新纹理）+ draw_surface
# 判据：PYGAMEST_MEMTRACE 下 live_alloc/live_bytes 线性涨 = 新纹理路径泄漏
import pygame


async def main():
    screen = pygame.display.set_mode((400, 300))
    font = pygame.font.Font("cjk", 16)
    frame = 0
    while frame < 9000:
        # 每帧新文本表面（新纹理——与 font_test 的每帧 cjk.render 同构）
        surf = font.render(f"leak probe {frame}", True, (200, 200, 200))
        with screen.render() as r:
            r.fill((20, 20, 30))
            pygame.gfxdraw.draw_surface(r, surf)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
