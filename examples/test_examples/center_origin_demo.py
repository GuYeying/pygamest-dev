# 中心原点验证 demo（2D + 3D 同屏对照）：
#   ① 2D Auto 兜底：过原点十字轴 + 四象限圆 + 原点白圆——(0,0) 应在屏幕正中
#   ② 2D y 向上：+Y 象限圆在屏幕上半（黄/绿），-Y 在下半（红/蓝）
#   ③ 3D 透视：世界 (0,0,-3) 文字牌投到屏幕正中心；(+1,+0.75,-3) 牌在右上
#      ——3D 原点与 2D 原点同一点（屏幕中心）
# 退出：ESC / 关窗
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))
    screen.set_camera(pygame.render.game_camera_ortho(800, 600, 800, 600))
    font = pygame.font.Font(None, 24)

    quad2d = font.render("2D origin (0,0) = screen center", True, (255, 220, 120))
    quad3d = font.render("3D (0,0,-3) = screen center", True, (120, 255, 160))
    quad3d_off = font.render("3D (+1,+0.75) = upper-right", True, (150, 200, 255))
    quad3d_center = font.render("<-- 3D origin", True, (255, 255, 255))
    aspect = 800 / 600

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        # ── ① 2D：Auto 兜底（中心原点正交，y 向上）──
        with screen.render() as f:
            f.fill((14, 14, 22))
            # 坐标轴（横纵过原点）
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_line(-400, 0, 400, 0), color=(80, 80, 100))
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_line(0, -300, 0, 300))
            # 四象限圆（y 向上：+y 在屏幕上半）
            pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(-200, 150, 0))
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_circle(26), color=(255, 200, 0))
            pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(200, 150, 0))
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_circle(26), color=(120, 255, 160))
            pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(-200, -150, 0))
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_circle(26), color=(255, 120, 120))
            pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(200, -150, 0))
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_circle(26), color=(120, 160, 255))
            # 原点白圆
            pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(0, 0, 0))
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_circle(18), color=(255, 255, 255))
            # 文字标注（中心系摆放）
            pygame.gfxdraw.set_transform(
                f, pygame.math.mat4_translation(-390, 260, 0))
            pygame.gfxdraw.draw_surface(f, quad2d)
            pygame.gfxdraw.set_transform(
                f, pygame.math.mat4_translation(-390, -274, 0))
            pygame.gfxdraw.draw_surface(f, quad3d)

        # ── ② 3D：透视相机（世界原点 = 屏幕中心）──
        with screen.render_depth() as f:
            pygame.gfxdraw.set_camera(f, pygame.render.game_camera_perspective(60.0, 800, 600, 800, 600, 0.1, 100.0))
            # 原点牌：文字中心对世界原点（z=-3 前方；透视投影 (0,0) → 屏幕中心）
            # 可见高 @z=3 ≈ 3.46 世界单位 → 文字 320px 宽 × k=0.0045 ≈ 1.44 单位（约屏宽 36%）
            k = 0.0045
            pygame.gfxdraw.set_transform(f,
                pygame.math.mat4_translation(0, 0, -3)
                .mul_mat4(pygame.math.mat4_scale(k, k, 1)))
            pygame.gfxdraw.draw_surface(f, quad3d)
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_circle(6), color=(255, 255, 255))
            # 右上偏移牌：+x 右、+y 上（y 向上方向验证）
            pygame.gfxdraw.set_transform(f,
                pygame.math.mat4_translation(1.0, 0.75, -3)
                .mul_mat4(pygame.math.mat4_scale(k, k, 1)))
            pygame.gfxdraw.draw_surface(f, quad3d_off)
            # 3D 原点标记：上方文字牌中心即世界原点（透视投影 (0,0) →
            # 屏幕中心）。⚠️ gfxdraw 图元半径 = i32 整数世界单位——透视
            # 空间做不了"小物体"（1 单位半径在近处即盖满屏——本 demo
            # 初版纯白屏根因）；3D 小物体用 draw_surface（quad 可任意缩放）

        pygame.display.flip()
        await pygame.tasks.yield_now()
