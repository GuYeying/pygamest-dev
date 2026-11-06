# spine_wasm_test —— wasm 平台 spine 运行测试（任务7）：**异步 fetch 供数**
# （web io 定约：v1 无同步 read_text——资源走 await pygame.io.fetch →
# bytes.decode() → 绑定字节入参）→ load_with_atlas → walk 240 帧渲染
# 上屏，状态行落画面 + wasm 控制台 [wasm-spine] 取证。
import pygame
import pygame_spine

ok = []
fail = []


def st(name, cond):
    (ok if cond else fail).append(name)
    print("[wasm-spine]", "PASS" if cond else "FAIL", name)


async def main():
    screen = pygame.display.set_mode((800, 600))
    j_bytes = await pygame.io.fetch("assets/spineboy/spineboy-ess.json")
    a_bytes = await pygame.io.fetch("assets/spineboy/spineboy.atlas")
    st("io.fetch 异步供数", j_bytes is not None and len(j_bytes) > 100)
    data, pages = pygame_spine.load_with_atlas(
        j_bytes.decode("utf-8"), a_bytes.decode("utf-8")
    )
    st("load_with_atlas 页数=1", pages == 1)
    sk = pygame_spine.Skeleton(data)
    sk.set_skin("default")
    walk = data.find_animation("walk")
    st("find_animation walk", walk is not None)
    state = pygame_spine.AnimationState()
    state.set_animation(walk, True)
    page0 = await pygame.image.load("assets/spineboy/spineboy.png")
    st("纹理加载", page0 is not None)

    font = pygame.font.Font("cjk", 16)
    frame = 0
    while frame < 240:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (30, 34, 44))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            state.update(1.0 / 60.0)
            state.apply(sk)
            sk.update_world_transform()
            m = pygame.math.mat4_translation(0, -120, 0).mul_mat4(
                pygame.math.mat4_scale(0.6, 0.6, 0.6)
            )
            pygame.gfxdraw.set_transform(t, m)
            pygame.gfxdraw.draw_spine(t, sk, [page0])
            status = f"wasm spine: PASS {len(ok)} FAIL {len(fail)}"
            color = (120, 255, 120) if not fail else (255, 120, 120)
            line = font.render(status, True, color)
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, 280, 0))
            pygame.gfxdraw.draw_surface(t, line)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
    print("[wasm-spine] 汇总:", "ALL PASS" if not fail else f"FAIL {fail}")
