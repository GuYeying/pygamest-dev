# touch_test —— pygame.touch 触摸专项案例（手机设备测试定向）：
# 触点数量 / 每指位置实时显示；桌面 = 鼠标模拟触点对照。ESC 退出。
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 20)
    finger_count = pygame.touch.get_count()
    touch_pts = []   # 触点轨迹（事件 MOUSEBUTTONDOWN 桌面模拟）

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
            if e.type == pygame.event.MOUSEBUTTONDOWN:
                px, py = pygame.mouse.get_pos()
                touch_pts.append((px - 400, 300 - py))
                touch_pts = touch_pts[-16:]

        lines = [f"touch.get_count = {finger_count}"]
        if finger_count > 0:
            for fid in range(finger_count):
                pos = pygame.touch.get_pos(fid)
                lines.append(f"手指 {fid}：{pos}")
        else:
            lines.append("无触点设备（桌面：鼠标点击 = 触点对照）")
        lines.append(f"点击轨迹 {len(touch_pts)} 点")

        with screen.render() as t:
            t.fill((16, 18, 26))
            pygame.gfxdraw.set_color(t, (120, 200, 220))
            for (cx, cy) in touch_pts:
                pygame.gfxdraw.filled_circle(t, cx, cy, 10)
            yy = 270
            for line in lines:
                s = font.render(line, True, (180, 220, 180))
                pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, yy, 0))
                pygame.gfxdraw.draw_surface(t, s)
                yy -= 24

        pygame.display.flip()
        pygame.time.delay(8)
        await pygame.next_frame()
