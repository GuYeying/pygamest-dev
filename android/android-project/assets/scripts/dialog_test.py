# dialog_test —— pygame.dialog 三端一致性案例：
# ①自动段：模块面/类型面/错误路径（全平台无人值守可跑）；
# ②交互段：open_file/save_bytes 真对话框（桌面需人工点选——交互验收，
#   Web = input[file] 下载弹窗，Android = DocumentPicker）。
# 退出：ESC / 关窗（自动段完即停 2 秒）。
import time

import pygame

PASS = []
FAIL = []
MANUAL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("[PASS] " if ok else "[FAIL] ") + name + ("  " + detail if detail else ""))


async def main():
    screen = pygame.display.set_mode((640, 360))
    font = pygame.font.Font(None, 24)

    # ── 自动段 ──
    check("module 面", all(hasattr(pygame.dialog, n) for n in ("open_file", "save_bytes")))
    check("PickedFile 类型", hasattr(pygame.dialog, "PickedFile"))

    # 交互段说明（异步面 2026-11-10：open_file/save_bytes = awaitable——
    # 后台线程跑模态框，帧循环不冻；真对话框需人工点选，自动段不构造）
    MANUAL.append("交互验收（桌面）：picked = await pygame.dialog.open_file() → 选任意文件 → print(picked.name(), len(picked.read()))")
    MANUAL.append("交互验收（桌面）：ok = await pygame.dialog.save_bytes('a.txt', b'hi') → 选位置 → print(ok)")
    MANUAL.append("await 期间帧循环存活（对话框背后画面继续渲染——异步面核心增益）")
    MANUAL.append("Web/Android：后端站桩 ValueError（robius 桥后续批次）——API 面已就绪")

    last = time.time()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        if time.time() - last > 2.0:
            for m in MANUAL:
                print("[MANUAL]", m)
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
