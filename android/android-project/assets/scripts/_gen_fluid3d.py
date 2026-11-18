# -*- coding: utf-8 -*-
"""fluid3d_game.py 生成器（SPHERE 数组从 fluid_test 提取拼接）"""
import re

src = open(r'D:/Projects/Rust/pygame-rs-dev/examples/fluid_test.py', encoding='utf-8').read()
m = re.search(r'SPHERE = \[(.*?)\]\n', src, re.S)
sphere = m.group(1).strip()

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
    return vec4<f32>(col, 1.0);
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
    let a = pow(1.0 - max(dot(n, v), 0.0), 2.2) * 0.30;
    return vec4<f32>(vec3<f32>(0.20, 0.60, 1.0) * a, a);
}
"""

body = '''
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
    screen = pygame.display.set_mode((800, 600))
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

    # ── 流体世界（salva DFSPH）——初始水块 + 龙头注水 ──
    fw = pp.FluidWorld(particle_radius=0.09)
    fh = fw.add_fluid_cuboid((0.0, 0.55, 0.0), (0.7, 0.5, 0.55))

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

    dbg_renderer = pp.DebugLinesRenderer3D()
    dbg_draw = pp.DebugDraw()

    frame = 0
    while frame < 3600:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        solid.step_frame(1.0 / 60.0)
        fw.step(1.0 / 60.0, solid)

        # 注水（龙头）：每 8 帧一小股；上限保护
        positions, _vel = fw.fluid_particles(fh)
        count = len(positions) // 3
        if frame % 8 == 0 and count < CAP:
            fw.add_fluid_cuboid((0.0, 1.65, 0.0), (0.13, 0.13, 0.13))
        positions, _vel = fw.fluid_particles(fh)
        count = len(positions) // 3
        ensure(count)

        # 相机（第三人称环绕 + 俯角）
        t_sec = frame / 60.0
        yaw = 25.0 * M.sin(t_sec * 0.22)
        eye = (M.sin(M.radians(yaw)) * 4.3, 2.55, M.cos(M.radians(yaw)) * 4.3)
        view = fps_view(eye, yaw, -17.0)
        cam_m = pygame.render.game_camera_perspective(
            52.0, 800 / 600, 0.1, 60.0).with_view(view)
        ac.write_buffer(cam_buf, cam_m.mvp())
        ac.write_buffer(eye_buf, M.mat4_translation(eye[0], eye[1], eye[2]))

        if core_pipe is None and count > 0:
            _cb, bind_c0 = core_uniforms[0]
            _gb, bind_g0 = glow_uniforms[0]
            core_pipe = ac.pipeline(core_shader, sphere_mesh, [bind_c0], cull="back",
                                    blend="opaque", depth_mode="standard",
                                    depth_write=True, label="liq_core_pipe")
            glow_pipe = ac.pipeline(glow_shader, sphere_mesh, [bind_g0], cull="back",
                                    blend="additive", depth_mode="standard",
                                    depth_write=False, label="liq_glow_pipe")

        with screen.render() as rt:
            rt.fill((10, 12, 18))
            with screen.raw_render(depth=True) as p:
                # 水槽线框（rapier 边界 collect——隔帧一次省带宽）
                if frame % 2 == 0:
                    sink = pp.LineSink3D()
                    pp.collect3d(solid, dbg_draw, sink)
                    dbg_renderer.set_mvp(cam_m.mvp())
                    rt.draw_debug_3d(dbg_renderer, sink)
                # ① 液体核心球（不透明深度写入）
                if core_pipe is not None:
                    p.set_pipeline(core_pipe)
                    for i in range(count):
                        x = positions[i * 3]
                        y = positions[i * 3 + 1]
                        z = positions[i * 3 + 2]
                        ac.write_buffer(core_uniforms[i][0],
                                        M.mat4_translation(x, y, z) @ M.mat4_scale(0.92))
                        p.set_bind_group(0, core_uniforms[i][1])
                        p.draw_mesh(sphere_mesh)
                # ② 加性光晕壳（1.5×，深度测试开/写关）
                if glow_pipe is not None:
                    p.set_pipeline(glow_pipe)
                    for i in range(count):
                        x = positions[i * 3]
                        y = positions[i * 3 + 1]
                        z = positions[i * 3 + 2]
                        ac.write_buffer(glow_uniforms[i][0],
                                        M.mat4_translation(x, y, z) @ M.mat4_scale(1.42))
                        p.set_bind_group(0, glow_uniforms[i][1])
                        p.draw_mesh(sphere_mesh)

            # HUD（像素域——未 set_camera，段级 = 画布像素正交）
            pygame.gfxdraw.set_transform(rt, M.mat4_translation(-388, 288, 0))
            pygame.gfxdraw.draw_surface(rt, cjk.render(
                f"[fluid3d] 粒子 {count} | 空格=注水爆发 | ESC 退出",
                True, (190, 210, 235)))

        pygame.display.flip()
        await pygame.next_frame()
        frame += 1
'''

out = ('# fluid3d_game —— 3D 游戏流体渲染案例（游戏场景液体观感专项）\n'
       '# 玻璃水槽（rapier 四壁+地面，step(dt, solid) 自动耦合 salva）+ 高处持续注水：\n'
       '# SPH 粒子双层渲染 = 游戏液体观感核心——\n'
       '#   ①不透明核心球（高度渐变深蓝 + 菲涅尔边缘光 + 高光）深度写入\n'
       '#   ②加性光晕壳（1.42×半径，深度测试开/写关）——重叠融为连贯液面\n'
       '# 相机：第三人称环绕（慢速 yaw 漂移 + 俯角）；空格 = 注水爆发；ESC 退出\n'
       'import pygame\n'
       'import pygame_physics as pp\n'
       'import pygame.math as M\n\n'
       'WGSL_CORE = """' + WGSL_CORE + '"""\n\n'
       'WGSL_GLOW = """' + WGSL_GLOW + '"""\n\n'
       '# 单元球（半径 0.14 icosphere——fluid_test 同源；模型缩放定视觉半径）\n'
       'SPHERE = [' + sphere + ']\n'
       + body)

open(r'D:/Projects/Rust/pygame-rs-dev/examples/fluid3d_game.py', 'w', encoding='utf-8').write(out)
print('written', len(out))
