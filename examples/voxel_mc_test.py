# voxel_mc_test —— pygame_voxelis 极简 MC 案例（阶段二验收样张）：
# 稀疏体素地形（VoxWorld 16×16×16 体素/chunk，体素 1.0）+ rapier3d
# 体素物理（每列 fixed cuboid + 动态立方体发射）+ 射线选择（cast_ray
# 命中 → 删除/放置）+ mesh_builder 法线光照渲染（voxelis 内建 mesh
# 数组出口——无 uv，片元按世界坐标/法线程序染色）。
# 交互：鼠标拖拽转向 / WASD-QE 漫游 / 左键删 / 右键放 / F 发射方块 /
# R 重建地形 / ESC 退出。控制台 [voxel-mc] 打点逐项验证。
import pygame
import pygame_voxelis
import pygame_physics as rp3

# 三角函数面 = pygame.math 模块属性（import 子模块需 __path__ 不可用；
# 属性直取可——cube_rotate 同款）
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

# 球体替换形态：动态小立方体 WGSL（model 矩阵 per-frame 更新——平移+
# 旋转自物理查询回填）
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

# 小立方体顶点（pos3+normal3 顺序展开 36 顶点——cube_rotate 模板瘦身）
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

# FPS view 矩阵（手写 look_at——pygame.math 无 look_at 面；yaw/pitch 驱动）
# 三角取 pygame.math 模块函数（裁剪版 stdlib 无 math——2026-11-10 补齐面）
def fps_view(eye, yaw_deg, pitch_deg):
    yaw = M.radians(yaw_deg)
    pitch = M.radians(pitch_deg)
    fx = M.cos(pitch) * M.sin(yaw)
    fy = M.sin(pitch)
    fz = -M.cos(pitch) * M.cos(yaw)
    f = (fx, fy, fz)                       # 前向
    up0 = (0.0, 1.0, 0.0)
    s = (fy * up0[2] - fz * up0[1],
         fz * up0[0] - fx * up0[2],
         fx * up0[1] - fy * up0[0])        # right = f × up
    u = (s[1] * fz - s[2] * fx,
         s[2] * fx - s[0] * fz,
         s[0] * fy - s[1] * fx)            # true up = s × f
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


async def main():
    pygame.display.set_caption("voxel_mc_test")
    screen = pygame.display.set_mode((1024, 640))
    cjk = pygame.font.Font("cjk", 15)
    ac = pygame.render.access()
    M = pygame.math
    frame = 0
    _fail = []

    def st(name, cond):
        if cond:
            print("[voxel-mc] PASS", name)
        else:
            _fail.append(name)
            print("[voxel-mc] FAIL", name)

    # ── 体素世界（16³/chunk，体素 1.0）+ 地形 ──
    vw = pygame_voxelis.VoxWorld(4, 16.0)
    st("VoxWorld 构造", vw is not None and vw.voxel_size() == 1.0)
    st("voxel_size 换算", abs(vw.voxel_size() - 1.0) < 1e-5)

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

    # ── 物理（表面体素 cuboid + 射线选择）──
    world = rp3.PhysicsWorld3D(gravity=(0, -9.81, 0))
    col_bodies = {}                          # (x,y,z) → body handle（表面块+放置块）
    for x in range(16):
        for z in range(16):
            h = height[x][z]
            # 只给每列顶层块放 collider（内部块打不到/走不进——案例级
            # 近似；删除顶层后露出的下一层不带 collider，v2 补增量）
            key = (x, h - 1, z)
            b = rp3.RigidBodyBuilder3D("fixed",
                                       translation=(x + 0.5, h - 0.5, z + 0.5))
            c = rp3.ColliderBuilder3D("cuboid", hx=0.5, hy=0.5, hz=0.5, friction=0.8)
            col_bodies[key] = world.insert(b, c)[0]

    # 时序契约：insert 后须至少 step 一次方可 cast_ray（broad_phase 时序）
    world.step_frame(1.0 / 60.0)
    hit = world.cast_ray((8.0, 8.0, 8.0), (0.0, -1.0, 0.0), None)
    st("cast_ray 命中地面", hit is not None and hit[1] > 0.0)

    # ── 相机（FPS 漫游）──
    eye = [8.0, 9.0, 22.0]
    yaw, pitch = 0.0, -12.0
    proj = pygame.render.camera_perspective(58.0, 1024 / 640, 0.1, 300.0)
    cam_buf = ac.buffer(64, label="cam_buf")
    model_buf = ac.buffer(64, label="model_buf")

    # ── 体素 mesh（voxelis 数组出口 → mesh_builder）──
    voxel_shader = ac.shader(WGSL_VOXEL, label="voxel_shader")
    cube_shader = ac.shader(WGSL_CUBE, label="ball_shader")
    vox_pipe = [None]   # 体素 pipeline + bind（交互重建时一并换新）
    vox_bind = [None]

    def rebuild_voxel_mesh():
        verts, norms, idx = vw.generate_mesh()
        # 顺序展开（indices → 顶点流；案例级规模免 index 管线）
        expanded = []
        for i in idx:
            v = (verts[i * 3], verts[i * 3 + 1], verts[i * 3 + 2])
            n = (norms[i * 3], norms[i * 3 + 1], norms[i * 3 + 2])
            expanded.extend(v)
            expanded.extend(n)
        mesh = ac.mesh(["float32x3", "float32x3"], expanded, label="voxel_mesh")
        bind = ac.bind_group([(0, "uniform", cam_buf)], label="voxel_bind")
        vox_bind[0] = bind
        vox_pipe[0] = ac.pipeline(voxel_shader, mesh, [bind],
                                  cull="back", blend="opaque",
                                  depth_mode="standard", depth_write=True,
                                  label="voxel_pipe")
        return mesh, len(idx) // 3

    vox_mesh, tri_count = rebuild_voxel_mesh()
    st("generate_mesh 出口", tri_count > 0)
    print(f"[voxel-mc] 地形 mesh：{tri_count} 三角形")

    # ── 发射方块（动态立方体 ×N——物理 + mesh model 矩阵跟随）──
    ball_mesh = ac.mesh(["float32x3", "float32x3"], CUBE_VERTS, label="ball_mesh")
    ball_bind = ac.bind_group([
        (0, "uniform", cam_buf),
        (1, "uniform", model_buf),
    ], label="ball_bind")
    ball_pipe = ac.pipeline(cube_shader, ball_mesh, [ball_bind],
                            cull="back", blend="opaque",
                            depth_mode="standard", depth_write=True,
                            label="ball_pipe")
    balls = []                               # (body_handle,)

    def launch_ball():
        yaw_r = M.radians(yaw)
        pitch_r = M.radians(pitch)
        d = (M.cos(pitch_r) * M.sin(yaw_r),
             M.sin(pitch_r),
             -M.cos(pitch_r) * M.cos(yaw_r))
        start = (eye[0] + d[0], eye[1] + d[1], eye[2] + d[2])
        b = rp3.RigidBodyBuilder3D("dynamic", translation=start,
                                   linvel=(d[0] * 9.0, d[1] * 9.0, d[2] * 9.0))
        c = rp3.ColliderBuilder3D("cuboid", hx=0.3, hy=0.3, hz=0.3,
                                  density=1.5, restitution=0.2, friction=0.6)
        balls.append(world.insert(b, c)[0])

    # ── 射线交互（删除/放置 + collider 同步 + remesh）──
    info = ""

    def mouse_ray():
        yaw_r = M.radians(yaw)
        pitch_r = M.radians(pitch)
        return (M.cos(pitch_r) * M.sin(yaw_r),
                M.sin(pitch_r),
                -M.cos(pitch_r) * M.cos(yaw_r))

    def pick_voxel():
        d = mouse_ray()
        hit = world.cast_ray(tuple(eye), d, None)
        if hit is None:
            return None
        toi = hit[1]
        px = eye[0] + d[0] * toi
        py = eye[1] + d[1] * toi
        pz = eye[2] + d[2] * toi
        # 命中点 ± ε·dir → 内侧格（删）/ 外侧格（放）——`// 1` 向负无穷
        # 取整 = floor（math 模块缺席，整除语义替代）
        inside = (int((px - d[0] * 0.05) // 1),
                  int((py - d[1] * 0.05) // 1),
                  int((pz - d[2] * 0.05) // 1))
        outside = (int((px + d[0] * 0.05) // 1),
                   int((py + d[1] * 0.05) // 1),
                   int((pz + d[2] * 0.05) // 1))
        return inside, outside, (px, py, pz)

    def remove_voxel(key):
        if vw.get_voxel(*key) is None:
            return False
        vw.remove_voxel(*key)
        bh = col_bodies.pop(key, None)
        if bh is not None:
            world.remove_body(bh)
        return True

    def place_voxel(key):
        if vw.get_voxel(*key) is not None:
            return False
        vw.set_voxel(key[0], key[1], key[2], 2)
        b = rp3.RigidBodyBuilder3D("fixed",
                                   translation=(key[0] + 0.5, key[1] + 0.5, key[2] + 0.5))
        c = rp3.ColliderBuilder3D("cuboid", hx=0.5, hy=0.5, hz=0.5, friction=0.8)
        col_bodies[key] = world.insert(b, c)[0]
        return True

    dragging = False
    text_cache = {}

    def hud_text(s, color=(210, 214, 224)):
        key = (s, color)
        if key not in text_cache:
            text_cache[key] = cjk.render(s, True, color)
        return text_cache[key]

    def draw_hud(rt):
        pygame.gfxdraw.set_transform(rt, M.mat4_translation(-500, 308, 0))
        pygame.gfxdraw.draw_surface(rt, hud_text(
            f"[voxel_mc] 体素 mesh {tri_count} 三角 | chunk {vw.chunk_count()} | "
            f"球 {len(balls)} | WASD+QE 漫游 拖拽转向 左删 右放 F 发射 R 重置"))
        pygame.gfxdraw.set_transform(rt, M.mat4_translation(-500, 288, 0))
        pygame.gfxdraw.draw_surface(rt, hud_text(info, (255, 220, 90)))

    while True:
        for e in pygame.event.get():
            if e.type == pygame.event.QUIT:
                return
            if e.type == pygame.event.KEYDOWN:
                if e.key == pygame.key.K_ESCAPE:
                    return
                if e.key == pygame.key.K_f:
                    launch_ball()
                if e.key == pygame.key.K_r:
                    for bh in list(col_bodies.values()):
                        world.remove_body(bh)
                    col_bodies.clear()
                    vw.clear()
                    build_terrain()
                    # 表面 collider 重建（R 全量重置——放置块一并清）
                    for x in range(16):
                        for z in range(16):
                            h = height[x][z]
                            b = rp3.RigidBodyBuilder3D(
                                "fixed", translation=(x + 0.5, h - 0.5, z + 0.5))
                            c = rp3.ColliderBuilder3D(
                                "cuboid", hx=0.5, hy=0.5, hz=0.5, friction=0.8)
                            col_bodies[(x, h - 1, z)] = world.insert(b, c)[0]
                    world.step_frame(1.0 / 60.0)   # 时序契约（cast_ray 前置）
                    vox_mesh, tri_count = rebuild_voxel_mesh()
                    info = "地形已重置"
            elif e.type == pygame.event.MOUSEBUTTONDOWN:
                if e.button == 1:
                    dragging = True
                    picked = pick_voxel()
                    if picked:
                        inside, outside, p = picked
                        if remove_voxel(inside):
                            vox_mesh, tri_count = rebuild_voxel_mesh()
                            info = f"删 {inside} @({p[0]:.1f},{p[1]:.1f},{p[2]:.1f})"
                        else:
                            info = f"删 {inside} 落空（air）"
                elif e.button == 3:
                    picked = pick_voxel()
                    if picked:
                        inside, outside, p = picked
                        if place_voxel(outside):
                            vox_mesh, tri_count = rebuild_voxel_mesh()
                            info = f"放 {outside} @({p[0]:.1f},{p[1]:.1f},{p[2]:.1f})"
                        else:
                            info = f"放 {outside} 落空（已有方块）"
            elif e.type == pygame.event.MOUSEBUTTONUP:
                if e.button == 1:
                    dragging = False
            elif e.type == pygame.event.MOUSEMOTION and dragging:
                yaw += e.rel[0] * 0.35
                pitch = max(-85.0, min(85.0, pitch + e.rel[1] * 0.35))

        # 漫游（WASD 平移 + QE 升降——get_pressed 视图，Key unhashable）
        pressed = pygame.key.get_pressed()
        yaw_r = M.radians(yaw)
        d = (M.cos(M.radians(pitch)) * M.sin(yaw_r), 0.0,
             -M.cos(M.radians(pitch)) * M.cos(yaw_r))
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

        # 物理 + 球位姿回填
        world.step_frame(1.0 / 60.0)
        mvp = proj.with_view(fps_view(eye, yaw, pitch)).mvp()
        pygame.render.write_camera_mvp(cam_buf, mvp)

        with screen.render() as rt:
            rt.fill((28, 34, 46))
            with screen.raw_render(depth=True) as p:
                p.set_pipeline(vox_pipe[0])
                p.set_bind_group(0, vox_bind[0])
                p.draw_mesh(vox_mesh)
                # 球（平移跟随——rotation 回填无 quat 构造器，v2 接）
                for bh in balls:
                    x, y, z = world.translation(bh)
                    ac.write_buffer(model_buf, M.mat4_translation(x, y, z))
                    p.set_pipeline(ball_pipe)
                    p.set_bind_group(0, ball_bind)
                    p.draw_mesh(ball_mesh)
            draw_hud(rt)

        pygame.display.flip()
        frame += 1
        await pygame.next_frame()
