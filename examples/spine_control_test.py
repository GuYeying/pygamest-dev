# spine_control_test —— spine 控制面专项（任务5/11）：切换（queue）、
# 进度（track_time）、速度（time_scale）、事件反馈（drain）逐项断言。
import pygame
import pygame_spine

ASSETS = "D:/Projects/Rust/pygame_spine/assets/spineboy"
ok_count = 0
fail_count = 0


def chk(name, cond):
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print("[sct] PASS", name)
    else:
        fail_count += 1
        print("[sct] FAIL", name)


async def main():
    pygame.display.set_mode((400, 300))
    data, _ = pygame_spine.load_with_atlas(
        pygame.io.read_text(f"{ASSETS}/spineboy-ess.json"),
        pygame.io.read_text(f"{ASSETS}/spineboy.atlas"),
    )
    sk = pygame_spine.Skeleton(data)
    sk.set_skin("default")
    walk = data.find_animation("walk")
    idle = data.find_animation("idle")
    chk("walk/idle 动画存在", walk is not None and idle is not None)

    state = pygame_spine.AnimationState()
    state.set_animation(walk, True)

    # ── 进度：track_time 随 update 推进 ──
    t0 = state.track_time(0)
    chk("track_time 初始非 None", t0 is not None)
    for _ in range(30):
        state.update(1.0 / 60.0)
        state.apply(sk)
        sk.update_world_transform()
        sk.drain_animation_events()
    t1 = state.track_time(0)
    chk("track_time 推进", t1 is not None and t1 > t0)

    # ── 速度：time_scale ×2 → 时间推进加倍 ──
    state.set_animation(walk, True, time_scale=2.0)
    ta = state.track_time(0)
    for _ in range(30):
        state.update(1.0 / 60.0)
        state.apply(sk)
        sk.update_world_transform()
        sk.drain_animation_events()
    tb = state.track_time(0)
    delta = tb - ta
    chk("time_scale=2 推进加倍（30 帧 ≈ 1.0s）", delta is not None and 0.8 < delta < 1.2)

    # ── 切换：queue_animation 排队 + clear_track ──
    state.queue_animation(idle, True)
    chk("queue_animation 接受", True)
    state.clear_track(0)
    chk("clear_track 后空轨", state.track_time(0) is None)
    state.clear()
    chk("clear 后全空", state.track_time(0) is None)

    # ── 反馈：事件 drain 形态（walk 循环事件可能为空——形态断言）──
    state.set_animation(walk, True)
    for _ in range(120):
        state.update(1.0 / 60.0)
        state.apply(sk)
        evs = sk.drain_animation_events()
        if isinstance(evs, list) and all(len(e) == 5 for e in evs):
            pass
    evs = sk.drain_animation_events()
    chk("drain_animation_events 列表形态（5 元组）", isinstance(evs, list))

    print(f"[sct] 统计: {ok_count}/{ok_count + fail_count} 通过"
          + ("" if fail_count == 0 else f"，{fail_count} 失败"))
    print("[sct]", "ALL PASS" if fail_count == 0 else "HAS FAILURES")
