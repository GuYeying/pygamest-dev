# image_test —— pygame.image 模块专项案例：load / load_from_bytes /
# get_size / transform.scale / flip_x / flip_y / rotate（纹理化上屏对照）。
# 依赖资产：cloth.png（examples 根）。退出：ESC / 关窗。
import pygame

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("[PASS] " if ok else "[FAIL] ") + name + ("  " + detail if detail else ""))


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 20)

    # ── load（文件路径——异步加载 shim，须 await）──
    img = await pygame.image.load("cloth.png")
    check("load cloth.png", img is not None, f"size={img.get_size()}")

    # ── load_from_bytes（字节入参——io 通道同构）──
    try:
        raw = pygame.io.read("cloth.png")
        img2 = pygame.image.load_from_bytes(raw)
        check("load_from_bytes", img2 is not None
              and img2.get_size() == img.get_size())
    except Exception as e:
        check("load_from_bytes", False, str(e)[:50])

    # ── transform 家族（scale/flip/rotate）──
    small = pygame.transform.scale(img, (120, 90))
    check("transform.scale", small.get_size() == (120, 90))
    flipped = pygame.transform.flip_x(img)
    check("flip_x", flipped.get_size() == img.get_size())
    rotated = pygame.transform.rotate(img, 30.0)
    check("rotate 30°（尺寸放大）", rotated.get_size()[0] >= img.get_size()[0])

    # ── 渲染：原图 / 缩放 / 翻转 / 旋转 四联上屏 ──
    frame = 0
    angle = 0.0
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        angle += 0.5
        rot_now = pygame.transform.rotate(img, angle)
        rot_m = pygame.math.mat4_from_quat(
            pygame.math.quat_from_axis_angle(0.0, 0.0, 1.0, angle))
        with screen.render() as rt:
            rt.fill((16, 18, 26))
            pygame.gfxdraw.set_transform(rt, pygame.math.mat4_translation(-360, 240, 0))
            pygame.gfxdraw.draw_surface(rt, img)
            pygame.gfxdraw.set_transform(rt, pygame.math.mat4_translation(-120, 240, 0))
            pygame.gfxdraw.draw_surface(rt, small)
            pygame.gfxdraw.set_transform(rt, pygame.math.mat4_translation(60, 240, 0))
            pygame.gfxdraw.draw_surface(rt, flipped)
            pygame.gfxdraw.set_transform(
                rt, pygame.math.mat4_translation(240, 180, 0) @
                pygame.math.mat4_scale(0.35, 0.35, 0.35) @ rot_m)
            pygame.gfxdraw.draw_surface(rt, rot_now)

            yy = -240
            for line in PASS + FAIL:
                s = font.render(line, True,
                                (140, 220, 140) if line in PASS else (230, 120, 120))
                pygame.gfxdraw.set_transform(rt, pygame.math.mat4_translation(-380, yy, 0))
                pygame.gfxdraw.draw_surface(rt, s)
                yy -= 22

        pygame.display.flip()
        frame += 1
        if frame == 30:
            print(f"[image-test] SUMMARY {'PASS' if not FAIL else 'FAIL ' + str(FAIL)} "
                  f"({len(PASS)} 项)")
        if frame > 60:
            return
        pygame.time.delay(8)
        await pygame.next_frame()
