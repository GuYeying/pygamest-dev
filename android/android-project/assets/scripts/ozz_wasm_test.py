# ozz_wasm_test —— wasm 平台 ozz 运行测试（任务7）：demo_player（内嵌
# 资产——零 fetch）sample(ratio) 240 帧骨骼渲染上屏 + 状态行。
# PASS 判据：状态行 ALL PASS 且画面见盒体+骨骼线摆动。
import pygame
import pygame_ozz

ok = []
fail = []


def st(name, cond):
    (ok if cond else fail).append(name)
    print("[wasm-ozz]", "PASS" if cond else "FAIL", name)


async def main():
    screen = pygame.display.set_mode((800, 600))
    p = pygame_ozz.demo_player()
    st("demo_player 构造", p is not None)
    st("关节数 > 0", p.num_joints() > 0)
    st("动画时长 > 0", p.duration() > 0)
    p.sample(0.5)
    pos = p.joint_positions_xy()
    st("sample 出关节位", len(pos) > 0)

    font = pygame.font.Font(None, 16)
    frame = 0
    while frame < 240:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (24, 26, 34))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            ratio = abs((frame % 120) - 60) / 60.0
            p.sample(ratio)
            pygame.gfxdraw.draw_ozz_bones(t, p, scale=150.0, cx=0.0, cy=-60.0)
            pygame.gfxdraw.draw_ozz_quads(t, p, scale=150.0, cx=0.0, cy=-60.0, size=26.0)
            status = f"wasm ozz: PASS {len(ok)} FAIL {len(fail)}"
            color = (120, 255, 120) if not fail else (255, 120, 120)
            line = font.render(status, True, color)
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-380, 280, 0))
            pygame.gfxdraw.draw_surface(t, line)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
    print("[wasm-ozz] 汇总:", "ALL PASS" if not fail else f"FAIL {fail}")
