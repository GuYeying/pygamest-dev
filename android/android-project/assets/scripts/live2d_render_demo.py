# live2d_render_demo —— mocari 渲染管线集成验证（sprite 工作流）：
# Hiyori 官方样例模型（Live2D Free Material License 资产，经 neocari
# 仓库分发副本 vendor）。rt.draw(buf) 全管线自理（产物面每帧传入——
# 同一对象可画任意尺寸/多个面）→ gfxdraw.draw_surface 上屏。参数/motion
# 双驱动，300 帧自动退出，第 30 帧像素探针自验可见性。
import time

import pygame
import pygame_live2d

MODEL = "D:/Projects/Rust/pygame_live2d/assets/models/Hiyori"
#MODEL = "D:/Projects/Rust/pygame-rs-dev/examples/Mao"

async def main():
    screen = pygame.display.set_mode((1000, 800),[pygame.display.NOFRAME,pygame.display.TRANSPARENT])
    # 产物面：与屏幕等尺寸（1:1 上屏；换任意尺寸只影响清晰度）
    buf = pygame.Surface((1000, 800))
    rt = pygame_live2d.load_runtime(f"{MODEL}/Hiyori.model3.json")
    print("[live2d_demo] canvas =", rt.canvas_size())
    print("[live2d_demo] drawable 数 =", rt.mesh_count())

    motion = pygame_live2d.load_motion(f"{MODEL}/motions/Hiyori_m01.motion3.json")
    player = pygame_live2d.motion_player(motion)
    
    clock = pygame.time.Clock()
    
    font = pygame.font.Font(None, 22)
    frame = 0
    last = time.time()
    while frame < 30000:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        now = time.time()
        dt = now - last
        last = now
        player.tick(dt)
        player.apply(rt)
        rt.update_meshes()
        # 全管线自理：蒙版/masked/整模型三段落 buf（居中 90% 画布利用率）
        rt.draw(buf, scale=0.9)
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (36, 40, 52))
            #pygame.gfxdraw.box(t, (-500, -400, 1000, 800))
            pygame.gfxdraw.draw_surface(t, buf)
            if frame == 30:
                probe = pygame.render.screen_probe()
                vis = sum(
                    1
                    for px in probe
                    if abs(px[0] - 36) + abs(px[1] - 40) + abs(px[2] - 52) > 30
                )
                print(f"[live2d_demo] 可见像素 = {vis}")
        label = font.render(f"live2d demo frame={frame}", True, (220, 220, 230))
        with screen.render() as t:
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, 270, 0))
            pygame.gfxdraw.draw_surface(t, label)
        clock.tick(60)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1

    print("[live2d_demo] DONE 300 帧")
