# live2d_render_demo —— mocari 渲染管线集成验证：Hiyori 官方样例模型
# （Live2D Free Material License 资产，经 neocari 仓库分发副本 vendor）
# 经 gfxdraw.draw_live2d 上屏。参数/motion 双驱动，300 帧自动退出，
# 第 30 帧像素探针自验可见性。
import time

import pygame
import pygame_live2d

MODEL = "D:/Projects/Rust/pygame_live2d/assets/models/Hiyori"

async def main():
    screen = pygame.display.set_mode((1000, 800))
    rt = pygame_live2d.load_runtime(f"{MODEL}/Hiyori.model3.json")
    print("[live2d_demo] canvas =", rt.canvas_size())
    print("[live2d_demo] drawable 数 =", rt.mesh_count())

    motion = pygame_live2d.load_motion(f"{MODEL}/motions/Hiyori_m01.motion3.json")
    player = pygame_live2d.motion_player(motion)

    font = pygame.font.Font(None, 22)
    frame = 0
    last = time.time()
    while frame < 300:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        now = time.time()
        dt = now - last
        last = now
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (36, 40, 52))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            player.tick(dt)
            player.apply(rt)
            rt.update_meshes()
            # 画布 2976×4175 像素域 → 适配视口（缩放 + 下移居中）
            s = 800/600#260.0 / 2087.0
            m = pygame.math.mat4_translation(0, -40, 0).mul_mat4(
                pygame.math.mat4_scale(s, s, s)
            )
            pygame.gfxdraw.set_transform(t, m)
            pygame.gfxdraw.draw_live2d(t, rt, scale=600.0)
            if frame == 30:
                probe = pygame.render.screen_probe()
                vis = sum(
                    1
                    for px in probe
                    if abs(px[0] - 36) + abs(px[1] - 40) + abs(px[2] - 52) > 30
                )
                print(f"[live2d_demo] 可见像素 = {vis}（>1000 即渲染成功）")
        label = font.render(f"live2d demo frame={frame}", True, (220, 220, 230))
        with screen.render() as t:
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, 270, 0))
            pygame.gfxdraw.draw_surface(t, label)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1

    print("[live2d_demo] DONE 300 帧")
