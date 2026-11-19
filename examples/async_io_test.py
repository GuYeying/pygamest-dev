# async_io_test —— tasks 异步加载 vs 阻塞加载 A/B 对照（FPS 视觉验收）：
# 8 个 2MB 分片文件（启动时生成）——阻塞按钮 = 依次同步全读（画面冻结
# 到读完）；异步按钮 = tasks.spawn 分帧协程（每帧读一片 + await 挂起，
# 画面持续推进）。egui 输入相对路径（默认分片 0）+ FPS/耗时/进度全显
# 示——分帧协程的"加载期间画面不冻结"直观验收。
import pygame
import pygame_gui as egui
_stopwatch = pygame.io.read_text is not None  # 探针占位

class SW:
    def __init__(self): self.t0 = pygame.time.get_ticks()
    def ms(self): return pygame.time.get_ticks() - self.t0

PARTS = 8
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
    screen = pygame.display.set_mode((800, 600))
    screen.set_camera(pygame.render.game_camera_ortho(800, 600, 800, 600))
    egui.init()
    cjk = pygame.font.Font("cjk", 15)

    # ── 测试分片生成（启动一次——8×16MB 全零，write 覆盖幂等）──
    big_path = "assets/big_single.bin"
    if not pygame.io.exists(big_path):
        pygame.io.write(big_path, bytes(BIG_BYTES))   # 128MB 全零单文件

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

              "dt =", round(dt, 1), flush=True)
        # 应用按钮请求（会话块外）
        if hud.want == "async" and job is None:
            hud.want = None
            hud.state = "异步中"
            job = pygame.tasks.spawn(chunk_loader([hud.path], hud))
        elif hud.want == "blocking":
            hud.want = None
            hud.state = "阻塞中（画面冻结）"
            t0 = SW()
            for p in [hud.path]:
                pygame.io.read(p)          # 同步全读——画面冻结
            blocking_ms = t0.ms()
            if blocking_ms > max_dt:
                max_dt = blocking_ms       # 冻结段计入最大帧间
            hud.state = "阻塞完成"
            hud.info = f"阻塞加载耗时 {blocking_ms:.0f} ms（期间画面冻结、FPS=0）"

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
                done_parts = int(hud.state.split("|")[1])
                w = int(500 * done_parts / PARTS)
                pygame.gfxdraw.set_color(t, (80, 200, 140))
                pygame.gfxdraw.box(t, (-250, -180, w, 24))
            pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(0, 0, 0))

            # egui 面板（输入路径 + 按钮）
            t.draw_ui(hud)

        pygame.display.flip()
        await pygame.next_frame()
        frame += 1


async def chunk_loader(paths, hud):   # paths = [单文件]（fetch 内部分块）
    # 分帧加载协程：每帧读一片 + await 挂起——画面持续推进
    t0 = SW()
    got = 0
    for p in paths:
        data = await pygame.io.fetch(p)   # 挂起一帧（本片读 16MB）
        got += len(data)
        hud.state = f"异步中|{i + 1}"
        await pygame.next_frame()
    return t0.ms(), got
