# live2d_shot —— 蒙版眼睛目验（真截图）：离屏 Surface 渲染 live2d →
# pygame.image.save 存 PNG。眼区位于画面上部中央（scale=900, ty=-300）。
import pygame
import pygame_live2d

MODEL = "D:/Projects/Rust/pygame_live2d/assets/models/Hiyori"


async def main():
    pygame.display.set_mode((400, 300))
    surf = pygame.Surface((800, 600))
    rt = pygame_live2d.load_runtime(f"{MODEL}/Hiyori.model3.json")
    motion = pygame_live2d.load_motion(f"{MODEL}/motions/Hiyori_m01.motion3.json")
    player = pygame_live2d.motion_player(motion)
    for frame in range(12):
        with surf.render() as t:
            pygame.gfxdraw.set_color(t, (36, 40, 52))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            if frame == 10:
                player.tick(1.0 / 30.0)
                player.apply(rt)
                rt.update_meshes()
                m = pygame.math.mat4_translation(0, -300, 0)
                pygame.gfxdraw.set_transform(t, m)
                pygame.gfxdraw.draw_live2d(t, rt, scale=900.0)
            else:
                player.tick(1.0 / 30.0)
                player.apply(rt)
                rt.update_meshes()
        pygame.display.flip()
        await pygame.next_frame()
    pygame.image.save(surf, "D:/Projects/Rust/pygame-rs-dev/examples/live2d_shot.png")
    print("SHOT SAVED")
