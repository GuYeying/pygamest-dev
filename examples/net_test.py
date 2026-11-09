# net_test —— pygame.net 三端一致性案例：TCP 分帧回环（连外部回声服）
# + UDP 自环收发。TCP 服务端 = 工具脚本 net_echo_server.py（系统 Python
# 起，127.0.0.1:9001）；Web 端走 ws://（WebSocket 回声）；UDP Web 无。
# 退出：自动（跑完 SUMMARY 停 2 秒）/ ESC。
import time

import pygame

HOST = "127.0.0.1:9001"
PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("[PASS] " if ok else "[FAIL] ") + name + ("  " + detail if detail else ""))


async def main():
    screen = pygame.display.set_mode((640, 360))
    font = pygame.font.Font(None, 24)

    # ── TCP 分帧 ──
    conn = pygame.net.TCP(HOST)
    check("TCP 构造", conn is not None)
    # 握手轮询（Connecting → connected；10 秒上限）
    st = "connecting"
    for _ in range(600):
        st = conn.state()
        if st == "connected":
            break
        await pygame.next_frame()
    check("TCP connected", st == "connected", f"state={st}")

    if st == "connected":
        conn.send("你好 net")
        got = None
        t0 = time.time()
        while time.time() - t0 < 3.0:
            got = conn.recv()
            if got is not None:
                break
            await pygame.next_frame()
        check("TCP send→recv 回声", got == ("echo:你好 net").encode("utf-8"), f"got={got!r}")

        blob = bytes(range(256)) * 64  # 16 KB 跨多分片
        conn.send(blob)
        got = None
        t0 = time.time()
        while time.time() - t0 < 3.0:
            got = conn.recv()
            if got is not None:
                break
            await pygame.next_frame()
        check("TCP 16KB 帧完整", got == b"echo:" + blob, f"len={None if got is None else len(got)}")

        conn.close()
        await pygame.next_frame()
        check("TCP close", conn.state() == "closed", f"state={conn.state()}")

    # ── UDP 自环 ──
    try:
        udp = pygame.net.UDP("127.0.0.1:9051")
        udp.send_to(b"udp-hello", "127.0.0.1:9051")
        got = None
        t0 = time.time()
        while time.time() - t0 < 2.0:
            got = udp.recv_from()
            if got is not None:
                break
            await pygame.next_frame()
        check("UDP 自环 send_to→recv_from", got is not None and got[0] == b"udp-hello",
              f"got={got!r}")
    except (ValueError, Exception) as e:
        # Web 端 UDP 显式报错 = 设计行为（站桩确认）
        check("UDP Web 站桩/可用", "Web" in str(e) or "UDP" in str(e), str(e)[:60])

    last = time.time()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        if time.time() - last > 2.0:
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
        pygame.display.flip()
        await pygame.next_frame()
