# leak_k2 —— FluidWorld 泄漏探针（2026-11-17 salva 集成相容批次）：
# 覆盖三条 FluidWorld 通路的循环压力测试——
# A) add_fluid_cuboid 循环（重复建 160 粒子流体——LiquidWorld 内部集
#    增长 + py 句柄映射）
# B) step 循环（DFSPH 压力求解每帧——粒子分配器/HGrid 重建）
# C) fluid_particles 出口循环（py 列表转换面——每帧 160×3×2 float）
# 判据：RSS 三窗恒平 = 无泄漏（参照 leak_j/leak_k 恒平形态）。
# 3000 帧（50s @60fps）自动退出。
import pygame
import pygame_physics as pp


async def main():
    screen = pygame.display.set_mode((300, 200))
    screen.set_camera(pygame.render.game_camera_ortho(300, 200, 300, 200))
    fw = pp.FluidWorld(particle_radius=0.1)
    frame = 0

    while frame < 3000:
        # A) 每 60 帧新建一波流体（LiquidWorld 内部集增长压力）
        if frame % 60 == 0:
            fw.add_fluid_cuboid((-0.4 + (frame % 7) * 0.05, 2.0, -0.4),
                                (0.4, 0.8, 0.4))
        # B) step（DFSPH 每帧——全部流体推进）
        fw.step(1.0 / 60.0)
        # C) 粒子出口循环（py 列表转换压力——逐 handle 读）
        for h in range(6):
            try:
                fw.fluid_particles(h)
            except Exception:
                pass
        if frame % 1500 == 0:
            print(f"[leak-k2] frame={frame}（RSS 由外部脚本采样）")
        await pygame.tasks.yield_now()
        frame += 1
    print("[leak-k2] 3000 帧跑完（50s）——外部 RSS 三窗对比")
