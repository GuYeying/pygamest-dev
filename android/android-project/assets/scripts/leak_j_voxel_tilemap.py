# leak_j —— 新模块泄漏探针（2026-11-16 批次相容测试）：
# 判据：PYGAMEST_MEMTRACE=1 下 live_alloc/live_bytes 线性涨 = 泄漏；
# RSS 恒平/边际递减 = 池化稳态。覆盖四条新通路：
# A) voxelis：set/remove 循环 + generate_mesh 重建（interner/树节点
#    回收验证——air prune 后 mesh 数组重建）
# B) tilemap：Tilemap 重复解析（TMX 解析器 + Map 泄漏）+ layer_mesh
#    重建循环（py 列表转换面）
# C) mesh index 新口：update_mesh_index_bytes 循环（索引缓冲复用）
# D) GameCamera with_view 链（Mat4 每帧新对象——py/Rust 两侧回收）
# 9000 帧（150s @60fps）后自动退出；[leak-j] 打 RSS 锚点。
import pygame
import pygame_voxelis
import pygame_tilemap
import pygame_physics as rp3

TMX = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<map version="1.10" orientation="orthogonal" renderorder="right-down" '
    'width="8" height="8" tilewidth="32" tileheight="32" '
    'infinite="0" nextlayerid="2" nextobjectid="1">'
    '<tileset firstgid="1" name="t" tilewidth="32" tileheight="32" '
    'tilecount="4" columns="4">'
    '<image source="atlas.png" width="128" height="32"/></tileset>'
    '<layer id="1" name="ground" width="8" height="8">'
    '<data encoding="csv">1,2,3,4,1,2,3,4,1,2,3,4,1,2,3,4,1,2,3,4,1,2,3,4,'
    '1,2,3,4,1,2,3,4,1,2,3,4,1,2,3,4,1,2,3,4,1,2,3,4,1,2,3,4,1,2,3,4,'
    '1,2,3,4,1,2,3,4</data></layer></map>'
)


async def main():
    screen = pygame.display.set_mode((400, 300))
    ac = pygame.render.access()
    frame = 0

    # 预置：体素世界 + TMX 文件 + 相机 uniform
    vw = pygame_voxelis.VoxWorld(4, 16.0)
    pygame.io.write_text("leak_j.tmx", TMX)
    cam_buf = ac.buffer(64, label="cam_buf")
    mesh = ac.mesh(["float32x2"], [0.0, 0.0, 1.0, 0.0, 1.0, 1.0],
                   indices=[0, 1, 2, 0, 2, 1], label="idx_mesh")
    cam = pygame.render.game_camera_ortho(400, 300, 400, 300)
    screen.set_camera(cam)

    while frame < 9000:
        # A) voxelis 编辑/remesh 循环（每 10 帧一轮——mesh 数组重建）
        if frame % 10 == 0:
            vwx = frame // 10 % 16
            vw.set_voxel(vwx, 0, 0, 1 + (frame // 10) % 4)
            vw.generate_mesh()
            vw.remove_voxel(vwx, 0, 0)
            vw.generate_mesh()
        # B) tilemap 解析 + layer_mesh 循环（每 30 帧一轮）
        if frame % 30 == 0:
            tm = pygame_tilemap.Tilemap("leak_j.tmx")
            tm.layer_mesh(0)
            tm.layer_tiles(0)
        # C) 索引缓冲原始字节更新循环（每帧——u16 复用路径）
        if frame % 5 == 0:
            ac.update_mesh_index_bytes(
                mesh, bytes((0, 1, 0, 2, 0, 1, 0, 2, 0, 1, 0, 2) if frame % 10 else (0, 0, 2, 0, 0, 1, 0, 0, 2, 0, 1, 2)))
        # D) GameCamera with_view 链（每帧——Mat4 新对象）
        cam = cam.with_view(pygame.math.mat4_from_cols_array(
            [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]))
        pygame.render.write_camera_mvp(cam_buf, cam.mvp())

        with screen.render() as rt:
            rt.fill((18, 20, 28))
        pygame.display.flip()
        if frame % 1500 == 0:
            import sys
            try:
                import resource  # unix
                rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                print(f"[leak-j] frame={frame} rss={rss}KB")
            except Exception:
                print(f"[leak-j] frame={frame}（RSS 由外部脚本采样）")
        await pygame.tasks.yield_now()
        frame += 1
    print("[leak-j] 9000 帧跑完（150s）——外部 RSS 对比 0 帧/4500 帧/9000 帧")
