# pygame.draw 模块专项测试（逐模块独立案例 2/N）
# 控制台 [draw-test] 逐项断言 + 全形状样张上屏（视觉验收）
# 覆盖：六形状（rect/circle/line/polygon/ellipse/arc）× 填充/描边 ×
#       颜色形态（3元/4元/kwargs）× 半透明叠加 × gfxdraw 兼容混绘
# 退出：ESC / 关窗
import pygame


async def main():
    screen = pygame.display.set_mode((800, 600))
    screen.set_camera(pygame.render.game_camera_ortho(800, 600, 800, 600))
    screen.set_camera(pygame.render.game_camera_ortho(800, 600, 800, 600))
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
            pygame.gfxdraw.set_topology(t, "triangles")
            pygame.gfxdraw.set_color(t, (0, 200, 90))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(35, 25, 0))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_rect(60, 40))                    # 实心
            pygame.gfxdraw.set_topology(t, "lines")
            pygame.gfxdraw.set_color(t, (255, 255, 255))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_rect_outline(60, 40))            # 描边
            pygame.gfxdraw.set_topology(t, "triangles")
            pygame.gfxdraw.set_color(t, (255, 200, 0))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(150, 30, 0))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_circle(22))                      # 填充圆
            pygame.gfxdraw.set_topology(t, "lines")
            pygame.gfxdraw.set_color(t, (255, 255, 255))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_circle_outline(22))              # 描边圆
            pygame.gfxdraw.set_topology(t, "triangles")
            pygame.gfxdraw.set_color(t, (200, 60, 60))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_line(5, 80, 190, 80))            # 线
            pygame.gfxdraw.set_color(t, (90, 120, 220))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_polygon([(30, 95), (90, 100), (70, 115)]))   # 填充三角
            pygame.gfxdraw.set_color(t, (255, 160, 60))
            pygame.gfxdraw.set_topology(t, "lines")
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_polygon_outline([(120, 95), (180, 100), (160, 115)]))  # 描边
            pygame.gfxdraw.set_topology(t, "triangles")
            pygame.gfxdraw.set_color(t, (60, 180, 120))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-55, -35, 0))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_ellipse(40, 20))   # 椭圆
            pygame.gfxdraw.set_color(t, (120, 220, 255))
            pygame.gfxdraw.set_topology(t, "lines")
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(40, -35, 0))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_arc(40, 0, 180))  # 弧（度数制）
            pygame.gfxdraw.set_topology(t, "default")
            pygame.gfxdraw.reset_transform(t)

    no_raise("六形状全绘（离屏会话）", lambda: shapes_on(off))

    # 半透明叠加（4 元色 alpha 分量）
    def translucent(s):
        with s.render() as t:
            pygame.gfxdraw.set_color(t, (255, 0, 0, 90))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(25, 25, 0))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_rect(40, 40))
            pygame.gfxdraw.set_color(t, (0, 0, 255, 90))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(45, 45, 0))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_rect(40, 40))   # 叠加区 = 混合色
    no_raise("半透明叠加", lambda: translucent(off))

    # gen 生成器面（与 push 同一 batch 零额外成本）
    def gfx(s):
        with s.render() as t:
            pygame.gfxdraw.set_color(t, (120, 255, 120))
            pygame.gfxdraw.set_topology(t, "lines")
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(40, 30, 0))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_circle_outline(18))
            pygame.gfxdraw.set_topology(t, "triangles")
            pygame.gfxdraw.set_color(t, (255, 255, 120))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_circle(8))
            pygame.gfxdraw.set_color(t, (255, 120, 255))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(95, 30, 0))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_rect(50, 36))
            pygame.gfxdraw.set_topology(t, "default")
    no_raise("gen 生成器面", lambda: gfx(off))

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

    # push 统一口（v1 批次：VertexBuf + set_topology + gen_* 生成器）——
    # sticky 状态流（色/拓扑/变换跨 push 持续，与 draw 族 one-shot 分立）
    def push_apis(s):
        with s.render() as t:
            # 生成器句柄 + sticky 色/变换（连 push 两份同色同拓扑）
            tri = pygame.gfxdraw.gen_circle(20)
            pygame.gfxdraw.set_topology(t, "triangles")
            pygame.gfxdraw.set_color(t, (255, 120, 60))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(60, 60, 0))
            pygame.gfxdraw.push(t, tri)
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(120, 60, 0))
            pygame.gfxdraw.push(t, tri)          # sticky：色/拓扑仍生效

            # 扁平 list + 索引覆盖
            pygame.gfxdraw.push(t, [160, 60, 220, 60, 190, 120])

            # bytes 直拷（手动 VertexBuf + set_indices）
            buf = pygame.gfxdraw.VertexBuf()
            buf.add_points([240, 60, 0, 300, 60, 0, 270, 120, 0])
            buf.set_indices([0, 1, 2])
            pygame.gfxdraw.push(t, buf)

            # lines 拓扑——顶点按 2 个点一组解释（每点仍 x,y,z 三分量）
            pygame.gfxdraw.set_topology(t, "lines")
            pygame.gfxdraw.set_color(t, (120, 220, 255))
            pygame.gfxdraw.push(t, [10, 120, 0, 90, 120, 0])

            # 拓扑复位（default）——后续 draw 族不受污染
            pygame.gfxdraw.set_topology(t, "default")
            pygame.gfxdraw.reset_transform(t)
    no_raise("push 统一口四通道", lambda: push_apis(off))

    # push 负路径：长度不校验（扁平 list 非 3 倍数）
    def push_bad_len(s):
        with s.render() as t:
            pygame.gfxdraw.set_topology(t, "triangles")
            pygame.gfxdraw.push(t, [10, 20, 30, 40])   # 4 个数 = 非 3 倍数
    try:
        push_bad_len(off)
        st("push 扁平长度 ValueError", False)
    except ValueError:
        st("push 扁平长度 ValueError", True)

    # 负路径：颜色分量不足 / 非法项
    def bad_color(s):
        with s.render() as t:
            pygame.gfxdraw.set_color(t, (0, 200))
    try:
        bad_color(off)
        st("颜色分量不足 TypeError", False)
    except TypeError:
        st("颜色分量不足 TypeError", True)
    try:
        off2 = pygame.Surface((30, 30))
        with off2.render() as t:
            pygame.gfxdraw.set_color(t, (255, 0, 0))
            pygame.gfxdraw.push(t, pygame.gfxdraw.gen_circle(-5))   # 负半径（生成器钳 0——不抛）
        st("circle 负半径钳制", True)
    except Exception:
        st("circle 负半径钳制", False)

    # ── 样张（每帧实绘——形状即测试本体）──
    label = cjk.render("gen_* 生成器 + push 统一口：六形状 + 半透明", True, (200, 200, 200))
    spec = [
        font.render("rect fill / rect outline / kwargs", True, (180, 180, 180)),
        font.render("circle fill / outline / line", True, (180, 180, 180)),
        font.render("polygon fill+outline / ellipse / arc(deg)", True, (180, 180, 180)),
        font.render("translucent overlap / gen mix", True, (180, 180, 180)),
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
            pygame.gfxdraw.set_topology(r, "triangles")
            pygame.gfxdraw.set_color(r, (0, 200, 90))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(80, 80, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_rect(120, 80))
            pygame.gfxdraw.set_topology(r, "lines")
            pygame.gfxdraw.set_color(r, (255, 255, 255))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_rect_outline(120, 80))
            pygame.gfxdraw.set_color(r, (90, 200, 255))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(220, 80, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_rect_outline(120, 80))
            pygame.gfxdraw.set_topology(r, "triangles")
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(20, 452, 0)); pygame.gfxdraw.draw_surface(r, spec[0])
            # 第二区：圆 + 线
            pygame.gfxdraw.set_color(r, (255, 200, 0))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(60, 220, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_circle(36))
            pygame.gfxdraw.set_topology(r, "lines")
            pygame.gfxdraw.set_color(r, (255, 255, 255))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(150, 220, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_circle_outline(36))
            pygame.gfxdraw.set_color(r, (200, 60, 60))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_line(20, 270, 250, 270))
            pygame.gfxdraw.set_topology(r, "triangles")
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(20, 312, 0)); pygame.gfxdraw.draw_surface(r, spec[1])
            # 第三区：多边形 + 椭圆 + 弧
            pygame.gfxdraw.set_color(r, (90, 120, 220))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_polygon([(280, 220), (380, 240), (350, 310), (280, 300)]))
            pygame.gfxdraw.set_color(r, (255, 160, 60))
            pygame.gfxdraw.set_topology(r, "lines")
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_polygon_outline([(20, 330), (120, 340), (90, 410)]))
            pygame.gfxdraw.set_topology(r, "triangles")
            pygame.gfxdraw.set_color(r, (60, 180, 120))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(-150, -75, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_ellipse(90, 45))
            pygame.gfxdraw.set_color(r, (120, 220, 255))
            pygame.gfxdraw.set_topology(r, "lines")
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(40, -90, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_arc(60, 180, 360))  # 圆弧（度数制）
            pygame.gfxdraw.set_topology(r, "triangles")
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(20, 152, 0)); pygame.gfxdraw.draw_surface(r, spec[2])
            # 第四区：半透明叠加 + gen 混绘
            pygame.gfxdraw.set_color(r, (255, 0, 0, 90))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(465, 105, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_rect(90, 90))
            pygame.gfxdraw.set_color(r, (0, 0, 255, 90))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(480, 120, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_circle(45))
            pygame.gfxdraw.set_color(r, (120, 255, 120))
            pygame.gfxdraw.set_topology(r, "lines")
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(620, 120, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_circle_outline(40))
            pygame.gfxdraw.set_topology(r, "triangles")
            pygame.gfxdraw.set_color(r, (255, 255, 120))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_circle(18))
            pygame.gfxdraw.set_color(r, (255, 120, 255))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(650, 240, 0))
            pygame.gfxdraw.push(r, pygame.gfxdraw.gen_rect_outline(140, 80))
            pygame.gfxdraw.set_topology(r, "default")
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
        await pygame.tasks.yield_now()
