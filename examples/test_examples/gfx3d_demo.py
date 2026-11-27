# gfx3d_demo —— 3D 几何的**单一渲染通道**验证（gen_* 生成 VertexBuf →
# draw_batch 渲染；不再有 cube/sphere/... 之类的直调 convenience 口）：
# render_depth 深度会话 + 透视相机（gfxdraw.set_camera）+ shape3d 六件套
# （box/sphere/plane/cylinder/cone/polygon3d）+ clear_camera 回 2D。
# 每个形状各自带颜色（原本共用一个会话色，全是紫的看不清结构）。
# 退出：ESC / 关窗。
import pygame

M = pygame.math


async def main():
    screen = pygame.display.set_mode((800, 600))
    cjk = pygame.font.Font("cjk", 17)
    title = cjk.render("gfxdraw 3D：gen_box/sphere/cylinder/cone/polygon3d + draw_batch",
                       True, (205, 205, 205))

    # 透视相机（GameCamera——gfxdraw.set_camera 段级口）。
    # 世界系 +y 向上、+z 朝屏幕里；视图矩阵是相机的逆——translate z=-8
    # 等价于「机位在 z=+8 朝 -z 看」，y=-2.2 等价于机位在 y=+2.2（俯视）
    cam = pygame.render.game_camera_perspective(55.0, 800, 600, 800, 600, 0.1, 100.0)
    view = M.mat4_translation(0.0, -2.2, -8.0)
    cam = cam.with_view(view)

    # 几何全部预生成一次（VertexBuf 可复用——每帧只提交绘制）
    # 地板放在原点下方（-y = 下方），物体都在它上面，互不穿插
    floor_buf = pygame.gfxdraw.gen_box([-4.0, -1.5, -4.0], [4.0, -0.5, 4.0])
    sphere_buf = pygame.gfxdraw.gen_sphere(0.8)
    cylinder_buf = pygame.gfxdraw.gen_cylinder(0.6, 2.0)
    cone_buf = pygame.gfxdraw.gen_cone(0.6, 1.2)
    # 六边形板：立起来的面（x/y 变化、z 固定），否则从机位看是一条线
    hex_pts = []
    for i in range(6):
        a = i / 6.0 * 6.2831853
        hex_pts += [-1.45 + M.cos(a) * 0.55, -0.25 + M.sin(a) * 0.55, 1.2]
    hex_buf = pygame.gfxdraw.gen_polygon3d(hex_pts)
    # 立方体与边框也只生成一次：旋转靠 transform（每帧不再新造 VertexBuf，
    # 稳态下本案例的几何对象分配数 = 0——长时间跑不堆垃圾）
    cube_buf = pygame.gfxdraw.gen_box([-0.6, -0.6, -0.6], [0.6, 0.6, 0.6])
    outline_buf = pygame.gfxdraw.gen_rect_outline(770, 570)
    # 常量摆位矩阵（预建一次，逐帧只复用；旋转体每帧只有 1 个新矩阵）
    t_sphere = M.mat4_translation(-2.6, 0.0, 0.5)
    t_cyl = M.mat4_translation(2.6, 0.0, 0.5)
    t_cone = M.mat4_translation(2.6, 1.8, 0.5)
    t_title = M.mat4_translation(-380, 270, 0)

    angle = 0.0
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        angle += 0.01
        ca = M.cos(angle)
        sa = M.sin(angle)

        with screen.render_depth() as rt:
            rt.fill((10, 11, 18))

            # 3D 段：透视相机 + 深度测试管线
            pygame.gfxdraw.set_camera(rt, cam)

            # 地板：薄盒（plane 直调渲染缺陷挂账——薄盒替代实证可靠）
            pygame.gfxdraw.draw_batch(rt, floor_buf, color=(64, 72, 100), cull="back")

            # 中央旋转立方体：几何固定，旋转 + 圆周位移全走 transform
            rot = M.mat4_from_quat(M.quat_from_axis_angle(0.0, 1.0, 0.0, angle * 57.29578))
            cube_xform = M.mat4_translation(ca * 1.5, 0.0, sa * 1.5) @ rot
            pygame.gfxdraw.draw_batch(rt, cube_buf, color=(255, 155, 60),
                                      cull="back", transform=cube_xform)

            # 球（左）：gen_sphere 以自身原点为心 → transform 摆位
            pygame.gfxdraw.draw_batch(rt, sphere_buf, color=(80, 210, 130),
                                      cull="back", transform=t_sphere)

            # 圆柱 + 圆锥（右）：gen_* 以「柱高中点」为原点；
            # 圆锥摆在圆柱上方（+y 向下 → 更小的 y 才是「上面」）
            pygame.gfxdraw.draw_batch(rt, cylinder_buf, color=(90, 180, 255),
                                      cull="back", transform=t_cyl)
            pygame.gfxdraw.draw_batch(rt, cone_buf, color=(255, 110, 120),
                                      cull="back", transform=t_cone)

            # polygon3d：竖立的六边形板（单面板不剔除）
            pygame.gfxdraw.draw_batch(rt, hex_buf, color=(240, 210, 90))

            # clear_camera：摘除透视 → 回目标尺寸正交（2D HUD 层）
            pygame.gfxdraw.clear_camera(rt)
            pygame.gfxdraw.draw_surface(rt, title, transform=t_title)

            # 正交 2D 边框（clear 后像素坐标直用；中心锚矩形盖住整屏）
            pygame.gfxdraw.draw_batch(rt, outline_buf, color=(150, 170, 150))

        pygame.display.flip()
        # 帧率上限（旧注释"深度会话每帧重建深度资源会 OOM"已不成立：
        # 屏幕深度纹理随 RenderSurface 建一次，只在 resize 时重建；
        # 5 分钟实测 WS/PR/GPU 专用内存均为平线）
        pygame.time.delay(8)
        await pygame.tasks.yield_now()




