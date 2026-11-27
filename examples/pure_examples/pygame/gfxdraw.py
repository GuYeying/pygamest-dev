# gfxdraw 纯净案例——gen_* 生成器 + draw_batch 统一口 + VertexBuf 手工构造
# 拓扑随数据（填充族 triangles / 线族 lines）+ buf.topology 覆写演示
import pygame

async def main():
    screen = pygame.display.set_mode((800, 500), gui=True)
    cloth = pygame.image.load("cloth.png")

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        with screen.render() as t:
            t.fill((24, 26, 34))

            # gen_* + draw_batch：拓扑随数据（outline=lines / 填充=triangles）
            pygame.gfxdraw.draw_batch(
                t, pygame.gfxdraw.gen_circle(50),
                transform=pygame.math.mat4_translation(-260, 120, 0),
                color=(230, 90, 60, 255),
            )
            pygame.gfxdraw.draw_batch(
                t, pygame.gfxdraw.gen_circle_outline(50),
                transform=pygame.math.mat4_translation(-120, 120, 0),
                color=(90, 160, 255, 255),
            )
            pygame.gfxdraw.draw_batch(
                t, pygame.gfxdraw.gen_rect(120, 90),
                transform=pygame.math.mat4_translation(40, 120, 0),
                color=(120, 200, 120, 255),
            )
            pygame.gfxdraw.draw_batch(
                t, pygame.gfxdraw.gen_arc(60, 0, 270),
                transform=pygame.math.mat4_translation(230, 120, 0),
                color=(240, 200, 80, 255),
            )

            # gen_* + set_transform 持久变换（blit/spine/ozz 桥同款形态）
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-260, -100, 0))
            pygame.gfxdraw.draw_batch(t, pygame.gfxdraw.gen_polygon3d(
                [-60.0, -40.0, 0.0, 60.0, -40.0, 0.0, 0.0, 60.0, 0.0]),
                color=(200, 120, 220, 255))

            # VertexBuf 手工构造 + topology 覆写（自定义流解释控制）
            buf = pygame.gfxdraw.gen_polygon([(-40, -40), (40, -40), (40, 40), (-40, 40)])
            buf.topology = "lines"                     # 填充数据按线段解释
            pygame.gfxdraw.draw_batch(
                t, buf,
                transform=pygame.math.mat4_translation(0, -100, 0),
                color=(90, 220, 180, 255),
            )

            # 贴图立方体（gen_cube + cloth 纹理 + 自定义 WGSL 见 cube_rotate）
            pygame.gfxdraw.draw_batch(
                t, pygame.gfxdraw.gen_sphere(45),
                transform=pygame.math.mat4_translation(260, -100, 0),
                color=(90, 120, 220, 255),
                wireframe=True,                        # one-shot 仅本批
            )

        pygame.display.flip()
        await pygame.tasks.yield_now()
