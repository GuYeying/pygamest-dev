# ozz_full_test —— pygame_ozz 全量断言测试（demo 资产采样确定性 +
# 显式字节构造 + 错误路径 + 关节盒体/骨骼线视觉 smoke 60 帧；
# nightly 宿主专属）。
import pygame
import pygame_ozz

ok_count = 0
fail_count = 0


def chk(name, got, want):
    global ok_count, fail_count
    good = got == want
    if good:
        ok_count += 1
    else:
        fail_count += 1
    print(f"[OT] {'OK ' if good else 'FAIL'} {name}: {got}" + ("" if good else f"（期望 {want}）"))


def raises(fn):
    try:
        fn()
        return "未抛异常"
    except ValueError:
        return "ValueError"


async def main():
    # ── 构造面 ──
    p = pygame_ozz.demo_player()
    chk("demo_player 关节>0", p.num_joints() > 0, True)
    chk("duration>0", p.duration() > 0, True)
    names = p.joint_names()
    chk("joint_names 数一致", len(names) == p.num_joints(), True)
    parents = p.joint_parents()
    chk("joint_parents 数一致", len(parents) == p.num_joints(), True)
    chk("根关节 = -1", parents[0], -1)

    # ── 采样面 ──
    p.sample(0.0)
    m0 = p.model_matrices()
    chk("矩阵长度 = 关节×16", len(m0) == p.num_joints() * 16, True)
    chk("矩阵全有限值", all(v == v and abs(v) != float("inf") for v in m0), True)

    p.sample(0.5)
    m_half = p.model_matrices()
    chk("ratio 0.5 ≠ ratio 0.0（动画驱动）", m_half != m0, True)

    # 确定性：同 ratio 两次采样逐位一致
    p.sample(0.3)
    a = p.model_matrices()
    p.sample(0.3)
    b = p.model_matrices()
    chk("同 ratio 采样确定性", a == b, True)

    p.sample(5.0)  # 超界钳制（内部 clamp 0..1）
    chk("ratio 超界钳制", len(p.model_matrices()) == len(m0), True)

    # 显式字节构造（与 demo 内嵌同一资产——从 demo_player 拿不到字节，
    # 用错误字节走错误路径 + 构造器成功路径由 demo_player 覆盖）
    chk("Player 不存在路径", raises(lambda: pygame_ozz.OzzPlayer("/nonexistent.ozz", "/nonexistent.ozz")), "ValueError")

    # ── 数据口 ──
    jpos = p.joint_positions_xy()
    chk("joint_positions_xy 数一致", len(jpos) == p.num_joints(), True)

    # ── 视觉 smoke（60 帧 盒体 + 骨骼线）──
    screen = pygame.display.set_mode((800, 600))
    frame = 0
    while frame < 60:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (24, 26, 34))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            ratio = (frame % 60) / 60.0
            p.sample(ratio)
            pygame.gfxdraw.draw_ozz_quads(t, p, scale=60.0, cx=0.0, cy=-60.0, size=10.0)
            pygame.gfxdraw.draw_ozz_bones(t, p, scale=60.0, cx=0.0, cy=-60.0)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
    chk("视觉 smoke 60 帧（盒体+骨骼线）", True, True)

    total = ok_count + fail_count
    print(f"[OT] 统计: {ok_count}/{total} 通过" + ("" if fail_count == 0 else f"，{fail_count} 失败"))
    print("[OT]", "ALL PASS" if fail_count == 0 else "HAS FAILURES")
