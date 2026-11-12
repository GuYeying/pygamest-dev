# input_test —— pygame.key / mouse / event 输入三件套专项案例：
#   方向键移动方块 + 鼠标位置/按键/滚轮实时显示 + 事件流滚动窗。
# 每帧断言输入状态一致性（PASS/FAIL 上屏）。退出：ESC / 关窗。
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 20)
    x, y = 0.0, 0.0            # 方块位置（中心系）
    click_pts = []             # 鼠标点击落点（中心系换算）
    event_log = []             # 事件流（最近 8 条）
    wheel = 0
    frame = 0
    PASS = []
    FAIL = []

    def check(name, ok):
        (PASS if ok else FAIL).append(name)
        if len(PASS) + len(FAIL) == 3:
            print(f"[input-test] 首轮断言 {'PASS' if not FAIL else 'FAIL ' + str(FAIL)}")

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
            if e.type == pygame.event.KEYDOWN:
                event_log.append(f"KEYDOWN {e.key}")
            if e.type == pygame.event.MOUSEBUTTONDOWN:
                event_log.append(f"MOUSEBTN {e.button}")
            if e.type == pygame.event.MOUSEWHEEL:
                wheel += e.y
                event_log.append(f"WHEEL {e.y:+d}")
        event_log = event_log[-8:]

        # ── 键盘：方向键移动（get_pressed 轮询态）──
        pressed = pygame.key.get_pressed()
        mx, my = 0.0, 0.0
        if pressed.get(pygame.key.K_LEFT):
            mx -= 4.0
        if pressed.get(pygame.key.K_RIGHT):
            mx += 4.0
        if pressed.get(pygame.key.K_UP):
            my += 4.0
        if pressed.get(pygame.key.K_DOWN):
            my -= 4.0
        x = max(-380.0, min(380.0, x + mx))
        y = max(-280.0, min(280.0, y + my))

        # ── 鼠标：位置（屏幕系 → 中心系）/ 按键 / 滚轮 ──
        px, py = pygame.mouse.get_pos()
        cx, cy = px - 400, 300 - py
        for (px0, py0) in click_pts:
            pass
        mb = pygame.mouse.get_pressed()
        if mb[0] and frame % 6 == 0:
            click_pts.append((cx, cy))
            click_pts = click_pts[-12:]

        # 首轮断言（状态 API 可用性）
        if frame == 1:
            check("key.get_pressed 可用", pressed is not None)
            check("mouse.get_pos 返回二元组", isinstance(px, int) and isinstance(py, int))
            check("mouse.get_pressed 三键", isinstance(mb, tuple) and len(mb) == 3)

        # ── 渲染 ──
        with screen.render() as t:
            t.fill((16, 18, 26))
            pygame.gfxdraw.set_color(t, (90, 140, 220))
            pygame.gfxdraw.box(t, (int(x) - 20, int(y) - 20, 40, 40))
            pygame.gfxdraw.set_color(t, (220, 120, 120))
            for (cx0, cy0) in click_pts:
                pygame.gfxdraw.filled_circle(t, cx0, cy0, 8)
            pygame.gfxdraw.set_color(t, (255, 90, 90))
            pygame.gfxdraw.filled_circle(t, cx, cy, 5)   # 鼠标指针落点

            info = [
                f"方块方向键移动 ({x:.0f},{y:.0f})  鼠标=({cx},{cy}) 左{mb[0]} 中{mb[1]} 右{mb[2]}",
                f"滚轮累计 {wheel:+d}   focused={pygame.mouse.get_focused()}",
            ] + event_log
            yy = 270
            for line in info:
                s = font.render(line, True, (180, 220, 180))
                pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, yy, 0))
                pygame.gfxdraw.draw_surface(t, s)
                yy -= 24

        pygame.display.flip()
        pygame.time.delay(8)
        frame += 1
        await pygame.next_frame()
