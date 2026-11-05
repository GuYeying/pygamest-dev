# spine_render_demo —— chine 渲染管线集成验证：程序化 region 骨架经
# gfxdraw.draw_spine 上屏（page0 纹理 = 程序化色块 Surface）。arm 骨
# 正弦摆动，body/hand 两方块跟随骨骼世界变换。300 帧自动退出。
import pygame
import pygame_spine

async def main():
    screen = pygame.display.set_mode((800, 600))
    data = pygame_spine.demo_textured_skeleton()
    sk = pygame_spine.Skeleton(data)
    sk.set_skin("default")

    # page0 纹理：64x64 四象限色块（region uv 全图 → 方块四色拼花）
    page0 = pygame.Surface((64, 64))
    with page0.render() as t:
        pygame.gfxdraw.set_color(t, (200, 60, 60))
        pygame.gfxdraw.box(t, (-32, -32, 32, 32))
        pygame.gfxdraw.set_color(t, (60, 200, 90))
        pygame.gfxdraw.box(t, (0, -32, 32, 32))
        pygame.gfxdraw.set_color(t, (70, 110, 220))
        pygame.gfxdraw.box(t, (-32, 0, 32, 32))
        pygame.gfxdraw.set_color(t, (230, 200, 70))
        pygame.gfxdraw.box(t, (0, 0, 32, 32))

    font = pygame.font.Font(None, 22)
    frame = 0
    while frame < 300:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (24, 26, 34))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            sk.set_bone_rotation(1, -30.0 + 60.0 * abs((frame % 120) - 60) / 60.0)  # 三角波摆动（冻结面无 math）
            sk.update_world_transform()
            pygame.gfxdraw.draw_spine(t, sk, [page0])
        label = font.render(f"spine demo frame={frame}", True, (220, 220, 230))
        with screen.render() as t:
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, 270, 0))
            pygame.gfxdraw.draw_surface(t, label)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1

    print("[spine_demo] DONE 300 帧")
