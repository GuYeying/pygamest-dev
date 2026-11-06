# live2d_closeup —— 眼部特写目验（多帧）：scale=2200 眼心对准画面中心，
# 采 3 个动画时点（睁眼/转眼/眨眼）存 PNG。
import pygame
import pygame_live2d

MODEL = "D:/Projects/Rust/pygame_live2d/assets/models/Hiyori"
SHOTS = [(8, "closeup_a"), (95, "closeup_b"), (175, "closeup_c")]


async def main():
    pygame.display.set_mode((400, 300))
    surf = pygame.Surface((800, 600))
    rt = pygame_live2d.load_runtime(f"{MODEL}/Hiyori.model3.json")
    motion = pygame_live2d.load_motion(f"{MODEL}/motions/Hiyori_m01.motion3.json")
    player = pygame_live2d.motion_player(motion)
    S = 2200.0
    ecx, ecy = 0.0, 0.416
    tx = -ecx * S
    ty = -ecy * S
    for frame in range(180):
        player.tick(1.0 / 30.0)
        player.apply(rt)
        rt.update_meshes()
        if frame in (s[0] for s in SHOTS):
            with surf.render() as t:
                pygame.gfxdraw.set_color(t, (36, 40, 52))
                pygame.gfxdraw.box(t, (-400, -300, 800, 600))
                m = pygame.math.mat4_translation(tx, ty, 0)
                pygame.gfxdraw.set_transform(t, m)
                pygame.gfxdraw.draw_live2d(t, rt, scale=S)
            for f, name in SHOTS:
                if f == frame:
                    pygame.image.save(surf, f"D:/Projects/Rust/pygame-rs-dev/examples/{name}.png")
                    print(f"{name} saved @frame{frame}")
        await pygame.next_frame()
    print("CLOSEUP DONE")
