# water_pool —— Evan Wallace WebGL-Water 路线（heightfield 水体，非 SPH）
# **GPU compute 波场**（1D dispatch + 双会话 ping-pong）+ VS 直读 storage
# 位移/法线 + 解析折射/菲涅尔着色 + rapier 实体刚体浮力×水池交互。
#
# 定约（2026-11-23 compute 数据链取证定案——挂账谜团全破）：
#   ① 波场 = **GPU compute**（双 storage buffer ping-pong；**1D
#     dispatch**：引擎 compute pass 丢 y 维 workgroup——dispatch(8,8)
     # 实测只跑 2/8 行组，1D 派发完全绕开【引擎 bug 挂账】）
#   ② ping-pong = **两条独立 compute 会话**（同会话两次 set_bind_group
#     被引擎自动排 0/1，shader 只认 group(0) = 第二 dispatch 复用第一
#     组 = ping-pong 断裂；两会话各 auto-index 0 ✓）
#   ③ uniform 结构 = **4×f32 精确 16B**（vec3 成员 16 对齐膨胀 =
#     min_binding_size 失配 = 管线创建验证失败——vec3 对齐陷阱）
#   ④ wake = **零均值注入**（py 逐帧交替正负 amp——纯正向 = 平均水位
#     泵升淹没波纹）；注入门槛 py 侧把关
#   ⑤ 浮力 = 静态水平面解析式（readback 免除）
#   ⑥ 水面 = VS 直读 storage（y=波高 + 邻域梯度法线——全 GPU 零编组）
#     + fresnel 反射天色 + 解析折射（池底瓷砖）+ 镜面高光
#   ⑦ 绘序 = 单 raw pass 三段（深度共享）；池壁 model = 平移@scale
# 控制：空格丢球 / C 丢立方 / 左键丢球 / ESC 退出；相机慢速环绕
import pygame
import pygame_physics as pp
M = pygame.math

# ── 场景常量 ──
POOL = (1.5, 0.8, 1.5)     # 池内腔半尺寸（水面基线 y=0，池底 y=-0.8）
GRID = 64                  # 波场分辨率
CELL = 3.0 / (GRID - 1)    # 格距（米）

WGSL_CS = """
struct Wake { gx: f32, gz: f32, amp: f32, pad: f32 };
@group(0) @binding(0) var<storage, read_write> cur: array<vec2<f32>>;
@group(0) @binding(1) var<storage, read> prev: array<vec2<f32>>;
@group(0) @binding(2) var<uniform> wake: Wake;
@compute @workgroup_size(64, 1, 1)
fn cs_main(@builtin(global_invocation_id) gid: vec3<u32>) {
    // **1D 派发**（引擎 compute 丢 y 维 workgroup——1D 绕开）
    let i = gid.x;
    let x = i % 64;
    let z = i / 64;
    let hc = prev[i].x;
    let vc = prev[i].y;
    var lap = 0.0;
    if (x > 0) { lap += prev[i - 1].x; } else { lap += hc; }
    if (x < 63) { lap += prev[i + 1].x; } else { lap += hc; }
    if (z > 0) { lap += prev[i - 64].x; } else { lap += hc; }
    if (z < 63) { lap += prev[i + 64].x; } else { lap += hc; }
    lap -= 4.0 * hc;
    var v = (vc + lap * 0.42) * 0.9965;
    var h = hc + v;
    // wake（零均值——py 交替正负）
    let dx = f32(x) - wake.gx;
    let dz = f32(z) - wake.gz;
    let t = max(0.0, 1.0 - (dx * dx + dz * dz) / 25.0);
    v = v + wake.amp * t * t;
    // 边界吸收
    let edge = min(min(x, 63 - x), min(z, 63 - z));
    if (edge < 2) {
        v = v * 0.90;
        h = h * 0.95;
    }
    cur[i] = vec2<f32>(h, v);
}
"""

WGSL_WATER = """
struct Cam { mvp: mat4x4<f32> };
struct Param {
    light: vec4<f32>,
    sky_hi: vec4<f32>,
    sky_lo: vec4<f32>,
    eye: vec4<f32>,
};
@group(0) @binding(0) var<uniform> cam: Cam;
@group(0) @binding(1) var<storage, read> field: array<vec2<f32>>;
@group(0) @binding(2) var<uniform> prm: Param;

fn h_at(x: i32, z: i32) -> f32 {
    let cx = clamp(x, 0, 63);
    let cz = clamp(z, 0, 63);
    return field[u32(cx + cz * 64)].x;
}

struct VIn { @location(0) pos: vec3<f32> }
struct VOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) wpos: vec3<f32>,
    @location(1) nrm: vec3<f32>,
}
@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    // 世界 xz → 格坐标（world = grid×CELL − 1.5 → grid = (w+1.5)/CELL）
    let gi = vec2<i32>((v.pos.xz + vec2<f32>(1.5)) / 0.0476190476 + vec2<f32>(0.5));
    let h = h_at(gi.x, gi.y);
    let wp = vec3<f32>(v.pos.x, h, v.pos.z);
    // 法线 = 邻域梯度（VS 直算——全 GPU 零编组）
    let hl = h_at(gi.x - 1, gi.y);
    let hr = h_at(gi.x + 1, gi.y);
    let hd = h_at(gi.x, gi.y - 1);
    let hu = h_at(gi.x, gi.y + 1);
    o.wpos = wp;
    o.nrm = normalize(vec3<f32>(-(hr - hl) / (2.0 * 0.0476190476), 1.0,
                                -(hu - hd) / (2.0 * 0.0476190476)));
    o.clip = cam.mvp * vec4<f32>(wp, 1.0);
    return o;
}
// 程序化瓷砖（池底——折射线终点采样）
fn tile_color(p: vec3<f32>) -> vec3<f32> {
    let q = p.xz * 1.6;
    let cell = floor(q);
    let f = fract(q);
    let seam = min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y));
    let line = smoothstep(0.0, 0.06, seam);
    let tint = select(vec3<f32>(0.16, 0.42, 0.55), vec3<f32>(0.13, 0.36, 0.48),
                      (cell.x + cell.y) % 2.0 < 1.0);
    return tint * line + vec3<f32>(0.85) * (1.0 - line) * 0.4;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let n = normalize(in.nrm);
    let Vn = normalize(prm.eye.xyz - in.wpos);
    // fresnel（Schlick）
    let f0 = 0.02;
    let fres = f0 + (1.0 - f0) * pow(1.0 - max(dot(n, Vn), 0.0), 5.0);
    // 反射天色
    let r = reflect(-Vn, n);
    let sky = mix(prm.sky_lo.rgb, prm.sky_hi.rgb, clamp(r.y * 0.5 + 0.5, 0.0, 1.0));
    // 解析折射：折射线与池底平面 y=-0.8 求交（池内 → 瓷砖；出界 → 池壁）
    let rd = normalize(refract(-Vn, n, 1.0 / 1.33));
    var floor_col = vec3<f32>(0.1, 0.3, 0.4);
    var path_len = 1.0;
    if (rd.y < -0.01) {
        let t = (in.wpos.y - (-0.8)) / (-rd.y);
        let hitp = in.wpos + rd * t;
        path_len = t;
        if (abs(hitp.x) < 1.5 && abs(hitp.z) < 1.5) {
            floor_col = tile_color(hitp);
        } else {
            floor_col = vec3<f32>(0.20, 0.46, 0.58);
        }
    } else {
        floor_col = vec3<f32>(0.20, 0.46, 0.58);
    }
    // 水色吸收
    let absorb = exp(-path_len * vec3<f32>(0.18, 0.09, 0.05));
    floor_col = floor_col * absorb + vec3<f32>(0.02, 0.10, 0.18) * (1.0 - absorb.g);
    // 镜面太阳高光
    let L = normalize(prm.light.xyz);
    let spec = pow(max(dot(reflect(-L, n), Vn), 0.0), 90.0) * 1.2;
    let col = mix(floor_col, sky, fres) + vec3<f32>(1.0) * spec;
    return vec4<f32>(col, 1.0);
}
"""

# ── 极简实体着色（池壁/刚体共用——model 矩阵 + 独立色 uniform）──
WGSL_SURF = """
struct Cam { mvp: mat4x4<f32> };
struct Eye  { pos: vec4<f32> };
@group(0) @binding(0) var<uniform> cam: Cam;
@group(0) @binding(1) var<uniform> model: mat4x4<f32>;
@group(0) @binding(2) var<uniform> eye: Eye;
@group(0) @binding(3) var<uniform> col: vec4<f32>;
struct VIn { @location(0) pos: vec3<f32>, @location(1) nrm: vec3<f32> }
struct VOut { @builtin(position) pos: vec4<f32>, @location(0) wpos: vec3<f32>, @location(1) nrm: vec3<f32> }
@vertex
fn vs_main(v: VIn) -> VOut {
    let wp = model * vec4<f32>(v.pos, 1.0);
    var o: VOut;
    o.pos = cam.mvp * wp;
    o.wpos = wp.xyz;
    o.nrm = normalize((model * vec4<f32>(v.nrm, 0.0)).xyz);
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let n = normalize(in.nrm);
    let v = normalize(eye.pos.xyz - in.wpos);
    let nl = max(dot(n, normalize(vec3<f32>(0.4, 0.9, 0.3))), 0.0);
    let rim = pow(1.0 - max(dot(n, v), 0.0), 2.5) * 0.25;
    let c = col.rgb;
    let lit = c * (0.35 + 0.65 * nl) + c * rim;
    return vec4<f32>(lit, 1.0);
}
"""

# 单位立方（36 顶点 pos3+nrm3——六面各两三角）
CUBE = []


def _quad(a, b, c, d, n):
    for p in (a, b, c, a, c, d):
        CUBE.extend(p)
        CUBE.extend(n)


_u = 0.5
_quad((-_u, -_u, _u), (_u, -_u, _u), (_u, _u, _u), (-_u, _u, _u), (0, 0, 1))
_quad((_u, -_u, -_u), (-_u, -_u, -_u), (-_u, _u, -_u), (_u, _u, -_u), (0, 0, -1))
_quad((_u, -_u, _u), (_u, -_u, -_u), (_u, _u, -_u), (_u, _u, _u), (1, 0, 0))
_quad((-_u, -_u, -_u), (-_u, -_u, _u), (-_u, _u, _u), (-_u, _u, -_u), (-1, 0, 0))
_quad((-_u, _u, _u), (_u, _u, _u), (_u, _u, -_u), (-_u, _u, -_u), (0, 1, 0))
_quad((-_u, -_u, -_u), (_u, -_u, -_u), (_u, -_u, _u), (-_u, -_u, _u), (0, -1, 0))

SPHERE = [-0.0736, 0.1191, 0.0, -0.53, 0.85, 0.0, -0.1133, 0.07, 0.0433, -0.81, 0.5, 0.31, -0.0433, 0.1133, 0.07, -0.31, 0.81, 0.5, -0.1133, 0.07, 0.0433, -0.81, 0.5, 0.31,
    -0.1191, 0.0, 0.0736, -0.85, 0.0, 0.53, -0.07, 0.0433, 0.1133, -0.5, 0.31, 0.81, -0.0433, 0.1133, 0.07, -0.31, 0.81, 0.5, -0.07, 0.0433, 0.1133, -0.5, 0.31, 0.81,
    0.0, 0.0736, 0.1191, 0.0, 0.53, 0.85, -0.1133, 0.07, 0.0433, -0.81, 0.5, 0.31, -0.07, 0.0433, 0.1133, -0.5, 0.31, 0.81, -0.0433, 0.1133, 0.07, -0.31, 0.81, 0.5,
    -0.0736, 0.1191, 0.0, -0.53, 0.85, 0.0, -0.0433, 0.1133, 0.07, -0.31, 0.81, 0.5, 0.0, 0.14, 0.0, 0.0, 1.0, 0.0, -0.0433, 0.1133, 0.07, -0.31, 0.81, 0.5,
    0.0, 0.0736, 0.1191, 0.0, 0.53, 0.85, 0.0433, 0.1133, 0.07, 0.31, 0.81, 0.5, 0.0, 0.14, 0.0, 0.0, 1.0, 0.0, 0.0433, 0.1133, 0.07, 0.31, 0.81, 0.5,
    0.0736, 0.1191, 0.0, 0.53, 0.85, 0.0, -0.0433, 0.1133, 0.07, -0.31, 0.81, 0.5, 0.0433, 0.1133, 0.07, 0.31, 0.81, 0.5, 0.0, 0.14, 0.0, 0.0, 1.0, 0.0,
    -0.0736, 0.1191, 0.0, -0.53, 0.85, 0.0, 0.0, 0.14, 0.0, 0.0, 1.0, 0.0, -0.0433, 0.1133, -0.07, -0.31, 0.81, -0.5, 0.0, 0.14, 0.0, 0.0, 1.0, 0.0,
    0.0736, 0.1191, 0.0, 0.53, 0.85, 0.0, 0.0433, 0.1133, -0.07, 0.31, 0.81, -0.5, -0.0433, 0.1133, -0.07, -0.31, 0.81, -0.5, 0.0433, 0.1133, -0.07, 0.31, 0.81, -0.5,
    0.0, 0.0736, -0.1191, 0.0, 0.53, -0.85, 0.0, 0.14, 0.0, 0.0, 1.0, 0.0, 0.0433, 0.1133, -0.07, 0.31, 0.81, -0.5, -0.0433, 0.1133, -0.07, -0.31, 0.81, -0.5,
    -0.0736, 0.1191, 0.0, -0.53, 0.85, 0.0, -0.0433, 0.1133, -0.07, -0.31, 0.81, -0.5, -0.1133, 0.07, -0.0433, -0.81, 0.5, -0.31, -0.0433, 0.1133, -0.07, -0.31, 0.81, -0.5,
    0.0, 0.0736, -0.1191, 0.0, 0.53, -0.85, -0.07, 0.0433, -0.1133, -0.5, 0.31, -0.81, -0.1133, 0.07, -0.0433, -0.81, 0.5, -0.31, -0.07, 0.0433, -0.1133, -0.5, 0.31, -0.81,
    -0.1191, 0.0, -0.0736, -0.85, 0.0, -0.53, -0.0433, 0.1133, -0.07, -0.31, 0.81, -0.5, -0.07, 0.0433, -0.1133, -0.5, 0.31, -0.81, -0.1133, 0.07, -0.0433, -0.81, 0.5, -0.31,
    -0.0736, 0.1191, 0.0, -0.53, 0.85, 0.0, -0.1133, 0.07, -0.0433, -0.81, 0.5, -0.31, -0.1133, 0.07, 0.0433, -0.81, 0.5, 0.31, -0.1133, 0.07, -0.0433, -0.81, 0.5, -0.31,
    -0.1191, 0.0, -0.0736, -0.85, 0.0, -0.53, -0.14, 0.0, 0.0, -1.0, 0.0, 0.0, -0.1133, 0.07, 0.0433, -0.81, 0.5, 0.31, -0.14, 0.0, 0.0, -1.0, 0.0, 0.0,
    -0.1191, 0.0, 0.0736, -0.85, 0.0, 0.53, -0.1133, 0.07, -0.0433, -0.81, 0.5, -0.31, -0.14, 0.0, 0.0, -1.0, 0.0, 0.0, -0.1133, 0.07, 0.0433, -0.81, 0.5, 0.31,
    0.0736, 0.1191, 0.0, 0.53, 0.85, 0.0, 0.0433, 0.1133, 0.07, 0.31, 0.81, 0.5, 0.1133, 0.07, 0.0433, 0.81, 0.5, 0.31, 0.0433, 0.1133, 0.07, 0.31, 0.81, 0.5,
    0.0, 0.0736, 0.1191, 0.0, 0.53, 0.85, 0.07, 0.0433, 0.1133, 0.5, 0.31, 0.81, 0.1133, 0.07, 0.0433, 0.81, 0.5, 0.31, 0.07, 0.0433, 0.1133, 0.5, 0.31, 0.81,
    0.1191, 0.0, 0.0736, 0.85, 0.0, 0.53, 0.0433, 0.1133, 0.07, 0.31, 0.81, 0.5, 0.07, 0.0433, 0.1133, 0.5, 0.31, 0.81, 0.1133, 0.07, 0.0433, 0.81, 0.5, 0.31,
    0.0, 0.0736, 0.1191, 0.0, 0.53, 0.85, -0.07, 0.0433, 0.1133, -0.5, 0.31, 0.81, 0.0, 0.0, 0.14, 0.0, 0.0, 1.0, -0.07, 0.0433, 0.1133, -0.5, 0.31, 0.81,
    -0.1191, 0.0, 0.0736, -0.85, 0.0, 0.53, -0.07, -0.0433, 0.1133, -0.5, -0.31, 0.81, 0.0, 0.0, 0.14, 0.0, 0.0, 1.0, -0.07, -0.0433, 0.1133, -0.5, -0.31, 0.81,
    0.0, -0.0736, 0.1191, 0.0, -0.53, 0.85, -0.07, 0.0433, 0.1133, -0.5, 0.31, 0.81, -0.07, -0.0433, 0.1133, -0.5, -0.31, 0.81, 0.0, 0.0, 0.14, 0.0, 0.0, 1.0,
    -0.1191, 0.0, 0.0736, -0.85, 0.0, 0.53, -0.14, 0.0, 0.0, -1.0, 0.0, 0.0, -0.1133, -0.07, 0.0433, -0.81, -0.5, 0.31, -0.14, 0.0, 0.0, -1.0, 0.0, 0.0,
    -0.1191, 0.0, -0.0736, -0.85, 0.0, -0.53, -0.1133, -0.07, -0.0433, -0.81, -0.5, -0.31, -0.1133, -0.07, 0.0433, -0.81, -0.5, 0.31, -0.1133, -0.07, -0.0433, -0.81, -0.5, -0.31,
    -0.0736, -0.1191, 0.0, -0.53, -0.85, 0.0, -0.14, 0.0, 0.0, -1.0, 0.0, 0.0, -0.1133, -0.07, -0.0433, -0.81, -0.5, -0.31, -0.1133, -0.07, 0.0433, -0.81, -0.5, 0.31,
    -0.1191, 0.0, -0.0736, -0.85, 0.0, -0.53, -0.07, 0.0433, -0.1133, -0.5, 0.31, -0.81, -0.07, -0.0433, -0.1133, -0.5, -0.31, -0.81, -0.07, 0.0433, -0.1133, -0.5, 0.31, -0.81,
    0.0, 0.0736, -0.1191, 0.0, 0.53, -0.85, 0.0, 0.0, -0.14, 0.0, 0.0, -1.0, -0.07, -0.0433, -0.1133, -0.5, -0.31, -0.81, 0.0, 0.0, -0.14, 0.0, 0.0, -1.0,
    0.0, -0.0736, -0.1191, 0.0, -0.53, -0.85, -0.07, 0.0433, -0.1133, -0.5, 0.31, -0.81, 0.0, 0.0, -0.14, 0.0, 0.0, -1.0, -0.07, -0.0433, -0.1133, -0.5, -0.31, -0.81,
    0.0, 0.0736, -0.1191, 0.0, 0.53, -0.85, 0.0433, 0.1133, -0.07, 0.31, 0.81, -0.5, 0.07, 0.0433, -0.1133, 0.5, 0.31, -0.81, 0.0433, 0.1133, -0.07, 0.31, 0.81, -0.5,
    0.0736, 0.1191, 0.0, 0.53, 0.85, 0.0, 0.1133, 0.07, -0.0433, 0.81, 0.5, -0.31, 0.07, 0.0433, -0.1133, 0.5, 0.31, -0.81, 0.1133, 0.07, -0.0433, 0.81, 0.5, -0.31,
    0.1191, 0.0, -0.0736, 0.85, 0.0, -0.53, 0.0433, 0.1133, -0.07, 0.31, 0.81, -0.5, 0.1133, 0.07, -0.0433, 0.81, 0.5, -0.31, 0.07, 0.0433, -0.1133, 0.5, 0.31, -0.81,
    0.0736, -0.1191, 0.0, 0.53, -0.85, 0.0, 0.1133, -0.07, 0.0433, 0.81, -0.5, 0.31, 0.0433, -0.1133, 0.07, 0.31, -0.81, 0.5, 0.1133, -0.07, 0.0433, 0.81, -0.5, 0.31,
    0.1191, 0.0, 0.0736, 0.85, 0.0, 0.53, 0.07, -0.0433, 0.1133, 0.5, -0.31, 0.81, 0.0433, -0.1133, 0.07, 0.31, -0.81, 0.5, 0.07, -0.0433, 0.1133, 0.5, -0.31, 0.81,
    0.0, -0.0736, 0.1191, 0.0, -0.53, 0.85, 0.1133, -0.07, 0.0433, 0.81, -0.5, 0.31, 0.07, -0.0433, 0.1133, 0.5, -0.31, 0.81, 0.0433, -0.1133, 0.07, 0.31, -0.81, 0.5,
    0.0736, -0.1191, 0.0, 0.53, -0.85, 0.0, 0.0433, -0.1133, 0.07, 0.31, -0.81, 0.5, 0.0, -0.14, 0.0, 0.0, -1.0, 0.0, 0.0433, -0.1133, 0.07, 0.31, -0.81, 0.5,
    0.0, -0.0736, 0.1191, 0.0, -0.53, 0.85, -0.0433, -0.1133, 0.07, -0.31, -0.81, 0.5, 0.0, -0.14, 0.0, 0.0, -1.0, 0.0, -0.0433, -0.1133, 0.07, -0.31, -0.81, 0.5,
    -0.0736, -0.1191, 0.0, -0.53, -0.85, 0.0, 0.0433, -0.1133, 0.07, 0.31, -0.81, 0.5, -0.0433, -0.1133, 0.07, -0.31, -0.81, 0.5, 0.0, -0.14, 0.0, 0.0, -1.0, 0.0,
    0.0736, -0.1191, 0.0, 0.53, -0.85, 0.0, 0.0, -0.14, 0.0, 0.0, -1.0, 0.0, 0.0433, -0.1133, -0.07, 0.31, -0.81, -0.5, 0.0, -0.14, 0.0, 0.0, -1.0, 0.0,
    -0.0736, -0.1191, 0.0, -0.53, -0.85, 0.0, -0.0433, -0.1133, -0.07, -0.31, -0.81, -0.5, 0.0433, -0.1133, -0.07, 0.31, -0.81, -0.5, -0.0433, -0.1133, -0.07, -0.31, -0.81, -0.5,
    0.0, -0.0736, -0.1191, 0.0, -0.53, -0.85, 0.0, -0.14, 0.0, 0.0, -1.0, 0.0, -0.0433, -0.1133, -0.07, -0.31, -0.81, -0.5, 0.0433, -0.1133, -0.07, 0.31, -0.81, -0.5,
    0.0736, -0.1191, 0.0, 0.53, -0.85, 0.0, 0.0433, -0.1133, -0.07, 0.31, -0.81, -0.5, 0.1133, -0.07, -0.0433, 0.81, -0.5, -0.31, 0.0433, -0.1133, -0.07, 0.31, -0.81, -0.5,
    0.0, -0.0736, -0.1191, 0.0, -0.53, -0.85, 0.07, -0.0433, -0.1133, 0.5, -0.31, -0.81, 0.1133, -0.07, -0.0433, 0.81, -0.5, -0.31, 0.07, -0.0433, -0.1133, 0.5, -0.31, -0.81,
    0.1191, 0.0, -0.0736, 0.85, 0.0, -0.53, 0.0433, -0.1133, -0.07, 0.31, -0.81, -0.5, 0.07, -0.0433, -0.1133, 0.5, -0.31, -0.81, 0.1133, -0.07, -0.0433, 0.81, -0.5, -0.31,
    0.0736, -0.1191, 0.0, 0.53, -0.85, 0.0, 0.1133, -0.07, -0.0433, 0.81, -0.5, -0.31, 0.1133, -0.07, 0.0433, 0.81, -0.5, 0.31, 0.1133, -0.07, -0.0433, 0.81, -0.5, -0.31,
    0.1191, 0.0, -0.0736, 0.85, 0.0, -0.53, 0.14, 0.0, 0.0, 1.0, 0.0, 0.0, 0.1133, -0.07, 0.0433, 0.81, -0.5, 0.31, 0.14, 0.0, 0.0, 1.0, 0.0, 0.0,
    0.1191, 0.0, 0.0736, 0.85, 0.0, 0.53, 0.1133, -0.07, -0.0433, 0.81, -0.5, -0.31, 0.14, 0.0, 0.0, 1.0, 0.0, 0.0, 0.1133, -0.07, 0.0433, 0.81, -0.5, 0.31,
    0.0, -0.0736, 0.1191, 0.0, -0.53, 0.85, 0.07, -0.0433, 0.1133, 0.5, -0.31, 0.81, 0.0, 0.0, 0.14, 0.0, 0.0, 1.0, 0.07, -0.0433, 0.1133, 0.5, -0.31, 0.81,
    0.1191, 0.0, 0.0736, 0.85, 0.0, 0.53, 0.07, 0.0433, 0.1133, 0.5, 0.31, 0.81, 0.0, 0.0, 0.14, 0.0, 0.0, 1.0, 0.07, 0.0433, 0.1133, 0.5, 0.31, 0.81,
    0.0, 0.0736, 0.1191, 0.0, 0.53, 0.85, 0.07, -0.0433, 0.1133, 0.5, -0.31, 0.81, 0.07, 0.0433, 0.1133, 0.5, 0.31, 0.81, 0.0, 0.0, 0.14, 0.0, 0.0, 1.0,
    -0.0736, -0.1191, 0.0, -0.53, -0.85, 0.0, -0.0433, -0.1133, 0.07, -0.31, -0.81, 0.5, -0.1133, -0.07, 0.0433, -0.81, -0.5, 0.31, -0.0433, -0.1133, 0.07, -0.31, -0.81, 0.5,
    0.0, -0.0736, 0.1191, 0.0, -0.53, 0.85, -0.07, -0.0433, 0.1133, -0.5, -0.31, 0.81, -0.1133, -0.07, 0.0433, -0.81, -0.5, 0.31, -0.07, -0.0433, 0.1133, -0.5, -0.31, 0.81,
    -0.1191, 0.0, 0.0736, -0.85, 0.0, 0.53, -0.0433, -0.1133, 0.07, -0.31, -0.81, 0.5, -0.07, -0.0433, 0.1133, -0.5, -0.31, 0.81, -0.1133, -0.07, 0.0433, -0.81, -0.5, 0.31,
    0.0, -0.0736, -0.1191, 0.0, -0.53, -0.85, -0.0433, -0.1133, -0.07, -0.31, -0.81, -0.5, -0.07, -0.0433, -0.1133, -0.5, -0.31, -0.81, -0.0433, -0.1133, -0.07, -0.31, -0.81, -0.5,
    -0.0736, -0.1191, 0.0, -0.53, -0.85, 0.0, -0.1133, -0.07, -0.0433, -0.81, -0.5, -0.31, -0.07, -0.0433, -0.1133, -0.5, -0.31, -0.81, -0.1133, -0.07, -0.0433, -0.81, -0.5, -0.31,
    -0.1191, 0.0, -0.0736, -0.85, 0.0, -0.53, -0.0433, -0.1133, -0.07, -0.31, -0.81, -0.5, -0.1133, -0.07, -0.0433, -0.81, -0.5, -0.31, -0.07, -0.0433, -0.1133, -0.5, -0.31, -0.81,
    0.1191, 0.0, -0.0736, 0.85, 0.0, -0.53, 0.07, -0.0433, -0.1133, 0.5, -0.31, -0.81, 0.07, 0.0433, -0.1133, 0.5, 0.31, -0.81, 0.07, -0.0433, -0.1133, 0.5, -0.31, -0.81,
    0.0, -0.0736, -0.1191, 0.0, -0.53, -0.85, 0.0, 0.0, -0.14, 0.0, 0.0, -1.0, 0.07, 0.0433, -0.1133, 0.5, 0.31, -0.81, 0.0, 0.0, -0.14, 0.0, 0.0, -1.0,
    0.0, 0.0736, -0.1191, 0.0, 0.53, -0.85, 0.07, -0.0433, -0.1133, 0.5, -0.31, -0.81, 0.0, 0.0, -0.14, 0.0, 0.0, -1.0, 0.07, 0.0433, -0.1133, 0.5, 0.31, -0.81,
    0.1191, 0.0, 0.0736, 0.85, 0.0, 0.53, 0.14, 0.0, 0.0, 1.0, 0.0, 0.0, 0.1133, 0.07, 0.0433, 0.81, 0.5, 0.31, 0.14, 0.0, 0.0, 1.0, 0.0, 0.0,
    0.1191, 0.0, -0.0736, 0.85, 0.0, -0.53, 0.1133, 0.07, -0.0433, 0.81, 0.5, -0.31, 0.1133, 0.07, 0.0433, 0.81, 0.5, 0.31, 0.1133, 0.07, -0.0433, 0.81, 0.5, -0.31,
    0.0736, 0.1191, 0.0, 0.53, 0.85, 0.0, 0.14, 0.0, 0.0, 1.0, 0.0, 0.0, 0.1133, 0.07, -0.0433, 0.81, 0.5, -0.31, 0.1133, 0.07, 0.0433, 0.81, 0.5, 0.31,]

def _pack_u16(idxs):
    out = bytearray()
    for v in idxs:
        out.append(v & 0xFF)
        out.append((v >> 8) & 0xFF)
    return bytes(out)


def fps_view(eye, yaw_deg, pitch_deg):
    yaw = M.radians(yaw_deg)
    pitch = M.radians(pitch_deg)
    fx = M.cos(pitch) * M.sin(yaw)
    fy = M.sin(pitch)
    fz = -M.cos(pitch) * M.cos(yaw)
    f = (fx, fy, fz)
    up0 = (0.0, 1.0, 0.0)
    s0 = (fy * up0[2] - fz * up0[1],
          fz * up0[0] - fx * up0[2],
          fx * up0[1] - fy * up0[0])
    sn = (s0[0] ** 2 + s0[1] ** 2 + s0[2] ** 2) ** 0.5
    s = (s0[0] / sn, s0[1] / sn, s0[2] / sn)
    u = (s[1] * fz - s[2] * fy,
         s[2] * fx - s[0] * fz,
         s[0] * fy - s[1] * fx)
    ex, ey, ez = eye
    m = [
        s[0], s[1], s[2], -s[0] * ex - s[1] * ey - s[2] * ez,
        u[0], u[1], u[2], -u[0] * ex - u[1] * ey - u[2] * ez,
        -f[0], -f[1], -f[2], f[0] * ex + f[1] * ey + f[2] * ez,
        0.0, 0.0, 0.0, 1.0,
    ]
    cols = [m[r * 4 + c] for c in range(4) for r in range(4)]
    return M.mat4_from_cols_array(cols)


async def main():
    pygame.display.set_caption("water_pool")
    screen = pygame.display.set_mode((800, 600)); pygame.render.set_fb_dump(True)
    cjk = pygame.font.Font("cjk", 15)
    ac = pygame.render.access()

    # ── GPU 波场（双 storage buffer ping-pong + wake uniform 16B 精确）──
    wave_a = ac.buffer(GRID * GRID * 8, usage="storage", label="wave_a")
    wave_b = ac.buffer(GRID * GRID * 8, usage="storage", label="wave_b")
    wake_buf = ac.buffer(16, label="wake_buf")
    ac.write_buffer(wake_buf, [31.5, 31.5, 0.0, 0.0])

    cs_shader = ac.shader(WGSL_CS, label="wave_cs")
    bg_a = ac.bind_group([(0, "storage_rw", wave_a),
                          (1, "storage", wave_b),
                          (2, "uniform", wake_buf)], label="bg_a")
    bg_b = ac.bind_group([(0, "storage_rw", wave_b),
                          (1, "storage", wave_a),
                          (2, "uniform", wake_buf)], label="bg_b")
    cs_pipe = ac.compute_pipeline(cs_shader, [bg_a], label="wave_cs_pipe")

    # ── 相机/参数 buffer ──
    cam_buf = ac.buffer(64, label="cam_buf")
    prm_buf = ac.buffer(64, label="water_prm")
    water_eye = ac.buffer(16, label="water_eye")

    # ── 水面网格（64² pos3 静态——位移/法线全 GPU VS 侧）──
    wverts = []
    for gz in range(GRID):
        for gx in range(GRID):
            wx = -1.5 + gx * CELL
            wz = -1.5 + gz * CELL
            wverts.extend([wx, 0.0, wz])
    wind = []
    for gz in range(GRID - 1):
        for gx in range(GRID - 1):
            a = gz * GRID + gx
            b = a + 1
            c = a + GRID
            d = c + 1
            wind.extend([a, c, b, b, c, d])
    water_mesh = ac.mesh(["float32x3"], wverts, index_bytes=_pack_u16(wind),
                         label="water_grid")
    water_bind = ac.bind_group([(0, "uniform", cam_buf),
                                (1, "storage", wave_b),
                                (2, "uniform", prm_buf),
                                (3, "uniform", water_eye)], label="water_bind")
    water_shader = ac.shader(WGSL_WATER, label="water_shader")
    water_pipe = ac.pipeline(water_shader, water_mesh, [water_bind],
                             cull="none", depth_mode="standard", depth_write=True,
                             label="water_pipe")

    def write_prm(eye):
        ac.write_buffer(prm_buf, [
            0.35, 0.9, 0.25, 0.0,
            0.55, 0.70, 0.90, 1.0,
            0.30, 0.42, 0.58, 1.0,
            eye[0], eye[1], eye[2], 1.0,
        ])
        ac.write_buffer(water_eye, [eye[0], eye[1], eye[2], 1.0])

    # ── 实体渲染资源（池壁×4 + 刚体；惰性池）──
    surf_shader = ac.shader(WGSL_SURF, label="surf_shader")
    cube_mesh = ac.mesh(["float32x3", "float32x3"], CUBE, label="cube")
    sphere_mesh = ac.mesh(["float32x3", "float32x3"], SPHERE, label="sph")

    def surf_resources(n):
        made = []
        for i in range(n):
            mb = ac.buffer(64, label=f"surf_m{i}")
            cb = ac.buffer(16, label=f"surf_c{i}")
            eb = ac.buffer(16, label=f"surf_e{i}")
            bg = ac.bind_group([(0, "uniform", cam_buf), (1, "uniform", mb),
                                (2, "uniform", eb), (3, "uniform", cb)],
                               label=f"surf_b{i}")
            made.append((mb, cb, eb, bg))
        return made

    wall_res = surf_resources(4)
    ball_res = surf_resources(8)
    cube_res = surf_resources(8)
    surf_pipe = ac.pipeline(surf_shader, cube_mesh, [wall_res[0][3]],
                            cull="back", depth_mode="standard", depth_write=True,
                            label="surf_pipe")

    # ── 物理（rapier：池底+四壁 fixed + 动态刚体）──
    solid = pp.PhysicsWorld3D(gravity=(0, -9.81, 0))
    solid.insert(
        pp.RigidBodyBuilder3D("fixed", translation=(0, -0.85, 0)),
        pp.ColliderBuilder3D("cuboid", hx=POOL[0] + 0.2, hy=0.05, hz=POOL[2] + 0.2))
    walls = [
        ((0.0, 0.0, -POOL[2] - 0.03), (POOL[0] + 0.08, POOL[1], 0.03)),
        ((0.0, 0.0,  POOL[2] + 0.03), (POOL[0] + 0.08, POOL[1], 0.03)),
        ((-POOL[0] - 0.03, 0.0, 0.0), (0.03, POOL[1], POOL[2] + 0.08)),
        (( POOL[0] + 0.03, 0.0, 0.0), (0.03, POOL[1], POOL[2] + 0.08)),
    ]
    wall_cols = [(0.72, 0.80, 0.86), (0.72, 0.80, 0.86),
                 (0.76, 0.84, 0.89), (0.76, 0.84, 0.89)]
    wall_bodies = []
    for c, (hx, hy, hz) in walls:
        wall_bodies.append(solid.insert(
            pp.RigidBodyBuilder3D("fixed", translation=c),
            pp.ColliderBuilder3D("cuboid", hx=hx, hy=hy, hz=hz))[0])
    solid.step_frame(1.0 / 60.0)

    balls = []     # (body_handle, res_i)
    cubes = []
    ball_n = [0]
    cube_n = [0]

    def drop_ball(x=0.5, z=0.0):
        bh = solid.insert(
            pp.RigidBodyBuilder3D("dynamic", translation=(x, 1.6, z)),
            pp.ColliderBuilder3D("ball", radius=0.28, density=300.0))[0]
        i = ball_n[0] % 8
        ball_n[0] += 1
        balls.append((bh, i))
        print(f"[pool] 丢球 #{len(balls)} @({x},{z})", flush=True)

    def drop_cube(x=-0.5, z=0.0):
        bh = solid.insert(
            pp.RigidBodyBuilder3D("dynamic", translation=(x, 1.6, z)),
            pp.ColliderBuilder3D("cuboid", hx=0.24, hy=0.24, hz=0.24,
                                 density=500.0))[0]
        i = cube_n[0] % 8
        cube_n[0] += 1
        cubes.append((bh, i))
        print(f"[pool] 丢立方 #{len(cubes)} @({x},{z})", flush=True)

    # ── 浮力（静态水平面解析式）+ wake（零均值交替注入）──
    G = 9.81
    RHO_W = 1000.0

    def buoyancy_step(frame):
        wake = None      # (gx, gz, amp)——最大注入源
        dt = 1.0 / 60.0
        for bh, _i in balls:
            pos = solid.translation(bh)
            vel = solid.linvel(bh)
            r = 0.28
            d = 0.0 - (pos[1] - r)
            if d > 0.0:
                dc = min(d, 2.0 * r)
                v_sub = 3.14159265 * dc * dc * (3.0 * r - dc) / 3.0
                f_up = RHO_W * G * v_sub
                k = min(dc / (2.0 * r), 1.0)
                fx = -90.0 * k * vel[0]
                fy = -90.0 * k * vel[1]
                fz = -90.0 * k * vel[2]
                solid.apply_impulse(bh, (fx * dt, f_up * dt + fy * dt, fz * dt))
                gx = (pos[0] + 1.5) / 3.0 * (GRID - 1)
                gz = (pos[2] + 1.5) / 3.0 * (GRID - 1)
                amp = max(-vel[1], 0.0) * 0.03 + (abs(vel[0]) + abs(vel[2])) * 0.008
                if wake is None or amp > wake[2]:
                    wake = (gx, gz, amp)
        for bh, _i in cubes:
            pos = solid.translation(bh)
            vel = solid.linvel(bh)
            hh = 0.24
            d = 0.0 - (pos[1] - hh)
            if d > 0.0:
                dc = min(d, 2.0 * hh)
                v_sub = (2.0 * hh) * (2.0 * hh) * dc
                f_up = RHO_W * G * v_sub
                k = min(dc / (2.0 * hh), 1.0)
                fx = -120.0 * k * vel[0]
                fy = -120.0 * k * vel[1]
                fz = -120.0 * k * vel[2]
                solid.apply_impulse(bh, (fx * dt, f_up * dt + fy * dt, fz * dt))
                gx = (pos[0] + 1.5) / 3.0 * (GRID - 1)
                gz = (pos[2] + 1.5) / 3.0 * (GRID - 1)
                amp = max(-vel[1], 0.0) * 0.035 + (abs(vel[0]) + abs(vel[2])) * 0.008
                if wake is None or amp > wake[2]:
                    wake = (gx, gz, amp)
        # **零均值交替注入** + 门槛（显著运动才注入）
        if wake is not None and wake[2] > 0.006:
            a = wake[2] if frame % 2 == 0 else -wake[2]
            ac.write_buffer(wake_buf, [wake[0], wake[1], a, 0.0])
        else:
            ac.write_buffer(wake_buf, [31.5, 31.5, 0.0, 0.0])

    # 开场各丢一个（即刻有交互观感）
    drop_ball()
    drop_cube()

    # ── 主循环 ──
    frame = 0
    while frame < 7200:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN:
                if e.key == pygame.key.K_ESCAPE:
                    return
                if e.key == pygame.key.K_SPACE:
                    drop_ball()
                if e.key == pygame.key.K_c:
                    drop_cube()
            if e.type == pygame.event.MOUSEBUTTONDOWN and e.button == 1:
                drop_ball()

        solid.step_frame(1.0 / 60.0)
        buoyancy_step(frame)

        # 相机（慢速环绕）
        t_sec = frame / 60.0
        yaw = 18.0 * t_sec
        eye = (M.sin(M.radians(yaw)) * 4.6, 2.7, M.cos(M.radians(yaw)) * 4.6)
        tgt = (0.0, 0.0, 0.0)
        d = (tgt[0] - eye[0], tgt[1] - eye[1], tgt[2] - eye[2])
        dl = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5
        pitch = M.degrees(M.asin(d[1] / dl))
        yaw_look = M.degrees(M.atan2(d[0], -d[2]))
        view = fps_view(eye, yaw_look, pitch)
        cam_m = pygame.render.game_camera_perspective(
            52.0, 800, 600, 800, 600, 0.1, 60.0).with_view(view)
        pygame.render.write_camera_mvp(cam_buf, cam_m.mvp())
        write_prm(eye)

        with screen.render() as rt:
            rt.fill((18, 26, 40))
            # **单 raw pass 三段**（深度共享——刚体淹没部分被水面遮挡）
            with screen.raw_render(depth=True) as p:
                # 池壁（model = 平移@scale——cube_mesh = 单位立方）
                p.set_pipeline(surf_pipe)
                for i in range(4):
                    mb, cb, eb, bg = wall_res[i]
                    c = walls[i][0]
                    hw, hh, hz2 = walls[i][1]
                    ac.write_buffer(mb, M.mat4_translation(c[0], c[1], c[2]) @
                                    M.mat4_scale(hw * 2.0, hh * 2.0, hz2 * 2.0))
                    ac.write_buffer(cb, [wall_cols[i][0], wall_cols[i][1],
                                         wall_cols[i][2], 1.0])
                    ac.write_buffer(eb, [eye[0], eye[1], eye[2], 1.0])
                    p.set_bind_group(0, bg)
                    p.draw_mesh(cube_mesh)
                # 水面（VS 直读 storage——位移/法线全 GPU）
                p.set_pipeline(water_pipe)
                p.set_bind_group(0, water_bind)
                p.draw_mesh(water_mesh)
                # 刚体（同 pass 深度共享）
                p.set_pipeline(surf_pipe)
                for bh, i in balls:
                    pos = solid.translation(bh)
                    mb, cb, eb, bg = ball_res[i % 8]
                    ac.write_buffer(mb, M.mat4_translation(pos[0], pos[1], pos[2]) @
                                    M.mat4_scale(0.56, 0.56, 0.56))
                    ac.write_buffer(cb, [0.92, 0.30, 0.25, 1.0])
                    ac.write_buffer(eb, [eye[0], eye[1], eye[2], 1.0])
                    p.set_bind_group(0, bg)
                    p.draw_mesh(sphere_mesh)
                for bh, i in cubes:
                    pos = solid.translation(bh)
                    mb, cb, eb, bg = cube_res[i % 8]
                    ac.write_buffer(mb, M.mat4_translation(pos[0], pos[1], pos[2]) @
                                    M.mat4_scale(0.48, 0.48, 0.48))
                    ac.write_buffer(cb, [0.95, 0.62, 0.20, 1.0])
                    ac.write_buffer(eb, [eye[0], eye[1], eye[2], 1.0])
                    p.set_bind_group(0, bg)
                    p.draw_mesh(cube_mesh)
            # **GPU 波场 ping-pong = 两条独立 compute 会话**（各 auto-index
            # 0——1D dispatch 绕开引擎 y 维丢失 bug；本帧写、下帧渲染读）
            with screen.raw_compute() as cp:
                cp.set_pipeline(cs_pipe)
                cp.set_bind_group(0, bg_a)
                cp.dispatch(64, 1, 1)
            with screen.raw_compute() as cp:
                cp.set_pipeline(cs_pipe)
                cp.set_bind_group(0, bg_b)
                cp.dispatch(64, 1, 1)

            # HUD
            pixel_cam = pygame.render.game_camera_ortho(800, 600, 800, 600)
            pygame.gfxdraw.set_camera(rt, pixel_cam)
            pygame.gfxdraw.draw_surface(rt, cjk.render(
                f"[water_pool] 球 {len(balls)} 立方 {len(cubes)} | "
                f"空格丢球 C丢立方 点击丢球 | ESC", True, (200, 220, 240)), transform=M.mat4_translation(-380, 288, 0))
            pygame.gfxdraw.clear_camera(rt)

        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1
