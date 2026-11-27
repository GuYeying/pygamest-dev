# 渲染统一 draw 面验收 demo（per-draw 相机/变换 + 中心原点坐标系）
#
# 验收点（对应 starfish/docs/渲染统一draw面设计.md）：
#   ① Auto2d 兜底：中心原点 2D 图元（不 set_camera——(0,0) 屏幕中心）
#   ② 会话级正交相机：显式 set_camera 后 2D 图元分段绘制
#   ③ 会话级透视相机：3D 空间放置（图片 quad 绕 y 旋转 + 文字牌 id）
#   ④ 同画布多相机：①②③ 同一 render 会话共存（段级相机切换）
# 退出：ESC / 关窗
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 26)
    title = font.render("render unify: ortho + perspective + 3D label (center origin)", True, (255, 220, 120))
    label = font.render("ID: player_1", True, (120, 255, 160))

    img = None
    try:
        img = await pygame.image.load("assets/ferris.png")
    except Exception as e:
        print("[unify-demo] 贴图缺资源（占位图顶上）:", e)

    ang = 0.0
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        ang += 0.6

        with screen.render_depth() as f:
            # ① Auto2d 兜底：中心原点 2D 图元——(0,0) = 屏幕中心，
            #    (-250, 150) = 中心左侧偏上（y 向上）
            pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(-250, 150, 0))
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_circle(36), color=(255, 200, 0))
            pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(-270, -20, 0))
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_rect(120, 80), color=(90, 120, 220))

            # ② 会话级正交相机（显式）——右侧 2D 圆（同画布分段）
            pygame.gfxdraw.set_camera(f, pygame.render.game_camera_ortho(800, 600, 800, 600))
            pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(250, 150, 0))
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_circle(30), color=(120, 255, 120))
            pygame.gfxdraw.clear_camera(f)

            # ③ 会话级透视相机：3D 空间放置
            pygame.gfxdraw.set_camera(f, pygame.render.game_camera_perspective(60.0, 800, 600, 800, 600, 0.1, 100.0))

            # 3a. 贴图 quad 绕 y 轴旋转（billboard 手动可算的历史考量
            #     已剔除——这里直接给世界模型矩阵）
            rot = pygame.math.quat_from_axis_angle(0.0, 1.0, 0.0, ang)
            world = (
                pygame.math.mat4_translation(-80, 0, -160)
                @ pygame.math.mat4_from_quat(rot)
                @ pygame.math.mat4_scale(60, 60, 60)
            )
            pygame.gfxdraw.set_transform(f, world)
            if img is not None:
                pygame.gfxdraw.draw_surface(f, img)
            else:
                pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_box(
                    [-30, -30, -30], [30, 30, 30]))

            # 3b. 3D 文字牌（游戏内 id）：文字表面 quad 放进世界
            #     （billboard 手动 = 让牌面朝相机——本 demo 相机固定
            #     看 -Z，恒等姿态即可）
            pygame.gfxdraw.set_transform(f, pygame.math.mat4_translation(60, 40, -160))
            pygame.gfxdraw.draw_surface(f, label)

            # ④ 回 Auto：中心系十字准星（验证 clear_camera 清除）
            pygame.gfxdraw.clear_camera(f)
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_line(-16, 0, 16, 0), color=(255, 255, 255))
            pygame.gfxdraw.draw_batch(f, pygame.gfxdraw.gen_line(0, -12, 0, 12))

        # HUD（叠加在 3D 内容之上——Auto 兜底段）
        with screen.render() as f:
            pygame.gfxdraw.draw_surface(f, title, transform=pygame.math.mat4_translation(0, -270))

        pygame.display.flip()
        await pygame.tasks.yield_now()
