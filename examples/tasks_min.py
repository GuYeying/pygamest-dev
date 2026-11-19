# tasks_min —— spawn 失败任务最小复现（失败存档/re-raise/命名）
import pygame

async def bad_load(res_name):
    await pygame.tasks.sleep(0.2)
    return "LOADED-" + res_name

async def main():
    pygame.display.set_mode((400, 300))
    t = pygame.tasks.spawn(bad_load("assets/hero.png"), "hero_load")
    await pygame.tasks.sleep(0.5)
    print("[min] gather form:", flush=True)
    r = await pygame.tasks.gather(bad_load("assets/hero.png"))
    print("[min] gather r =", r, flush=True)
    print("[min] t type =", type(t).__name__, flush=True)
    print("[min] t =", t, flush=True)
    print("[min] failed attr =", t.failed, flush=True)
    print("[min] failed() =", t.failed(), flush=True)
    print("[min] ex =", t.exception(), "name =", t.name, flush=True)
    try:
        await t.wait()
        print("[min] await ok (Task awaitable)", flush=True)
    except BaseException as e:
        print("[min] caught:", type(e).__name__, e, flush=True)
    print("[min] END", flush=True)
