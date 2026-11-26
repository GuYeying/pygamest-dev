# 区域后渲染取证探针——with horizontal 之后的控件是否上屏
# （STARFISH_FB_BMP 由 shell 侧注入；FB dump 由 set_fb_dump 开启）
import pygame
import pygame_gui as egui

pygame.render.set_fb_dump(True)


class P(egui.UiBase):
    def draw(self, ui):
        ui.label("TOP-MARKER")
        with ui.horizontal():
            ui.label("MID-A")
            ui.button("MID-B")
        ui.label("BOTTOM-MARKER")
        ui.heading("HEAD-MARKER")


async def main():
    screen = pygame.display.set_mode((400, 300), gui=True)
    frame = 0
    while frame < 180:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            egui.event(e)
        with screen.render() as t:
            t.draw_ui(P())
        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1
    print("[diag-region] done")
