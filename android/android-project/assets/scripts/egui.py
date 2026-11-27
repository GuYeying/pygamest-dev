# pure_examples/gui.py —— pygame_gui 全组件标准 showcase（标准 example
# 批次首件，2026-11-25；**纯手动**形态——2026-11-25 用户定夺：主题/页面
# 全手动切换，无自动巡检）：
# 六分页（selectable 侧栏）：基础 / 输入 / 数值 / 布局 / 主题 / 窗口模式
# ——全组件逐页；主题手动切换（set_theme + style_override 三预设 +
# style_reset，按钮即切）；窗口模式页 = window_mode_test 功能 API 全集
#（窗式 / 竖屏比例 / 横屏比例 / 横全屏 / 竖全屏——运行时 set_mode 重开
# 语义 + 像素相机跨画布重声明 + set_orientation）。
# 断言 = [gui-page] PASS/FAIL（回归网正典格式）：60 帧面板健康 +
# 各交互按钮触发即 mark。退出：ESC / 关窗。
import pygame
import pygame_gui as egui

FULLSCREEN = pygame.display.FULLSCREEN
MODES = [
    ("窗式 1280×800", (1280, 800), 0, "landscape"),
    ("竖屏比例", (450, 800), 0, "portrait"),
    ("横全屏", (0, 0), FULLSCREEN, "landscape"),
    ("竖全屏", (0, 0), FULLSCREEN, "portrait"),
]
PAGES = ("基础", "输入", "数值", "布局", "主题", "窗口模式")
FONT_SCALE = 1.4   # 全局字阶（set_font_scale——UI 整体变大，矢量无损）


class App(egui.UiBase):
    def __init__(self):
        # 基础
        self.page = 0
        self.clicks = 0
        self.checked = True
        self.sel = False
        # 输入
        self.name = "玩家"
        self.password = "secret"
        self.mline = "多行文本\n第二行"
        self.mode = 1
        self.combo = 1
        # 数值
        self.gravity = 9.8
        self.speed = 1.0
        self.n = 5
        self.frac = 0.0
        self.color = (120, 160, 220, 255)
        self.range = (0.0, 10.0)
        self.date = (2026, 11, 25)
        # 主题
        self.theme = "dark"
        self.font_scale = FONT_SCALE
        # 窗口模式
        self.wm = 0
        self.wm_want = -1
        self.info = "窗式 1280×800"
        self.cur_size = (1280, 800)
        # 健康账本
        self.fails = []

    def mark(self, name, cond=True):
        if not cond:
            self.fails.append(name)
        print(f"[gui-page] {'PASS' if cond else 'FAIL'} {name}")

    def draw(self, ui):
        # ── 侧栏分页（selectable 行 + horizontal 布局）──
        with ui.horizontal():
            for i, p in enumerate(PAGES):
                if ui.selectable(p, self.page == i):
                    self.page = i
        ui.separator()

        if self.page == 0:
            # ═══ 基础控件 ═══
            ui.heading("heading 标题")
            ui.small_heading("small_heading 小标题")
            ui.strong("strong 加粗文本")
            ui.label("label 普通文本")
            ui.monospace("monospace 等宽 0O l1I")
            ui.colored("colored 彩色文本", 255, 180, 90)
            ui.hyperlink("hyperlink 超链接", "https://example.com")
            ui.separator()
            if ui.button("button 按钮"):
                self.clicks += 1
            ui.label(f"点击数 = {self.clicks}")
            self.checked = ui.checkbox("checkbox 复选框", self.checked)
            if ui.selectable("selectable 可选行", self.sel):
                self.sel = not self.sel
            ui.separator()
            ui.collapsing("collapsing 折叠头", True,
                          lambda inner: inner.label("折叠内容"))
            with ui.horizontal():
                ui.spinner(16)
                ui.label("spinner 转圈指示")

        elif self.page == 1:
            # ═══ 输入 ═══
            ui.heading("输入")
            self.name = ui.text_edit(self.name)
            ui.label(f"单行内容 = {self.name}")
            self.password = ui.password(self.password)
            ui.label(f"密码长度 = {len(self.password)}")
            self.mline = ui.text_edit_multiline(self.mline)
            ui.separator()
            self.mode = ui.radio_group(("简单", "普通", "困难"), self.mode)
            ui.label(f"radio 选中 = {self.mode}")
            self.combo = ui.combo_box("combo_box 下拉",
                                      ("方案 A", "方案 B", "方案 C"), self.combo)
            ui.label(f"combo 选中 = {self.combo}")

        elif self.page == 2:
            # ═══ 数值 ═══
            ui.heading("数值")
            self.gravity = ui.slider_f32("slider_f32 重力", self.gravity, 0.0, 20.0)
            self.n = ui.slider_int("slider_int 数量", self.n, 0, 100)
            ui.separator()
            self.speed = ui.drag_f32("drag_f32 速度", self.speed, 0.05, 0.0, 5.0)
            self.n = ui.drag_int("drag_int 整数", self.n, 1, 0, 100)
            ui.label(f"drag 联动值 = {self.n}")
            ui.separator()
            self.frac = self.frac + 0.005 if self.frac < 1.0 else 0.0
            ui.progress_bar(self.frac)
            ui.separator()
            r0, r1 = self.range
            self.range = ui.range_slider_f32("range_slider 区间", r0, r1, 0.0, 20.0)
            ui.label(f"区间 = [{self.range[0]:.1f}, {self.range[1]:.1f}]（界 0..20）")
            self.date = ui.date_picker(*self.date)
            ui.label(f"日期 = {self.date[0]}-{self.date[1]:02d}-{self.date[2]:02d}（点击弹框）")
            ui.separator()
            r, g, b, a = self.color
            self.color = ui.color_edit(r, g, b, a)
            ui.colored("color_edit 联动色样（非预乘；含 blending 选择）",
                       r, g, b, a)

        elif self.page == 3:
            # ═══ 布局 ═══
            ui.heading("布局")
            ui.label("horizontal 同行三兄弟：")
            with ui.horizontal():
                ui.label("甲")
                ui.button("乙")
                ui.label("丙")
            ui.add_space(8)
            ui.label("vertical 纵排：")
            with ui.vertical():
                ui.label("上")
                ui.label("中")
                ui.label("下")
            ui.separator()
            ui.group(lambda inner: inner.label("group 边框组"))
            ui.separator()
            ui.collapsing("collapsing 布局折叠", False,
                          lambda inner: inner.label("展开后的内容"))
            # scroll_area（仅回调形态——clip 同步约束）
            ui.scroll_area(
                lambda inner: [inner.label(f"滚动行 {i}") for i in range(30)])

        elif self.page == 4:
            # ═══ 主题（**纯手动**——按钮即切，无自动巡检）═══
            ui.heading("主题")
            ui.label(f"当前主题 = {self.theme}")
            if ui.button("切换 dark / light"):
                self.theme = "light" if self.theme == "dark" else "dark"
                self.mark(f"set_theme({self.theme})", egui.set_theme(self.theme))
            ui.separator()
            # ── 全局字阶（set_font_scale——五档文本样式全乘，控件随文本
            #    自适配；UI 整体变大变小的正解）──
            self.font_scale = ui.slider_f32(
                "字体/UI 缩放 (set_font_scale)", self.font_scale, 1.0, 2.5)
            egui.set_font_scale(self.font_scale)
            ui.label(f"字阶 = {self.font_scale:.2f}（整体变大变小 · 矢量无损 · 1.0 还原）")
            ui.separator()
            ui.strong("完全定制主题（style_override kwargs 任意子集）：")
            with ui.horizontal():
                if ui.button("① 蓝紫圆角"):
                    self.mark("定制①", egui.style_override(
                        accent=(90, 160, 255, 255),
                        bg=(24, 22, 44, 255),
                        rounding=12.0,
                        item_spacing=(10, 8),
                        button_padding=(14, 6),
                        font_size=16.0))
                if ui.button("② 翠绿紧凑"):
                    self.mark("定制②", egui.style_override(
                        accent=(40, 200, 120, 255),
                        bg=(16, 34, 24, 255),
                        rounding=4.0,
                        item_spacing=(6, 4),
                        button_padding=(8, 3),
                        font_size=13.0))
                if ui.button("③ 暖橙大字"):
                    self.mark("定制③", egui.style_override(
                        accent=(255, 150, 60, 255),
                        rounding=18.0,
                        font_size=20.0))
                if ui.button("④ style_reset 归零"):
                    egui.style_reset()
                    self.mark("style_reset")
            ui.small_heading("（accent=强调色 bg=面板底色 rounding=圆角 "
                             "item_spacing/button_padding=间距 font_size=字号）")

        else:
            # ═══ 窗口模式（window_mode_test 功能 API 全集）═══
            ui.heading("窗口模式")
            for i, (name, _sz, _fl, _o) in enumerate(MODES):
                checked = ui.checkbox(name, self.wm == i)
                if checked and self.wm != i:
                    self.wm_want = i
                    self.wm = i
            ui.separator()
            ui.label(self.info)
            ui.label(f"logical = {self.cur_size[0]}×{self.cur_size[1]}")
            ui.label("窗式/比例 = 运行时 set_mode 重开；全屏 = FULLSCREEN 旗标")
            ui.label("横竖屏 = set_orientation（桌面窗口跟随比例重开）")
            ui.label("像素相机跨画布**不跟随**——每切必重声明（v3.1 定约）")


async def main():
    pygame.display.set_caption("gui —— 全组件标准 showcase")
    screen = pygame.display.set_mode((1280, 800), gui=True)
    screen.set_camera(pygame.render.game_camera_ortho(1280, 800, 1280, 800))
    egui.set_font_scale(FONT_SCALE)   # 全局字阶（启动即放大——矢量无损）
    app = App()
    applied = 0
    frame = 0

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return
            egui.event(e)

        # ── 窗口模式应用（会话块外——display 可重开语义）──
        if app.wm_want >= 0:
            name, size, flags, orient = MODES[app.wm_want]
            try:
                pygame.display.set_orientation(orient)
            except Exception as ex:
                print("[gui-page] set_orientation:", ex)
            screen = (pygame.display.set_mode(size, [flags]) if flags
                      else pygame.display.set_mode(size))
            # 像素相机重声明（跨画布相机不跟随——window_mode_test 定约）
            screen.set_camera(pygame.render.game_camera_ortho(
                size[0], size[1], size[0], size[1]))
            applied += 1
            app.info = f"mode = {name}（应用 {applied} 次）"
            app.mark(f"窗口模式应用 {name}")
            app.wm_want = -1

        # 健康断言（60 帧一次——draw 链无异常即 PASS；无视觉副作用）
        if frame == 60:
            app.mark("60 帧面板绘制无异常", not app.fails)

        with screen.render() as t:
            t.fill((30, 32, 40))
            t.draw_ui(app)
            _mp = pygame.mouse.get_pos()
            pygame.gfxdraw.draw_batch(t, pygame.gfxdraw.gen_circle(12), color=(255, 0, 0), transform=pygame.math.mat4_translation(_mp[0], _mp[1], 0))
        app.cur_size = screen.get_size()
        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1
