# tasks_min —— tasks 等待定约示范（RP 委派链恢复值坑规避）：
# spawn 任务的 **return 值会丢**（RP yield from 委派链恢复值传播坑，
# 恢复值恒 None）——**结果用引用承载**（hud 属性/全局容器/完成表），
# 轮询 done 后读引用；**不用 await t 取返回值**（委派形态炸
# NoneType not callable——挂账）。任务等待正道 = gather（任务表
# tick 驱动零委派，tasks_test 实证）。
import pygame

async def load_part(p):
    data = await pygame.io.fetch(p)
    return len(data)

async def main():
    pygame.display.set_mode((400, 300))
    pygame.io.write("assets/t.bin", bytes(20 * 1024 * 1024))
    got_box = []                          # 引用承载（不走 return）
    t = pygame.tasks.spawn(loader(got_box, "assets/t.bin"))
    for i in range(20):
        await pygame.tasks.sleep(0.2)
        if t.done:
            print("[m] done got =", got_box[0] if got_box else None,
                  "ex =", t.exception(), flush=True)
            break
    print("[m] DONE", flush=True)

async def loader(out, p):
    data = await pygame.io.fetch(p)
    out.append(len(data))
