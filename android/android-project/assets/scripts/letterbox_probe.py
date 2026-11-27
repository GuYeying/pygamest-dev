import pygame

# 窗口化 letterbox 校准探针（无 FULLSCREEN 旗标）：画布 1024×768，
# 引擎等比缩放居中映射到原生窗口——蓝底 = 逻辑画布实际落位（黑边宽
# 度一目了然），黄描边 + 四角白点验证锚点，红圈 = 触摸映射落点。
# 若蓝区铺满无黑边 = 物理窗口恰好同比例；若对称黑边 = letterbox 正确；
# 若偏移/溢出 = 映射残差（对照 dev_log [present] 行定位）。


async def main():
    w, h = 1024, 768
    screen = pygame.display.set_mode((w, h))
    print(f"[probe] set_mode = ({w}, {h}) 窗口化；get_size = {screen.get_size()}")
    # 像素域：显式声明正交相机（不设 = 裸 NDC 直通）
    screen.set_camera(pygame.render.game_camera_ortho(w, h, w, h))
    # 几何预生成一次（VertexBuf 复用——逐帧只提交）
    canvas_outline = pygame.gfxdraw.gen_rect_outline(w, h)
    corner_dot = pygame.gfxdraw.gen_circle(8)
    touch_dot = pygame.gfxdraw.gen_circle(20)
    frame = 0
    pos = None
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.MOUSEMOTION:
                pos = (e.x, e.y)
        with screen.render() as r:
            r.fill((0, 0, 255))
            # 画布边缘描边（gfxdraw 恒 1px——几何生成器中心锚，原点即画布中心）
            pygame.gfxdraw.draw_batch(r, canvas_outline, color=(255, 255, 0, 255))
            for cx, cy in ((-w // 2 + 8, -h // 2 + 8), (w // 2 - 8, -h // 2 + 8),
                           (-w // 2 + 8, h // 2 - 8), (w // 2 - 8, h // 2 - 8)):
                pygame.gfxdraw.draw_batch(
                    r, corner_dot, color=(255, 255, 255, 255),
                    transform=pygame.math.mat4_translation(cx, cy, 0))
            if pos:
                pygame.gfxdraw.draw_batch(
                    r, touch_dot, color=(255, 0, 0, 255),
                    transform=pygame.math.mat4_translation(pos[0], pos[1], 0))
        pygame.display.flip()
        frame += 1
        if frame == 1 or frame % 120 == 0:
            print(f"[probe] frame {frame}: surface = {screen.get_size()}")
        await pygame.tasks.yield_now()
