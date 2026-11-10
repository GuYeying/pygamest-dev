# net_egui_chat —— egui + net 综合案例：连接 PC 回声服务器（地址候选
# 三顺位：回环/局域网/模拟器宿主），egui 输入框打字 → TCP 发送 → 回声
# 显示在消息流（IME 隐式链 + net 轮询面 + egui UI 三链同屏验证）。
# 退出：ESC / 返回键。服务端：电脑跑 examples/net_echo_server.py。
import time

import pygame
import pygame_gui as egui

HOSTS = [
    "127.0.0.1:9001",      # USB adb reverse / 本机
    "192.168.31.12:9001",  # 局域网直连（PC 网卡）
    "10.0.2.2:9001",       # Android 模拟器宿主
]


class Hud(egui.UiBase):
    def __init__(self):
        super().__init__()
        self.draft = ""
        self.log = ["[系统] 连接中…"]
        self.state = "connecting"

    def draw(self, ui):
        ui.heading("net + egui 聊天（回声服务器）")
        self.draft = ui.text_edit(self.draft)
        if ui.button("发送") and self.draft:
            self.pending_send = self.draft
            self.draft = ""
        for line in self.log[-12:]:
            ui.label(line)
        ui.label(f"连接态 = {self.state}")


async def main():
    screen = pygame.display.set_mode((800, 600))
    egui.init()
    hud = Hud()

    # 连接（三顺位候选——谁通用谁）
    conn = None
    for host in HOSTS:
        try:
            c = pygame.net.TCP(host)
        except Exception:
            continue
        t0 = time.time()
        while time.time() - t0 < 5.0:
            if c.state() == "connected":
                break
            await pygame.next_frame()
        if c.state() == "connected":
            conn = c
            hud.log.append(f"[系统] 已连接 {host}")
            hud.state = "connected"
            break
        c.close()
    if conn is None:
        hud.state = "closed"
        hud.log.append("[系统] 三候选均未连上——检查 PC 端 net_echo_server.py")

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
            egui.event(e)

        # 发送（按钮置位 → TCP 帧）
        if getattr(hud, "pending_send", None):
            msg = hud.pending_send
            hud.pending_send = None
            conn.send(msg)
            hud.log.append(f"我: {msg}")

        # 接收（轮询面——每帧查收）
        got = conn.recv() if hud.state == "connected" else None
        while got is not None:
            hud.log.append(f"回声: {got.decode('utf-8', 'replace')}")
            got = conn.recv()

        with screen.render() as r:
            r.fill((24, 26, 34))
            r.draw_ui(hud)

        pygame.display.flip()
        await pygame.next_frame()
