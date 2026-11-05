# live2d_render_demo —— mocari 渲染管线集成验证：Hiyori 官方样例模型
# （Live2D Free Material License 资产，经 neocari 仓库分发副本 vendor）
# 经 gfxdraw.draw_live2d 上屏。ParamAngleX 正弦驱动（参数 → 网格重建
# 每帧）。300 帧自动退出。
import pygame
import pygame_live2d

MODEL_DIR = "D:/Projects/Rust/pygame_live2d/assets/models/Hiyori"

async def main():
    screen = pygame.display.set_mode((800, 600))
    rt = pygame_live2d.load_runtime(f"{MODEL_DIR}/Hiyori.model3.json")
    print("[live2d_demo] canvas =", rt.canvas_size())
    print("[live2d_demo] 参数数 =", len(rt.parameter_ids()))
    print("[live2d_demo] drawable 数 =", rt.mesh_count())

    font = pygame.font.Font(None, 22)
    frame = 0
    while frame < 300:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (36, 40, 52))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            # 参数驱动（归一 0..1 → 角度摆动）
            rt.set_parameter_normalized("ParamAngleX", abs((frame % 120) - 60) / 60.0)
            rt.set_parameter_normalized("ParamAngleZ", 0.5 - 0.4 * abs((frame % 90) - 45) / 45.0)
            rt.update_meshes()
            pygame.gfxdraw.draw_live2d(t, rt)
        label = font.render(f"live2d demo frame={frame}", True, (220, 220, 230))
        with screen.render() as t:
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, 270, 0))
            pygame.gfxdraw.draw_surface(t, label)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1

    print("[live2d_demo] DONE 300 帧")
