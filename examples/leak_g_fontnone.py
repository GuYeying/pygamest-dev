# leak_g —— 泄漏复查（用户报告：Font(None) 每帧新文本 render 疑似不释放，
# spine_render_demo 的 label 行注释后改善）。三段对照：
# A. Font(None) 每帧新文本 render+draw（复现用户场景）
# B. 同上但不绘制（只 render 丢引用——隔离字形/纹理上传路径）
# C. cjk 每帧新文本（对照——此前已验证走平的路径）
import pygame


async def main():
    screen = pygame.display.set_mode((400, 300))
    fnone = pygame.font.Font(None, 22)
    fcjk = pygame.font.Font("cjk", 16)
    frame = 0
    while frame < 9000:
        label = fnone.render(f"spineboy walk frame={frame}", True, (220, 220, 230))
        cjk_label = fcjk.render(f"中文 {frame}", True, (180, 220, 255))
        with screen.render() as r:
            r.fill((20, 20, 30))
            pygame.gfxdraw.draw_surface(r, label)
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(0, 40, 0))
            pygame.gfxdraw.draw_surface(r, cjk_label)
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_identity())
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
