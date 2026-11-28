# fluid3d_game —— 3D 游戏流体渲染案例（游戏场景液体观感专项）
# 玻璃水槽（rapier 四壁+地面，step(dt, solid) 自动耦合 salva）+ 高处持续注水：
# SPH 粒子双层渲染 = 游戏液体观感核心——
#   ①不透明核心球（高度渐变深蓝 + 菲涅尔边缘光 + 高光）深度写入
#   ②加性光晕壳（1.42×半径，深度测试开/写关）——重叠融为连贯液面
# 相机：第三人称环绕（慢速 yaw 漂移 + 俯角）；空格 = 注水爆发；ESC 退出
import pygame
import pygame_physics as pp
M = pygame.math

WGSL_CORE = """
struct Camera { mvp: mat4x4<f32> };
struct Model  { model: mat4x4<f32> };
struct Eye    { pos: vec4<f32> };
@group(0) @binding(0) var<uniform> camera: Camera;
@group(0) @binding(1) var<uniform> model: Model;
@group(0) @binding(2) var<uniform> eye: Eye;
struct VIn { @location(0) pos: vec3<f32>, @location(1) nrm: vec3<f32> }
struct VOut { @builtin(position) pos: vec4<f32>, @location(0) wpos: vec3<f32>, @location(1) nrm: vec3<f32> }
@vertex
fn vs_main(v: VIn) -> VOut {
    let wp = model.model * vec4<f32>(v.pos, 1.0);
    var o: VOut;
    o.pos = camera.mvp * wp;
    o.wpos = wp.xyz;
    o.nrm = normalize((model.model * vec4<f32>(v.nrm, 0.0)).xyz);
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let n = normalize(in.nrm);
    let v = normalize(eye.pos.xyz - in.wpos);
    let nl = max(dot(n, normalize(vec3<f32>(0.35, 0.9, 0.3))), 0.0);
    // 深度渐变（深蓝→亮青，按世界高度）
    let hgt = clamp((in.wpos.y + 0.1) / 1.1, 0.0, 1.0);
    let base = mix(vec3<f32>(0.02, 0.09, 0.20), vec3<f32>(0.12, 0.50, 0.80), hgt);
    let rim = pow(1.0 - max(dot(n, v), 0.0), 3.0);
    let spec = pow(max(dot(reflect(-normalize(vec3<f32>(0.3, 1.0, 0.35)), n), v), 0.0), 48.0);
    let col = base * (0.4 + 0.6 * nl) + vec3<f32>(0.25, 0.75, 1.0) * rim * 0.55 + vec3<f32>(1.0) * spec * 0.55;
    // **视深 24bit 打包写入 rgb**（离屏 = Rgba8Unorm 线性——rgb 三通道
    // 定点 5.5m/16M ≈ 0.33μm/级，量化彻底消失。编码窗 = 槽域深度带
    // [1.5,7]m。曾 alpha 8bit：全视锥编码流体带仅 15 级 ×0.24m = 法线
    // 重建假法线暗月牙；收窗后仍 2.2cm/级台阶 spec 萤火（2026-11-23
    // 用户目验"脏图形"两轮根因）。alpha = 覆盖标记 1.0；背景 =
    // 不透明哨兵 fill((0,0,0,255))，合成端打包值 x==0 判空）
    let vd = length(in.wpos - eye.pos.xyz);
    let d01 = clamp((vd - 1.5) / 5.5, 0.0, 1.0);
    let x = floor(d01 * 16777215.0 + 0.5);
    let r8 = floor(x / 65536.0);
    let g8 = floor((x - r8 * 65536.0) / 256.0);
    let b8 = x - r8 * 65536.0 - g8 * 256.0;
    return vec4<f32>(r8 / 255.0, g8 / 255.0, b8 / 255.0, 1.0);
}
"""

WGSL_GLOW = """
struct Camera { mvp: mat4x4<f32> };
struct Model  { model: mat4x4<f32> };
struct Eye    { pos: vec4<f32> };
@group(0) @binding(0) var<uniform> camera: Camera;
@group(0) @binding(1) var<uniform> model: Model;
@group(0) @binding(2) var<uniform> eye: Eye;
struct VIn { @location(0) pos: vec3<f32>, @location(1) nrm: vec3<f32> }
struct VOut { @builtin(position) pos: vec4<f32>, @location(0) wpos: vec3<f32>, @location(1) nrm: vec3<f32> }
@vertex
fn vs_main(v: VIn) -> VOut {
    let wp = model.model * vec4<f32>(v.pos, 1.0);
    var o: VOut;
    o.pos = camera.mvp * wp;
    o.wpos = wp.xyz;
    o.nrm = normalize((model.model * vec4<f32>(v.nrm, 0.0)).xyz);
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let n = normalize(in.nrm);
    let v = normalize(eye.pos.xyz - in.wpos);
    let a = pow(1.0 - max(dot(n, v), 0.0), 1.8) * 0.55;
    return vec4<f32>(vec3<f32>(0.20, 0.60, 1.0) * a, a);
}
"""

# ── screen-space 流体着色器 v3.3——SDF 式连续液面（可分离高斯深度场
# 平滑）：blurH/blurV 双 pass 把**球缘深度差横向纵向抹平**（跨球融合
# ——逐球 rim 深度起伏正是"单个球"观感的来源， bilateral 的边缘保持
# 恰好保住了它），着色 pass 在平滑场上做梯度法线重建 = 连续液面。
# FluidParams 80B（dir = 模糊方向共享布局；三 pass 各持独立 uniform
# ——raw 会话回放延迟性，共享 buf 被后写覆盖）

WGSL_BLUR = """
struct FluidParams {
    texel: vec2<f32>,
    tan_half: f32,
    aspect: f32,
    near: f32,
    far: f32,
    light: vec3<f32>,
    bg: vec3<f32>,
    dir: vec2<f32>,        // 模糊方向（H=(1,0) / V=(0,1)）
    pad: vec2<f32>,
};
@group(0) @binding(0) var tex: texture_2d<f32>;
@group(0) @binding(1) var<uniform> fp: FluidParams;
struct VIn { @location(0) pos: vec2<f32>, @location(1) uv: vec2<f32> }
struct VOut { @builtin(position) pos: vec4<f32>, @location(0) uv: vec2<f32> }
@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    o.pos = vec4<f32>(v.pos, 0.0, 1.0);
    o.uv = v.uv;
    return o;
}
// **24bit 打包视深读取**（x == 0 = 哨兵背景 → 返 -1；越界 textureLoad
// 返零 = 哨兵 = 自动出局）
fn load_d01(px: vec2<i32>) -> f32 {
    let t = textureLoad(tex, px, 0);
    let x = floor(t.r * 255.0 + 0.5) * 65536.0
          + floor(t.g * 255.0 + 0.5) * 256.0
          + floor(t.b * 255.0 + 0.5);
    if (x < 0.5) {
        return -1.0;
    }
    return x / 16777215.0;
}
// 24bit 打包回写（平滑场下游同协议解包；alpha 恒 1 = 覆盖语义）
fn store_d01(d01: f32) -> vec4<f32> {
    let x = floor(clamp(d01, 0.0, 1.0) * 16777215.0 + 0.5);
    let r8 = floor(x / 65536.0);
    let g8 = floor((x - r8 * 65536.0) / 256.0);
    let b8 = x - r8 * 65536.0 - g8 * 256.0;
    return vec4<f32>(r8 / 255.0, g8 / 255.0, b8 / 255.0, 1.0);
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let pc = vec2<i32>(floor(in.pos.xy));
    if (load_d01(pc) < 0.0) {
        return vec4<f32>(vec3<f32>(0.0), 1.0);   // 哨兵背景透传
    }
    // **可分离高斯 σ≈5（±12px）**——纯几何权重，**无深度差权重**：
    // 跨球融合 = 液面连续化本意；背景 tap 由哨兵判据出局
    var sum = 0.0;
    var wsum = 0.0;
    let stp = vec2<i32>(i32(fp.dir.x + 0.5), i32(fp.dir.y + 0.5));
    for (var i: i32 = -12; i <= 12; i++) {
        let tap = load_d01(pc + stp * i);
        if (tap >= 0.0) {
            let w = exp(-f32(i * i) / 50.0);     // 2σ²=50
            sum += tap * w;
            wsum += w;
        }
    }
    if (wsum < 0.0001) {
        return vec4<f32>(vec3<f32>(0.0), 1.0);   // 全无效 = 背景哨兵
    }
    return store_d01(sum / wsum);
}
"""

WGSL_SHADE = """
struct FluidParams {
    texel: vec2<f32>,
    tan_half: f32,
    aspect: f32,
    near: f32,
    far: f32,
    light: vec3<f32>,
    bg: vec3<f32>,
    dir: vec2<f32>,        // 未用（布局对齐 blur——三 buf 同构）
    pad: vec2<f32>,
};
@group(0) @binding(0) var tex: texture_2d<f32>;
@group(0) @binding(1) var<uniform> fp: FluidParams;
struct VIn { @location(0) pos: vec2<f32>, @location(1) uv: vec2<f32> }
struct VOut { @builtin(position) pos: vec4<f32>, @location(0) uv: vec2<f32> }
@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    o.pos = vec4<f32>(v.pos, 0.0, 1.0);
    o.uv = v.uv;
    return o;
}
// 米制视深反推（d01 → 米）——与球 pass 的 [1.5,7]m 编码窗互逆
fn d01_to_meters(d01: f32) -> f32 {
    return d01 * (fp.far - fp.near) + fp.near;
}
// **24bit 打包视深读取**（x == 0 = 哨兵背景 → 返 -1）
fn load_d01(px: vec2<i32>) -> f32 {
    let t = textureLoad(tex, px, 0);
    let x = floor(t.r * 255.0 + 0.5) * 65536.0
          + floor(t.g * 255.0 + 0.5) * 256.0
          + floor(t.b * 255.0 + 0.5);
    if (x < 0.5) {
        return -1.0;
    }
    return x / 16777215.0;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let pc = vec2<i32>(floor(in.pos.xy));
    // 平滑深度场（blurH/blurV 已就绪——球缘深度差已融合）
    let sm = load_d01(pc);
    // 米制视深反推 → 视空间位置 → 法线重建（屏幕空间梯度）
    // **导数必须先于非均匀分支**（WGSL uniform control flow——浏览器
    // Dawn 严格校验，桌面后端宽松不报；背景像素导数结果弃用无影响）
    let vz = d01_to_meters(sm);
    let t = fp.tan_half;
    let px = (in.uv.x - 0.5) * 2.0 * t * fp.aspect * vz;
    let py = (0.5 - in.uv.y) * 2.0 * t * vz;
    let pos = vec3<f32>(px, py, -vz);
    let n = normalize(cross(dpdx(pos), dpdy(pos)));
    let nf = select(n, -n, n.z > 0.0);
    // 背景（无液体——输出主屏背景色）
    if (sm < 0.0) {
        return vec4<f32>(fp.bg, 1.0);
    }
    // 流体着色（方向光+菲涅尔+深度色渐变）
    let L = normalize(fp.light);
    let nl = max(dot(nf, L), 0.0);
    let V = normalize(-pos);
    let fres = pow(1.0 - max(dot(nf, V), 0.0), 3.0) * 0.6;
    let hgt = clamp((d01_to_meters(sm) - fp.near) / (fp.far - fp.near), 0.0, 1.0);
    let base = mix(vec3<f32>(0.02, 0.10, 0.22), vec3<f32>(0.15, 0.55, 0.85), hgt);
    let spec = pow(max(dot(reflect(-L, nf), V), 0.0), 28.0) * 0.25;
    let col = base * (0.35 + 0.65 * nl) + vec3<f32>(0.3, 0.75, 1.0) * fres + vec3<f32>(1.0) * spec;
    return vec4<f32>(col, 1.0);
}
"""


# 单元球（半径 0.14 icosphere——fluid_test 同源；模型缩放定视觉半径）
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

# ── 物理与渲染状态 ──
CAP = 650               # 粒子上限（逐粒子双 pass 绘制预算）
TANK = (2.0, 0.9, 1.6)  # 水槽内腔半尺寸


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
    pygame.display.set_caption("fluid3d_game")
    screen = pygame.display.set_mode((800, 600)); pygame.render.set_fb_dump(True)
    cjk = pygame.font.Font("cjk", 15)
    ac = pygame.render.access()                        # 主（交换链格式——主 canvas 通道）
    ac_off = pygame.render.access(offscreen=True)          # 离屏（恒 RGBA8——离屏面管线用）
    cam_buf = ac.buffer(64, label="cam_buf")
    eye_buf = ac.buffer(16, label="eye_buf")

    # ── 物理：地面 + 四壁（rapier fixed——step(dt, solid) 自动耦合；
    # 渲染位置检验 = **相机**全周环绕，刚体保持 fixed）──
    solid = pp.PhysicsWorld3D(gravity=(0, -9.81, 0))
    solid.insert(
        pp.RigidBodyBuilder3D("fixed", translation=(0, -0.06, 0)),
        pp.ColliderBuilder3D("cuboid", hx=TANK[0] + 0.1, hy=0.06, hz=TANK[2] + 0.1,
                             friction=0.15))
    walls = [
        ((0.0, TANK[1] * 0.5, -TANK[2]), (TANK[0] + 0.08, TANK[1], 0.06)),
        ((0.0, TANK[1] * 0.5,  TANK[2]), (TANK[0] + 0.08, TANK[1], 0.06)),
        ((-TANK[0], TANK[1] * 0.5, 0.0), (0.06, TANK[1], TANK[2] + 0.08)),
        (( TANK[0], TANK[1] * 0.5, 0.0), (0.06, TANK[1], TANK[2] + 0.08)),
    ]
    for c, (hx, hy, hz) in walls:
        solid.insert(
            pp.RigidBodyBuilder3D("fixed", translation=c),
            pp.ColliderBuilder3D("cuboid", hx=hx, hy=hy, hz=hz, friction=0.2))
    solid.step_frame(1.0 / 60.0)

    # ── 动态刚体（浮球——丢进流体测试动态刚体×流体交互）──
    for i in range(3):
        solid.insert(
            pp.RigidBodyBuilder3D("dynamic", translation=(-0.2 + i * 0.2, 0.9, 0.0),
                                   linvel=(0.0, -1.0, 0.0)),
            pp.ColliderBuilder3D("ball", radius=0.08, density=2.0,
                                 restitution=0.3, friction=0.4))

    # ── 流体世界（salva DFSPH）——初始水块 + 龙头注水 ──
    fw = pp.FluidWorld(particle_radius=0.09)
    fh = fw.add_fluid_cuboid((0.0, 0.55, 0.0), (0.7, 0.5, 0.55))
    handles = [fh]  # 每次注水 = 新 fluid 句柄——渲染枚举全量


    def total_count():
        n = 0
        for h in handles:
            n += len(fw.fluid_particles(h)[0]) // 3
        return n  # 每次注水 = 新 fluid 句柄——渲染枚举全量

    # ── 资源链 ──
    sphere_mesh = ac.mesh(["float32x3", "float32x3"], SPHERE, label="sph")
    core_shader = ac.shader(WGSL_CORE, label="liq_core")
    glow_shader = ac.shader(WGSL_GLOW, label="liq_glow")
    cam_buf2 = cam_buf
    eye_buf2 = eye_buf
    core_uniforms = []
    glow_uniforms = []

    def ensure(count):
        while len(core_uniforms) < count:
            i = len(core_uniforms)
            cb = ac.buffer(64, label=f"core_m{i}")
            gb = ac.buffer(64, label=f"glow_m{i}")
            bind_c = ac.bind_group([(0, "uniform", cam_buf2), (1, "uniform", cb),
                                    (2, "uniform", eye_buf2)])
            bind_g = ac.bind_group([(0, "uniform", cam_buf2), (1, "uniform", gb),
                                    (2, "uniform", eye_buf2)])
            core_uniforms.append((cb, bind_c))
            glow_uniforms.append((gb, bind_g))

    core_pipe = None
    glow_pipe = None

    # ── screen-space 流体管线资源（v3.3——SDF 式连续液面：球 pass 离屏
    # depth 面 + blurH/blurV 可分离高斯深度场平滑 + 法线重建着色 pass）──
    fluid_surf = pygame.Surface((800, 600), depth_buffer=True)   # 离屏面（depth_buffer=True——render_depth 用）
    fluid_blur = pygame.Surface((800, 600))                      # blurH 中转（打包深度场）
    fluid_smooth = pygame.Surface((800, 600))                    # blurV 输出（平滑深度场——着色输入）
    fluid_comp = pygame.Surface((800, 600))                      # 合成面（全屏流体 pass 输出——draw_surface 贴主屏）
    # 全屏 quad——uv **y 翻转**（顶点 uv(0,0) 在 NDC(-1,-1)=屏幕左下，
    # 纹理 v=0 = 图像顶行；不翻 = 整幅垂直镜像 = 流体上下颠倒）
    quad_fs = ac.mesh(["float32x2", "float32x2"],
                      [-1.0, -1.0, 0.0, 1.0, 1.0, -1.0, 1.0, 1.0,
                       1.0, 1.0, 1.0, 0.0, -1.0, 1.0, 0.0, 0.0],
                      index_bytes=bytes([0,0, 1,0, 2,0, 0,0, 2,0, 3,0]),
                      label="quad_fs")
    blur_shader = ac.shader(WGSL_BLUR, label="fluid_blur_shader")
    fluid_shader = ac.shader(WGSL_SHADE, label="fluid_fs_shader")
    # **三 pass 各持独立 uniform**（raw 会话回放延迟性——共享 buf 被
    # 后写覆盖，同帧多 pass 各写同 buf = 前序 pass 拿到的是末次内容）
    fp_h = ac.buffer(80, label="fluid_fp_h")     # dir=(1,0)
    fp_v = ac.buffer(80, label="fluid_fp_v")     # dir=(0,1)
    fp_s = ac.buffer(80, label="fluid_fp_s")     # 着色参数

    def fp_write(buf, dir_x, dir_y):
        # 80B = 20 f32：texel/tan_half/aspect/near/far（pad2）/
        # light（pad1）/bg（pad1）/dir（pad2）——WGSL uniform 对齐布局
        ac.write_buffer(buf, [
            1.0 / 800.0, 1.0 / 600.0,
            M.tan(M.radians(52.0) * 0.5),
            800.0 / 600.0,
            1.5, 7.0, 0.0, 0.0,
            0.45, 0.85, 0.30, 0.0,
            10.0 / 255.0, 12.0 / 255.0, 18.0 / 255.0, 0.0,
            dir_x, dir_y, 0.0, 0.0,
        ])

    bind_h = ac.bind_group([(0, "texture", fluid_surf),
                            (1, "uniform", fp_h)], label="fluid_bind_h")
    bind_v = ac.bind_group([(0, "texture", fluid_blur),
                            (1, "uniform", fp_v)], label="fluid_bind_v")
    bind_s = ac.bind_group([(0, "texture", fluid_smooth),
                            (1, "uniform", fp_s)], label="fluid_bind_s")
    blur_pipe = ac_off.pipeline(blur_shader, quad_fs, [bind_h],
                            cull="none", blend="opaque", label="fluid_blur_pipe")
    fluid_pipe = ac_off.pipeline(fluid_shader, quad_fs, [bind_s],
                             cull="none", blend="opaque", label="fluid_ss_pipe")
    pixel_cam = pygame.render.game_camera_ortho(800, 600, 800, 600)
    dbg_renderer = pp.DebugLinesRenderer3D()
    dbg_draw = pp.DebugDraw3D()

    frame = 0
    while frame < 3600:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        solid.step_frame(1.0 / 60.0)
        # 流体**半步×2**（注水冲击粒子单步位移 5.6m/s×1/60≈0.093m 逼近
        # 0.12m 壁厚穿越阈值——debug python 偶发穿墙（用户实测）；半步
        # 0.047m < 粒子半径 0.09 安全余量）
        fw.step(1.0 / 120.0, solid)
        fw.step(1.0 / 120.0, solid)
        # **速度钳制**（DFSPH 冲击压力尖峰 15-20 m/s 半步整穿 0.12m 壁
        # ——用户实测残余穿透根因；上限 12：半步位移 0.1m < 0.12 壁厚）
        fw.clamp_velocity(12.0)

        # 注水（龙头）：每 8 帧一小股（每次 = 新 fluid 句柄）；全句柄
        # 粒子聚合渲染；上限保护
        if frame % 10 == 0 and total_count() < CAP:
            jx = 0.35 * M.sin(frame * 0.73)
            jz = 0.35 * M.cos(frame * 0.61)
            handles.append(fw.add_fluid_cuboid((jx, 1.62, jz), (0.2, 0.42, 0.2)))
        positions = []
        for h in handles:
            p, _v = fw.fluid_particles(h)
            positions.extend(p)
        count = len(positions) // 3
        ensure(count)

        # 相机**全周环绕**（渲染位置正确性检验——yaw 匀速转一周 20s 后
        # 持续；半径/高度恒定，流体应全程贴槽体线框不偏移）
        yaw = frame * 0.3                   # 0.3°/帧 = 18°/s → 一周 1200 帧（20s）
        eye = (M.sin(M.radians(yaw)) * 4.4, 2.8, M.cos(M.radians(yaw)) * 4.4)
        tgt = (0.0, 0.55, 0.0)
        d = (tgt[0] - eye[0], tgt[1] - eye[1], tgt[2] - eye[2])
        dl = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5
        pitch = M.degrees(M.asin(d[1] / dl))
        yaw_look = M.degrees(M.atan2(d[0], -d[2]))
        view = fps_view(eye, yaw_look, pitch)
        cam_m = pygame.render.game_camera_perspective(
            52.0, 800, 600, 800, 600, 0.1, 60.0).with_view(view)
        pygame.render.write_camera_mvp(cam_buf, cam_m.mvp())
        ac.write_buffer(eye_buf, [eye[0], eye[1], eye[2], 1.0])
        # 流体三 pass 参数（**每帧必写**——曾漏写 = uniform 全零整屏黑；
        # 三 buf 独立 = raw 会话回放延迟性下各 pass 拿到自己的内容）
        fp_write(fp_h, 1.0, 0.0)
        fp_write(fp_v, 0.0, 1.0)
        fp_write(fp_s, 0.0, 0.0)

        if core_pipe is None and count > 0:
            _cb, bind_c0 = core_uniforms[0]
            _gb, bind_g0 = glow_uniforms[0]
            core_pipe = ac_off.pipeline(core_shader, sphere_mesh, [bind_c0], cull="back",
                                    blend="opaque", depth_mode="standard",
                                    depth_write=True, label="liq_core_pipe")
            glow_pipe = ac_off.pipeline(glow_shader, sphere_mesh, [bind_g0], cull="back",
                                    blend="additive", depth_mode="standard",
                                    depth_write=False, label="liq_glow_pipe")

        # ── Pass 1：粒子球深度编码 → 离屏 fluid_surf（rgb = 24bit 打包
        # 视深 [1.5,7]m 编码窗；alpha = 覆盖标记）──
        # **raw 会话必须 with 形态**（裸赋值 = 命令记录但从不回放——
        # 2026-11-23 fluid 恒不可见根因之一）
        with fluid_surf.render() as ft:
            # **不透明哨兵清屏**（fill 走会话 alpha 混合材质——曾
            # fill((0,0,0,0))：srcAlpha=0 混合 = 保留原色 = 永远清不掉，
            # 上一帧球位残留 = 用户实测"每帧累计脏图形"；alpha=1 覆盖
            # 生效，背景判据 = 打包值 x==0（真实球像素 vd≥2.1m →
            # x≈1.8M 恒非零））
            ft.fill((0, 0, 0, 255))   # alpha 0-255 整数语义——曾 (…,1)=1/255≈透明混合=清不掉
            with ft.raw_render(depth=True) as p:
                if core_pipe is not None:
                    p.set_pipeline(core_pipe)
                    for i in range(count):
                        x = positions[i * 3]
                        y = positions[i * 3 + 1]
                        z = positions[i * 3 + 2]
                        ac.write_buffer(core_uniforms[i][0],
                                        M.mat4_translation(x, y, z) @ M.mat4_scale(1.15, 1.15, 1.15))
                        p.set_bind_group(0, core_uniforms[i][1])
                        p.draw_mesh(sphere_mesh)

        # ── Pass 2a：blurH（可分离高斯横向 σ≈5）fluid_surf → fluid_blur
        # ── Pass 2b：blurV（纵向）fluid_blur → fluid_smooth
        # ── Pass 3：着色（平滑场上梯度法线重建）fluid_smooth → fluid_comp
        # SDF 式连续液面 v3.3：跨球融合 = 球缘深度差横向纵向抹平（bilateral
        # 的边缘保持恰好保住了逐球 rim = "单个球"观感来源）；背景 tap 哨
        # 兵出局 = 轮廓不动；每面一帧一会话（回放时序 = 会话序天然串行）
        with fluid_blur.render() as fb:
            with fb.raw_render() as p:
                p.set_pipeline(blur_pipe)
                p.set_bind_group(0, bind_h)
                p.draw_mesh(quad_fs)
        with fluid_smooth.render() as fsm:
            with fsm.raw_render() as p:
                p.set_pipeline(blur_pipe)
                p.set_bind_group(0, bind_v)
                p.draw_mesh(quad_fs)
        # **合成不能 raw 在主屏**（raw 回放 = present 全部批之后、"恒在
        # 游戏内容之上"——全屏 quad 会把线框/HUD 全部盖掉；离屏面 raw =
        # flush 收口只盖自己，再以游戏内容批 draw_surface 贴主屏）
        with fluid_comp.render() as fc:
            with fc.raw_render() as p:
                p.set_pipeline(fluid_pipe)
                p.set_bind_group(0, bind_s)
                p.draw_mesh(quad_fs)

        with screen.render() as rt:
            rt.fill((10, 12, 18))
            # ── Pass 3：流体合成贴主屏（gfxdraw 像素域 blit——全屏
            # 800×600 恰好铺满；游戏内容批——与线框/HUD 同序）──
            pygame.gfxdraw.set_camera(rt, pixel_cam)
            pygame.gfxdraw.draw_surface(rt, fluid_comp)
            # 水槽线框（rapier 边界 collect——**每帧**绘制：曾隔帧
            # frame % 2"省带宽"= 30Hz 闪烁，2026-11-19 用户实测根修；
            # sink 每帧局部新建 + vbo/ibo 逐帧覆写）
            sink = pp.LineSink3D()
            pp.collect3d(solid, dbg_draw, sink)
            dbg_renderer.set_mvp(cam_m.mvp())
            rt.draw_debug_3d(dbg_renderer, sink)

            # HUD（段级显式像素相机——v3.1 全显式：None 段 = NDC，像素
            # 域必须声明；画毕 clear_camera 交还段状态）
            pygame.gfxdraw.set_camera(rt, pixel_cam)
            pygame.gfxdraw.draw_surface(rt, cjk.render(
                f"[fluid3d] 粒子 {count} | 相机 {yaw % 360.0:.0f}° | ESC 退出",
                True, (190, 210, 235)), transform=M.mat4_translation(-388, 288, 0))
            pygame.gfxdraw.clear_camera(rt)

        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1
