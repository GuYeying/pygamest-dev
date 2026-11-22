# leak_k —— mixer 泄漏探针（2026-11-16 相容批次）：程序化 WAV 字节
# （零资产）→ load_from_bytes → play → 循环——解码器/Sound/通道池回收
# 验证。判据：RSS 恒平/边际递减 = 池化稳态；线性涨 = 泄漏。
import pygame


def wav_bytes(freq=440.0, secs=0.05, rate=22050):
    """最小 WAV 字节（单声道 16bit PCM——手拼 LE，struct 模块被裁）。"""
    def u32(v):
        return bytes((v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255))
    def u16(v):
        return bytes((v & 255, (v >> 8) & 255))
    n = int(rate * secs)
    samples = []
    for i in range(n):
        amp = int(12000 * ((i % rate) / rate * 2 - 1))
        samples += [amp & 255, (amp >> 8) & 255]
    data = bytes(samples)
    hdr = (
        b"RIFF" + u32(36 + len(data)) + b"WAVE"
        + b"fmt " + u32(16) + u16(1) + u16(1) + u32(rate) + u32(rate * 2)
        + u16(2) + u16(16)
        + b"data" + u32(len(data))
    )
    return hdr + data


async def main():
    screen = pygame.display.set_mode((400, 300))
    screen.set_camera(pygame.render.game_camera_ortho(400, 300, 400, 300))
    pygame.mixer.init(4)
    frame = 0
    while frame < 3000:  # 50s @60fps——每帧一轮 load/play
        snd = pygame.mixer.load_from_bytes(wav_bytes(440.0 + (frame % 20) * 20))
        snd.play()
        snd.stop()  # 显式停（通道归还）
        if frame % 1500 == 0:
            print(f"[leak-k] frame={frame}（RSS 由外部脚本采样）")
        await pygame.tasks.yield_now()
        frame += 1
    print("[leak-k] 3000 帧跑完（50s）——外部 RSS 三窗对比")
