# voxel_mc_test —— pygame_voxelis 极简 MC 案例（阶段二验收样张，
# 2026-11-16 优化版）：
# 稀疏体素地形（VoxWorld 16×16×16 体素/chunk，体素 1.0）+ rapier3d
# 体素物理（表面 cuboid + 动态方块发射）+ 射线选择（cast_ray 命中 →
# 删除/放置）+ mesh_builder 法线光照渲染。
# 优化四点：① GameCamera 显式相机接入（perspective + set_camera 定约
# ——MVP = game.cam.mvp()（world→画布 fit_ndc 内聚）经 write_camera_mvp
# 的 fit 双乘）② 球渲染/物理尺寸对齐（mesh scale = 2×collider half
# ——修复"碰撞体积与渲染网格大小不符"）③ 单块顶点语义 probe（mesh
# 世界盒 [x,x+1] ≡ collider 盒——证词打点）④ 删除顶层后的露层 collider
# 增量补挂（消除"mesh 有块物理穿"）。
# 交互：鼠标拖拽转向 / WASD-QE 漫游 / 左键删 / 右键放 / F 发射方块 /
# R 重建地形 / ESC 退出。控制台 [voxel-mc] 打点逐项验证。
import pygame
import pygame_voxelis
import pygame_physics as rp3  # noqa: 已有 rp3 别名（流体面 pp 同库）
import pygame_physics as rp3

# 三角函数面 = pygame.math 模块属性（import 子模块需 __path__ 不可用；
# 属性直取——模块级供 fps_view 等顶层函数引用）
M = pygame.math

# WGSL：顶点 = pos3 + normal3；片元 = 法线光照 + 世界坐标程序染色
# （顶面草绿 checker / 侧面土棕——体素值染色走扩展 attribute，v2 再接）
WGSL_VOXEL = """
struct Camera {
    mvp: mat4x4<f32>,
};

@group(0) @binding(0) var<uniform> camera: Camera;

struct VIn {
    @location(0) pos: vec3<f32>,
    @location(1) nrm: vec3<f32>,
}

struct VOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) world: vec3<f32>,
    @location(1) normal: vec3<f32>,
}

@vertex
fn vs_main(vin: VIn) -> VOut {
    var o: VOut;
    o.pos = camera.mvp * vec4<f32>(vin.pos, 1.0);
    o.world = vin.pos;
    o.normal = vin.nrm;
    return o;
}

@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    // 程序染色：顶面草绿 checker（floor(x)+floor(z) 奇偶），侧面土棕
    let checker = (floor(in.world.x) + floor(in.world.z)) % 2.0;
    var base = vec3<f32>(0.55, 0.38, 0.22);   // 土棕（侧面）
    if (in.normal.y > 0.5) {
        base = mix(vec3<f32>(0.30, 0.62, 0.20), vec3<f32>(0.42, 0.74, 0.26), checker);
    } else if (in.normal.y < -0.5) {
        base = vec3<f32>(0.30, 0.24, 0.18);   // 底面暗土
    }
    // 法线漫反射 + 环境光
    let light_dir = normalize(vec3<f32>(0.5, 0.9, 0.35));
    let ndotl = max(dot(in.normal, light_dir), 0.0);
    let brightness = 0.30 + 0.70 * ndotl;
    return vec4<f32>(base * brightness, 1.0);
}
"""

# 发射方块 WGSL（model 矩阵 per-game.frame 更新——平移自物理查询回填）
WGSL_CUBE = """
struct Camera {
    mvp: mat4x4<f32>,
};
struct Model {
    model: mat4x4<f32>,
};

@group(0) @binding(0) var<uniform> camera: Camera;
@group(0) @binding(1) var<uniform> model: Model;

struct VIn {
    @location(0) pos: vec3<f32>,
    @location(1) nrm: vec3<f32>,
}

struct VOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) normal: vec3<f32>,
}

@vertex
fn vs_main(vin: VIn) -> VOut {
    var o: VOut;
    let wp = model.model * vec4<f32>(vin.pos, 1.0);
    o.pos = camera.mvp * wp;
    o.normal = normalize((model.model * vec4<f32>(vin.nrm, 0.0)).xyz);
    return o;
}

@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    let light_dir = normalize(vec3<f32>(0.5, 0.9, 0.35));
    let ndotl = max(dot(in.normal, light_dir), 0.0);
    let brightness = 0.35 + 0.65 * ndotl;
    return vec4<f32>(vec3<f32>(0.85, 0.55, 0.15) * brightness, 1.0);
}
"""

# 小立方体顶点（pos3+normal3 顺序展开 36 顶点；±0.5 = 单位 1.0 宽
# ——发射方块 collider half=0.5，渲染 scale 1.0 即物理一致）
CUBE_VERTS = [
    # 前 +z
    -0.5, -0.5,  0.5,  0, 0, 1,   0.5, -0.5,  0.5,  0, 0, 1,   0.5, 0.5,  0.5,  0, 0, 1,
    -0.5, -0.5,  0.5,  0, 0, 1,   0.5,  0.5,  0.5,  0, 0, 1,  -0.5,  0.5,  0.5,  0, 0, 1,
    # 后 -z
     0.5, -0.5, -0.5,  0, 0,-1,  -0.5, -0.5, -0.5,  0, 0,-1,  -0.5,  0.5, -0.5,  0, 0,-1,
     0.5, -0.5, -0.5,  0, 0,-1,  -0.5,  0.5, -0.5,  0, 0,-1,   0.5,  0.5, -0.5,  0, 0,-1,
    # 右 +x
     0.5, -0.5,  0.5,  1, 0, 0,   0.5, -0.5, -0.5,  1, 0, 0,   0.5,  0.5, -0.5,  1, 0, 0,
     0.5, -0.5,  0.5,  1, 0, 0,   0.5,  0.5, -0.5,  1, 0, 0,   0.5,  0.5,  0.5,  1, 0, 0,
    # 左 -x
    -0.5, -0.5, -0.5, -1, 0, 0,  -0.5, -0.5,  0.5, -1, 0, 0,  -0.5,  0.5,  0.5, -1, 0, 0,
    -0.5, -0.5, -0.5, -1, 0, 0,  -0.5,  0.5,  0.5, -1, 0, 0,  -0.5,  0.5, -0.5, -1, 0, 0,
    # 上 +y
    -0.5,  0.5,  0.5,  0, 1, 0,   0.5,  0.5,  0.5,  0, 1, 0,   0.5,  0.5, -0.5,  0, 1, 0,
    -0.5,  0.5,  0.5,  0, 1, 0,   0.5,  0.5, -0.5,  0, 1, 0,  -0.5,  0.5, -0.5,  0, 1, 0,
    # 下 -y
    -0.5, -0.5,  0.5,  0,-1, 0,  -0.5, -0.5, -0.5,  0,-1, 0,   0.5, -0.5, -0.5,  0,-1, 0,
    -0.5, -0.5,  0.5,  0,-1, 0,   0.5, -0.5, -0.5,  0,-1, 0,   0.5, -0.5,  0.5,  0,-1, 0,
]

# FPS view 矩阵（手写 look_at——game.yaw/game.pitch 驱动；返回 Mat4 直配 GameCamera
# with_view；三角取 pygame.math 模块函数——裁剪版 stdlib 无 math）
def fps_view(eye, yaw_deg, pitch_deg):
    yaw = M.radians(yaw_deg)
    pitch = M.radians(pitch_deg)
    fx = M.cos(pitch) * M.sin(yaw)
    fy = M.sin(pitch)
    fz = -M.cos(pitch) * M.cos(yaw)
    f = (fx, fy, fz)                       # 前向（单位——三角恒等式保证）
    up0 = (0.0, 1.0, 0.0)
    s0 = (fy * up0[2] - fz * up0[1],
          fz * up0[0] - fx * up0[2],
          fx * up0[1] - fy * up0[0])       # right = f × up（模 = cos(game.pitch)
                                            # ≠ 1——**必须归一化**，否则
                                            # game.pitch 越大横竖缩放越失配 =
                                            # 旋转画面拉伸畸变，2026-11-17
                                            # 用户实测报障根因）
    sn = (s0[0] * s0[0] + s0[1] * s0[1] + s0[2] * s0[2]) ** 0.5
    s = (s0[0] / sn, s0[1] / sn, s0[2] / sn)
    u = (s[1] * fz - s[2] * fy,
         s[2] * fx - s[0] * fz,
         s[0] * fy - s[1] * fx)            # true up = s × f（s⊥f 双单位
                                            # → u 自动单位）
    ex, ey, ez = eye
    # 视图基（行主视觉——标准 view 行向量）→ 列主展开（from_cols_array
    # 列主序契约：out[c*4+r] = m[r*4+c]）
    m = [
        s[0], s[1], s[2], -s[0] * ex - s[1] * ey - s[2] * ez,
        u[0], u[1], u[2], -u[0] * ex - u[1] * ey - u[2] * ez,
        -f[0], -f[1], -f[2], f[0] * ex + f[1] * ey + f[2] * ez,
        0.0, 0.0, 0.0, 1.0,
    ]
    cols = [m[r * 4 + c] for c in range(4) for r in range(4)]
    return M.mat4_from_cols_array(cols)


WGSL_HUDQ = """
// HUD 定位贴片：单位 quad × rect（NDC x, y顶, w, h）× 每行文字纹理
struct QRect { rect: vec4<f32> };
@group(0) @binding(0) var tex: texture_2d<f32>;
@group(0) @binding(1) var samp: sampler;
@group(0) @binding(2) var<uniform> qr: QRect;
struct VIn { @location(0) pos: vec2<f32>, @location(1) uv: vec2<f32> }
struct VOut { @builtin(position) pos: vec4<f32>, @location(0) uv: vec2<f32> }
@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    // 单位 quad（pos ±1）→ 贴片内 [0,1] 归一化再乘 rect——直接乘
    // rect.zw = 高宽各翻倍（文字胖一倍实测）。y 向 **向下延伸**：
    // rect.y = 贴片顶（NDC 大 = 屏上方），底 = rect.y - h（NDC 小 =
    // 屏下方）——曾向上延伸 = 整块倒置（用户实测文字翻转 2026-11-21）
    o.pos = vec4<f32>(qr.rect.xy + vec2<f32>((v.pos.x + 1.0) * 0.5, -(1.0 - v.pos.y) * 0.5) * qr.rect.zw, 0.0, 1.0);
    o.uv = v.uv;
    return o;
}
@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
    return textureSample(tex, samp, in.uv);
}
"""


class Game:
    def __init__(self):
        self.frame = 0
        self.grabbed = False
        self.last_pos = None
        self.info = ""
        self.debug_on = False
        self.fluid_on = False
        self.fluid_world = None
        self.fluid_fh = None
        self.cam = None
        self.yaw = 0.0
        self.pitch = -12.0
        self.vox_mesh = None
        self.tri_count = 0
        self._last_ms = 0


async def main():
    game = Game()   # 状态对象在 main 闭包内——协程经闭包读写属性
    pygame.display.set_caption("voxel_mc_test")
    # **清屏色直出 + 填充 pass 消除**（2026-11-21 GPU 占用治理第二弹）：
    # SurfaceSettings.clear_color = 引擎 LoadOp::Clear 直出底色——内容层
    # 的填充 quad 删除，pass 数 2→1；present_mode 显式化（flip 实验口）
    surf_set = pygame.render.SurfaceSettings(
        present_mode="fifo",
        clear_color=[28 / 255, 34 / 255, 46 / 255, 1.0])
    screen = pygame.display.set_mode((2048, 1280), surface_settings=surf_set)
    cjk = pygame.font.Font("cjk", 25)
    clock = pygame.time.Clock()               # 帧率上限节流（tick 60——GPU 占用治理）
    ac = pygame.render.access()
    game.frame = 0
    _fail = []

    def st(name, cond):
        if cond:
            print("[voxel-mc] PASS", name)
        else:
            _fail.append(name)
            print("[voxel-mc] FAIL", name)

    # ── 体素世界（16³/chunk，体素 1.0）+ 地形 ──
    vw = pygame_voxelis.VoxWorld(4, 16.0)
    st("VoxWorld 构造", vw is not None)
    st("voxel_size 换算", abs(vw.voxel_size() - 1.0) < 1e-5)

    # ── 单块顶点语义 probe（碰撞对齐证词）：体素 (0,0,0) 世界盒 =
    # [0,1]³ ≡ collider（中心 +0.5、half 0.5）——绑定层公式 chunk
    # offset + CUBE ±half_voxel + 0.5 中心偏移的落地验证 ──
    probe = pygame_voxelis.VoxWorld(4, 16.0)
    probe.set_voxel(0, 0, 0, 1)
    pv, _pn, _pi = probe.generate_mesh()
    pmin = (min(pv[0::3]), min(pv[1::3]), min(pv[2::3]))
    pmax = (max(pv[0::3]), max(pv[1::3]), max(pv[2::3]))
    ok = (abs(pmin[0]) < 1e-4 and abs(pmin[1]) < 1e-4 and abs(pmin[2]) < 1e-4
          and abs(pmax[0] - 1.0) < 1e-4 and abs(pmax[1] - 1.0) < 1e-4
          and abs(pmax[2] - 1.0) < 1e-4)
    st(f"单块 mesh 盒 {tuple(round(x,3) for x in pmin)}..{tuple(round(x,3) for x in pmax)} ≡ collider [0,1]³", ok)

    height = [[4 + int(2.0 * M.sin(x * 0.4) * M.cos(z * 0.3))
               for z in range(16)] for x in range(16)]

    def build_terrain():
        for x in range(16):
            for z in range(16):
                h = height[x][z]
                for y in range(h):
                    vw.set_voxel(x, y, z, 1)
        vw.set_voxel(3, height[3][3], 3, 2)     # 石块样本（值区分存证）
        vw.set_voxel(5, height[5][5], 5, 2)

    build_terrain()
    # chunk_count 宽松断言（VoxModel::new 预建 world_bounds 网格——
    # 32³ 全量 chunk 表，非稀疏指标；≥1 = 至少根 chunk 存在）
    st("地形写入后 chunk_count>=1", vw.chunk_count() >= 1)
    st("get_voxel 读回", vw.get_voxel(3, height[3][3], 3) == 2)
    st("get_voxel 空 = None", vw.get_voxel(100, 100, 100) is None)

    # ── 物理（**单 voxel collider**——官方 voxel 案例对齐 2026-11-20：
    # 全体素 = 1 个 VoxelGeometry 形状碰撞体（parry voxelization），编辑
    # = 形状原位 set_voxel（ColliderSet::get_mut 自带 modified 脏标记 →
    # 下步 step 自动刷 broadphase），零刚体插拔；渲染 = voxelis mesh、
    # 物理 = rapier voxel shape——编辑双写同步。坐标约定对齐钉死：
    # parry 格 key (x,y,z) ≡ 世界 [x,x+1)³ ≡ voxelis 同款（voxel_center
    # = (key+0.5)*size，collider 恒等位）──）
    world = rp3.PhysicsWorld3D(gravity=(0, -9.81, 0))
    terrain_col = [None, None]               # (body_handle, collider_handle)
    stats = [0]                              # 当前体素数（HUD）

    def rebuild_terrain_collider():
        # 体素 collider 全量重建（首次/R 重置共用——voxelis 模型为事实
        # 源，物理形状全量镜像；旧体弃置换新）
        if terrain_col[0] is not None:
            world.remove_body(terrain_col[0])
        keys = []
        for x in range(16):
            for z in range(16):
                # 列内全枚举（含列顶层之上的石块样本 y=h——get_voxel 判
                # 空，宁多扫不漏挂）
                for y in range(height[x][z] + 2):
                    if vw.get_voxel(x, y, z) is not None:
                        keys.extend((x, y, z))
        stats[0] = len(keys) // 3
        b = rp3.RigidBodyBuilder3D("fixed")
        c = rp3.ColliderBuilder3D("voxels", voxel_size=1.0, voxels=keys,
                                  friction=0.8)
        terrain_col[0], terrain_col[1] = world.insert(b, c)

    rebuild_terrain_collider()               # 全量镜像 voxelis → 物理

    # 时序契约：insert 后须至少 step 一次方可 cast_ray（broad_phase 时序）
    world.step()                     # 时序契约（cast_ray 前置——broad_phase 就绪步进）
    hit = world.cast_ray_filtered((8.0, 8.0, 8.0), (0.0, -1.0, 0.0), None, "only_fixed")
    st("cast_ray 命中地面", hit is not None and hit[1] > 0.0)

    # ── 相机（GameCamera 显式定约——perspective letterbox 内聚）──
    eye = [8.0, 9.0, 22.0]
    game.yaw, game.pitch = 0.0, -12.0
    game.cam = pygame.render.game_camera_perspective(
        48.0, 1024, 640, 1024, 640, 0.1, 300.0)
    screen.set_camera(game.cam)                   # 会话级显式相机（空档自动面）
    cam_buf = ac.buffer(64, label="cam_buf")
    model_buf = ac.buffer(64, label="model_buf")

    # ── 体素 mesh（voxelis 数组出口 → mesh_builder）──
    voxel_shader = ac.shader(WGSL_VOXEL, label="voxel_shader")
    cube_shader = ac.shader(WGSL_CUBE, label="ball_shader")
    vox_pipe = [None]   # 体素 pipeline + bind（交互重建时一并换新）
    vox_bind = [None]
    vox_mesh_buf = [None, 0]   # (mesh, 唯一顶点容量)——update_mesh 原地更新用

    # ── HUD 定位贴片（**胶片免除**——每行文字一张定位小贴片，3D 后
    # 单条 raw pass 追加 draw 直绘在 3D 上）──
    # 曾绕胶片 = 每帧多 2 条 pass（hud_surf 清屏+文字 1 条 + 合成 1 条
    # ≈ GPU 占用 +10%，2026-11-21 pass 地板实测：4 条 → 2 条 = 占用
    # 减半）。零件全现成：Surface 即纹理（fluid3d 同款绑定）、raw 的
    # pipeline/bind/mesh 命令齐备——零引擎改动。
    _sw, _sh = screen.get_size()
    hud_unit = ac.mesh(["float32x2", "float32x2"],
                       # 6 顶点两三角（TriangleList 定约——4 顶点 = 半屏）；
                       # uv：pos(-1,-1)（贴片底）→ uv(0,1)（纹理底行）——
                       # 贴片与文字纹理方向一致，无翻转需求
                       [-1.0, -1.0, 0.0, 1.0, 1.0, -1.0, 1.0, 1.0,
                        1.0, 1.0, 1.0, 0.0, -1.0, -1.0, 0.0, 1.0,
                        1.0, 1.0, 1.0, 0.0, -1.0, 1.0, 0.0, 0.0],
                       label="hud_unit")
    hudq_shader = ac.shader(WGSL_HUDQ, label="hudq_shader")
    hudq_pipe = [None]
    cross_surf = cjk.render("+", True, (240, 240, 240))   # 准星 = 加号字形
    # 行表：[纹理面, 位置buf, bind, 当前面引用]——文字面变化才换 bind
    hud_lines = []

    def hud_line(i, cx_px, cy_px, text_surf):
        # 行/令牌槽更新：rect 位置每帧写（16B）；纹理面变化才重建 bind。
        # 位置 = **像素中心**（调用方按帧内实测尺寸换算——窗口/全屏切换
        # 自适应，2026-11-21 用户问询：动态屏幕大小文字位置跟随）
        while len(hud_lines) <= i:
            hud_lines.append([None, None, None, None])
        ln = hud_lines[i]
        w, h = text_surf.get_size()
        sw, sh = screen.get_size()
        nx, ny = sw / 2, sh / 2
        # 变换位 = 贴片**中心**（draw_surface 中心锚同语义）
        rect = [(cx_px - w / 2) / nx, ((cy_px) + h / 2) / ny, w / nx, h / ny]
        if ln[1] is None:
            ln[1] = ac.buffer(16, label=f"hud_l{i}")
        ln[0] = text_surf
        ln[2] = ac.bind_group([(0, "texture", text_surf),
                               (1, "sampler", None),
                               (2, "uniform", ln[1])], label=f"hud_l{i}_bind")
        ac.write_buffer(ln[1], list(rect))
        if hudq_pipe[0] is None:
            hudq_pipe[0] = ac.pipeline(hudq_shader, hud_unit, [ln[2]],
                                       cull="none", blend="alpha", label="hudq_pipe")
        return ln[2]

    def rebuild_voxel_mesh():
        # **generate_mesh_bytes**（f32/u16 LE 原始字节——RP 零逐元素转换，
        # list 口的 20400 次 new_float ≈ remesh 卡帧残余）+ 容量垫底 +
        # update_mesh_vertex/index_bytes 原地更新（超限才整 mesh 重建）
        _t0 = pygame.time.get_ticks()
        vb, ib = vw.generate_mesh_bytes()
        _t1 = pygame.time.get_ticks()
        if vox_mesh_buf[0] is None:
            # 首建：顶点/索引双 4x 容量垫底（update 字节口不增长——容量内
            # 原地写；索引垫底 = 0 号退化三角不可见，写时计数自动重设）
            mesh = ac.mesh(["float32x3", "float32x3"],
                           vertices_bytes=vb + bytes(len(vb) * 3),
                           index_bytes=ib + bytes(len(ib) * 3),
                           label="voxel_mesh")
            vox_mesh_buf[0] = mesh
            vox_mesh_buf[1] = len(vb)
            bind = ac.bind_group([(0, "uniform", cam_buf)], label="voxel_bind")
            vox_bind[0] = bind
            vox_pipe[0] = ac.pipeline(voxel_shader, mesh, [bind],
                                      cull="back", blend="opaque",
                                      depth_mode="standard", depth_write=True,
                                      label="voxel_pipe")
        elif True:  # [已定性 2026-11-22]——协程形态下原地 update_mesh_bytes 后 mesh 全灭（probe 实证），单协程正常——整重建路径替代（正确性优先），原地更新的协程兼容挂账 GPU 级取证
            mesh = ac.mesh(["float32x3", "float32x3"],
                           vertices_bytes=vb + bytes(len(vb) * 3),
                           index_bytes=ib, label="voxel_mesh")
            vox_mesh_buf[0] = mesh
            vox_mesh_buf[1] = len(vb)
        else:
            ac.update_mesh_vertex_bytes(vox_mesh_buf[0], vb)   # 原地直喂
            ac.update_mesh_index_bytes(vox_mesh_buf[0], ib)
        _t2 = pygame.time.get_ticks()
        # [TEMP 计时]——remesh 分解（voxelis 出口 / GPU 更新）
        print(f"[remesh] gen={_t1 - _t0}ms gpu={_t2 - _t1}ms "
              f"三角={len(ib) // 6}", flush=True)
        return vox_mesh_buf[0], len(ib) // 6

    game.vox_mesh, game.tri_count = rebuild_voxel_mesh()
    st("generate_mesh 出口", game.tri_count > 0)
    print(f"[voxel-mc] 地形 mesh：{game.tri_count} 三角形")

    # ── 发射方块（动态立方体——collider half 0.5 ≡ 渲染 scale 1.0，
    # 尺寸严格对齐；物理验证核心样张）──
    # ⚠️ 每球**独立 model uniform + bind**（2026-11-17 修复：RawPass 是
    # 记录-回放（draw 排程到 present 收口执行），而 write_buffer 立即
    # 生效——共享一个 model_buf 时回放读到的是**最后一次写入**的矩阵，
    # 多球全部叠在同一位置 = "上次发射的消失了"的假象（物理体其实
    # 都在）。独立 buffer 后每球矩阵各自定格，互不覆盖）
    ball_mesh = ac.mesh(["float32x3", "float32x3"], CUBE_VERTS, label="ball_mesh")
    ball_bind0 = ac.bind_group([
        (0, "uniform", cam_buf),
        (1, "uniform", model_buf),
    ], label="ball_bind")
    ball_pipe = ac.pipeline(cube_shader, ball_mesh, [ball_bind0],
                            cull="back", blend="opaque",
                            depth_mode="standard", depth_write=True,
                            label="ball_pipe")
    balls = []          # (body_handle, model_buf, bind) 流

    def launch_ball():
        yaw_r = M.radians(game.yaw)
        pitch_r = M.radians(game.pitch)
        d = (M.cos(pitch_r) * M.sin(yaw_r),
             M.sin(pitch_r),
             -M.cos(pitch_r) * M.cos(yaw_r))
        start = (eye[0] + d[0], eye[1] + d[1], eye[2] + d[2])
        b = rp3.RigidBodyBuilder3D("dynamic", translation=start,
                                   linvel=(d[0] * 9.0, d[1] * 9.0, d[2] * 9.0))
        c = rp3.ColliderBuilder3D("cuboid", hx=0.5, hy=0.5, hz=0.5,
                                  density=1.5, restitution=0.2, friction=0.6)
        bh = world.insert(b, c)[0]
        mbuf = ac.buffer(64, label=f"ball_model_{len(balls)}")
        bind = ac.bind_group([
            (0, "uniform", cam_buf),
            (1, "uniform", mbuf),
        ], label=f"ball_bind_{len(balls)}")
        balls.append((bh, mbuf, bind))

    # ── 射线交互（删除/放置 + collider 同步 + remesh）──
    game.info = ""

    def mouse_ray():
        yaw_r = M.radians(game.yaw)
        pitch_r = M.radians(game.pitch)
        return (M.cos(pitch_r) * M.sin(yaw_r),
                M.sin(pitch_r),
                -M.cos(pitch_r) * M.cos(yaw_r))

    def pick_voxel():
        d = mouse_ray()
        # **rapier 体素射线**（官方 voxel 案例对齐——broadphase query
        # 命中自带 FeatureId→voxel_key 直映射，DDA 自算退役；axis-aligned
        # 形状 → 法线恒 ±1 单轴）
        hit = world.cast_ray_voxel(eye, d, 64.0)
        if hit is None:
            return None
        _ch, toi, normal, key, center = hit
        n = (int(round(normal[0])), int(round(normal[1])), int(round(normal[2])))
        inside = (int(key[0]), int(key[1]), int(key[2]))
        # 放置格 = 命中格沿命中面法线外侧（官方 affected_key 同语义）
        outside = (key[0] + n[0], key[1] + n[1], key[2] + n[2])
        return inside, outside, center, n

    def remove_voxel(key):
        if vw.get_voxel(*key) is None:
            print(f"[edit] 删 {key} 落空（air——射线/准星分歧）", flush=True)  # [TEMP]
            return False
        _t0 = pygame.time.get_ticks()
        vw.remove_voxel(*key)                          # 渲染源（voxelis）
        _t1 = pygame.time.get_ticks()
        world.set_voxel(terrain_col[1], *key, False)   # 物理原位（官方对齐）
        _t2 = pygame.time.get_ticks()
        game.vox_mesh, game.tri_count = rebuild_voxel_mesh()     # remesh（渲染出口）
        _t3 = pygame.time.get_ticks()
        # [TEMP 分段计时]——卡帧归因（vw/rapier 原位/remesh 管线重建）
        print(f"[edit] 删 {key}: vw={_t1 - _t0}ms rapier={_t2 - _t1}ms "
              f"remesh={_t3 - _t2}ms 三角={game.tri_count}", flush=True)
        # [TEMP 形状探针]——被删格正下方向上打：命中本格 = rapier 形状
        # 未生效；命中上一层 = 形状已更新
        _probe = world.cast_ray_voxel(
            (key[0] + 0.5, -1.0, key[2] + 0.5), (0, 1, 0), 30.0)
        print(f"[edit-probe] 上行射线 -> "
              f"{_probe[3] if _probe else 'None（全空）'}", flush=True)
        stats[0] -= 1
        return True

    def place_voxel(key):
        if vw.get_voxel(*key) is not None:
            print(f"[edit] 放 {key} 落空（已有方块）", flush=True)  # [TEMP]
            return False
        _t0 = pygame.time.get_ticks()
        vw.set_voxel(key[0], key[1], key[2], 2)
        _t1 = pygame.time.get_ticks()
        world.set_voxel(terrain_col[1], key[0], key[1], key[2], True)
        _t2 = pygame.time.get_ticks()
        game.vox_mesh, game.tri_count = rebuild_voxel_mesh()
        _t3 = pygame.time.get_ticks()
        # [TEMP 分段计时]——卡帧归因（vw/rapier 原位/remesh 管线重建）
        print(f"[edit] 放 {key}: vw={_t1 - _t0}ms rapier={_t2 - _t1}ms "
              f"remesh={_t3 - _t2}ms 三角={game.tri_count}", flush=True)
        stats[0] += 1
        return True

    game._last_ms = 0                          # 帧耗时统计基准
    _dt_sum = [0.0, 0]                    # (ms 累计, 帧数)——120 帧平均窗
    _step_sum = [0, 0]                    # step/fluidstep 累计 ms
    perf = [16.7, 0.0, 0.0]               # HUD 展示 (帧ms, step_ms, fluid_ms)
    game.grabbed = False                       # TAB 抓取态（FPS 沉浸式——grab
                                          # + 隐藏光标，免按键自由转向）
    game.last_pos = None                       # 拖拽差分锚（Event 无 rel——x/y 差分自算）
    game.debug_on = False                      # T 键：collider 线框叠加（对齐检查）
    game.fluid_on = False                      # F2 键：流体元素开关（水柱注入）
    game.fluid_world = None                    # 惰性创建（首次 F2 时）
    game.fluid_fh = None
    fluid_res = [None, None]              # 流体渲染 (model_buf, bind)——F2 开启时一次建
    dbg_draw = rp3.DebugDraw3D()
    dbg_renderer = rp3.DebugLinesRenderer3D()   # 相机由 set_mvp 直写（默认构造即可）
    text_cache = {}

    def hud_text(s, color=(210, 214, 224)):
        key = (s, color)
        if key not in text_cache:
            text_cache[key] = cjk.render(s, True, color)
        return text_cache[key]

    def draw_hud():
        # HUD 贴片更新（无胶片——raw pass 直绘在 3D 上）。位置 = 像素
        # 中心，按帧内实测尺寸换算（窗口/全屏切换自适应）
        _sw, _sh = screen.get_size()
        _nx, _ny = _sw / 2, _sh / 2
        hud_line(0, -450 / 1024 * _nx, 608 / 640 * _ny, hud_text(
            f"[voxel_mc] 体素 mesh {game.tri_count} 三角 | chunk {vw.chunk_count()} | "
            f"球 {len(balls)} | WASD漫游 QE升降 拖拽/TAB抓取=转向+俯仰 左删右放 F发射 R重置 T碰撞体显示 F2流体"))
        hud_line(1, -450 / 1024 * _nx, 588 / 640 * _ny, hud_text(
            game.info + (" | T:collider线框 ON" if game.debug_on else ""), (255, 220, 90)))
        # 中心准星（加号字形贴片——FPS 沉浸式瞄准参照，pick 与准星同源
        # 同约定：game.yaw/game.pitch 前向）
        hud_line(3, 0, 0, cross_surf)
        draw_perf_row(_nx, _ny)

    def draw_perf_row(_nx, _ny):
        # 性能行 = **令牌拼装**（字符集缓存——固定标签 + 数字 0-9 预渲染
        # 各一张永久缓存，每帧零光栅化零上传：曾整串渲染 = 每次变化
        # 字体光栅化+纹理+bind ≈2-4ms 尖峰，2026-11-21 用户提出不缓存
        # 直觉后定形）。布局 = 左锚 x 逐令牌步进，位置 16B/令牌直写
        pm = int(perf[0] / 4) * 4
        fps = 1000 // max(pm, 1)
        col = (150, 230, 180)
        toks = [("帧", col), ("~", col), (str(pm), col), ("ms", col),
                ("（", col), (str(fps), col), ("fps", col), ("）", col),
                ("｜", col), ("物理 step", col), (str(int(perf[1])), col),
                ("ms", col), ("｜", col), ("流体 step", col),
                (str(int(perf[2])), col), ("ms", col), ("｜", col),
                ("刚体", col), (str(len(balls)), col), ("｜", col),
                ("体素", col), (str(stats[0]), col),
                ("（单 voxel collider）", col)]
        x = -0.95 * _nx                       # 行左缘（相对比例——23 令牌全宽收进半幅）
        yc = 568 / 640 * _ny                  # 行中心 y
        for i, (s, c) in enumerate(toks):
            surf = hud_text(s, c)             # 缓存命中（令牌串恒定）
            w = surf.get_size()[0]
            hud_line(10 + i, x + w / 2, yc, surf)
            x += w + 4                        # 步进（+4px 间距）

    # ── 异步双协程拆分（设计定约 2026-11-22）──────────────────
    # logic = 事件/漫游/物理 accumulator/交互；render = 绘制/flip/限帧
    # 帧泵统一推进（协作式）；让出原语改名后 = tasks.yield_now()
    # 共享状态经闭包（单线程协作式，零竞态）────────────────────
    running = [True]                          # 全局退出旗标（跨协程共享——list 原位改）

    async def logic_task():
        while running[0]:
            for e in pygame.event.get():
                if e.type == pygame.event.QUIT:
                    running[0] = False
                    return
                if e.type == pygame.event.KEYDOWN:
                    if e.key == pygame.key.K_ESCAPE:
                        running[0] = False
                        return
                    if e.key == pygame.key.K_TAB:
                        # FPS 沉浸式抓取切换（2026-11-20 用户定约）：TAB =
                        # grab（鼠标限定窗口内逃不出）+ 隐藏光标 + 免按键
                        # 自由转向；再按 TAB 释放回拖拽形态。last_pos 重锚
                        # 防切换瞬间跳变。
                        game.grabbed = not game.grabbed
                        pygame.mouse.set_grab(game.grabbed)
                        pygame.mouse.set_visible(not game.grabbed)
                        game.last_pos = None
                        game.info = ("TAB 抓取鼠标：FPS 沉浸式（自由转向，左删右放不变）"
                                if game.grabbed else "TAB 已释放鼠标（回拖拽形态）")
                    if e.key == pygame.key.K_f:
                        launch_ball()
                    if e.key == pygame.key.K_t:
                        game.debug_on = not game.debug_on
                    if e.key == pygame.key.K_F2:
                        game.fluid_on = not game.fluid_on
                        if game.fluid_on and game.fluid_world is None:
                            game.fluid_world = rp3.FluidWorld(particle_radius=0.1)
                            game.fluid_fh = game.fluid_world.add_fluid_cuboid(
                                (-0.4, 4.0, -0.4), (0.8, 2.0, 0.8))
                            # 流体渲染资源一次性建（per-body 独立 buffer 定约
                            # ——每帧新建 = 分配泄漏，2026-11-20 实测修正）
                            fluid_res[0] = ac.buffer(64, label="fluid_model")
                            fluid_res[1] = ac.bind_group([
                                (0, "uniform", cam_buf),
                                (1, "uniform", fluid_res[0]),
                            ], label="fluid_model_bind")
                            print('[voxel_mc] 流体已注入（160 粒子水柱）')
                    if e.key == pygame.key.K_r:
                        for bh, _mb, _bd in balls:
                            world.remove_body(bh)
                        balls.clear()
                        vw.clear()
                        build_terrain()
                        rebuild_terrain_collider()     # 体素 collider 全量重建
                        world.step()                    # 时序契约（cast_ray 前置——broad_phase 就绪步进，不动 accumulator）
                        game.vox_mesh, game.tri_count = rebuild_voxel_mesh()
                        game.info = "地形+视角已重置"
                        # 视角同步归位（game.pitch 残留低俯角 = "旋转看起来绕斜轴"
                        # 的观感来源——R 全量重置含视角）
                        eye[0], eye[1], eye[2] = 8.0, 9.0, 22.0
                        game.yaw = 0.0
                        game.pitch = -12.0
                elif e.type == pygame.event.MOUSEBUTTONDOWN:
                    if e.button == 1:
                        #dragging = True
                        picked = pick_voxel()
                        if picked:
                            inside, outside, p, normal = picked
                            if remove_voxel(inside):
                                game.vox_mesh, game.tri_count = rebuild_voxel_mesh()
                                game.info = (f"删 {inside} @({p[0]:.1f},{p[1]:.1f},{p[2]:.1f})"
                                        f" 法线{normal}")
                            else:
                                game.info = f"删 {inside} 落空（air）"
                    elif e.button == 3:
                        picked = pick_voxel()
                        if picked:
                            inside, outside, p, normal = picked
                            if place_voxel(outside):
                                game.vox_mesh, game.tri_count = rebuild_voxel_mesh()
                                game.info = (f"放 {outside} @({p[0]:.1f},{p[1]:.1f},{p[2]:.1f})"
                                        f" 法线{normal}")
                            else:
                                game.info = f"放 {outside} 落空（已有方块）"
                elif e.type == pygame.event.MOUSEBUTTONUP:
                    if e.button == 1:
                        dragging = False
                elif e.type == pygame.event.MOUSEMOTION and game.grabbed:
                    # 拖拽 / grab 态 = 转向 + 俯仰（FPS 全形态——x 差分 game.yaw /
                    # y 差分 game.pitch，用户定约 2026-11-17；grab 态免按键
                    # 2026-11-20）
                    if game.last_pos is not None:
                        game.yaw += (e.x - game.last_pos[0]) * 0.1
                        game.pitch = max(-85.0, min(85.0,
                                               game.pitch + (e.y - game.last_pos[1]) * 0.1))
                    game.last_pos = (e.x, e.y)

            # 漫游（WASD 平移 + QE 升降——get_pressed 视图，Key unhashable）
            pressed = pygame.key.get_pressed()
            yaw_r = M.radians(game.yaw)
            d = (M.cos(M.radians(game.pitch)) * M.sin(yaw_r), 0.0,
                 -M.cos(M.radians(game.pitch)) * M.cos(yaw_r))
            right = (M.cos(yaw_r), 0.0, M.sin(yaw_r))
            speed = 0.09
            if pressed.get(pygame.key.K_w):
                eye[0] += d[0] * speed; eye[2] += d[2] * speed
            if pressed.get(pygame.key.K_s):
                eye[0] -= d[0] * speed; eye[2] -= d[2] * speed
            if pressed.get(pygame.key.K_a):
                eye[0] -= right[0] * speed; eye[2] -= right[2] * speed
            if pressed.get(pygame.key.K_d):
                eye[0] += right[0] * speed; eye[2] += right[2] * speed
            if pressed.get(pygame.key.K_q):
                eye[1] -= speed
            if pressed.get(pygame.key.K_e):
                eye[1] += speed

            # 物理 + GameCamera MVP（with_view 每帧替换——letterbox 内聚直
            # 喂 uniform（双参口自动组合 present_fit 画布→物理段——两段不同不双乘））
            _s0 = pygame.time.get_ticks()      # step 单独计时（物理/渲染分摊
            world.step_frame(clock.get_time() / 1000.0)   # 真实帧间隔喂 accumulator（修复字面量+tick120=2倍速）
            _step_sum[0] += pygame.time.get_ticks() - _s0
            if game.fluid_on and game.fluid_world is not None:
                _f0 = pygame.time.get_ticks()
                game.fluid_world.step(1.0 / 60.0)
                _step_sum[1] += pygame.time.get_ticks() - _f0
            game.cam = game.cam.with_view(fps_view(eye, game.yaw, game.pitch))
            pygame.render.write_camera_mvp(cam_buf, game.cam.mvp())

            draw_hud()   # HUD 贴片位置/内容更新（raw 直绘用，无胶片）

            # 物理数据正确性打点（60 帧一次）：球中心/速度——静止贴面判据
            # （中心 y ≈ 下方命中面 y + 0.5，容差 ±0.05）
            if game.frame == 120 and not balls:
                launch_ball()   # 自动发射一颗（落地核对打点——无人交互自动触发）
            if game.frame % 60 == 0 and balls:
                vx, vy, vz = world.linvel(balls[0][0])
                spd = (vx * vx + vy * vy + vz * vz) ** 0.5
                x, y, z = world.translation(balls[0][0])
                if spd < 0.05:
                    # 体素查询判定（cast_ray 会命中球自身 collider → toi=0，
                    # 非引擎异常）：球心下方 0.6 处的支撑格有体素 → 格顶 =
                    # by+1，球心应 = 格顶 + 0.5
                    bx, bz = int(x // 1), int(z // 1)
                    by = int((y - 0.6) // 1)
                    below = vw.get_voxel(bx, by, bz)
                    if below is not None:
                        expected = by + 1 + 0.5
                        ok = abs(y - expected) < 0.06
                        print(f"[voxel-mc] 落地贴面核对：球心 y={y:.2f} 支撑体素 "
                              f"{bx,by,bz} 顶面 y={by + 1}（期望球心 {expected:.1f}）→ "
                              + ("PASS 物理数据正确" if ok else "FAIL 物理数据异常"))
                        st("球静止贴面（物理数据正确）", ok)
                        print(f"[game.frame-probe] game.frame={game.frame} mod150={game.frame % 150}", flush=True)
            # [TEMP 自动删放取证]——remesh 更新链可视化（删失败自动放）
            if game.frame % 150 == 0 and game.frame > 300:
                picked = pick_voxel()
                if picked:
                    inside, outside, p, normal = picked
                    if remove_voxel(inside):
                        game.vox_mesh, game.tri_count = rebuild_voxel_mesh()
                        game.info = f"自动删 {inside}"
                    elif place_voxel(outside):
                        game.vox_mesh, game.tri_count = rebuild_voxel_mesh()
                        game.info = f"自动放 {outside}"
                else:
                    print(f"[edit-miss] game.frame={game.frame} picked=None（射线未命中体素）",
                          flush=True)
                    # probe 画面像素取证（删格中心位——网格更新判定）
                    d = screen.probe()
                    hit = [(x, y, r, g, b) for x, y, r, g, b, a in
                           [d[i:i+6] for i in range(0, len(d), 6)]
                           if (r, g, b) != (18, 20, 28)]
                    print(f"[PROBE-EDIT] game.frame={game.frame} 非背景 {len(hit)}: {hit[:5]}",
                          flush=True)
            await pygame.tasks.yield_now()   # 让出（改名后 tasks.yield_now）

    async def render_task():
        while running[0]:
            with screen.render() as rt:
                with screen.raw_render(depth=True) as p:
                    p.set_pipeline(vox_pipe[0])
                    p.set_bind_group(0, vox_bind[0])
                    p.draw_mesh(game.vox_mesh)
                    # 球（平移 + **旋转回填**——每球独立 model uniform，
                    # 回放时矩阵各自定格不互覆盖；Quaternion xyzw 直呼构造）
                    for bh, mbuf, bind in balls:
                        x, y, z = world.translation(bh)
                        qx, qy, qz, qw = world.rotation(bh)
                        ac.write_buffer(
                            mbuf,
                            M.mat4_translation(x, y, z)
                            @ M.mat4_from_quat(M.Quaternion(qx, qy, qz, qw)))
                        p.set_pipeline(ball_pipe)
                        p.set_bind_group(0, bind)
                        p.draw_mesh(ball_mesh)
                    # 流体粒子球（F2 开——salva 粒子出口 → instanced 球）
                    if game.fluid_on and game.fluid_world is not None:
                        fpos, _fv = game.fluid_world.fluid_particles(game.fluid_fh)
                        # buffer/bind **开启时刻一次性建**（曾每帧新建 = GPU
                        # 分配泄漏——balls 同款 per-body 资源定约）
                        for i in range(len(fpos) // 3):
                            fx = fpos[i * 3]; fy = fpos[i * 3 + 1]; fz = fpos[i * 3 + 2]
                            ac.write_buffer(fluid_res[0], M.mat4_translation(fx, fy, fz))
                            p.set_pipeline(ball_pipe)
                            p.set_bind_group(0, fluid_res[1])
                            p.draw_mesh(ball_mesh)
                if game.debug_on:
                    # collider 线框叠加（D 键——set_mvp 绝对对齐：与主管线
                    # 喂同一个 game.cam.mvp()，投影/view/near/far 全同）
                    sink = rp3.LineSink3D()
                    rp3.collect3d(world, dbg_draw, sink)
                    dbg_renderer.set_mvp(game.cam.mvp())
                    rt.draw_debug_3d(dbg_renderer, sink)
                # HUD 贴片直绘（3D raw pass **追加 draw**——登记序即执行序，
                # 无胶片无合成 pass：每行文字 = 定位小贴片，blend 压在地形上）
                draw_hud()
                with screen.raw_render() as ph:
                    ph.set_pipeline(hudq_pipe[0])
                    for ln in hud_lines:
                        if ln[0] is None:
                            continue                     # 未用槽位跳过
                        ph.set_bind_group(0, ln[2])
                        ph.draw_mesh(hud_unit)


            pygame.display.flip()
            # 帧耗时统计窗（120 帧平均——物理/渲染分摊常驻可见，性能排查用）
            _now = pygame.time.get_ticks()
            if game._last_ms > 0 and _now > game._last_ms:
                _dt_sum[0] += _now - game._last_ms
                _dt_sum[1] += 1
            game._last_ms = _now
            if _dt_sum[1] >= 120:
                perf[0] = _dt_sum[0] / _dt_sum[1]
                perf[1] = _step_sum[0] / _dt_sum[1]
                perf[2] = _step_sum[1] / _dt_sum[1]
                _dt_sum[0] = 0
                _dt_sum[1] = 0
                _step_sum[0] = 0
                _step_sum[1] = 0
            game.frame += 1
            await pygame.tasks.yield_now()   # 让出（帧尾单挂起点）

    t_logic = pygame.tasks.spawn(logic_task())
    t_render = pygame.tasks.spawn(render_task())
    while running[0]:                    # 保活泵（任务帧泵自动推进；旗标收口）
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                running[0] = False
                return
        # 任务健康打点（协程死因取证——调度器异常存档）
        if t_logic.failed():
            print("[async] LOGIC-TASK-DEAD:", repr(t_logic.exception()))
            return
        if t_render.failed():
            print("[async] RENDER-TASK-DEAD:", repr(t_render.exception()))
            return
        # 总帧率节拍（全局域——tick 归 main，渲染/逻辑域不私有限帧；
        # vsync 已超目标时引擎不再补睡——无双重节流）
        clock.tick(120)
        await pygame.tasks.yield_now()
