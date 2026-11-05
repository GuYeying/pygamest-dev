# 镜像/旋转像素级判定探针——screen_probe 回读客观验证
# ① x 镜像：scale(-1,1,1) 后红色圆应从左半移到右半
# ② y 镜像：scale(1,-1,1) 后红色圆应从下半移到上半
# ③ 旋转中心：旋转 90° 后红色圆应从左侧移到顶部（绕中心转不飘）
import pygame


async def main():
    screen = pygame.display.set_mode((400, 400))
    M = pygame.math

    # 源面：红色圆在左侧（不对称——镜像可辨）
    art = pygame.Surface((200, 200))
    with art.render() as t:
        t.fill((0, 0, 0, 0))
        pygame.gfx.draw.set_color(t,(255, 0, 0))
        pygame.gfxdraw.filled_circle(t, -50, 0, 30, (255, 0, 0))

    font = pygame.font.Font(None, 18)
    results = []

    def probe_and_report(label, transform):
        """画一帧 + 回读 7×5 网格 → 报红色像素在哪半"""
        with screen.render() as f:
            f.fill((0, 0, 20))
            pygame.gfxdraw.set_transform(f, transform)
            pygame.gfxdraw.draw_surface(f, art)
        pygame.display.flip()
        # present 后回读
        pts = pygame.render.screen_probe()
        red_left = sum(1 for x, y, r, g, b, a in pts if x < 200 and r > 180 and g < 80)
        red_right = sum(1 for x, y, r, g, b, a in pts if x >= 200 and r > 180 and g < 80)
        red_top = sum(1 for x, y, r, g, b, a in pts if y < 200 and r > 180 and g < 80)
        red_bot = sum(1 for x, y, r, g, b, a in pts if y >= 200 and r > 180 and g < 80)
        pos = f"L={red_left} R={red_right} T={red_top} B={red_bot}"
        results.append((label, pos))
        print(f"[mirror] {label}: {pos}")

    # ── 帧循环外做三次判定（每帧一个 transform，回读后下一个）──
    # ① 无变换（基线：红圆在左侧）
    probe_and_report("identity（基线：红圆应在左）", M.mat4_translation(0, 0, 0))
    await pygame.next_frame()

    # ② x 镜像
    probe_and_report("scale(-1,1)（x 镜像：红圆应到右）",
                     M.mat4_translation(0, 0, 0).mul_mat4(M.mat4_scale(-1, 1, 1)))
    await pygame.next_frame()

    # ③ y 镜像
    probe_and_report("scale(1,-1)（y 镜像：红圆仍左右不变）",
                     M.mat4_translation(0, 0, 0).mul_mat4(M.mat4_scale(1, -1, 1)))
    await pygame.next_frame()

    # ④ 旋转 90°（红圆从左→顶，绕中心）
    probe_and_report("rot 90°（红圆应到顶）",
                     M.mat4_translation(0, 0, 0).mul_mat4(
                         M.mat4_from_quat(M.quat_from_axis_angle(0, 0, 1, 90))))
    await pygame.next_frame()

    # ⑤ 旋转 180°（红圆从左→右）
    probe_and_report("rot 180°（红圆应到右）",
                     M.mat4_translation(0, 0, 0).mul_mat4(
                         M.mat4_from_quat(M.quat_from_axis_angle(0, 0, 1, 180))))
    await pygame.next_frame()

    print("\n[mirror] === 汇总 ===")
    for label, pos in results:
        print(f"  {label}: {pos}")
    print("[mirror] 完成（窗口保持——ESC 退出）")

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        await pygame.next_frame()
