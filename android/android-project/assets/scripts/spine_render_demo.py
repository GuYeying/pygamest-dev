# spine_render_demo —— chine 渲染管线真资产验证：Spineboy 官方导出
# （EsotericSoftware/spine-runtimes examples/spineboy/export，Spine
# Runtimes License）load_with_atlas 一体绑定 → walk 动画 AnimationState
# 播放 → gfxdraw.draw_spine 上屏。300 帧自动退出。
import time

import pygame
import pygame_spine

ASSETS = "assets/spineboy"

async def main():
    screen = pygame.display.set_mode((800, 600))
    # 一体加载：路径进对象出（io 在绑定层闭环——Python 零搬运）
    data, pages = pygame_spine.load_with_atlas(
        f"{ASSETS}/spineboy-ess.json", f"{ASSETS}/spineboy.atlas"
    )
    print("[spine_demo] 图集页数 =", pages)
    sk = pygame_spine.Skeleton(data)
    sk.set_skin("default")
    anim = data.find_animation("walk")
    print("[spine_demo] walk 动画 =", anim is not None, "| duration =", anim.duration() if anim else None)
    state = pygame_spine.AnimationState()
    state.set_animation(anim, True)

    # 图集页纹理：spineboy.png（1024×256 单页）
    page0 = await pygame.image.load(f"{ASSETS}/spineboy.png")

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
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (30, 34, 44))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            state.update(dt)
            state.apply(sk)
            sk.update_world_transform()
            # spineboy 世界坐标：y 向上、原点在脚底——抬到屏幕中部
            zoom = pygame.math.mat4_scale(0.6, 0.6, 0.6)
            m = pygame.math.mat4_translation(0, -120, 0).mul_mat4(zoom)
            pygame.gfxdraw.set_transform(t, m)
            pygame.gfxdraw.draw_spine(t, sk, [page0])
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(0, 0, 0))
        label = font.render(f"spineboy walk frame={frame}", True, (220, 220, 230))
        with screen.render() as t:
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, 270, 0))
            pygame.gfxdraw.draw_surface(t, label)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1

    print("[spine_demo] DONE 300 帧")
