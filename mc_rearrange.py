# 程序化重排：voxel_mc_async.py 主循环 → logic/render 双协程
# 用法：target/debug/python.exe mc_rearrange.py（引擎 io 模块读写）
import pygame

SRC = 'examples/voxel_mc_async.py'
L = pygame.io.read(SRC).decode('utf-8').splitlines(keepends=True)
print('TOTAL', len(L))

head, seg1, seg2, seg3, seg4 = L[:556], L[556:676], L[676:722], L[722:744], L[744:766]
print('SEG', len(seg1), len(seg2), len(seg3), len(seg4))

def ind4(lines):
    return [('    ' + l) if l.strip() else l for l in lines]

out = ''.join(head)
out += "    # ── 异步双协程拆分（设计定约 2026-11-22）──────────────────\n"
out += "    # logic = 事件/漫游/物理 accumulator/交互；render = 绘制/flip/限帧\n"
out += "    # 帧泵统一推进（协作式）；让出原语改名后 = tasks.yield_now()\n"
out += "    # 共享状态经闭包（单线程协作式，零竞态）────────────────────\n"
out += "    async def logic_task():\n"
out += "        nonlocal grabbed, last_pos, info, debug_on, fluid_on\n"
out += "        nonlocal fluid_world, fluid_fh, frame\n"
out += "        while True:\n"
out += ''.join(ind4(seg1[1:]))
out += ''.join(ind4(seg3))
out += "            await pygame.next_frame()   # 让出（改名后 tasks.yield_now）\n\n"
out += "    async def render_task():\n"
out += "        while True:\n"
out += ''.join(ind4(seg2))
out += ''.join(ind4(seg4))
out += "            await pygame.next_frame()   # 让出（改名后 tasks.yield_now）\n\n"
out += "    pygame.tasks.spawn(logic_task())\n"
out += "    pygame.tasks.spawn(render_task())\n"
out += "    while True:                          # 保活泵（任务帧泵自动推进）\n"
out += "        for e in pygame.event.get():\n"
out += "            if e.type == pygame.event.QUIT:\n"
out += "                return\n"
out += "        await pygame.next_frame()\n"

pygame.io.write(SRC, out.encode('utf-8'))
print('WRITTEN', len(out.splitlines()), 'lines')
