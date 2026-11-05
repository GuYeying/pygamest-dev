import pygame
import pygame.event
import sys

# Surface 真实处理尺寸探针（自适应满屏）：Android 壳把实测屏幕尺寸
# 附在 sys.argv 末尾（argv[-2:]），脚本据此 set_mode——画布 = 屏幕，
# 1:1 满屏零变形（"std 屏幕尺寸接口"的壳层先行形态）。桌面/web 无
# 附加参数 = 回退 1024×768。蓝底标画布边界，黄描边 + 四角白点验证
# 锚点，红圈 = 触摸映射落点。

FULLSCREEN = 2  # 1 << 1

async def main():
    req_w, req_h = 1024, 768
    if len(sys.argv) >= 3:
        req_w, req_h = int(sys.argv[-2]), int(sys.argv[-1])
    screen = pygame.display.set_mode((req_w, req_h), FULLSCREEN)
    sw, sh = screen.get_size()
    hw, hh = sw // 2, sh // 2
    print(f"[probe] 请求 = ({req_w}, {req_h})；FULLSCREEN 生效 = ({sw}, {sh})")
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
            # 中心原点：全屏 rect = 从左下角 (-hw, -hh) 开始
            pygame.gfxdraw.set_color(r, (255, 255, 0))
            pygame.gfxdraw.rectangle(r, (-hw, -hh, sw, sh))
            # 四角圆 = 四个屏幕角落（中心系）
            for cx, cy in ((-hw + 8, -hh + 8), (hw - 8, -hh + 8),
                           (-hw + 8, hh - 8), (hw - 8, hh - 8)):
                pygame.gfxdraw.set_color(r, (255, 255, 255))
                pygame.gfxdraw.filled_circle(r, cx, cy, 8)
            if pos:
                pygame.gfxdraw.set_color(r, (255, 0, 0))
                pygame.gfxdraw.filled_circle(r, pos[0], pos[1], 20)
        pygame.display.flip()
        frame += 1
        if frame == 1 or frame % 120 == 0:
            print(f"[probe] frame {frame}: surface = {screen.get_size()}")
        await pygame.next_frame()
