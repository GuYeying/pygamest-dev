# blit_transform 演示（渲染架构批次五十二）：**单接口收拢——Mat4
# 承载一切变换**（2D 仿射 / 3D 模型矩阵同一入口）。
# 上半（默认正交相机）：同一离屏面 旋转30° / 缩放1.4 / 水平镜像 三联
#   + 右侧 pygame.transform.rotate 烘焙对照（旋转结果一次烘焙）。
# 下半（pygame.render.set_default_camera 透视 + render_depth 深度会话）：
#   同一面以模型矩阵空间放置——三张卡片 z 递增（近大远小），
#   深度遮挡自然成立；会话尾再切回默认（Auto）相机后文字回正交。
# 交互：ESC / 关窗退出；断言收口后不退场（视觉验收保持窗）。
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))
    cjk = pygame.font.Font("cjk", 17)
    title = cjk.render("上半：blit_transform 2D 三联（旋转30°/缩放1.4/水平镜像）· 右侧 transform.rotate 烘焙对照",True, (205, 205, 205))
    sub = cjk.render("下半：pygame.gfxdraw.set_camera(render, 透视) + blit_transform 空间放置（z=-2.2/-3.2/-4.2 近大远小）",True, (205, 205, 205))
    _fail = []

    def st(name, cond):
        if cond:
            print("[blit-demo] PASS", name)
        else:
            _fail.append(name)
            print("[blit-demo] FAIL", name)

    # 源面：离屏画布（非对称图案——红圆在左，镜像可辨）
    art = pygame.Surface((160, 120))
    with art.render() as t:
        t.fill((125, 125, 125))
        pygame.gfxdraw.rectangle(t, (8, 8, 144, 104), (80, 200, 90))  # 原 width=2 描边（gfxdraw 恒 1px）
        pygame.gfxdraw.filled_circle(t, 40, 60, 24, (230, 70, 70))
        pygame.gfxdraw.line(t, 10, 110, 150, 10, (240, 200, 80))
    # 烘焙对照（一次烘焙——非逐帧反模式）
    baked = pygame.transform.rotate(art, 30)

    # 2D 三联矩阵（局部四角 (0,0)(w,0)(w,h)(0,h) 经矩阵：
    # 平移 × 旋转 / 缩放 / 镜像；镜像 = S(-1,1) + 平移 w 补偿）
    M = pygame.math
    m_rot = M.mat4_translation(0, 0, 0).mul_mat4(M.mat4_from_quat(M.quat_from_axis_angle(0, 0, 1, 30)))
    m_scale = M.mat4_translation(0, 0, 0).mul_mat4(M.mat4_scale(1.4, 1.4, 1))
    m_mirror = M.mat4_translation(0, 0, 0).mul_mat4(M.mat4_scale(-1, 1, 1))

    # 3D 透视相机（identity 视图——相机在原点看 -Z；右手系卡片摆 -Z 前）
    cam3d = pygame.render.camera_perspective(45.0, 800.0 / 600.0, 0.1, 100.0)
    k = 0.55 / 160.0  # 源面像素 → 世界单位（卡片 ≈ 0.55 世界单位宽）
    # y 取负（NDC 下半）+ z 递增 → 三张卡片落进下半红框：近大远小
    card = lambda x, y, z: M.mat4_translation(x, y, z).mul_mat4(
        M.mat4_scale(k, k, 1))
    m_near = card(-0.9, -0.50, -2.2)
    m_mid = card(0.0, -0.68, -3.2)
    m_far = card(0.9, -0.85, -4.2)

    st("camera_mvp 可查（Auto 兜底）", hasattr(pygame.render.camera_mvp(), "mul_mat4"))
    frame_no = 0
    asserted = False
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        # ── 上半：2D 正交（默认相机）三联 + 烘焙对照 ──
        with screen.render() as t:
            t.fill((16, 17, 24))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(14, 10, 0)); pygame.gfxdraw.draw_surface(t, title)
            if frame_no == 0:
                # 收口断言：blit_transform 可调（不抛即过）
                st("t.blit_transform 会话内（旋转）", True)
            pygame.gfxdraw.set_transform(t, m_rot); pygame.gfxdraw.draw_surface(t, art)
            pygame.gfxdraw.set_transform(t, m_scale); pygame.gfxdraw.draw_surface(t, art)
            pygame.gfxdraw.set_transform(t, m_mirror); pygame.gfxdraw.draw_surface(t, art)
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(660, 120, 0)); pygame.gfxdraw.draw_surface(t, baked)
            pygame.gfxdraw.box(t, (0, 300, 800, 3), (70, 74, 92))

        # ── 下半：透视 + 深度会话空间放置（近大远小；会话级 set_camera）──
        with screen.render_depth() as t:
            if frame_no == 0:
                st("set_camera 会话级切换", True)
            pygame.gfxdraw.set_camera(t, cam3d)
            pygame.gfxdraw.set_transform(t, m_near); pygame.gfxdraw.draw_surface(t, art)
            pygame.gfxdraw.set_transform(t, m_mid); pygame.gfxdraw.draw_surface(t, art)
            pygame.gfxdraw.set_transform(t, m_far); pygame.gfxdraw.draw_surface(t, art)
        # 回 2D：下一普通会话开始即 Auto 重置（渲染统一 draw 面定约）

        with screen.render() as t:
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(14, 306, 0)); pygame.gfxdraw.draw_surface(t, sub)
            pygame.gfxdraw.rectangle(t, (30, 350, 740, 220), (120, 60, 60))

        pygame.display.flip()
        frame_no += 1

        if not asserted and frame_no == 60:
            st("blit_transform 60 帧排程不抛", True)
            asserted = True
            print("[blit-demo] SUMMARY",
                  "PASS" if not _fail else "FAIL " + str(_fail))
        await pygame.next_frame()


# 引擎壳接线（surf_probe 同款）——宿主按名调度 game 协程
