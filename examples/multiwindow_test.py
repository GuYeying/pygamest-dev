# multiwindow_test —— 多窗口案例（2026-11-16 第二批验收样张）：
# 主窗（set_mode）+ 副窗（create_window——windows-only，multi-window
# feature 白名单）。双窗同帧独立渲染（各窗独立会话/flip）；不支持
# 构建/平台 = create_window 抛 RuntimeError（前置断言）。600 帧自动
# 退；[multi-win] 逐项断言。
import pygame

MULTI = pygame.get_platform() == "windows"

async def main():
    pygame.display.set_caption("multiwindow_test")
    screen = pygame.display.set_mode((640, 480))
    cjk = pygame.font.Font("cjk", 15)
    ac = pygame.render.access()
    M = pygame.math
    frame = 0
    _fail = []

    def st(name, cond):
        if cond:
            print("[multi-win] PASS", name)
        else:
            _fail.append(name)
            print("[multi-win] FAIL", name)

    st(f"平台 = {pygame.get_platform()}", True)
    st(f"多窗预判（platform == windows）= {MULTI}", isinstance(MULTI, bool))

    if not MULTI:
        # 不支持构建/平台：create_window 必须抛 RuntimeError（用户定约
        # ——运行时检测抛错）；主窗独立跑一轮验证基线完好。
        try:
            pygame.display.create_window((300, 200), id="win2")
            st("不支持平台 create_window 抛错", False)
        except RuntimeError as e:
            st(f"不支持平台抛错（{str(e)[:24]}...）", True)
        print("[multi-win] SUMMARY",
              "PASS" if not _fail else "FAIL " + str(_fail))
        frame_cap = 120
    else:
        # ── 副窗（windows + multi-window feature）——会话面绘制
        # （raw overlay per-id 为 v2——文档标注）──
        win2 = pygame.display.create_window((320, 240), id="win2")
        st("create_window 副窗", win2 is not None)
        st("副窗 get_size = 320×240", tuple(win2.get_size()) == (320, 240))

        text_cache = {}

        def hud_text(s, color=(210, 214, 224)):
            if s not in text_cache:
                text_cache[s] = cjk.render(s, True, color)
            return text_cache[s]

        frame_cap = 600

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return

        # 主窗帧（标准会话）
        with screen.render() as rt:
            rt.fill((26, 32, 44))
            pygame.gfxdraw.set_transform(rt, M.mat4_translation(-300, 220, 0))
            pygame.gfxdraw.draw_surface(rt, hud_text(
                f"主窗 | 平台 {pygame.get_platform()} | 多窗={MULTI}"))

        if MULTI:
            # 副窗独立会话/flip（双窗同帧）——⚠️ gfxdraw 绘制面多窗 v2
            # （纹理 usage 冲突挂账：pygame_texture RESOURCE+COLOR_TARGET
            # 同 pass 冲突——render/fill/flip 已通）
            with win2.render() as rt:
                rt.fill((60, 30, 44))
            win2.flip()

        pygame.display.flip()
        frame += 1
        if frame == 30:
            print("[multi-win] SUMMARY",
                  "PASS" if not _fail else "FAIL " + str(_fail))
        if frame > frame_cap:
            return
        await pygame.next_frame()
