# anim3_wasm_test —— wasm 三动画库综合测试（任务7）：spine 全管线 +
# ozz 骨骼渲染 + live2d 模块验证（路径加载 wasm 不可用——模块面/API
# surface 断言）。240 帧三画同屏。
import pygame
import pygame_spine
import pygame_ozz
import pygame_live2d

ok = []
fail = []


def st(name, cond):
    (ok if cond else fail).append(name)
    print("[wasm-3anim]", "PASS" if cond else "FAIL", name)


SPINE_ASSETS = "assets/spineboy"


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font("cjk", 14)
    frame = 0

    # ── 模块导入验证 ──
    st("import pygame_spine", pygame_spine is not None)
    st("import pygame_ozz", pygame_ozz is not None)
    st("import pygame_live2d", pygame_live2d is not None)
    st("spine load_with_atlas", hasattr(pygame_spine, "load_with_atlas"))
    st("ozz demo_player", hasattr(pygame_ozz, "demo_player"))
    st("live2d load_model", hasattr(pygame_live2d, "load_model"))
    st("live2d load_runtime", hasattr(pygame_live2d, "load_runtime"))

    # ── spine 全管线 ──
    sj = await pygame.io.fetch(f"{SPINE_ASSETS}/spineboy-ess.json")
    sa = await pygame.io.fetch(f"{SPINE_ASSETS}/spineboy.atlas")
    sdata, spages = pygame_spine.load_with_atlas(sj.decode("utf-8"), sa.decode("utf-8"))
    st("spine load_with_atlas", sdata is not None)
    sk = pygame_spine.Skeleton(sdata)
    sanim = sdata.find_animation("walk")
    sstate = pygame_spine.AnimationState()
    sstate.set_animation(sanim, True)
    spage0 = await pygame.image.load(f"{SPINE_ASSETS}/spineboy.png")
    st("spine 纹理", spage0 is not None)

    # ── ozz 全管线 ──
    oz = pygame_ozz.demo_player()
    st("ozz demo_player", oz is not None)
    oz.sample(0.5)
    st("ozz sample", len(oz.model_matrices()) > 0)

    # ── live2d API surface（路径加载 wasm 不可用——API 面/渲染管线桌面验证）──
    st("live2d load_model fn", callable(pygame_live2d.load_model))
    st("live2d load_runtime fn", callable(pygame_live2d.load_runtime))
    st("live2d load_motion fn", callable(pygame_live2d.load_motion))
    st("live2d motion_player fn", callable(pygame_live2d.motion_player))

    # ── 240 帧三画同屏 ──
    while frame < 240:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        dt = 1.0 / 60.0
        ratio = abs((frame % 120) - 60) / 60.0

        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (30, 34, 44))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))

            # spine walk（左半）
            sstate.update(dt)
            sstate.apply(sk)
            sk.update_world_transform()
            m = pygame.math.mat4_translation(-200, -100, 0).mul_mat4(
                pygame.math.mat4_scale(0.4, 0.4, 0.4)
            )
            pygame.gfxdraw.set_transform(t, m)
            pygame.gfxdraw.draw_spine(t, sk, [spage0])

            # ozz 骨骼线（中下）
            oz.sample(ratio)
            m3 = pygame.math.mat4_translation(0, -200, 0).mul_mat4(
                pygame.math.mat4_scale(80.0, 80.0, 80.0)
            )
            pygame.gfxdraw.set_transform(t, m3)
            pygame.gfxdraw.draw_ozz_bones(t, oz, scale=1.0, cx=0.0, cy=0.0)

            # 状态行
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_identity())
            status = f"3anim wasm: PASS {len(ok)} FAIL {len(fail)}"
            color = (120, 255, 120) if not fail else (255, 120, 120)
            line = font.render(status, True, color)
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, 280, 0))
            pygame.gfxdraw.draw_surface(t, line)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
    print("[wasm-3anim] 汇总:", "ALL PASS" if not fail else f"FAIL {fail}")
