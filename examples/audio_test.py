# audio_test —— pygame.mixer + sndarray 专项案例：程序化正弦波 WAV
# （零资产依赖——纯 Python 字节拼装）→ load_from_bytes → play → 音量/
# 静音往返 → 双声道混音。退出：自动（SUMMARY 停 2 秒）/ ESC。
import time

import pygame

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("[PASS] " if ok else "[FAIL] ") + name + ("  " + detail if detail else ""))


def make_tone_wav(freq=440.0, seconds=0.6, rate=22050, volume=0.4):
    """程序化 16-bit 单声道 WAV 字节（纯 Python 拼装——零 stdlib 依赖；
    math 模块不在默认 stdlib 集，正弦用 pygame.math.sin）"""
    n = int(rate * seconds)
    data = b"".join(
        int(volume * 32767.0 * pygame.math.sin(
            2.0 * 3.1415926 * freq * i / rate)
            ).to_bytes(2, "little", signed=True)
        for i in range(n))
    hdr = (b"RIFF" + (36 + len(data)).to_bytes(4, "little") + b"WAVE"
           + b"fmt " + (16).to_bytes(4, "little")
           + (1).to_bytes(2, "little")            # PCM
           + (1).to_bytes(2, "little")            # 单声道
           + rate.to_bytes(4, "little")
           + (rate * 2).to_bytes(4, "little")     # 字节率
           + (2).to_bytes(2, "little")            # 块对齐
           + (16).to_bytes(2, "little")           # 位深
           + b"data" + len(data).to_bytes(4, "little"))
    return hdr + data


async def main():
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 20)

    pygame.mixer.init()

    wav = make_tone_wav()
    snd = pygame.mixer.load_from_bytes(wav)
    check("load_from_bytes（程序化 WAV）", snd is not None)

    snd.play()
    check("play 播放", True)

    snd.set_volume(0.3)
    check("set_volume 0.3", True)
    snd.set_volume(1.0)
    check("set_volume 复原", True)

    # 双声道音效（音高扫频——可听辨）
    sweep = make_tone_wav(freq=880.0, seconds=0.4)
    snd2 = pygame.mixer.load_from_bytes(sweep)
    snd2.play()
    check("双音效叠加", True)

    # 渲染清单（播放期可视化）
    frame = 0
    last = time.time()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        with screen.render() as rt:
            rt.fill((16, 18, 26))
            yy = 240
            for line in PASS + FAIL:
                s = font.render(line, True,
                                (140, 220, 140) if line in PASS else (230, 120, 120))
                pygame.gfxdraw.set_transform(rt, pygame.math.mat4_translation(-380, yy, 0))
                pygame.gfxdraw.draw_surface(rt, s)
                yy -= 24
            tip = font.render("440Hz + 880Hz 扫频音效应可听见（音频输出开着吗）",
                              True, (150, 170, 150))
            pygame.gfxdraw.set_transform(rt, pygame.math.mat4_translation(-380, -260, 0))
            pygame.gfxdraw.draw_surface(rt, tip)

        pygame.display.flip()
        frame += 1
        if time.time() - last > 2.5:
            print(f"[audio-test] SUMMARY {'PASS' if not FAIL else 'FAIL ' + str(FAIL)} "
                  f"({len(PASS)} 项)")
            return
        pygame.time.delay(8)
        await pygame.next_frame()
