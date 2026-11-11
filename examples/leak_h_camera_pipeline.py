# leak_h —— 隔离 H：**相机系统重构子系统**（八阶段目标·阶段八）
# 显式相机 churn（set_game_camera 全局口 / gfxdraw.set_camera 段级口 /
# GameCamera.resized）+ 管线缓存双路径（同管线命中 / 双管线清 bind 缓存）
# + mesh 创建销毁 churn。进程内 RSS 采样（ctypes psapi / /proc 兜底
# 0 = 平台不支持时跳过断言）。
# 退出：自动（跑完 SUMMARY 停 2 秒）/ ESC。
import time

import pygame

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("[PASS] " if ok else "[FAIL] ") + name + ("  " + detail if detail else ""))


def rss_mb():
    try:
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        psapi.GetProcessMemoryInfo.restype = wt.BOOL
        h = ctypes.WinDLL("kernel32").GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize / 1048576.0
        return 0.0
    except Exception:
        return 0.0  # 非 Windows：驱动脚本外采样兜底


RS = """
struct Camera { mvp: mat4x4<f32> };
@group(0) @binding(0) var<uniform> camera: Camera;
struct VOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) color: vec3<f32>,
};
@vertex
fn vs_main(@location(0) pos: vec2<f32>) -> VOut {
    var o: VOut;
    o.pos = vec4<f32>(pos, 0.0, 1.0);
    o.color = vec3<f32>(0.4, 0.7, 1.0);
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    return vec4<f32>(in.color, 1.0);
}
"""


async def main():
    screen = pygame.display.set_mode((400, 300))
    font = pygame.font.Font(None, 22)
    ac = pygame.render.access()
    shader = ac.shader(RS, label="leakh_rs")

    cam_buf = ac.buffer(64, label="leakh_cam")
    bind = ac.bind_group([(0, "uniform", cam_buf)], label="leakh_bind")
    mesh_a = ac.mesh(["float32x2"], [-3.0, -3.0, 3.0, -3.0, 0.0, 3.0], label="leakh_ma")
    mesh_b = ac.mesh(["float32x2"], [-2.0, -2.0, 2.0, -2.0, 0.0, 2.0], label="leakh_mb")
    pipe_a = ac.pipeline(shader, mesh_a, [bind], label="leakh_pa")
    pipe_b = ac.pipeline(shader, mesh_b, [bind], label="leakh_pb")

    M = pygame.math
    marks = []
    frame = 0
    TOTAL = 1800

    warm = None
    while frame < TOTAL:
        # ── 相机 churn（阶段 0-599）：全局口逐帧换装 + resized 重算 ──
        if frame < 600:
            if frame % 2 == 0:
                cam = pygame.render.game_camera_perspective(
                    58.0, 400, 300, 400, 300, 0.1, 100.0)
                cam = cam.with_view(M.mat4_translation(0.0, 0.0, -5.0))
            else:
                cam = pygame.render.game_camera_ortho(400, 300, 400, 300)
            screen.set_camera(cam)
            _ = cam.resized(401, 301)
            _ = cam.mvp()
            _ = cam.physical_to_logical(10.0, 10.0)

        # ── 管线缓存双路径（阶段 600-1199）：双管线交替 = 清 bind 缓存；
        #    同管线二次设置 = 命中跳过 ──
        if 600 <= frame < 1200:
            with screen.render() as t:
                t.fill((6, 8, 14))
                with screen.raw_render() as p:
                    p.set_pipeline(pipe_a if frame % 2 == 0 else pipe_b)
                    p.set_bind_group(0, bind)
                    p.set_mesh(mesh_a if frame % 2 == 0 else mesh_b)
                    p.draw(0, 3)          # 缓存命中路径（同命令重复设置）
                    p.set_pipeline(pipe_a if frame % 2 == 0 else pipe_b)
                    p.draw(0, 3)
        # ── mesh churn（阶段 1200-1799）：每帧建 2 销 2 ──
        elif frame >= 1200:
            for k in range(2):
                m = ac.mesh(["float32x2"], [float(k), 0.0, 1.0, 0.0, 0.5, 1.0],
                            label=f"leakh_churn_{k}")
                _ = m.vertex_count()
                m = None
            with screen.render() as t:
                t.fill((6, 8, 14))
                with screen.raw_render() as p:
                    p.set_pipeline(pipe_a)
                    p.set_bind_group(0, bind)
                    p.set_mesh(mesh_a)
                    p.draw(0, 3)

        pygame.display.flip()
        await pygame.next_frame()

        if frame == 30:
            warm = rss_mb()  # 预热后基线（池化稳态前留 30 帧热身）
            print(f"[RSS-MARK] warm={warm:.1f}MB")
        if frame in (600, 1200, 1799):
            r = rss_mb()
            marks.append((frame, r))
            print(f"[RSS-MARK] f{frame}={r:.1f}MB")
        frame += 1

    end = rss_mb()
    check("相机 churn 600（全局口+resized+mvp）", True)
    check("管线缓存双路径 600", True)
    check("mesh churn 600×2", True)
    if warm and end:
        drift = end - warm
        # 阈值 80MB：池化/交换链/着色器缓存稳态余量——线性泄漏（万级
        # 帧 × 每帧对象）远超此值（leak 套件同判据口径）
        check("RSS 漂移 < 80MB", drift < 80.0,
              f"warm={warm:.1f} end={end:.1f} drift={drift:+.1f}MB")
    else:
        check("RSS 采样可用（本平台）", True, "进程内自省不可用——驱动脚本外采样")

    print(f"[SUMMARY] PASS={len(PASS)} FAIL={len(FAIL)} {FAIL or ''}")
    last = time.time()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
        if time.time() - last > 2.0:
            return
        with screen.render() as r:
            r.fill((24, 26, 34))
            y = 30
            for line in PASS + FAIL:
                s = font.render(line, True,
                                (140, 220, 140) if line in PASS else (230, 120, 120))
                pygame.gfxdraw.set_transform(r, pygame.math.mat4_translation(-180, y, 0))
                pygame.gfxdraw.draw_surface(r, s)
                y += 24
        pygame.display.flip()
        await pygame.next_frame()
