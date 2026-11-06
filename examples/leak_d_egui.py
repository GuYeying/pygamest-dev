# leak_d —— 隔离 D：仅 egui HUD 每帧（无 compute/无文本渲染）
import pygame
import pygame_gui as egui


class HUD(egui.UiBase):
    def __init__(self):
        self.n = 2048
        self.fps = 60.0

    def draw(self, ui):
        ui.heading("diag hud")
        ui.checkbox("tier", False)
        ui.separator()
        ui.label(f"n {self.n}")
        ui.label(f"fps {self.fps:.1f}")


async def main():
    screen = pygame.display.set_mode((400, 300))
    egui.init()
    hud = HUD()
    frame = 0
    while frame < 9000:
        for e in pygame.event.get():
            egui.event(e)
            if e.type == pygame.event.QUIT:
                return
        with screen.render() as t:
            t.fill((6, 8, 14))
            t.draw_ui(hud)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
