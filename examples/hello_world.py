
import pygame

async def main():

    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 32)

    hello_world_text = font.render("Hello Wrold!", True, (255, 255, 255))

    clock = pygame.time.Clock()

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        with screen.render() as r:
            pygame.gfxdraw.set_pos(r, 325, 275); pygame.gfxdraw.draw_surface(r, hello_world_text)

        clock.tick(60)

        pygame.display.flip()

        await pygame.next_frame()
