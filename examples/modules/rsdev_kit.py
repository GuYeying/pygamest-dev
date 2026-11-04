# rsdev_kit —— 相机/矩阵封装（开发者模板随包）。
#
# 收拢引擎高级渲染接口（camera_perspective / draw_surface）的必备调用，
# 收敛成**画布域友好形态**。
#
# 核心定约（渲染统一 draw 面）：相机选择是**会话级**——`cam.use(t)`
# 转发 `t.set_camera(...)`（每会话/每目标独立持有，互不串线）；变换走
# `t.set_transform(...)`（CPU 烘顶点）；坐标系 = **中心原点、y 向上**
# （2D 正交/3D 透视/物理米制三方同构）。letterbox 呈现由引擎统一施加。
import pygame


class Camera2D:
    """2D 正交相机（**中心原点**：(0,0) 屏幕中心 → (±w/2, ±h/2)，y 向上）"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cam = pygame.render.camera_ortho(float(w), float(h))

    def use(self, t):
        """会话相机切换（t = render 会话对象；仅本会话生效）"""
        t.set_camera(self.cam)


class Camera3D:
    """3D 透视相机（y 向上右手系，看向 -Z；纵横比恒取画布——三端同源）"""

    def __init__(self, w, h, fov=45.0, near=0.1, far=100.0):
        self.cam = pygame.render.camera_perspective(
            fov, float(w) / float(h), near, far)

    def use(self, t):
        t.set_camera(self.cam)


def use_2d(t, w, h):
    """回 2D 正交（3D 会话后的标准回切）"""
    Camera2D(w, h).use(t)


def fit():
    """呈现拟合矩阵（NDC 域）——**自管相机（write_buffer 直写矩阵的
    自绘管线）专用**：引擎无法拦截组合 letterbox，自绘内容左乘本矩阵
    即与主绘制同一映射。桌面/全屏恒等，Android 窗口化收进居中画布。
    帧内快照语义（每帧重取）"""
    return pygame.render.present_fit()


# ── 矩阵链（set_transform 的变换参数；可读名替代手写 .mul_mat4 链）──

def pos(x, y, z=0.0):
    """平移"""
    return pygame.math.mat4_translation(x, y, z)


def rot_z(deg):
    """绕 Z 轴旋转（度数制；2D 卡片旋转用）"""
    return pygame.math.mat4_from_quat(
        pygame.math.quat_from_axis_angle(0, 0, 1, deg))


def scale(s, sy=None, sz=1.0):
    """缩放（单参 = 等比；sy=None 时取 s）"""
    if sy is None:
        sy = s
    return pygame.math.mat4_scale(s, sy, sz)


def chain(*mats):
    """依序复合（与 .mul_mat4 链同序：chain(T, R) = demo 的 T.mul_mat4(R)
    ——先传者在外层，顶点先经后传者变换）"""
    m = mats[0]
    for n in mats[1:]:
        m = m.mul_mat4(n)
    return m
