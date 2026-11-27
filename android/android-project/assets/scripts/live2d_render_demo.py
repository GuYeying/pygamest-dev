# live2d_render_demo —— mocari 渲染管线集成验证（sprite 工作流）：
# Hiyori 官方样例模型（Live2D Free Material License 资产，经 neocari
# 仓库分发副本 vendor）。rt.draw(buf) 全管线自理（产物面每帧传入——
# 同一对象可画任意尺寸/多个面）→ gfxdraw.draw_surface 上屏。参数/motion
# 双驱动，300 帧自动退出，第 30 帧像素探针自验可见性。
import time

import pygame

# pygame_live2d 是**可选能力**（Cargo feature live2d）——默认解释器里没有
# 这个子模块，此时给出明确提示并跳过，而不是抛 traceback
try:
    import pygame_live2d
except ModuleNotFoundError:
    pygame_live2d = None

# 模型目录：dev 解释器没有 `os` 模块，用 open 探路——从 dev 仓根启动时
# 资产在 examples/assets 下，从 examples/ 启动时在 assets 下
MODEL = "assets/models/Hiyori"
for _cand in ("assets/models/Hiyori", "examples/assets/models/Hiyori"):
    try:
        with open(_cand + "/Hiyori.model3.json", "rb") as _f:
            pass
        MODEL = _cand
        break
    except OSError:
        continue

async def main():
    if pygame_live2d is None:
        print("[live2d_demo] 跳过：当前解释器未编译 live2d 能力"
              "（重建时加 --features live2d）")
        return
    screen = pygame.display.set_mode((1000, 800),[pygame.display.NOFRAME,pygame.display.TRANSPARENT])
    screen.set_camera(pygame.render.game_camera_ortho(1000, 800, 1000, 800))
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
            t.fill((36, 40, 52))                     # 背景（原 set_color + box 的等价写法）
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
            pygame.gfxdraw.draw_surface(t, label, transform=pygame.math.mat4_translation(-380, 270, 0))
        clock.tick(60)
        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1

    print("[live2d_demo] DONE 300 帧")
