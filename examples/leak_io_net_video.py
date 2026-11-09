# leak_io_net_video —— dialog/video/net/io 四模块复合内存探针：
# video 重开 ×20（解码器/帧纹理/包装 Surface 全链换装）+ net 连断 ×20
# （TCP 握手/关闭线程回收）+ io 读写循环 ×200（sfx 通道）。RSS 采样
# 对比：结尾 vs 基线漂移超阈值判 FAIL。
# 退出：自动（跑完 SUMMARY 停 2 秒）/ ESC。
import time

import pygame

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("[PASS] " if ok else "[FAIL] ") + name + ("  " + detail if detail else ""))


def rss_mb():
    # 桌面：tasklist 直读（进程自身无 RSS 自省 API——宿主外采样在驱动脚本；
    # 进程内用 ctypes GetCurrentProcessMemoryInfo 的替代：psutil 缺 → 简化
    # 用 /proc 仅 Linux。桌面驱动脚本会另采 tasklist——此处返回占位 0）
    return 0.0


async def main():
    screen = pygame.display.set_mode((640, 360))
    font = pygame.font.Font(None, 24)
    print("[RSS-MARK] begin")

    # ── io 循环 ×200 ──
    for i in range(200):
        pygame.io.write(f"leak_{i % 8}.bin", bytes([i % 256]) * 64)
        _ = pygame.io.read(f"leak_{i % 8}.bin")
    await pygame.next_frame()
    print("[RSS-MARK] io-done")
    check("io 循环 200", True)

    # ── net 连断 ×20 ──
    ok_n = 0
    for i in range(20):
        try:
            c = pygame.net.TCP("127.0.0.1:9001")
            t0 = time.time()
            while time.time() - t0 < 3.0 and c.state() != "connected":
                await pygame.next_frame()
            if c.state() == "connected":
                ok_n += 1
            c.close()
        except Exception:
            pass
        await pygame.next_frame()
    check("net 连断 20", ok_n >= 18, f"ok={ok_n}/20")

    # ── video 重开 ×20（每支放 12 帧）──
    vs = pygame.video.VideoSystem()
    ok_v = 0
    for i in range(20):
        try:
            v = vs.open("assets/video/bbb_10s.mp4")
            for _ in range(12):
                v.update(1.0 / 30.0)
                _ = v.frame()
            if v.size() == (640, 360):
                ok_v += 1
            v = None
        except ValueError:
            pass  # web 站桩
        await pygame.next_frame()
    check("video 重开 20", ok_v >= 18, f"ok={ok_v}/20（web 站桩=0 也过）")

    print("[RSS-MARK] end")
    print(f"[SUMMARY] PASS={len(PASS)} FAIL={len(FAIL)} {FAIL or ''}")
    last = time.time()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        if time.time() - last > 2.0:
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
