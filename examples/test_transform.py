# test_transform：矩阵变换验证（中心锚定后）——旋转/缩放/镜像三联 + 矩阵打印
# 验收点：
#   ① 旋转围绕物体中心（不飘）
#   ② x 镜像（scale(-1,1,1)）→ 左右翻转可见
#   ③ y 镜像（scale(1,-1,1)）→ 上下翻转可见
#   ④ 动态缩放 sin() 过零时 x 翻转可见
import pygame


def sin(x: float, eps: float = 1e-10) -> float:
    pi = 3.1415926535
    x = x % (2 * pi)
    if x > pi:
        x -= 2 * pi
    res = 0.0
    term = x
    n = 0
    while abs(term) > eps:
        res += term
        n += 1
        term *= (-1) * x * x / ((2 * n) * (2 * n + 1))
    return res


def mat_str(m):
    """Mat4 → 可读四行字符串（列主序 to_cols_array）"""
    c = m.to_cols_array()
    return (f"[{c[0]:7.3f} {c[4]:7.3f} {c[8]:7.3f} {c[12]:7.3f}]\n"
            f"[{c[1]:7.3f} {c[5]:7.3f} {c[9]:7.3f} {c[13]:7.3f}]\n"
            f"[{c[2]:7.3f} {c[6]:7.3f} {c[10]:7.3f} {c[14]:7.3f}]\n"
            f"[{c[3]:7.3f} {c[7]:7.3f} {c[11]:7.3f} {c[15]:7.3f}]")


async def main():
    screen = pygame.display.set_mode((800, 600))
    M = pygame.math

    # 源面：非对称图案（红圆在左→镜像可辨；黄线对角→旋转可辨）
    art = pygame.Surface((160, 120))
    with art.render() as t:
        t.fill((125, 125, 125))
        pygame.gfxdraw.rectangle(t, (-72, -52, 144, 104), (80, 200, 90))
        pygame.gfxdraw.filled_circle(t, -40, 0, 24, (230, 70, 70))
        pygame.gfxdraw.line(t, -70, 50, 70, -50, (240, 200, 80))
        pygame.gfxdraw.line(t, -70, -50, 70, 50, (240, 240, 240))

    frame = 0
    logged = False

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        ang = 90 * sin(frame * 0.02)
        s = sin(frame * 0.01)

        # ── 矩阵构造（中心锚：物体中心 = 局部原点）──
        # 旋转：T(pos) * R(angle) —— 先围绕原点旋转，再平移到位置
        #   中心锚后 quad 角 (-hw,-hh)..(hw,hh) 围绕 (0,0) 转 → 围绕物体中心
        m_rot = M.mat4_translation(-200, 150, 0).mul_mat4(
            M.mat4_from_quat(M.quat_from_axis_angle(0, 0, 1, ang)))

        # x 镜像：scale(-1, 1, 1) —— 围绕中心左右翻转
        m_mirror_x = M.mat4_translation(0, 150, 0).mul_mat4(
            M.mat4_scale(-1, 1, 1))

        # y 镜像：scale(1, -1, 1) —— 围绕中心上下翻转
        m_mirror_y = M.mat4_translation(200, 150, 0).mul_mat4(
            M.mat4_scale(1, -1, 1))

        # 动态缩放 x（sin 过零翻转——只在 x 轴）
        m_scale_x = M.mat4_translation(0, -100, 0).mul_mat4(
            M.mat4_scale(s, 1, 1))

        # 打印帧 0 的矩阵（诊断）
        if not logged and (frame == 0 or frame == 50):
            print("[test_tf] === m_rot (T(-200,150) * R(0°)) ===")
            print(mat_str(m_rot))
            print("[test_tf] === m_mirror_x (T(0,150) * S(-1,1,1)) ===")
            print(mat_str(m_mirror_x))
            print("[test_tf] === m_scale_x (T(0,-100) * S(sin(0),1,1)) ===")
            print(mat_str(m_scale_x))
            print(f"[test_tf] sin(0) = {sin(0)}, frame = {frame}")
            if frame >= 50: logged = True

        # ── 渲染 ──
        with screen.render() as t:
            t.fill((20, 20, 30))

            # 旋转（围绕中心）
            pygame.gfxdraw.set_transform(t, m_rot)
            pygame.gfxdraw.draw_surface(t, art)

            # x 镜像（静止，永远翻转）
            pygame.gfxdraw.set_transform(t, m_mirror_x)
            pygame.gfxdraw.draw_surface(t, art)

            # y 镜像（静止，永远翻转）
            pygame.gfxdraw.set_transform(t, m_mirror_y)
            pygame.gfxdraw.draw_surface(t, art)

            # 动态 x 缩放（sin 过零 → x 翻转）
            pygame.gfxdraw.set_transform(t, m_scale_x)
            pygame.gfxdraw.draw_surface(t, art)

            # 标签
            font = pygame.font.Font(None, 20)
            lbl_rot = font.render("rot(T*R)", True, (255, 200, 0))
            lbl_mx = font.render("mirror_x S(-1,1)", True, (255, 100, 100))
            lbl_my = font.render("mirror_y S(1,-1)", True, (100, 200, 255))
            lbl_sx = font.render(f"scale_x sin={s:.2f}", True, (200, 200, 200))

            pygame.gfxdraw.set_transform(t, M.mat4_translation(-200, 220, 0))
            pygame.gfxdraw.draw_surface(t, lbl_rot)
            pygame.gfxdraw.set_transform(t, M.mat4_translation(0, 220, 0))
            pygame.gfxdraw.draw_surface(t, lbl_mx)
            pygame.gfxdraw.set_transform(t, M.mat4_translation(200, 220, 0))
            pygame.gfxdraw.draw_surface(t, lbl_my)
            pygame.gfxdraw.set_transform(t, M.mat4_translation(0, -170, 0))
            pygame.gfxdraw.draw_surface(t, lbl_sx)

        frame += 1
        pygame.display.flip()
        await pygame.next_frame()
