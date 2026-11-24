# pygame.tasks 冒烟验证（tasks.py 可读性重构后——行为零变回归）
# 脚本形态定约：async def main()——帧桥驱动主协程逐帧 pump 任务表
#（同步 while 循环脚本不进帧泵——engine_frame 恒 0，实测）
import pygame

results = []

async def worker(v, n):
    for _ in range(n):
        await pygame.tasks.sleep_frames(1)
    return v * 10

async def producer(q):
    await pygame.tasks.sleep_frames(2)
    q.put(99)

async def slow():
    while True:
        await pygame.tasks.sleep_frames(1)

async def main():
    pygame.display.set_mode((64, 64))

    # ① gather：参数序返回 + 多任务并发
    r = await pygame.tasks.gather(worker(1, 3), worker(2, 2))
    results.append(("gather", r))
    # ② Task.wait：spawn 产物等待
    t = pygame.tasks.spawn(worker(5, 1), "t5")
    results.append(("task_wait", await t.wait()))
    # ③ yield_now 多轮（挂起原语规范名）
    for _ in range(3):
        await pygame.tasks.yield_now()
    results.append("yield_ok")
    # ④ Queue：跨任务 put/get
    q = pygame.tasks.Queue()
    pygame.tasks.spawn(producer(q))
    results.append(("queue", await q.get()))
    # ⑤ wait_for 超时取消（无限任务泄漏防护）
    try:
        await pygame.tasks.wait_for(slow(), 5)
        results.append("wait_for-NO-TIMEOUT")   # 不应到达
    except TimeoutError:
        results.append("timeout_ok")
    # ⑥ sleep 秒版（≥1 帧语义）
    await pygame.tasks.sleep(0.02)
    results.append("sleep_ok")

    expect = [("gather", [10, 20]), ("task_wait", 50), "yield_ok",
              ("queue", 99), "timeout_ok", "sleep_ok"]
    if results == expect:
        print(f"[tasks-smoke] ALL PASS (engine_frame={pygame.tasks.frame()})")
    else:
        print(f"[tasks-smoke] FAIL results={results!r}")
