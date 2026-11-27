# 状态参数化验证（2026-11-27）——blend/cull 从全局改为逐绘制参数
# ① 五种 blend 像素真值（BMP 取证，配合 STARFISH_FB_BMP）
# ② wireframe 不跨调用残留（draw_batch 线框后 draw_surface 必须仍是实心）
# ③ cull=back 的 3D 形状（离屏深度面，不崩）
# ④ 旧 set_blend_mode / set_cull_mode 明确抛 RuntimeError
# 退出：40 帧后自动返回
import pygame

M = pygame.math


async def main():
    pygame.render.set_fb_dump(True)
    fails = []

    def st(name, cond, detail=""):
        print(("[state-test] PASS " if cond else "[state-test] FAIL ") + name,
              detail, flush=True)
        if not cond:
            fails.append(name)

    # ── ④ 旧口：必须明确报错，而不是静默无效 ──
    try:
        pygame.render.set_blend_mode("opaque")
        st("set_blend_mode 已移除（抛 RuntimeError）", False)
    except RuntimeError as e:
        st("set_blend_mode 已移除（抛 RuntimeError）", True)
    try:
        pygame.render.set_cull_mode("back")
        st("set_cull_mode 已移除（抛 RuntimeError）", False)
    except RuntimeError:
        st("set_cull_mode 已移除（抛 RuntimeError）", True)

    # GPU 槽必须先建立（离屏 Surface 的渲染会话同样依赖）
    screen = pygame.display.set_mode((800, 600))
    screen.set_camera(pygame.render.game_camera_ortho(800, 600, 800, 600))

    # ── 参数校验面 ──
    buf = pygame.gfxdraw.gen_rect(100, 80)
    try:
        with pygame.Surface((200, 200)).render() as t:
            pygame.gfxdraw.draw_batch(t, buf, blend="bogus")
        st("非法 blend 抛 ValueError", False)
    except ValueError:
        st("非法 blend 抛 ValueError", True)
    try:
        with pygame.Surface((200, 200)).render() as t:
            pygame.gfxdraw.draw_batch(t, buf, cull="front")
        st("cull=front 拒绝（只允 none/back）", False)
    except ValueError:
        st("cull=front 拒绝（只允 none/back）", True)

    # ── ③ 3D：gen_* + draw_batch(cull=back)，主屏深度会话（一次性，随后 2D 覆盖）──
    cam = pygame.render.game_camera_perspective(
        50.0, 800, 600, 800, 600, 0.1, 100.0)
    cam = cam.with_view(M.mat4_translation(0.0, 0.0, -5.0))
    try:
        with screen.render_depth() as t:
            t.fill((0, 0, 0))
            pygame.gfxdraw.set_camera(t, cam)
            pygame.gfxdraw.draw_batch(
                t, pygame.gfxdraw.gen_sphere(1.2),
                cull="back", color=(200, 200, 200))
            pygame.gfxdraw.draw_batch(
                t, pygame.gfxdraw.gen_cube(1.5),
                transform=M.mat4_translation(2.2, 0.0, 0.0),
                cull="back", color=(200, 120, 60))
            pygame.gfxdraw.clear_camera(t)
        st("3D gen_* + cull=back 无异常", True)
    except Exception as e:  # noqa: BLE001
        st("3D gen_* + cull=back 无异常", False, repr(e))
    screen.set_camera(pygame.render.game_camera_ortho(800, 600, 800, 600))

    # ── ① / ② 主屏像素真值 ──
    green = pygame.Surface((120, 120))
    green.fill((0, 255, 0))
    modes = ["alpha", "noblend", "additive", "multiply", "premultiplied"]
    xs = [-300, -150, 0, 150, 300]
    frame = 0
    while True:
        with screen.render() as rt:
            rt.fill((40, 40, 40))
            # 五种 blend 各一块（100×80，中心 y=120）
            for x, mode in zip(xs, modes):
                color = (200, 0, 0, 100) if mode == "premultiplied" else (255, 0, 0, 128)
                pygame.gfxdraw.draw_batch(
                    rt, buf, transform=M.mat4_translation(float(x), 120.0, 0.0),
                    color=color, blend=mode)
            # ② 线框残留探针：先线框画一遍，再画实心面
            pygame.gfxdraw.draw_batch(
                rt, pygame.gfxdraw.gen_rect(120, 120),
                transform=M.mat4_translation(0.0, -120.0, 0.0), wireframe=True)
            pygame.gfxdraw.draw_surface(
                rt, green, dst_rect=[-60.0, -180.0, 120.0, 120.0])
        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1
        if frame > 40:
            break

    for f in fails:
        print("[state-test] 失败项:", f, flush=True)
    print("[state-test] done fail_count=%d" % len(fails), flush=True)
