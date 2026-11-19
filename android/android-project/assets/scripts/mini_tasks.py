import pygame

async def bg():
    n = 0
    while n < 30:
        await pygame.next_frame()
        n += 1
    print("[mini] bg done, frame =", pygame.tasks.frame())

async def main():
    pygame.display.set_mode((300, 200))
    T = pygame.tasks
    tk = T.spawn(bg())
    for i in range(8):
        await pygame.tasks.sleep(0.1)
        print(f"[mini] f={T.frame()} task.done={tk.done}")
    print("[mini] DONE")

async def _m():
    pass
