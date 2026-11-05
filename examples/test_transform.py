# blit_transform 演示（渲染架构批次五十二）：**单接口收拢——Mat4
# 承载一切变换**（2D 仿射 / 3D 模型矩阵同一入口）。
# 上半（默认正交相机）：同一离屏面 旋转30° / 缩放1.4 / 水平镜像 三联
#   + 右侧 pygame.transform.rotate 烘焙对照（旋转结果一次烘焙）。
# 下半（pygame.render.set_default_camera 透视 + render_depth 深度会话）：
#   同一面以模型矩阵空间放置——三张卡片 z 递增（近大远小），
#   深度遮挡自然成立；会话尾再切回默认（Auto）相机后文字回正交。
# 交互：ESC / 关窗退出；断言收口后不退场（视觉验收保持窗）。
import pygame


def sin(x: float, eps: float = 1e-10) -> float:
    """
    手搓 sin，泰勒级数逼近
    :param x: 弧度
    :param eps: 精度
    :return: sin(x)
    """
    # 先把 x 折到 [-π, π] 加速收敛

    pi = 3.1415926535
    x = x % (2 * pi)
    if x > pi:
        x -= 2 * pi

    res = 0.0
    term = x  # n=0 第一项
    n = 0

    while abs(term) > eps:
        res += term
        n += 1
        # 递推计算下一项
        term *= (-1) * x * x / ((2 * n) * (2 * n + 1))
    return res



async def main():
    screen = pygame.display.set_mode((800, 600))

    _fail = []


    # 源面：离屏画布（非对称图案——红圆在左，镜像可辨）
    art = pygame.Surface((160, 120))
    with art.render() as t:
        t.fill((125, 125, 125))
        pygame.gfxdraw.rectangle(t, (8, 8, 144, 104), (80, 200, 90))  # 原 width=2 描边（gfxdraw 恒 1px）
        pygame.gfxdraw.filled_circle(t, 40, 60, 24, (230, 70, 70))
        pygame.gfxdraw.line(t, 10, 110, 150, 10, (240, 200, 80))
    # 烘焙对照（一次烘焙——非逐帧反模式）
    baked_rotated_surface = pygame.transform.rotate(art, 30)



    # # 3D 透视相机（identity 视图——相机在原点看 -Z；右手系卡片摆 -Z 前）
    # #cam3d = pygame.render.camera_perspective(45.0, 800.0 / 600.0, 0.1, 100.0)
    # k = 0.55 / 160.0  # 源面像素 → 世界单位（卡片 ≈ 0.55 世界单位宽）
    # # y 取负（NDC 下半）+ z 递增 → 三张卡片落进下半红框：近大远小
    # card = lambda x, y, z: M.mat4_translation(x, y, z).mul_mat4(
    #     M.mat4_scale(k, k, 1))
    # m_near = card(-0.9, -0.50, -2.2)
    # m_mid = card(0.0, -0.68, -3.2)
    # m_far = card(0.9, -0.85, -4.2)
    frame = 0 
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return


        # 2D 三联矩阵（局部四角 (0,0)(w,0)(w,h)(0,h) 经矩阵：
        # 平移 × 旋转 / 缩放 / 镜像；镜像 = S(-1,1) + 平移 w 补偿）
        M = pygame.math
        #m_rot    = M.mat4_translation(100, 0, 0).mul_mat4(M.mat4_from_quat(M.quat_from_axis_angle(0, 0, 1, 90*sin(frame*0.01))))#错误的
        m_rot    = M.mat4_from_quat(M.quat_from_axis_angle(0, 0, 1, 90*sin(frame*0.01))).mul_mat4(M.mat4_translation(0, 0, 0))#正确的
        m_scale  = M.mat4_translation(-100, 0, 0).mul_mat4(M.mat4_scale(1.4, 1.4, 1))
        m_mirror = M.mat4_translation(0, 0, 0).mul_mat4(M.mat4_scale(sin(frame*0.01), sin(frame*0.01), 1))

        #print(sin(frame*0.01))
        # ── 上半：2D 正交（默认相机）三联 + 烘焙对照 ──
        with screen.render() as t:
            t.fill((0, 125, 0))
            pygame.gfxdraw.set_transform(t, m_rot); pygame.gfxdraw.draw_surface(t, art)
            pygame.gfxdraw.set_transform(t, m_scale); pygame.gfxdraw.draw_surface(t, art)
            pygame.gfxdraw.set_transform(t, m_mirror); pygame.gfxdraw.draw_surface(t, art)
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(660, 120, 0)); pygame.gfxdraw.draw_surface(t, baked_rotated_surface)
            pygame.gfxdraw.box(t, (0, 300, 800, 3), (70, 74, 92))

        frame+=1
        pygame.display.flip()
        await pygame.next_frame()


# 引擎壳接线（surf_probe 同款）——宿主按名调度 game 协程
