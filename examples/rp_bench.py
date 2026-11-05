# rp_bench —— RustPython 本体性能基准（纯解释器，无 GPU/引擎热路径）
# 目的：测 RustPython 本身解释性能——评估游戏脚本的纯逻辑上限。
# 指标经 font 渲染上屏（每项 = 耗时 ms + 吞吐 ops/s），同步打印 console。
# 基准集：整数循环 / 浮点运算 / 函数调用 / 递归 / 列表 / 字典 /
#         字符串 / 类实例化 / f-string——九项覆盖解释器主热路径。
# 基准启动跑一次（桌面约 3~5s，安卓按比例放大），结果缓存逐帧上屏。
import pygame


def run_benches():
    """九项基准 → [(名称, 耗时ms, 吞吐ops/s)]；pygame.time 计时
    （嵌入构建无 time 模块——引擎 ticks 即钟）。"""
    out = []

    def bench(name, iters, fn):
        t0 = pygame.time.get_ticks()
        r = fn()
        dt = pygame.time.get_ticks() - t0
        rate = iters * 1000 // max(dt, 1)
        out.append((name, dt, rate))
        return r

    def b_int():
        s = 0
        i = 0
        n = 1000000
        while i < n:
            s += i
            i += 1
        return s
    bench("整数循环累加   1M while", 1000000, b_int)

    def b_float():
        x = 1.0
        i = 0
        n = 500000
        while i < n:
            x = x * 1.0000001 + 0.5
            i += 1
        return x
    bench("浮点乘加       500k", 500000, b_float)

    def b_call():
        def f(a, b):
            return a + b
        s = 0
        i = 0
        n = 200000
        while i < n:
            s = f(s, i)
            i += 1
        return s
    bench("函数调用       200k", 200000, b_call)

    def fib(n):
        if n < 2:
            return n
        return fib(n - 1) + fib(n - 2)
    bench("递归 fib(22)", 57491, lambda: fib(22))

    def b_list():
        a = []
        i = 0
        n = 100000
        while i < n:
            a.append(i)
            i += 1
        s = 0
        for v in a:
            s += v
        return s
    bench("列表建+遍历   100k", 100000, b_list)

    def b_dict():
        d = {}
        i = 0
        n = 100000
        while i < n:
            d[i] = i * 2
            i += 1
        s = 0
        for k in d:
            s += d[k]
        return s
    bench("字典写+读     100k", 100000, b_dict)

    def b_str():
        parts = []
        i = 0
        n = 20000
        while i < n:
            parts.append("item_" + str(i))
            i += 1
        return "_".join(parts)
    bench("字符串拼接     20k", 20000, b_str)

    def b_class():
        class P:
            def __init__(self, x):
                self.x = x

            def double(self):
                return self.x * 2
        s = 0
        i = 0
        n = 100000
        while i < n:
            p = P(i)
            s += p.double()
            i += 1
        return s
    bench("类实例+方法   100k", 100000, b_class)

    def b_fmt():
        s = ""
        i = 0
        n = 50000
        while i < n:
            s = f"{i}:{s}" if i % 10 == 0 else f"{i}"
            i += 1
        return len(s)
    bench("f-string 格式  50k", 50000, b_fmt)

    return out


async def main():
    screen = pygame.display.set_mode((800, 600))
    cjk = pygame.font.Font("cjk", 17)
    title = cjk.render("RustPython 本体性能基准（耗时 ms / 吞吐 ops/s）",
                       True, (255, 220, 120))
    hint = cjk.render("纯解释器基准——引擎调用不在统计内；结果同步打印 console",
                      True, (140, 140, 150))

    t_all0 = pygame.time.get_ticks()
    results = run_benches()
    total_ms = pygame.time.get_ticks() - t_all0
    print("[rp-bench] 总耗时", total_ms, "ms")
    for name, ms, rate in results:
        print(f"[rp-bench] {name}  {ms} ms  {rate} ops/s")

    # 结果行缓存（bench 一次，逐帧 blit 缓存面）
    lines = [cjk.render(f"{name}   {ms} ms   {rate:,} ops/s",
                        True, (210, 230, 210))
             for name, ms, rate in results]
    sum_line = cjk.render(f"合计 {total_ms} ms —— 数值越大越慢；对比 CPython 差距即移植成本",
                          True, (255, 170, 170))

    frame = 0
    fps = 0.0
    last = pygame.time.get_ticks()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        now = pygame.time.get_ticks()
        dt = now - last
        last = now
        if dt > 0:
            fps = fps * 0.9 + (1000.0 / dt) * 0.1

        with screen.render() as t:
            t.fill((16, 18, 26))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(14, 10, 0)); pygame.gfxdraw.draw_surface(t, title)
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(14, 36, 0)); pygame.gfxdraw.draw_surface(t, hint)
            y = 70
            for surf in lines:
                pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(24, y, 0)); pygame.gfxdraw.draw_surface(t, surf)
                y += 30
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(24, y + 6, 0)); pygame.gfxdraw.draw_surface(t, sum_line)
            bar = cjk.render(f"FPS {fps:.1f}", True, (150, 200, 255))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(660, 560, 0)); pygame.gfxdraw.draw_surface(t, bar)
        pygame.display.flip()
        frame += 1
        await pygame.next_frame()
