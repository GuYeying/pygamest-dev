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
    // **视深归一写入 alpha**（screen-space 流体管线输入——depth01 供
    // bilateral 平滑与法线重建；near=0.5 far=60 与主相机参数一致）
    let vd = length(in.wpos - eye.pos.xyz);
    let d01 = clamp((vd - 0.5) / 59.5, 0.0, 1.0);
    return vec4<f32>(col, d01);
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

WGSL_FLUID_FS = """
struct FluidParams {
    texel: vec2<f32>,      // 1/宽, 1/高
    tan_half: f32,         // tan(fov_y/2)
    aspect: f32,
    near: f32,
    far: f32,
    light: vec3<f32>,
    bg: vec3<f32>,
};
@group(0) @binding(0) var tex: texture_2d<f32>;
@group(0) @binding(1) var samp: sampler;
@group(0) @binding(2) var<uniform> fp: FluidParams;
struct VIn { @location(0) pos: vec2<f32>, @location(1) uv: vec2<f32> }
struct VOut { @builtin(position) pos: vec4<f32>, @location(0) uv: vec2<f32> }
@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    o.pos = vec4<f32>(v.pos, 0.0, 1.0);
    o.uv = v.uv;
    return o;
}
// 米制视深反推（d01 → 米）——与球 pass 的 depth01 编码互逆
fn d01_to_meters(d01: f32) -> f32 {
    return d01 * (fp.far - fp.near) + fp.near;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let d0 = textureSampleLevel(tex, samp, in.uv, 0.0).a;
    // 背景（离屏 alpha=0 = 无液体——输出主屏背景色）
    if (d0 < 0.004) {
        return vec4<f32>(fp.bg, 1.0);
    }
    // **5×5 bilateral**（深度差高斯权重——球边缘深度跳变不跨边平滑）
    var sum = 0.0;
    var wsum = 0.0;
    for (var dy: i32 = -2; dy <= 2; dy++) {
        for (var dx: i32 = -2; dx <= 2; dx++) {
            let uv2 = in.uv + vec2<f32>(f32(dx), f32(dy)) * fp.texel;
            let sd = textureSampleLevel(tex, samp, uv2, 0.0).a;
            let dd = (sd - d0) * 12.0;
            let sp = exp(-f32(dx * dx + dy * dy) * 0.15);
            let w = sp * exp(-dd * dd);
            sum += sd * w;
            wsum += w;
        }
    }
    let sm = select(d0, sum / max(wsum, 0.0001), wsum > 0.0);
    // 米制视深反推 → 视空间位置 → 法线重建（屏幕空间梯度）
    let vz = d01_to_meters(sm);
    let t = fp.tan_half;
    let px = (in.uv.x - 0.5) * 2.0 * t * fp.aspect * vz;
    let py = (0.5 - in.uv.y) * 2.0 * t * vz;
    let pos = vec3<f32>(px, py, -vz);
    let n = normalize(cross(dpdx(pos), dpdy(pos)));
    let nf = select(n, -n, n.z > 0.0);
    // 流体着色（方向光+菲涅尔+深度色渐变）
    let L = normalize(fp.light);
    let nl = max(dot(nf, L), 0.0);
    let V = normalize(-pos);
    let fres = pow(1.0 - max(dot(nf, V), 0.0), 3.0) * 0.6;
    let hgt = clamp((sm - fp.near) / (fp.far * 0.3), 0.0, 1.0);
    let base = mix(vec3<f32>(0.02, 0.10, 0.22), vec3<f32>(0.15, 0.55, 0.85), hgt);
    let spec = pow(max(dot(reflect(-L, nf), V), 0.0), 40.0) * 0.5;
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
    ac = pygame.render.access()
    cam_buf = ac.buffer(64, label="cam_buf")
    eye_buf = ac.buffer(16, label="eye_buf")

    # ── 物理：地面 + 四壁（rapier fixed——step(dt, solid) 自动耦合）──
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

    # ── screen-space 流体管线资源（v3.2——离屏 depth 面 + 全屏
    # bilateral/法线重建/着色 pass）──
    fluid_surf = pygame.Surface((800, 600), depth_buffer=True)   # 离屏面（depth_buffer=True——render_depth 用）
    quad_fs = ac.mesh(["float32x2", "float32x2"],
                      [-1.0, -1.0, 0.0, 0.0, 1.0, -1.0, 1.0, 0.0,
                       1.0, 1.0, 1.0, 1.0, -1.0, 1.0, 0.0, 1.0],
                      label="quad_fs")
    fluid_shader = ac.shader(WGSL_FLUID_FS, label="fluid_fs_shader")
    fluid_fp = ac.buffer(64, label="fluid_fp")
    fluid_bind = ac.bind_group([(0, "texture", fluid_surf),
                                (1, "sampler", None),
                                (2, "uniform", fluid_fp)],
                               label="fluid_bind")
    fluid_pipe = ac.pipeline(fluid_shader, quad_fs, [fluid_bind],
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
        fw.step(1.0 / 60.0, solid)

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

        # 相机（第三人称环绕 + 俯角）
        t_sec = frame / 60.0
        yaw = 25.0 * M.sin(t_sec * 0.22)
        eye = (M.sin(M.radians(yaw)) * 4.1, 2.9, M.cos(M.radians(yaw)) * 4.1)
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

        if core_pipe is None and count > 0:
            _cb, bind_c0 = core_uniforms[0]
            _gb, bind_g0 = glow_uniforms[0]
            core_pipe = ac.pipeline(core_shader, sphere_mesh, [bind_c0], cull="back",
                                    blend="opaque", depth_mode="standard",
                                    depth_write=True, label="liq_core_pipe")
            glow_pipe = ac.pipeline(glow_shader, sphere_mesh, [bind_g0], cull="back",
                                    blend="additive", depth_mode="standard",
                                    depth_write=False, label="liq_glow_pipe")

        # ── Pass 1：粒子球深度编码 → 离屏 fluid_surf（alpha = 视深01）──
        # screen-space 流体管线（v3.2——球间融合成连续液体表面替代单球
        # 观感）：球 pass 输出视深归一到 alpha，主屏全屏 pass 做 bilateral
        # 平滑 + 法线重建 + 流体着色
        with fluid_surf.render() as ft:
            ft.fill((0, 0, 0, 0))
            p = ft.raw_render(depth=True)
            if core_pipe is not None:
                p.set_pipeline(core_pipe)
                for i in range(count):
                    x = positions[i * 3]
                    y = positions[i * 3 + 1]
                    z = positions[i * 3 + 2]
                    ac.write_buffer(core_uniforms[i][0],
                                    M.mat4_translation(x, y, z) @ M.mat4_scale(0.92, 0.92, 0.92))
                    p.set_bind_group(0, core_uniforms[i][1])
                    p.draw_mesh(sphere_mesh)

        with screen.render() as rt:
            rt.fill((10, 12, 18))
            # ── Pass 2：主屏全屏流体 pass（bilateral 平滑 + 法线重建 +
            # 流体着色——采样 fluid_surf 的 alpha 视深）──
            with screen.raw_render() as p:
                p.set_pipeline(fluid_pipe)
                p.set_bind_group(0, fluid_bind)
                p.draw_mesh(quad_fs)
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
            pygame.gfxdraw.set_transform(rt, M.mat4_translation(-388, 288, 0))
            pygame.gfxdraw.draw_surface(rt, cjk.render(
                f"[fluid3d] 粒子 {count} | 空格=注水爆发 | ESC 退出",
                True, (190, 210, 235)))
            pygame.gfxdraw.clear_camera(rt)

        pygame.display.flip()
        await pygame.tasks.yield_now()
        frame += 1
