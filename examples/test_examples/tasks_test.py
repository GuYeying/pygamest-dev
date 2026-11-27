# tasks_test —— pygame.tasks 协作式微调度器验收（v1 API 面，2026-11-19）：
# sleep（秒版）/ gather 并发 / spawn+Task 状态 / wait_for 超时 /
# Queue 跨协程 / cancel。帧桥单步机制纯包装（asyncio 词汇、帧驱动
# 语义——有界任务；流媒体永不入 tasks，控制走即时状态口）。
import pygame

async def worker(name, frames):
    n = 0
    while n < frames:
        await pygame.tasks.yield_now()
        n += 1
    return f"{name}-done"

async def slow_load():
    await pygame.tasks.sleep(0.5)          # 30 帧
    return "asset"

async def bad_load(res_name):
    await pygame.tasks.sleep(0.2)
    raise ValueError("资源缺失: " + res_name)

async def hung():
    while True:
        await pygame.tasks.yield_now()          # 永不完成（wait_for 超时对象）

async def producer(q):
    await pygame.tasks.sleep(0.2)
    q.put("hello")
    q.put("world")

async def main():
    pygame.display.set_caption("tasks_test")
    screen = pygame.display.set_mode((800, 600))
    cjk = pygame.font.Font("cjk", 15)
    T = pygame.tasks
    _fail = []

    def st(name, ok):
        print(("[tasks-test] PASS " if ok else "[tasks-test] FAIL ") + name)
        if not ok:
            _fail.append(name)

    # ① gather 三任务并发（总耗时 ≈ 最慢者）
    t0 = T.frame()
    r = await T.gather(worker("a", 30), worker("b", 60), slow_load())
    st("gather 三任务全完成", all(x in ("a-done", "b-done", "asset") for x in r))
    st("gather 并发（总帧 ≤ 最慢+10）", T.frame() - t0 <= 70)

    # ② spawn 后台推进 + Task 状态查询
    tk = T.spawn(worker("bg", 90))
    await pygame.tasks.sleep(0.1)
    st("spawn 未完成态", not tk.done)
    await pygame.tasks.sleep(1.5)

    # ③ wait_for 正常完成
    v = await T.wait_for(worker("wf", 30), 2.0)
    st("wait_for 正常返回", v == "wf-done")

    # ④ wait_for 超时止损（防无限任务泄漏）
    try:
        await T.wait_for(hung(), 0.5)
        st("wait_for 超时抛 TimeoutError", False)
    except TimeoutError:
        st("wait_for 超时抛 TimeoutError", True)

    # ⑤ Queue 跨协程传递（put 即时 / get 挂起轮询）
    q = T.Queue()
    T.spawn(producer(q))
    s = await q.get()
    s2 = await q.get()
    st("Queue 跨协程传递", s == "hello" and s2 == "world")

    # ⑥ cancel 协作式终止
    tk2 = T.spawn(worker("cc", 120))
    await pygame.tasks.sleep(0.2)
    tk2.cancel()
    st("cancel 终止任务", tk2.done and tk2.cancelled)

    # ⑦ 失败定位（异常存档 + re-raise + 任务命名——资源加载失败场景）
    t = pygame.tasks.spawn(bad_load("assets/hero.png"), "hero_load")
    await pygame.tasks.sleep(0.5)
    st("任务失败存档 failed()/exception()", t.failed() and t.exception() is not None)
    st("失败定位 = 任务名", t.name == "hero_load")
    try:
        await t.wait()
        st("await 任务重抛异常", False)
    except ValueError as e:
        st("await 任务重抛异常", "hero.png" in str(e))
    try:
        await T.gather(worker("ok", 10), bad_load("b"))
        st("gather 首异常重抛", False)
    except ValueError:
        st("gather 首异常重抛", True)

    print("[tasks-test] SUMMARY", "PASS" if not _fail else "FAIL " + str(_fail))

    # 续演窗（视觉确认——验收窗保持）
    frame = 0
    while frame < 150:
        with screen.render() as t:
            t.fill((16, 20, 30))
            pygame.gfxdraw.draw_surface(t, cjk.render(
                "pygame.tasks 微调度器 " + ("全部 PASS" if not _fail else "有失败项"),
                True, (150, 220, 170) if not _fail else (255, 120, 120)), transform=pygame.math.mat4_translation(-390, 280, 0))
        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1
