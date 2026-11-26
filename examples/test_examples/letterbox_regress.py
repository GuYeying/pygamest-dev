import pygame
import pygame.event

# letterbox 桌面回归：逻辑==物理恒等映射锚点——get_size 回 set_mode 值，
# 30 帧后自退（窗口一闪即退，CI 可跑）
async def main():
    screen = pygame.display.set_mode((800, 600))
    screen.set_camera(pygame.render.game_camera_ortho(800, 600, 800, 600))
    screen.set_camera(pygame.render.game_camera_ortho(800, 600, 800, 600))
    assert screen.get_size() == (800, 600), f"get_size={screen.get_size()}"
    print("[regress] get_size 恒等 ✓", screen.get_size())
    for frame in range(30):
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        with screen.render() as r:
            r.fill((20, 120, 20))
            pygame.gfxdraw.set_color(r,(255, 255, 0))
            pygame.gfxdraw.set_topology(r, "lines")
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(200, 155, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_rect_outline(200, 150))
            pygame.gfxdraw.set_topology(r, "default")
        pygame.display.flip()
        await pygame.tasks.yield_now()
    assert screen.get_size() == (800, 600)
    print("[regress] 30 帧渲染 + 尺寸稳定 ✓")
