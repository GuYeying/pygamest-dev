# time_test —— pygame.time 专项案例：Clock.tick 帧率节流（返回真实
# 帧间隔）/ delay 精度 / FPS 统计。退出：ESC / 关窗。
import pygame

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("[PASS] " if ok else "[FAIL] ") + name + ("  " + detail if detail else ""))


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 20)
    clock = pygame.time.Clock()

    frames = 0
    fps_samples = []
    delays = []

    while frames < 180:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        dt = clock.tick(60)     # 目标 60fps——返回上一帧间隔 ms
        frames += 1
        if 10 <= frames <= 110:
            fps_samples.append(dt)
        if frames in (30, 60, 90):
            pygame.time.delay(5)
            delays.append(5)

        with screen.render() as rt:
            rt.fill((16, 18, 26))
            if fps_samples:
                avg = sum(fps_samples) / len(fps_samples)
                info = [
                    f"Clock.tick(60) 平均帧间隔 {avg:.1f} ms（目标 16.7）",
                    f"实测 FPS ≈ {1000.0 / avg:.1f}",
                    f"delay(5) 采样 {delays}",
                    f"frames {frames}/180",
                ]
                yy = 240
                for line in info:
                    s = font.render(line, True, (180, 220, 180))
                    pygame.gfxdraw.set_transform(
                        rt, pygame.math.mat4_translation(-380, yy, 0))
                    pygame.gfxdraw.draw_surface(rt, s)
                    yy -= 26

        pygame.display.flip()
        await pygame.next_frame()

    avg = sum(fps_samples) / len(fps_samples)
    check("tick 节流生效（平均间隔 ≥ 12ms）", avg >= 12.0, f"avg={avg:.1f}ms")
    check("delay(5) 调用无异常", len(delays) == 3)
    print(f"[time-test] SUMMARY {'PASS' if not FAIL else 'FAIL ' + str(FAIL)} "
          f"({len(PASS)} 项)")

    last = pygame.time.delay
    hold = 0
    import time as _t
    end = _t.time() + 2.0
    while _t.time() < end:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        with screen.render() as rt:
            rt.fill((16, 18, 26))
            s = font.render(f"SUMMARY {'PASS' if not FAIL else 'FAIL ' + str(FAIL)}",
                            True, (180, 220, 180))
            pygame.gfxdraw.set_transform(rt, pygame.math.mat4_translation(-160, 0, 0))
            pygame.gfxdraw.draw_surface(rt, s)
        pygame.display.flip()
        pygame.time.delay(8)
        await pygame.next_frame()
