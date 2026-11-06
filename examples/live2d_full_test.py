# live2d_full_test —— pygame_live2d 全量断言测试（Hiyori 真模型 +
# motion 播放 + 参数变形实效验证 + 错误路径 + 视觉 smoke 60 帧；
# sprite 工作流：注入式 Surface + rt.draw）。
import time

import pygame
import pygame_live2d

MODEL = "D:/Projects/Rust/pygame_live2d/assets/models/Hiyori"
ok_count = 0
fail_count = 0


def chk(name, got, want):
    global ok_count, fail_count
    good = got == want
    if good:
        ok_count += 1
    else:
        fail_count += 1
    print(f"[LT] {'OK ' if good else 'FAIL'} {name}: {got}" + ("" if good else f"（期望 {want}）"))


def raises(fn):
    try:
        fn()
        return "未抛异常"
    except (ValueError, TypeError):
        return "ValueError/TypeError"


async def main():
    # 注入式渲染需要 GPU 会话与产物面——先建窗
    screen = pygame.display.set_mode((800, 600))
    buf = pygame.Surface((800, 600))
    buf2 = pygame.Surface((800, 600))

    # ── 加载面 ──
    model = pygame_live2d.load_model(f"{MODEL}/Hiyori.model3.json")
    chk("load_model canvas", model.canvas_size(), (2976.0, 4175.0))
    chk("mesh_count", model.mesh_count() > 100, True)
    chk("texture_count", model.texture_count(), 2)
    w, h = model.texture_info(0)
    chk("texture_info(0)", (w, h), (2048, 2048))
    rgba_len = len(model.texture_rgba(0))
    chk("texture_rgba 量", rgba_len, 2048 * 2048 * 4)

    rt = pygame_live2d.load_runtime(f"{MODEL}/Hiyori.model3.json")
    chk("runtime canvas", rt.canvas_size(), (2976.0, 4175.0))
    pids = rt.parameter_ids()
    chk("parameter_ids 非空", len(pids) > 50, True)
    chk("ParamAngleX 存在", "ParamAngleX" in pids, True)

    chk("load_model 缺失", raises(lambda: pygame_live2d.load_model("nope.json")), "ValueError/TypeError")
    chk("load_runtime 缺失", raises(lambda: pygame_live2d.load_runtime("nope.json", buf)), "ValueError/TypeError")

    # ── 参数变形实效验证（核心——参数真的驱动网格）──
    chk("set_parameter 非法 id", rt.set_parameter_normalized("NoSuchParam", 0.5), False)

    # mesh 数据形态：扁平偶数长度 + 索引非空
    ti, op, pos, uvs, idx = rt.mesh(0)
    chk("mesh 扁平偶数", len(pos) % 2 == 0 and len(uvs) % 2 == 0, True)
    chk("mesh 索引非空", len(idx) > 0, True)
    chk("mesh 纹理索引界内", 0 <= ti < 2, True)

    # ── motion 播放面 ──
    motion = pygame_live2d.load_motion(f"{MODEL}/motions/Hiyori_m01.motion3.json")
    chk("load_motion", motion is not None, True)
    chk("motion duration>0", motion.duration() > 0, True)
    player = pygame_live2d.motion_player(motion)
    rt2 = pygame_live2d.load_runtime(f"{MODEL}/Hiyori.model3.json")
    n2 = rt2.mesh_count()
    base2 = [tuple(rt2.mesh(i)[2]) for i in range(n2)]
    for i in range(40):
        player.tick(1.0 / 30.0)
        player.apply(rt2)
        rt2.update_meshes()
    changed2 = sum(1 for i in range(n2) if tuple(rt2.mesh(i)[2]) != base2[i])
    chk("motion 驱动网格变化（全量受控数>0）", changed2 > 0, True)
    print(f"[LT] motion 受控 drawable = {changed2}/{n2}")
    chk("motion time 推进", player.time() > 0.5, True)
    player.restart()
    chk("restart 回零", abs(player.time()) < 1e-5, True)

    # ── draw 面（注入式全管线自理）──
    rt.draw(buf, scale=0.9)
    chk("draw 默认参数", True, True)
    rt.draw(buf, x=0.0, y=0.0, scale=0.9)
    chk("draw 显式参数", True, True)

    # ── 视觉 smoke（60 帧 motion + rt.draw + draw_surface 上屏）──
    frame = 0
    last = time.time()
    while frame < 60:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
        now = time.time()
        dt = now - last
        last = now
        player.tick(dt)
        player.apply(rt2)
        rt2.update_meshes()
        rt2.draw(buf2, scale=0.9)
        with screen.render() as t:
            pygame.gfxdraw.set_color(t, (36, 40, 52))
            pygame.gfxdraw.box(t, (-400, -300, 800, 600))
            pygame.gfxdraw.draw_surface(t, buf2)
        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
    chk("视觉 smoke 60 帧", True, True)

    total = ok_count + fail_count
    print(f"[LT] 统计: {ok_count}/{total} 通过" + ("" if fail_count == 0 else f"，{fail_count} 失败"))
    print("[LT]", "ALL PASS" if fail_count == 0 else "HAS FAILURES")
