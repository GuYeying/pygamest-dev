# compute_probe —— GPU 粒子系统 v3：档位可选（egui 复选框）+ FPS 实时上屏
# 数据通路 v3 = storage → **mesh 顶点缓冲（instanced 步进）**：
#   instanced draw 每实例一粒，pos 经顶点属性直进 VS——顶点属性是
#   固定功能通路，规避 VS 段纹理/SSBO 读取的多平台静默失效
#   （DX12/GLES 双实测 2026-10-30；uniform 另有 64KB 上限）。
# 粒子自初始化在 GPU（WGSL hash——百万级 Python 列表不可行）；档位
# 切换 = cfg.mode=1 单帧自初始化 + draw_indirect [3, n, 0, 0]。
# 桌面/真机共用；console 仅档位切换一行日志（大数输出已去除）。
import pygame
import pygame_gui as egui

MAXN = 1048576                       # 顶点缓冲容量（105 万粒）
TIERS = [(2048, "2048"), (65536, "6.5万"), (262144, "26万"), (MAXN, "105万")]

COMPUTE_WGSL = """
struct Particle { pos: vec4<f32>, vel: vec4<f32> };   // vec4 对齐：平面连续
@group(0) @binding(0) var<storage, read_write> state: array<Particle>;
struct Config { n: u32, mode: u32, dt_ms: u32, pad1: u32 };
@group(0) @binding(1) var<uniform> cfg: Config;
@group(0) @binding(2) var<storage, read_write> out_pos: array<vec2<f32>>;   // 连续 pos 平面（渲染拷贝源）

fn hash(u0: u32) -> u32 {          // bit-mix（GPU 自初始化伪随机）
    var x = u0;
    x ^= x >> 16u; x *= 0x7feb352du;
    x ^= x >> 15u; x *= 0x846ca68bu;
    x ^= x >> 16u;
    return x;
}

@compute @workgroup_size(64)
fn cs_main(@builtin(global_invocation_id) gid: vec3<u32>) {
    if (gid.x >= cfg.n) { return; }
    var p = state[gid.x];
    if (cfg.mode == 1u) {           // 单帧自初始化（脚本置 mode=1 一帧后回 0）
        p.pos = vec4<f32>(-300.0 + f32(hash(gid.x) % 600u),
                          -200.0 + f32(hash(gid.x ^ 0x9e3779b9u) % 400u), 0.0, 0.0);
        p.vel = vec4<f32>(f32(hash(gid.x ^ 0x85ebca6bu) % 121u) - 60.0,
                          f32(hash(gid.x ^ 0xc2b2ae35u) % 61u) - 30.0, 0.0, 0.0);
    }
    // dt 驱动（真实毫秒→秒，钳 1..50ms——帧率解耦，各平台运动一致）
    let dt = clamp(f32(cfg.dt_ms) / 1000.0, 0.001, 0.05);
    p.vel = p.vel + vec4<f32>(0.0, -240.0, 0.0, 0.0) * dt;  // 重力
    p.pos = p.pos + p.vel * dt;                              // 积分
    if (p.pos.x < -390.0 || p.pos.x > 390.0) {                  // 反弹
        p.vel.x = -p.vel.x;
        p.pos.x = clamp(p.pos.x, -390.0, 390.0);
    }
    if (p.pos.y < -290.0 || p.pos.y > 290.0) {
        p.vel.y = -p.vel.y;
        p.pos.y = clamp(p.pos.y, -290.0, 290.0);
    }
    state[gid.x] = p;
    out_pos[gid.x] = p.pos.xy;      // 连续平面直写（避免 32B 交错拷贝错位）
}
"""

RENDER_WGSL = """
struct Camera { mvp: mat4x4<f32> };
@group(0) @binding(0) var<uniform> camera: Camera;

struct VOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) color: vec3<f32>,
};

const CORNERS = array<vec2<f32>, 3>(
    vec2<f32>(-2.0, -2.0), vec2<f32>(2.0, -2.0), vec2<f32>(0.0, 2.0));

// instanced：每实例一粒——pos = 顶点属性（实例步进，固定功能可靠通路）；
// vertex_index 每实例归零 → corner 常量展开；instance_index → 色相
@vertex
fn vs_main(@location(0) pos: vec2<f32>,
           @builtin(vertex_index) vi: u32,
           @builtin(instance_index) ii: u32) -> VOut {
    let hue = f32(ii % 64u) / 64.0;
    var o: VOut;
    o.pos = camera.mvp * vec4<f32>(pos + CORNERS[vi], 0.0, 1.0);
    o.color = vec3<f32>(hue, 0.9 - hue * 0.6, 0.3 + hue * 0.4);
    return o;
}

@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    return vec4<f32>(in.color, 1.0);
}
"""


class HUD(egui.UiBase):
    """档位复选框（互斥）+ FPS。切换经 switch_to 由主循环消费。"""

    def __init__(self):
        self.tier = 0
        self.switch_to = -1            # >=0 = 主循环切档
        self.fps = 0.0
        self.n = TIERS[0][0]

    def draw(self, ui):
        ui.heading("GPU 粒子档位")
        for i in range(len(TIERS)):
            name = TIERS[i][1]
            checked = ui.checkbox(name, self.tier == i)
            if checked and self.tier != i:
                self.switch_to = i
                self.tier = i
        ui.separator()
        ui.label(f"粒子数 {self.n}")
        ui.label(f"FPS {self.fps:.1f}")


async def main():
    screen = pygame.display.set_mode((800, 600))
    ac = pygame.render.access()
    egui.init()
    hud = HUD()
    cjk = pygame.font.Font("cjk", 16)

    # ── 资源链（一次建满档；粒子自初始化在 GPU，Python 零循环）──
    compute_shader = ac.shader(COMPUTE_WGSL, label="p3_cs")
    render_shader = ac.shader(RENDER_WGSL, label="p3_rs")

    state = ac.buffer(MAXN * 32, usage="storage", label="p3_state")
    pos_out = ac.buffer(MAXN * 8, usage="storage", label="p3_posout")   # vec2 × MAXN
    # inst_pos2：实例步进网格（容量预留零填充——pos 每帧 GPU 直搬进来）
    # floats = MAXN×2（inst_pos2 = 每实例 vec2 = 8B——此前 MAXN 少算一半）
    mesh = ac.mesh("inst_pos2", floats=MAXN * 2, label="p3_mesh")
    cfg_buf = ac.buffer(16, label="p3_cfg")
    cam_buf = ac.buffer(64, label="p3_cam")
    ind_buf = ac.buffer(16, usage="indirect", label="p3_ind")

    state_bind = ac.bind_group(
        [(0, "storage_rw", state), (1, "uniform", cfg_buf),
         (2, "storage_rw", pos_out)], label="p3_state_bind")
    rbind = ac.bind_group([(0, "uniform", cam_buf)], label="p3_rbind")
    cpipe = ac.compute_pipeline(compute_shader, [state_bind], label="p3_cpipe")
    rpipe = ac.pipeline(render_shader, mesh, [rbind], label="p3_rpipe")
    cam = pygame.render.camera_ortho(800.0, 600.0)

    frame = 0
    reset_frame = -10               # mode=1 生效帧（下一帧回 0）
    fps = 0.0
    last_ticks = pygame.time.get_ticks()
    fps_surf = None                 # FPS 文本缓存（每 10 帧重渲）

    def set_tier(i):
        n = TIERS[i][0]
        hud.n = n
        ac.write_buffer_u32(cfg_buf, [n, 1, 16, 0])          # mode=1 自初始化
        ac.write_buffer_u32(ind_buf, [3, n, 0, 0])           # 3 顶点 × n 实例
        print(f"[cp3] 档位 → {TIERS[i][1]}（{n} 粒）")

    set_tier(0)
    last_ticks = pygame.time.get_ticks()
    while True:
        for e in pygame.event.get():
            egui.event(e)
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN and e.key == pygame.key.K_ESCAPE:
                return

        # 切档收口：mode=1 只保持一帧；dt 驱动（真实毫秒，钳 1..50）
        now_ticks = pygame.time.get_ticks()
        dt_ms = min(50, max(1, now_ticks - last_ticks))
        last_ticks = now_ticks
        if reset_frame >= 0 and frame == reset_frame + 1:
            ac.write_buffer_u32(cfg_buf, [hud.n, 0, dt_ms, 0])
            reset_frame = -10
        elif frame != reset_frame:
            ac.write_buffer_u32(cfg_buf, [hud.n, 0, dt_ms, 0])
        if hud.switch_to >= 0:
            set_tier(hud.switch_to)
            hud.switch_to = -1
            reset_frame = frame

        pygame.render.write_camera_mvp(cam_buf, cam.mvp())

        # FPS（EMA 平滑；10 帧一刷文本）
        now = pygame.time.get_ticks()
        dt = now - last_ticks
        last_ticks = now
        if dt > 0:
            fps = fps * 0.9 + (1000.0 / dt) * 0.1
        hud.fps = fps
        if frame % 10 == 0:
            fps_surf = cjk.render(
                f"FPS {fps:.1f} · {hud.n} 粒 · instanced 通路",
                True, (180, 220, 255))

        with screen.render() as t:
            t.fill((6, 8, 14))
            pygame.gfxdraw.set_color(t,(255, 0, 255))
            pygame.gfxdraw.rectangle(t, (-399, -299, 798, 598),)  # 原 width=2 描边（gfxdraw 恒 1px）       # 画布边界诊断
            with t.raw_compute() as p:
                p.set_pipeline(cpipe)
                p.set_bind_group(0, state_bind)
                p.dispatch(MAXN // 64, 1, 1)                  # shader 端 cfg.n 早退
                # 连续 pos 平面 → 顶点缓冲（8B/粒子；源 = out_pos 非交错）
                p.copy_mesh_vertices(mesh, pos_out, hud.n * 8)
            with t.raw_render() as p:
                p.set_pipeline(rpipe)
                p.set_bind_group(0, rbind)
                p.set_mesh(mesh)
                p.draw_indirect(ind_buf, 0)                   # [3, n, 0, 0]
            if fps_surf:
                pygame.gfxdraw.set_transform(t, pygame.math.mat4_translation(-370, 280, 0)); pygame.gfxdraw.draw_surface(t, fps_surf)
            t.draw_ui(hud)
        pygame.display.flip()
        frame += 1
        await pygame.next_frame()
