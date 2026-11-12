# gamepad_test —— pygame.gamepad 专项案例：设备枚举 / 连接状态 / 按键
# 轮询 / 摇杆读取（无手柄 = 合法输出"未连接"）。方向键 = 视觉对照方块。
# 退出：ESC / 关窗。
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 20)
    count = pygame.gamepad.get_count()
    x, y = 0.0, 0.0

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        lines = [f"手柄数量 {count}"]
        if count > 0:
            for gid in range(count):
                lines.append(f"手柄 {gid}：A={pygame.gamepad.get_pressed(gid, 0)} "
                             f"B={pygame.gamepad.get_pressed(gid, 1)}")
            # 手柄左摇杆（按键 13/14/11/12 = SDL 十字，视布局而定）
            if pygame.gamepad.get_pressed(0, 13):
                x -= 4.0
            if pygame.gamepad.get_pressed(0, 14):
                x += 4.0
            if pygame.gamepad.get_pressed(0, 11):
                y += 4.0
            if pygame.gamepad.get_pressed(0, 12):
                y -= 4.0
        else:
            lines.append("未连接手柄（连接后此案例实时显示按键态）")
            lines.append("方向键 = 视觉对照方块")

        kb = pygame.key.get_pressed()
        if kb.get(pygame.key.K_LEFT):
            x -= 4.0
        if kb.get(pygame.key.K_RIGHT):
            x += 4.0
        if kb.get(pygame.key.K_UP):
            y += 4.0
        if kb.get(pygame.key.K_DOWN):
            y -= 4.0
        x = max(-380.0, min(380.0, x))
        y = max(-280.0, min(280.0, y))

        with screen.render() as t:
            t.fill((16, 18, 26))
            pygame.gfxdraw.set_color(t, (90, 140, 220))
            pygame.gfxdraw.box(t, (int(x) - 20, int(y) - 20, 40, 40))
            yy = 270
            for line in lines:
                s = font.render(line, True, (180, 220, 180))
                pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, yy, 0))
                pygame.gfxdraw.draw_surface(t, s)
                yy -= 24

        pygame.display.flip()
        pygame.time.delay(8)
        await pygame.next_frame()
