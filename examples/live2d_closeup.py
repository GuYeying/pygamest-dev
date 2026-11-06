# live2d_closeup —— 眼部特写目验（多动画时点）：scale 放大 + y 平移
# 取景头部（内容锚定后 y<0 = 内容下移 = 露出上半身），存 3 张 PNG。
import pygame
import pygame_live2d

MODEL = "D:/Projects/Rust/pygame_live2d/assets/models/Hiyori"
SHOTS = [(8, "closeup_a"), (95, "closeup_b"), (175, "closeup_c")]


async def main():
    pygame.display.set_mode((400, 300))
    buf = pygame.Surface((800, 600))
    rt = pygame_live2d.load_runtime(f"{MODEL}/Hiyori.model3.json", buf)
    motion = pygame_live2d.load_motion(f"{MODEL}/motions/Hiyori_m01.motion3.json")
    player = pygame_live2d.motion_player(motion)
    for frame in range(180):
        player.tick(1.0 / 30.0)
        player.apply(rt)
        rt.update_meshes()
        if frame in (s[0] for s in SHOTS):
            rt.draw(x=0.0, y=-0.65, scale=1.7)
            for f, name in SHOTS:
                if f == frame:
                    pygame.image.save(
                        buf, f"D:/Projects/Rust/pygame-rs-dev/examples/{name}.png"
                    )
                    print(f"{name} saved @frame{frame}")
        await pygame.next_frame()
    print("CLOSEUP DONE")
