# settings_probe —— SurfaceSettings/GpuSettings py 面冒烟 + 运存对照
# （2026-11-16 批次）：省内存形态（memory_usage hints + low_power +
# 单帧交换链）跑 hello 同款负载——控制台打 API 断言；外部脚本采样
# WorkingSet 对比基线（默认形态 debug ≈ 513MB）。
import pygame


async def main():
    gpu = pygame.render.GpuSettings(
        memory_hints="memory_usage",
        power_preference="low_power",
    )
    surf = pygame.render.SurfaceSettings(desired_maximum_frame_latency=1)
    print("[settings-probe] 构造 OK")

    screen = pygame.display.set_mode(
        (800, 600), gpu_settings=gpu, surface_settings=surf)
    screen.set_camera(pygame.render.game_camera_ortho(800, 600, 800, 600))
    print("[settings-probe] set_mode kwargs 透传 OK")

    font = pygame.font.Font(None, 32)
    text = font.render("memory_usage + low_power + latency=1", True, (255, 255, 255))

    frame = 0
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        with screen.render() as r:
            r.fill((30, 34, 44))
            pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(-180, 20, 0))
            pygame.gfxdraw.draw_surface(r, text)
        pygame.display.flip()
        frame += 1
        if frame == 3000:      # 15s @60fps——外部采样窗口
            print("[settings-probe] 3000 帧跑完，正常退出")
            return
        await pygame.tasks.yield_now()
