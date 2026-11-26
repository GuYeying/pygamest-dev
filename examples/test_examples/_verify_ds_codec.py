# ds + codec 运行时验证（headless——无显示依赖）
import pygame

ok = [0]
def check(name, got, want):
    assert got == want, f"{name}: got {got!r} want {want!r}"
    ok[0] += 1
    print(f"  PASS {name}")

# ═══ pygame.ds ═══
print("== pygame.ds ==")
h = pygame.ds.Heap()
h.push(2.5, "a")
h.push(1.0, "b")
h.push(0.5, "c")
check("Heap.len", h.len(), 3)
check("Heap.pop", h.pop(), (0.5, "c"))
check("Heap.pop2", h.pop(), (1.0, "b"))
check("Heap.empty", h.is_empty(), False)

h2 = pygame.ds.Heap()
h2.from_pairs([(3.0, "c"), (1.0, "a"), (2.0, "b")])
check("Heap.from_pairs.pop", h2.pop(), (1.0, "a"))

top = h2.push_pop(0.2, "new")
check("Heap.push_pop", top, (2.0, "b"))  # 旧根 2.0 被顶掉
check("Heap.push_pop.in", h2.pop(), (0.2, "new"))

sl = pygame.ds.SortedList()
sl.insert(1.5, "enemy_a")
sl.insert(0.3, "enemy_b")
sl.insert(2.7, "enemy_c")
check("SL.first", sl.first(), (0.3, "enemy_b"))
check("SL.last", sl.last(), (2.7, "enemy_c"))
check("SL.bisect_left", sl.bisect_left(1.0), 1)
check("SL.bisect_right", sl.bisect_right(1.5), 2)
check("SL.contains", sl.contains(1.5), True)
check("SL.contains.no", sl.contains(9.9), False)
check("SL.range", sl.range(0.0, 2.0), ["enemy_b", "enemy_a"])
check("SL.get", sl.get(0), (0.3, "enemy_b"))
check("SL.get.oob", sl.get(99), None)
check("SL.len", sl.len(), 3)
sl.remove_at(1)
check("SL.after_remove.first", sl.first(), (0.3, "enemy_b"))
check("SL.after_remove.len", sl.len(), 2)

uf = pygame.ds.UnionFind(10)
check("UF.components0", uf.components(), 10)
check("UF.union", uf.union(0, 1), True)
check("UF.union.same", uf.union(0, 1), False)
uf.union(1, 2)
check("UF.connected", uf.connected(0, 2), True)
check("UF.connected.no", uf.connected(0, 3), False)
check("UF.find", uf.find(2), uf.find(0))
check("UF.components", uf.components(), 8)
check("UF.len", uf.len(), 10)

# ═══ pygame.codec ═══
print("== pygame.codec ==")
check("sha256_hex(abc)",
      pygame.codec.sha256_hex(bytes([97, 98, 99])),
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
d = pygame.codec.sha256_bytes(bytes([97, 98, 99]))
check("sha256_bytes.len", len(d), 32)
check("sha256_bytes[0]", d[0], 0xBA)

data = bytes([104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100] * 40)  # "hello world"*40
packed = pygame.codec.zlib_compress(data)
check("zlib.smaller", len(packed) < len(data), True)
back = pygame.codec.zlib_decompress(packed)
check("zlib.roundtrip", bytes(back), data)
check("zlib.corrupt", pygame.codec.zlib_decompress([1, 2, 3]), [])

b64 = pygame.codec.b64_encode(bytes([104, 101, 108, 108, 111]))
check("b64.hello", b64, "aGVsbG8=")
check("b64.roundtrip", bytes(pygame.codec.b64_decode(b64)), bytes([104, 101, 108, 108, 111]))
try:
    pygame.codec.b64_decode("aG!s")
    print("  FAIL b64 非法字符未报错")
except Exception as e:
    print(f"  PASS b64 非法字符报错: {type(e).__name__}")

# 存档链端到端：zlib + b64 + sha256 校验
blob = pygame.codec.zlib_compress(data)
line = pygame.codec.b64_encode(blob) + "|" + pygame.codec.sha256_hex(blob)
b64back, digest = line.split("|")
assert bytes(pygame.codec.zlib_decompress(pygame.codec.b64_decode(b64back))) == data
assert pygame.codec.sha256_hex(pygame.codec.b64_decode(b64back)) == digest
ok[0] += 1
print("  PASS 存档链端到端")

print(f"\nALL PASS ({ok[0]} checks)")
