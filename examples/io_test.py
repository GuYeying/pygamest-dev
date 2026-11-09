# io_test —— pygame.io 三端一致性案例（Windows/wasm/Android 同一脚本）：
# 写读闭环（字节/文本）、exists、异步通道（pending→ready→take）。
# 退出：自动（3 秒后）/ ESC。
import time

import pygame

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("[PASS] " if ok else "[FAIL] ") + name + ("  " + detail if detail else ""))


async def main():
    screen = pygame.display.set_mode((640, 360))
    font = pygame.font.Font(None, 24)
    payload = b"hello-io-" * 10

    # ① 字节写读闭环
    pygame.io.write("io_case.bin", payload)
    check("write+read bytes", pygame.io.read("io_case.bin") == payload)
    check("exists", pygame.io.exists("io_case.bin"))

    # ② 文本写读闭环（UTF-8 中文）
    pygame.io.write_text("io_case.txt", "你好 io 测试")
    check("write_text+read_text", pygame.io.read_text("io_case.txt") == "你好 io 测试")

    # ③ 异步通道：io_pending_append → 轮询 io_ready → io_take 恢复
    pygame.io.io_pending_append("io_case.txt")
    got = None
    for _ in range(300):
        if pygame.io.io_ready("io_case.txt"):
            got = pygame.io.io_take("io_case.txt")
            break
        await pygame.next_frame()
    check("pending→ready→take", got == "你好 io 测试".encode(),
          f"got={got!r}")

    # ④ 缺失读取 = ValueError（错误路径显式）
    try:
        pygame.io.read("__missing_case__.bin")
        check("missing read raises", False, "no exception")
    except ValueError:
        check("missing read raises", True)

    last = time.time()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        now = time.time()
        if now - last > 3.0:
            print(f"[SUMMARY] PASS={len(PASS)} FAIL={len(FAIL)} {FAIL or ''}")
            return
        with screen.render() as r:
            r.fill((24, 26, 34))
            y = 30
            for line in PASS + FAIL:
                s = font.render(line, True, (140, 220, 140) if line in PASS else (230, 120, 120))
                pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(-280, y, 0))
                pygame.gfxdraw.draw_surface(r, s)
                y += 26
            summ = font.render(f"PASS={len(PASS)} FAIL={len(FAIL)}", True, (220, 220, 140))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(-280, y + 30, 0))
            pygame.gfxdraw.draw_surface(r, summ)
        pygame.display.flip()
        await pygame.next_frame()
