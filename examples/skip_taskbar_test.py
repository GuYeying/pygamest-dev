# skip_taskbar_test —— 任务栏隐藏能力位验证（桌宠第二梯队）：普通窗
# set_skip_taskbar(True) → OS 状态读回 True → 翻转恢复 False → 读回
# False；全程渲染不中断。视觉验收：任务栏按钮消失/复现（手动——
# Windows 任务栏、macOS Dock 图标）；注意 Win32 工具窗语义 = Alt+Tab
# 一并隐藏（桌宠场景通常正合预期）。
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_skip_taskbar(True)
    assert pygame.display.get_skip_taskbar() is True
    print("[st-test] 任务栏隐藏 ON 读回 True ✓")

    font = pygame.font.Font("cjk", 16)
    skip_taskbar = True
    frame = 0
    while frame < 600:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        # 每 300 帧自动翻转隐藏态（演示 + 读回自检循环）
        if frame % 300 == 299:
            skip_taskbar = not skip_taskbar
            pygame.display.set_skip_taskbar(skip_taskbar)
        readback = pygame.display.get_skip_taskbar()
        assert readback == skip_taskbar, "读回与设定不一致"
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (30, 34, 44))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            line = font.render(
                f"任务栏隐藏={skip_taskbar} 读回={readback} · frame {frame}（ESC 退出）",
                True, (255, 255, 255))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-300, 240, 0))
            pygame.gfxdraw.draw_surface(t, line)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
    print("[st-test] 600 帧读回自检全过 ✓")
