# live2d_shot —— live2d sprite 工作流目验（真截图）：rt.draw(buf) →
# rt.draw() 全管线自理 → image.save 存 PNG（全透明底人物图）。
import pygame
import pygame_live2d

MODEL = "assets/models/Hiyori"


async def main():
    pygame.display.set_mode((400, 300))
    buf = pygame.Surface((800, 600))
    rt = pygame_live2d.load_runtime(f"{MODEL}/Hiyori.model3.json")
    motion = pygame_live2d.load_motion(f"{MODEL}/motions/Hiyori_m01.motion3.json")
    player = pygame_live2d.motion_player(motion)
    for frame in range(12):
        player.tick(1.0 / 30.0)
        player.apply(rt)
        rt.update_meshes()
        if frame == 10:
            rt.draw(buf, scale=0.9)
        await pygame.next_frame()
    pygame.image.save(buf, "live2d_shot.png")
    print("SHOT SAVED")
