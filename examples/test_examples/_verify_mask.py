# pygame.mask 冒烟验证（headless——挂账④"mask 死 crate"转活正典：
# 无 starfish-mask crate 可删——绑定自持于 pygamest PySurface；"死"的
# 实义 = 零案例零验证，本案例补齐核心口）
import pygame

ok = [0]
def check(name, got, want):
    assert got == want, f"{name}: got {got!r} want {want!r}"
    ok[0] += 1
    print(f"  PASS {name}")

screen = pygame.display.set_mode((64, 64))

# ── 构造 + 位读写 ──
m = pygame.mask.Mask((8, 8))
check("构造空 count", m.count(), 0)
check("get_size", m.get_size(), (8, 8))
m.set_at((3, 5))
check("set_at/get_at", (m.get_at((3, 5)), m.get_at((0, 0))), (True, False))
check("count 单位", m.count(), 1)

# ── fill / invert ──
m.fill(True)
check("fill count", m.count(), 64)
m.invert()
check("invert count", m.count(), 0)
m.invert()
check("invert 复原", m.count(), 64)

# ── overlap（两 mask 错位重叠）──
a = pygame.mask.Mask((4, 4))
a.fill(True)
b = pygame.mask.Mask((4, 4))
b.fill(True)
check("overlap 全叠", a.overlap(b, (0, 0)), (0, 0))
check("overlap 错位", a.overlap(b, (2, 2)), (2, 2))
check("overlap 无叠", a.overlap(b, (4, 0)), None)
check("overlap_area", a.overlap_area(b, (2, 2)), 4)
check("overlap_area 无叠", a.overlap_area(b, (4, 0)), 0)

# ── surface 路径（OptionalArg 坑族修复后：单参/双参均须可用）──
surf = pygame.Surface((4, 4))
sm = pygame.mask.from_surface(surf)          # 单参（threshold 默认 127）
check("from_surface 类型", type(sm).__name__, "Mask")
sm2 = pygame.mask.from_surface(surf, 200)    # 双参显式
check("from_surface 双参", type(sm2).__name__, "Mask")

print(f"\nALL PASS ({ok[0]} checks)")
