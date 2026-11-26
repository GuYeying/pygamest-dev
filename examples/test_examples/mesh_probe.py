# mesh_probe —— ozz mesh.ozz 格式求解器（io.read_bytes 供数 + 纯 Python 解码；
# 冻结解释器无 struct/math/file-io——全手工解码）。
import pygame

PATH = "D:/Projects/Rust/pygame-rs-dev/examples/3dmodels/bin/arnaud_mesh.ozz"


async def main():
    pygame.display.set_mode((200, 100))
    buf = pygame.io.read(PATH)
    print(f"[probe] size={len(buf)}")

    pos = 1  # endian tag
    end = buf.index(b"\x00", pos)
    tag = buf[pos:end].decode()
    pos = end + 1
    version = int.from_bytes(buf[pos:pos + 4], "little")
    pos += 4
    print(f"[probe] tag={tag} version={version}")

    def u32(p):
        return int.from_bytes(buf[p:p + 4], "little"), p + 4

    # 原始 u32 流（前 12 个 + positions 尾窗——分段诊断）
    p2 = pos
    vals = []
    for i in range(4400):
        v, p2 = u32(p2)
        vals.append(v)
    for i in list(range(12)) + list(range(4190, 4208)):
        print(f"[probe]   +{i}: {vals[i]}")

    def u32(p):
        return int.from_bytes(buf[p:p + 4], "little"), p + 4

    def f32(p):
        i = int.from_bytes(buf[p:p + 4], "little")
        sign = -1.0 if (i >> 31) else 1.0
        e = (i >> 23) & 0xFF
        m = i & 0x7FFFFF
        if e == 0:
            return 0.0
        return sign * (1.0 + m / 8388608.0) * (2.0 ** (e - 127))

    def finite(p, n):
        for k in range(min(n, 12)):
            v = f32(p + 4 * k)
            if v != v or v == float("inf") or v == -float("inf"):
                return False
        return True

    def try_parse(pos):
        parts, pos = u32(pos)
        if parts == 0 or parts > 16:
            return [f"parts={parts} 不合理"]
        d = [f"parts={parts}"]
        for pi in range(parts):
            pver, pos = u32(pos)
            if pver != 1:
                d.append(f"p{pi}.ver={pver} FAIL")
                return d
            d.append(f"p{pi}.ver=1")
            pcnt, pos = u32(pos)
            if pcnt % 3 or pcnt == 0 or pcnt > 60000 or not finite(pos, pcnt):
                d.append(f"p{pi}.pos={pcnt} FAIL")
                return d
            pos += 4 * pcnt
            d.append(f"p{pi}: pos={pcnt // 3}v")
            ncnt, pos = u32(pos)
            if ncnt % 3 or ncnt > 60000 or not finite(pos, ncnt):
                d.append(f" nor={ncnt} FAIL")
                return d
            pos += 4 * ncnt
            d.append(f" nor={ncnt // 3}v")
            tcnt, pos = u32(pos)
            if tcnt % 4 or tcnt > 60000 or not finite(pos, tcnt):
                d.append(f" tan={tcnt} FAIL")
                return d
            pos += 4 * tcnt
            d.append(f" tan={tcnt // 4}v")
            ucnt, pos = u32(pos)
            if ucnt % 2 or ucnt > 60000:
                d.append(f" uv={ucnt} FAIL")
                return d
            pos += 4 * ucnt
            d.append(f" uv={ucnt // 2}v")
            ccnt, pos = u32(pos)
            if ccnt % 4 or ccnt > 60000:
                d.append(f" col={ccnt} FAIL")
                return d
            pos += ccnt
            d.append(f" col={ccnt // 4}v")
            icnt, pos = u32(pos)
            verts = pcnt // 3
            if icnt == 0 or icnt % verts or icnt > 60000:
                d.append(f" jidx={icnt}(v={verts}) FAIL")
                return d
            pos += 2 * icnt
            d.append(f" jidx={icnt // verts}inf")
            wcnt, pos = u32(pos)
            if wcnt % verts or wcnt > 60000:
                d.append(f" jw={wcnt}(v={verts}) FAIL")
                return d
            pos += 4 * wcnt
            d.append(f" jw={wcnt // verts}inf")
        # p0 结束点标记（后续结构诊断）
        d.append(f" p0末位={pos}")
        tcnt, pos = u32(pos)
        if tcnt % 3 or tcnt > 180000:
            d.append(f" tris={tcnt} FAIL")
            return d
        pos += 2 * tcnt
        d.append(f" tris={tcnt // 3}")
        rcnt, pos = u32(pos)
        if rcnt > 1000:
            d.append(f" remap={rcnt} FAIL")
            return d
        pos += 2 * rcnt
        d.append(f" remap={rcnt}")
        bcnt, pos = u32(pos)
        if bcnt == 0 or bcnt > 1000:
            d.append(f" ibp={bcnt} FAIL")
            return d
        pos += 16 * bcnt
        d.append(f" ibp={bcnt}")
        d.append(f" 剩余={len(buf) - pos}B")
        if len(buf) - pos == 0:
            d.append("** 完整吻合 **")
        return d

    for line in try_parse(pos):
        print("[probe]  ", line)
