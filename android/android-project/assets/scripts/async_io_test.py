# async_io_test —— tasks 异步加载 vs 阻塞加载 A/B 对照（FPS 视觉验收）：
# 128MB 单文件（native 启动时生成 / wasm build.py 预置）——阻塞按钮 =
# 同步全读（画面冻结到读完）；异步按钮 = tasks.spawn 分帧协程（native
# 每帧读 8MB 块 + await 挂起；wasm io_size None 退化 fetch 全量——网络
# 层流式不卡帧）。egui 输入相对路径 + FPS/耗时/进度全显示——分帧协程
# 的"加载期间画面不冻结"直观验收。
import pygame
import pygame_gui as egui
_stopwatch = pygame.io.read_text is not None  # 探针占位

class SW:
    def __init__(self): self.t0 = pygame.time.get_ticks()
    def ms(self): return pygame.time.get_ticks() - self.t0

PARTS = 16                     # 128MB / 8MB 块 = 16 帧（wasm = 1 次 fetch 全量）
BIG_BYTES = 128 * 1024 * 1024  # 单文件 128MB（fetch 自动分块流式 v3.1）


class Hud(egui.UiBase):
    def __init__(self):
        self.path = "assets/big_part"
        self.state = "待机"
        self.info = "选按钮开始对照"
        self.want = None
        self.async_ms = -1.0

    def draw(self, ui):
        ui.heading("异步 IO A/B 对照（tasks 分帧 vs 同步阻塞）")
        self.path = ui.text_edit(self.path)
        if ui.button("① 异步加载（tasks 分帧）"):
            self.want = "async"
        if ui.button("② 阻塞加载（同步读）"):
            self.want = "blocking"
        ui.label(f"状态: {self.state}")
        ui.label(self.info)


async def main():
    pygame.display.set_caption("async_io_test")
    screen = pygame.display.set_mode((800, 600), gui=True)
    screen.set_camera(pygame.render.game_camera_ortho(800, 600, 800, 600))
    cjk = pygame.font.Font("cjk", 15)

    # ── 测试分片生成（启动一次——8×16MB 全零，write 覆盖幂等）──
    big_path = "assets/big_single.bin"
    if not pygame.io.exists(big_path):
        # 生成段 try/except（**wasm 退化**——io.write 的 wasm 分支 Err，
        # 无法同步生成大文件：wasm 的测试文件由 build.py 预置到
        # web/assets，fetch 同 origin 下载承载）
        try:
            pygame.io.write(big_path, bytes(BIG_BYTES))   # 128MB 全零单文件
        except Exception as ex:
            print("[aiot] 大文件生成跳过（wasm/只读承载）:", ex, flush=True)

    hud = Hud()
    hud.path = "assets/big_single.bin"

    frame = 0
    fps_ms = 16.7
    last_ms = 0.0
    job = None
    max_dt = 0.0
    blocking_ms = -1.0
    async_ms = -1.0

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_a:
                hud.want = "async"
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_b:
                hud.want = "blocking"
            if e.type == pygame.event.QUIT:
                return
            egui.event(e)

        # 帧间 ms（FPS 口径）+ 最大帧间（卡帧判据——>50 = 有冻结）
        now = SW()
        dt = now.ms() - last_ms
        last_ms = now.ms()
        if dt > 0.5:
            fps_ms = fps_ms * 0.8 + dt * 0.2   # 平滑
            if dt > max_dt:
                max_dt = dt

        if frame == 220:
            pygame.render.set_fb_dump(False)  # B1 取证定格（阻塞完成帧）

        # 自动演示序列（frame 驱动——零输入依赖：阻塞 → 异步）
        if frame == 180:
            hud.want = "blocking"
        if frame == 400:
            hud.want = "async"

        # 应用按钮请求（会话块外）
        if hud.want == "async" and job is None:
            hud.want = None
            hud.state = "异步中"
            job = pygame.tasks.spawn(chunk_loader(hud.path, hud))
        elif hud.want == "blocking":
            hud.want = None
            hud.state = "阻塞中（画面冻结）"
            t0 = SW()
            pygame.io.read(hud.path)          # 同步全读——画面冻结
            blocking_ms = t0.ms()
            if blocking_ms > max_dt:
                max_dt = blocking_ms       # 冻结段计入最大帧间
            hud.state = "阻塞完成"
            hud.info = f"阻塞加载耗时 {blocking_ms:.0f} ms（期间画面冻结、FPS=0）"
            print("[aiot] blocking_ms =", blocking_ms, flush=True)  # 结果输出（wasm 画面文字难截读——console 为准）

        # 异步任务收割（耗时读 hud.async_ms——**不碰 job.result**，
        # RP 委派链恢复值坑定约）
        if job is not None and job.done:
            job = None
            async_ms = hud.async_ms
            hud.state = "异步完成"
            hud.info = (f"异步加载总耗时 {async_ms:.0f} ms（分 {PARTS} 帧——"
                        f"期间 FPS 未归零）")

        with screen.render() as t:
            t.fill((14, 16, 24))
            # 大字 FPS（帧间 ms 越大 = 越卡）
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-330, 270, 0))
            pygame.gfxdraw.draw_surface(t, cjk.render(
                f"FPS ≈ {1000.0 / max(fps_ms, 0.01):.0f}  帧间 {fps_ms:.1f}ms  最大 {max_dt:.0f}ms",
                True, (255, 230, 120) if fps_ms > 40 else (150, 230, 150)))

            # 耗时对照
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-330, 240, 0))
            b_txt = f"阻塞加载: {blocking_ms:.0f} ms（画面冻结）" if blocking_ms >= 0 else "阻塞加载: 未测"
            pygame.gfxdraw.draw_surface(t, cjk.render(b_txt, True, (250, 160, 140)))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-330, 214, 0))
            a_txt = f"异步加载: {async_ms:.0f} ms（分 {PARTS} 帧，画面流畅）" if async_ms >= 0 else "异步加载: 未测"
            pygame.gfxdraw.draw_surface(t, cjk.render(a_txt, True, (140, 230, 180)))

            # 进度条（异步中）
            if "异步中" in hud.state and "|" in hud.state:
                done_pct = int(hud.state.split("|")[1])
                w = int(500 * done_pct / 100)
                pygame.gfxdraw.set_color(t, (80, 200, 140))
                pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-250 + w // 2, -168, 0))
                pygame.gfxdraw.push(t, pygame.gfxdraw.gen_rect(w, 24))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(0, 0, 0))

            # egui 面板（输入路径 + 按钮）
            t.draw_ui(hud)

        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1


async def chunk_loader(path, hud):
    # **coroutine 形态**（无裸 yield——async gen 在 RP 驱动有病态）：
    # native = io_size 分块判定 + io_read_chunk 同步区间读（每帧一块，
    # 块级毫秒级不超帧预算）+ await tasks.yield_now 挂起交出控制权——画面
    # 持续推进；wasm = io_size None（fetch 全量承载定约）→ await
    # io.fetch 全量退化（网络层流式不卡帧）+ 完成表 io_take 直取
    t0 = SW()
    total = pygame.io.io_size(path)
    if total is None:
        await pygame.io.fetch(path)          # wasm：fetch 全量（挂起至入表）
        pygame.io.io_take(path)              # 完成表直取（委派链 return 丢规避）
        hud.state = "异步中|100"
    else:
        off = 0
        chunk = 8 * 1024 * 1024
        while off < total:
            n = min(chunk, total - off)
            pygame.io.io_read_chunk(path, off, n)
            off += n
            hud.state = f"异步中|{off * 100 // total}"
            await pygame.tasks.yield_now()        # 挂起一帧（画面推进）
    hud.async_ms = t0.ms()
    print("[aiot] async_ms =", hud.async_ms, flush=True)       # 结果输出（wasm 画面文字难截读——console 为准）
