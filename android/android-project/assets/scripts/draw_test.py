# pygame.draw 模块专项测试（逐模块独立案例 2/N）
# 控制台 [draw-test] 逐项断言 + 全形状样张上屏（视觉验收）
# 覆盖：六形状（rect/circle/line/polygon/ellipse/arc）× 填充/描边 ×
#       颜色形态（3元/4元/kwargs）× 半透明叠加 × gfxdraw 兼容混绘
# 退出：ESC / 关窗
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 20)
    cjk = pygame.font.Font("cjk", 20)
    _fail = []

    def st(name, cond):
        if cond:
            print("[draw-test] PASS", name)
        else:
            _fail.append(name)
            print("[draw-test] FAIL", name)

    def no_raise(name, fn):
        try:
            fn()
            st(name, True)
        except Exception as e:
            st(name, False)
            print("    [draw-test] 异常:", e)

    # ── 程序化断言（帧 1；离屏 Surface 会话）──
    off = pygame.Surface((200, 120))

    def shapes_on(s):
        with s.render() as t:
            pygame.gfxdraw.box(t, (5, 5, 60, 40), (0, 200, 90))                                # 实心
            pygame.gfxdraw.rectangle(t, (5, 5, 60, 40), (255, 255, 255))  # 原 width=3 描边（gfxdraw 恒 1px）                          # 描边
            pygame.gfxdraw.filled_circle(t, 150, 30, 22, (255, 200, 0))                              # 填充圆
            pygame.gfxdraw.circle(t, 150, 30, 22, (255, 255, 255))  # 原 width=2 描边（gfxdraw 恒 1px）                         # 描边圆
            pygame.gfxdraw.line(t, 5, 80, 190, 80, (200, 60, 60))                        # 线
            pygame.gfxdraw.filled_polygon(t, [(30, 95), (90, 100), (70, 115)], (90, 120, 220))         # 填充三角
            pygame.gfxdraw.polygon(t, [(120, 95), (180, 100), (160, 115)], (255, 160, 60))  # 原 width=2 描边（gfxdraw 恒 1px）   # 描边
            pygame.gfxdraw.filled_ellipse(t, -55, -35, 40, 20, (60, 180, 120))  # 椭圆（中心 cx=45-100, cy=25-60）
            pygame.gfxdraw.arc(t, 40, -35, 40, 0.0, 3.14159, (120, 220, 255))  # 弧（椭圆弧→圆弧 v1 降级）

    no_raise("六形状全绘（离屏会话）", lambda: shapes_on(off))

    # 半透明叠加（4 元色 alpha 分量）
    def translucent(s):
        with s.render() as t:
            pygame.gfxdraw.box(t, (5, 5, 40, 40), (255, 0, 0, 90))
            pygame.gfxdraw.box(t, (25, 25, 40, 40), (0, 0, 255, 90))   # 叠加区 = 混合色
    no_raise("半透明叠加", lambda: translucent(off))

    # gfxdraw 兼容签名面（与 r.* 同一 batch 零额外成本）
    def gfx(s):
        with s.render() as t:
            pygame.gfxdraw.circle(t, 40, 30, 18, (120, 255, 120))
            pygame.gfxdraw.filled_circle(t, 40, 30, 8, (255, 255, 120))
            pygame.gfxdraw.rectangle(t, (70, 12, 50, 36), (255, 120, 255))
    no_raise("gfxdraw 兼容面", lambda: gfx(off))

    # vertices/geometry 逃逸舱（原始顶点 + 索引几何）
    def raw_verts(s):
        with s.render() as t:
            t.vertices("triangles", [(10, 10), (90, 10), (50, 90)], (120, 220, 255))
            t.vertices("lines", [(10, 100), (90, 100)], (255, 160, 60))
    no_raise("vertices 三角/线", lambda: raw_verts(off))

    def raw_geom(s):
        with s.render() as t:
            t.geometry("filled", [(10, 10), (90, 10), (90, 90), (10, 90)],
                       [0, 1, 2, 0, 2, 3], (120, 255, 160))
            t.geometry("line", [(10, 10), (90, 10), (90, 90), (10, 90)],
                       None, (255, 120, 255))
    no_raise("geometry 索引填充/线框", lambda: raw_geom(off))

    # 负路径：颜色分量不足 / 非法项
    def bad_color(s):
        with s.render() as t:
            pygame.gfxdraw.box(t, (0, 0, 1, 1), (0, 200))
    try:
        bad_color(off)
        st("颜色分量不足 TypeError", False)
    except TypeError:
        st("颜色分量不足 TypeError", True)
    try:
        off2 = pygame.Surface((30, 30))
        with off2.render() as t:
            pygame.gfxdraw.filled_circle(t, -85, -45, -5, (255, 0, 0))   # 负半径钳制（不抛）
        st("circle 负半径钳制", True)
    except Exception:
        st("circle 负半径钳制", False)

    # ── 样张（每帧实绘——形状即测试本体）──
    label = cjk.render("pygame.draw 六形状 + 半透明 + gfxdraw 兼容", True, (200, 200, 200))
    spec = [
        font.render("filled rect / outline w=3 / kwargs", True, (180, 180, 180)),
        font.render("circle fill / outline w=2 / line", True, (180, 180, 180)),
        font.render("polygon fill+outline / ellipse / arc(rad)", True, (180, 180, 180)),
        font.render("translucent overlap / gfxdraw compat", True, (180, 180, 180)),
    ]

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        
        with screen.render() as r:
            r.fill((240, 24, 34))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(12, 8, 0)); pygame.gfxdraw.draw_surface(r, label)
            # 第一区：矩形三形态
            pygame.gfxdraw.box(r, (20, 40, 120, 80), (0, 200, 90))
            pygame.gfxdraw.rectangle(r, (20, 40, 120, 80), (255, 255, 255))  # 原 width=3 描边（gfxdraw 恒 1px）
            pygame.gfxdraw.rectangle(r, (160, 40, 120, 80), (90, 200, 255))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(20, 452, 0)); pygame.gfxdraw.draw_surface(r, spec[0])
            # 第二区：圆 + 线
            pygame.gfxdraw.filled_circle(r, 60, 220, 36, (255, 200, 0))
            pygame.gfxdraw.circle(r, 150, 220, 36, (255, 255, 255))  # 原 width=2 描边（gfxdraw 恒 1px）
            pygame.gfxdraw.line(r, 20, 270, 250, 270, (200, 60, 60))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(20, 312, 0)); pygame.gfxdraw.draw_surface(r, spec[1])
            # 第三区：多边形 + 椭圆 + 弧
            pygame.gfxdraw.filled_polygon(r, [(280, 220), (380, 240), (350, 310), (280, 300)], (90, 120, 220))
            pygame.gfxdraw.polygon(r, [(20, 330), (120, 340), (90, 410)], (255, 160, 60))  # 原 width=2 描边（gfxdraw 恒 1px）
            pygame.gfxdraw.filled_ellipse(r, -150, -75, 90, 45, (60, 180, 120))
            pygame.gfxdraw.arc(r, 40, -90, 60, 180, 360, (120, 220, 255))  # 椭圆弧→圆弧 v1（度数制）
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(20, 152, 0)); pygame.gfxdraw.draw_surface(r, spec[2])
            # 第四区：半透明叠加 + gfxdraw 兼容混绘
            pygame.gfxdraw.box(r, (420, 60, 90, 90), (255, 0, 0, 90))
            pygame.gfxdraw.filled_circle(r, 480, 120, 45, (0, 0, 255, 90))
            pygame.gfxdraw.circle(r, 620, 120, 40, (120, 255, 120))
            pygame.gfxdraw.filled_circle(r, 620, 120, 18, (255, 255, 120))
            pygame.gfxdraw.rectangle(r, (580, 200, 140, 80), (255, 120, 255))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(420, 10, 0)); pygame.gfxdraw.draw_surface(r, spec[3])
            # 离屏 Surface 会话产物 blit（独立绘制目标）
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(20, 460, 0)); pygame.gfxdraw.draw_surface(r, off)
            # 第五区：vertices/geometry 逃逸舱（批次三十八——原始顶点 +
            # 索引几何直通；主体三角扇 + 线框）
            r.vertices("triangles",
                       [(560, 460), (760, 460), (760, 560), (560, 560), (660, 620)],
                       (90, 120, 220))
            r.vertices("lines", [(560, 460), (760, 460), (760, 560), (560, 560)],
                       (255, 255, 255))
            r.geometry("filled", [(580, 480), (740, 480), (740, 540), (580, 540)],
                       [0, 1, 2, 0, 2, 3], (255, 160, 60))
        pygame.display.flip()
        await pygame.next_frame()
