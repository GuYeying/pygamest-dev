# click_through_test —— 穿透能力位 M1 验证（任务14-M1）：透明窗形态
# set_click_through(True) → OS 位读回 True → 恢复 False → 读回 False；
# 全程渲染不中断（穿透只改命中测试不影响呈现——设计稿 DComp 兼容实证）。
# 视觉验收：状态行实时显示穿透态；手动点击画面（穿透态点击落到下层）。
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600),
                                     pygame.display.NOFRAME | pygame.display.TRANSPARENT)
    pygame.display.set_click_through(True)
    assert pygame.display.get_click_through() is True
    print("[ct-test] 穿透 ON 读回 True ✓")

    font = pygame.font.Font("cjk", 16)
    click_through = True
    frame = 0
    while frame < 600:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        # 每 300 帧自动翻转穿透态（演示 + 读回自检循环）
        if frame % 300 == 299:
            click_through = not click_through
            pygame.display.set_click_through(click_through)
        readback = pygame.display.get_click_through()
        assert readback == click_through, "读回与设定不一致"
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (40, 120, 220, 140))
            pygame.gfxdraw.box(t, (-300, -200, 600, 400))
            line = font.render(
                f"穿透={click_through} 读回={readback} · frame {frame}（ESC 退出）",
                True, (255, 255, 255))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-300, 240, 0))
            pygame.gfxdraw.draw_surface(t, line)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
    print("[ct-test] 600 帧读回自检全过 ✓")
