# math 标量补全 + parse + random 运行时验证（headless）
import pygame
m = pygame.math   # pygame 非 package（无 __path__）——子模块走属性别名

ok = [0]
def check(name, got, want, tol=None):
    if tol is not None:
        assert abs(got - want) <= tol, f"{name}: got {got!r} want {want!r} (tol {tol})"
    else:
        assert got == want, f"{name}: got {got!r} want {want!r}"
    ok[0] += 1
    print(f"  PASS {name}")

# ═══ pygame.math 标量段（f2a28ab 批次）═══
print("== pygame.math 标量 ==")
check("pi", m.pi, 3.141592653589793)
check("tau", m.tau, 6.283185307179586)
check("e", m.e, 2.718281828459045)
check("inf isinf", m.isinf(m.inf), True)
check("nan isnan", m.isnan(m.nan), True)

check("sin(0)", m.sin(0.0), 0.0, 1e-9)
check("cos(0)", m.cos(0.0), 1.0, 1e-9)
check("sin(pi/2)", m.sin(m.pi / 2), 1.0, 1e-6)
check("tan(pi/4)", m.tan(m.pi / 4), 1.0, 1e-6)
check("atan2(1,1)", m.atan2(1.0, 1.0), m.pi / 4, 1e-6)
check("asin(1)", m.asin(1.0), m.pi / 2, 1e-6)
check("acos(1)", m.acos(1.0), 0.0, 1e-6)
check("asin 域外 NaN", m.isnan(m.asin(2.0)), True)      # Rust 语义非异常
check("degrees", m.degrees(m.pi), 180.0, 1e-6)     # f32 内核精度界
check("radians", m.radians(180.0), m.pi, 1e-6)     # f32 π ≈ 3.14159274

check("sqrt(9)", m.sqrt(9), 3.0, 1e-12)
check("exp(1)", m.exp(1.0), m.e, 1e-9)
check("log(e)", m.log(m.e), 1.0, 1e-9)
check("log(8,2)", m.log(8, 2), 3.0, 1e-9)
check("log2(8)", m.log2(8), 3.0, 1e-12)
check("log10(100)", m.log10(100), 2.0, 1e-12)
check("pow", m.pow(2, 10), 1024.0, 1e-9)

check("floor", m.floor(2.7), 2)          # 返回 int
check("ceil", m.ceil(2.1), 3)
check("trunc", m.trunc(-2.7), -2)
check("floor int 型", type(m.floor(2.7)).__name__, "int")

check("fabs", m.fabs(-3.5), 3.5, 1e-12)
check("fmod", m.fmod(7.5, 2.0), 1.5, 1e-12)
check("copysign", m.copysign(3.0, -1.0), -3.0, 1e-12)
check("hypot", m.hypot(3, 4), 5.0, 1e-12)
check("isfinite", m.isfinite(1.5), True)
check("isfinite inf", m.isfinite(m.inf), False)
check("int 参数直入", m.hypot(3, 4) == 5.0, True)       # ArgIntoFloat 收 int

# ═══ pygame.parse ═══
print("== pygame.parse ==")
cfg = pygame.parse.loads('{"w": 800, "vsync": true, "items": [1, 2.5, "x"], "n": null}')
check("loads 嵌套", (cfg["w"], cfg["vsync"], cfg["items"][1], cfg["n"]), (800, True, 2.5, None))
roundtrip = pygame.parse.loads(pygame.parse.dumps(cfg))
check("roundtrip", roundtrip, cfg)
check("dump_pretty 有缩进", "\n" in pygame.parse.dump_pretty(cfg), True)

t = pygame.parse.loads_toml('[win]\nw = 800\nfs = false\n')
check("loads_toml", (t["win"]["w"], t["win"]["fs"]), (800, False))
check("dumps_toml 含段", "[" in pygame.parse.dumps_toml({"win": {"w": 800}}), True)

try:
    pygame.parse.dumps(float("nan"))
    print("  FAIL NaN 未报错")
except Exception as e:
    print(f"  PASS NaN ValueError: {type(e).__name__}")
try:
    pygame.parse.loads("{bad json")
    print("  FAIL 坏 json 未报错")
except Exception as e:
    print(f"  PASS 坏 json ValueError: {type(e).__name__}")
try:
    pygame.parse.dumps({"k": bytes([1])})
    print("  FAIL bytes 未报错")
except Exception as e:
    print(f"  PASS bytes 不支持 ValueError: {type(e).__name__}")

# ═══ pygame.random ═══
print("== pygame.random ==")
pygame.random.seed(42)
seq_a = [pygame.random.random() for _ in range(8)]
pygame.random.seed(42)
seq_b = [pygame.random.random() for _ in range(8)]
check("seed 确定性", seq_a == seq_b, True)
check("random 域", all(0.0 <= v < 1.0 for v in seq_a), True)

pygame.random.seed(7)
dice = set()
for _ in range(300):
    v = pygame.random.randint(1, 6)
    dice.add(v)
    assert 1 <= v <= 6, f"randint 越界 {v}"
check("randint 含两端", dice == {1, 2, 3, 4, 5, 6}, True)

pygame.random.seed(9)
for _ in range(200):
    u = pygame.random.uniform(-2.0, 3.0)
    assert -2.0 <= u <= 3.0, f"uniform 越界 {u}"
check("uniform 域", True, True)

src = [1, 2, 3, 4, 5]
out = pygame.random.shuffle(src)
check("shuffle 新列表", (out != src, sorted(out), src), (True, [1, 2, 3, 4, 5], [1, 2, 3, 4, 5]))
check("choice", pygame.random.choice(["a", "b"]) in ("a", "b"), True)

gs = [pygame.random.gaussian(0.0, 1.0) for _ in range(500)]
mean = sum(gs) / len(gs)
check("gaussian 均值", -0.4 < mean < 0.4, True)

ux, uy = pygame.random.unit_vec2()
check("unit_vec2 模长", ux * ux + uy * uy, 1.0, 1e-5)
vx, vy, vz = pygame.random.unit_vec3()
check("unit_vec3 模长", vx * vx + vy * vy + vz * vz, 1.0, 1e-5)
cx, cy = pygame.random.in_circle(5)
check("in_circle 域", cx * cx + cy * cy <= 25.0, True)
sx, sy, sz = pygame.random.in_sphere(5)
check("in_sphere 域", sx * sx + sy * sy + sz * sz <= 25.0, True)

lst = pygame.random.rand_list(100)
check("rand_list", (len(lst), all(0.0 <= v < 1.0 for v in lst)), (100, True))

# Random 类：独立流确定性 + 互不踩 + reseed
r1 = pygame.random.Random(42)
r2 = pygame.random.Random(42)
r3 = pygame.random.Random(99)
sa = [r1.randint(0, 1000) for _ in range(10)]
sb = [r2.randint(0, 1000) for _ in range(10)]
sc = [r3.randint(0, 1000) for _ in range(10)]
check("Random 同种子同序列", sa == sb, True)
check("Random 异种子异序列", sa != sc, True)
check("Random choice_from", 0 <= r1.choice_from(10) < 10, True)
r1.reseed(7)
check("Random reseed 变序列", [r1.randint(0, 1000) for _ in range(10)] != sa, True)

print(f"\nALL PASS ({ok[0]} checks)")
