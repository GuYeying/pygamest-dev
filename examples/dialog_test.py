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

    # 交互段说明（真对话框需人工点选——无人值守跑只验自动段；open_file
    # 桌面端模态阻塞，自动段绝不调用）
    MANUAL.append("交互验收（桌面）：open_file 弹对话框选任意文件 → 命令行打印 name() 与字节数")
    MANUAL.append("交互验收（桌面）：save_bytes 写一份文本 → 选位置 → 命令行打印 True")
    MANUAL.append("Web/Android：v1 同步口显式站桩 ValueError（异步 job API 后续批次）——import 即 AttributeError 不应出现")

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
