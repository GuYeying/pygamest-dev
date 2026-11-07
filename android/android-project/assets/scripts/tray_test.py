# tray_test —— 系统托盘能力位验证（桌宠第二梯队）：程序化 Surface
# 图标 → set_tray（tooltip + 平铺菜单）→ 循环收 trayclick/traymenu/
# traydoubleclick 事件 → frame 300 摘除重装（生命周期验证）→ 自动退出。
# 手动验收：托盘区出现图标（悬停看提示），左键点图标 → 控制台打印
# trayclick，右键 → 弹菜单，点菜单项 → 打印 traymenu（点"退出"提前结束）。
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))

    # 托盘图标：64×64 程序化 Surface（绿底 + 红圆——一眼可辨）
    icon = pygame.Surface((64, 64))
    with icon.render() as t:
        t.fill((40, 120, 60))
        pygame.gfxdraw.set_color(t, (230, 70, 70))
        pygame.gfxdraw.filled_circle(t, 32, 32, 20)

    pygame.display.set_tray(
        icon,
        "pygamest 托盘测试（左键=事件 右键=菜单）",
        [("show", "显示窗口"), ("about", "关于"), ("quit", "退出")],
    )
    print("[tray-test] 托盘已安装（3 菜单项）✓")

    font = pygame.font.Font("cjk", 16)
    last_event = "（无）"
    frame = 0
    while frame < 1200:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
            if e.type == pygame.event.TRAYMENU:
                last_event = f"traymenu id={e.id}"
                print(f"[tray-test] {last_event}")
                if e.id == "quit":
                    print("[tray-test] 菜单'退出'触发 → 结束")
                    return
            elif e.type == pygame.event.TRAYCLICK:
                last_event = f"trayclick button={e.button} pos=({e.x},{e.y})"
                print(f"[tray-test] {last_event}")
            elif e.type == pygame.event.TRAYDOUBLECLICK:
                last_event = f"traydoubleclick button={e.button}"
                print(f"[tray-test] {last_event}")
        # frame 300：摘除重装（Drop 摘图标 + 重建生命周期验证）
        if frame == 300:
            pygame.display.remove_tray()
            print("[tray-test] 托盘已摘除（图标应消失）✓")
        if frame == 420:
            pygame.display.set_tray(icon, "pygamest 托盘测试（重装）")
            print("[tray-test] 托盘已重装（无菜单）✓")
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (30, 34, 44))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            line = font.render(
                f"frame {frame} · 最近托盘事件: {last_event}（ESC 退出）",
                True, (255, 255, 255))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-360, 240, 0))
            pygame.gfxdraw.draw_surface(t, line)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
    print("[tray-test] 1200 帧跑完（全程 Err-free）✓")
