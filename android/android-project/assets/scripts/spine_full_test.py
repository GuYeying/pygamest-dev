# spine_full_test —— pygame_spine 全量断言测试（真资产 spineboy +
# 程序化 demo + 错误路径 + 视觉 smoke 60 帧）。输出 [ST] 逐项 +
# 最终 PASS/FAIL 统计。
import time

import pygame
import pygame_spine

ASSETS = "assets/spineboy"
ok_count = 0
fail_count = 0


def chk(name, got, want):
    global ok_count, fail_count
    good = got == want
    if good:
        ok_count += 1
    else:
        fail_count += 1
    print(f"[ST] {'OK ' if good else 'FAIL'} {name}: {got}" + ("" if good else f"（期望 {want}）"))


def raises(fn):
    try:
        fn()
        return "未抛异常"
    except ValueError:
        return "ValueError"
    except TypeError:
        return "TypeError"


async def main():
    # ── 加载面（路径进对象出——io 在绑定层闭环）──
    data = pygame_spine.load_json(f"{ASSETS}/spineboy-ess.json")
    chk("load_json bone_count>0", data.bone_count() > 0, True)

    data_bin = pygame_spine.load_binary(f"{ASSETS}/spineboy-ess.skel")
    chk("load_binary 骨骼数一致", data_bin.bone_count() == data.bone_count(), True)

    demo = pygame_spine.demo_skeleton()
    chk("demo_skeleton 骨骼数", demo.bone_count(), 3)
    chk("demo bone_name(1)", demo.bone_name(1), "arm")

    tex_demo = pygame_spine.demo_textured_skeleton()
    chk("demo_textured 存在", tex_demo.bone_count() > 0, True)

    data2, pages = pygame_spine.load_with_atlas(
        f"{ASSETS}/spineboy-ess.json",
        f"{ASSETS}/spineboy.atlas",
    )
    chk("load_with_atlas 页数", pages, 1)

    chk("load_json 不存在路径", raises(lambda: pygame_spine.load_json("/nonexistent.json")), "ValueError")
    chk("load_binary 不存在路径", raises(lambda: pygame_spine.load_binary("/nonexistent.skel")), "ValueError")

    # ── 检索面 ──
    walk = data.find_animation("walk")
    chk("find_animation walk", walk is not None, True)
    chk("walk duration", abs(walk.duration() - 1.0) < 0.05, True)
    chk("find_animation 缺失", data.find_animation("nope"), None)

    # ── 姿态面 ──
    sk = pygame_spine.Skeleton(data2)
    sk.set_skin("default")
    chk("set_skin 合法", True, True)
    chk("set_skin 非法", raises(lambda: sk.set_skin("bad_skin")), "ValueError")

    sk.update_world_transform()
    x0, y0, *_ = sk.bone_world(0)
    sk.set_bone_rotation(0, 90.0)
    sk.update_world_transform()
    x1, y1, *_ = sk.bone_world(1)
    chk("旋转传播改变子骨世界位", (round(x1, 1), round(y1, 1)) != (round(x0, 1), round(y0, 1)), True)

    sk.set_position(10.0, 20.0)
    sk.set_scale(2.0, 2.0)
    sk.update_world_transform()
    x2, y2, *_ = sk.bone_world(0)
    chk("平移缩放作用于根", (round(x2), round(y2)) == (10, 20), True)

    chk("bone_world 越界", raises(lambda: sk.bone_world(999)), "ValueError")
    chk("set_bone_rotation 越界", raises(lambda: sk.set_bone_rotation(999, 0.0)), "ValueError")

    # ── 动画播放面 ──
    state = pygame_spine.AnimationState()
    state.set_animation(walk, True)
    sk3 = pygame_spine.Skeleton(data2)
    sk3.set_skin("default")
    poses = []
    for i in range(30):
        state.update(1.0 / 30.0)
        state.apply(sk3)
        sk3.update_world_transform()
        x, y, *_ = sk3.bone_world(3)
        poses.append((round(x, 2), round(y, 2)))
    chk("walk 驱动骨位变化", len(set(poses)) > 5, True)

    chk("Animation.duration", abs(walk.duration() - 1.0) < 0.05, True)

    # ── 渲染数据面 ──
    sk.update_world_transform()
    cmds = sk.render_commands()
    chk("spineboy render_commands 非空", len(cmds) > 0, True)
    demo_sk = pygame_spine.Skeleton(tex_demo)
    demo_sk.set_skin("default")
    demo_sk.update_world_transform()
    demo_cmds = demo_sk.render_commands()
    chk("demo_textured render_commands 非空（region 可无 atlas 出几何）", len(demo_cmds) == 2, True)
    chk("demo 命令结构（4 顶点 6 索引 page0）",
        len(demo_cmds[0][2]) == 8 and len(demo_cmds[0][4]) == 6 and demo_cmds[0][0] == 0, True)

    # ── 视觉 smoke（60 帧 walk + draw_spine）──
    screen = pygame.display.set_mode((800, 600))
    page0 = await pygame.image.load(f"{ASSETS}/spineboy.png")
    frame = 0
    last = time.time()
    while frame < 60:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        now = time.time()
        dt = now - last
        last = now
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (30, 34, 44))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            state.update(dt)
            state.apply(sk3)
            sk3.update_world_transform()
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(0, -40, 0))
            pygame.gfxdraw.draw_spine(t, sk3, [page0])
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(0, 0, 0))
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
    chk("视觉 smoke 60 帧", True, True)

    total = ok_count + fail_count
    print(f"[ST] 统计: {ok_count}/{total} 通过" + ("" if fail_count == 0 else f"，{fail_count} 失败"))
    print("[ST]", "ALL PASS" if fail_count == 0 else "HAS FAILURES")
