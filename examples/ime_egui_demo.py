# ime_egui_demo —— Android IME + egui 输入框端到端验证（常驻不退）：
# egui text_edit + 原始 textinput 事件双通道回显。点按屏幕任意处呼出
# 软键盘，点 egui 输入框聚焦后打字——文字落框 + 原始事件计数同步增长
# = 双通道实证。退出：返回键。
import pygame
import pygame_gui as egui


class Hud:
    def __init__(self):
        self.name = "点我打字"
        self.raw_n = 0
        self.last_raw = "-"

    def draw(self, ui):
        ui.heading("IME + egui 输入框验证")
        self.name = ui.text_edit(self.name)
        ui.label(f"输入框内容 = {self.name}")
        ui.label(f"原始 textinput 事件 n={self.raw_n} last={self.last_raw}")
        ui.label("点按屏幕呼出键盘；返回键收起/退出")


async def main():
    screen = pygame.display.set_mode((1080, 600))
    hud = Hud()
    gui = egui.Gui(screen)

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
            if e.type == "textinput":
                hud.raw_n += 1
                hud.last_raw = e.text
            gui.event(e)

        with screen.render() as r:
            r.fill((24, 26, 34))
            gui.draw_ui(r)

        pygame.display.flip()
        await pygame.next_frame()
