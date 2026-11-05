# ozz_render_demo —— ozz-animation-rs 采样链集成验证：playback demo
# 资产（内嵌）sample(ratio) → 关节世界位 → gfxdraw.draw_ozz_bones 骨骼
# 线上屏（父子连线，y 同构零翻转）。ratio 呼吸摆动。300 帧自动退出。
import pygame
import pygame_ozz

async def main():
    screen = pygame.display.set_mode((800, 600))
    p = pygame_ozz.demo_player()
    print("[ozz_demo] 关节数 =", p.num_joints())
    print("[ozz_demo] 动画时长 =", p.duration())

    font = pygame.font.Font(None, 22)
    frame = 0
    while frame < 300:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (24, 26, 34))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            ratio = abs((frame % 120) - 60) / 60.0
            p.sample(ratio)
            pygame.gfxdraw.draw_ozz_bones(t, p, scale=60.0, cx=0.0, cy=-80.0)
            pygame.gfxdraw.draw_ozz_quads(t, p, scale=60.0, cx=0.0, cy=-80.0, size=10.0)
        label = font.render(f"ozz demo frame={frame} ratio={ratio:.2f}", True, (220, 220, 230))
        with screen.render() as t:
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, 270, 0))
            pygame.gfxdraw.draw_surface(t, label)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1

    print("[ozz_demo] DONE 300 帧")
