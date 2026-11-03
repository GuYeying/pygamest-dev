//! 通用运行驱动（**平台零感知**）：拿到 [`RunRequest`] 后的全部流程——
//! RP genesis → sys.argv → 模块表 → 字体预载 → 创建期旗标预扫描 → 建窗 →
//! run_script_in（帧桥/协程驱动/traceback）→ 退出码。
//!
//! 各阶段打点沿用（①解释器 ②字体 ③建窗 ④执行 → 首帧分段）——
//! 启动耗时归因仪表，跨平台口径一致。
//!
//! 平台差异只允许存在于 [`crate::host::Host::acquire`]（拿载荷）与
//! 平台 main 的收尾（退出码语义）里，不得下沉到本模块。
// RP 嵌入 API 经 pygamest re-export（vendored path 在 pygamest 仓内）
use pygamest::rustpython_vm as rustpython_vm;


use crate::host::{Host, RunRequest};
use pygamest::rpy;
use starfish_pygame::display;
use starfish_std::debug::Stopwatch;

/// 阶段打点（**Debug 级**——启动耗时归因仪表属诊断；发行壳 Info 级别
/// 下不落盘，dev Debug 级别全见）。console_log 单路语义不变（wasm 控
/// 制台回退；壳注入诊断 sink 时自动同步落盘）
fn log(msg: &str) {
    starfish_debug::log_debug!(msg);
}

/// 失败出口（恒 Error——发行壳 Info 级别下也必落盘）
fn log_err(msg: &str) {
    starfish_debug::log_error!(msg);
}

/// 驱动一次运行，返回进程退出码（0 = 成功；2 = 载荷不可得；1 = 运行错误
/// ——python 同语义）
pub async fn run<H: Host>(host: &H) -> i32 {
    #[cfg(target_arch = "wasm32")]
    crate::platform::web::breadcrumb("B2 runtime::run 进入");
    // 资源加密嵌入钥接线（本仓 build.rs 编译期嵌入——assets.key 在源码树
    // 时生效；未嵌入 = no-op dev 明文形态）。钥不进 Python 层。
    if let (Some(hex), magic) = (
        std::option_env!("ASSET_KEY_HEX"),
        std::option_env!("ASSET_MAGIC"),
    ) {
        if hex.len() == 64 {
            let mut key = [0u8; 32];
            for (i, b) in hex.as_bytes().chunks(2).enumerate() {
                key[i] = u8::from_str_radix(std::str::from_utf8(b).unwrap_or("0"), 16)
                    .unwrap_or(0);
            }
            let mut m = [b'S'; 5];
            if let Some(magic) = magic {
                let src = magic.as_bytes();
                if src.len() == 5 {
                    m.copy_from_slice(src);
                }
            }
            starfish_pygame::sfx::init_crypto(key, m);
            starfish_debug::log_debug!("[asset-key] 嵌入钥接线完成（magic 已注入）");
        }
    }
    let name = host.name();
    let t0 = Stopwatch::now();
    // ── 载荷获取（唯一平台差异点）──
    let req: RunRequest = match host.acquire().await {
        Ok(r) => r,
        Err(msg) => {
            log_err(&format!("[{name}] {msg}"));
            return 2;
        }
    };
    // cwd 切模块根（资源相对路径与脚本预期一致；starfish-io 桌面基准 =
    // cwd——io 正确性的锚点；web/android 端各由平台承载，此调用无害）
    if let Some(root) = &req.module_root {
        let _ = std::env::set_current_dir(root);
    }
    // ── 控制台阶段：建窗前完成全部确定性启动开销（各阶段打点——
    // 顺序与耗时可审计，"白窗等待"归因用；"开始/就绪"成对——崩溃
    // 定位到具体阶段）──
    let t_rp = Stopwatch::now();
    log(&format!("[{name}] ①genesis 开始"));
    let interp = rpy::new_interpreter();
    log(&format!("[{name}] ①解释器就绪 {}ms", t_rp.ms()));
    // sys.argv：宿主参数 + Android 追加实测屏幕尺寸（外部窗口 attach
    // 时记录）——脚本 set_mode 自适应屏幕的取数通道（"std 屏幕尺寸
    // 接口"的壳层先行形态；桌面/web 不追加，argv 保持 CLI 原样）
    let mut argv: Vec<String> = host.args();
    #[cfg(target_os = "android")]
    if let Some((ew, eh)) = starfish_we::embedded::external_size() {
        argv.push(ew.to_string());
        argv.push(eh.to_string());
    }
    interp.enter(|vm| set_argv(vm, &req.name, &argv)); // python 标准 sys.argv
    // 游戏脚本模块加载（python 行为：唯一解析根 = main 所在目录——
    // sys.path[0] 同语义）。modules/、resources/ 仅为打包便利文件夹，
    // 无导入特权：加载 modules 下模块 = import modules.xxx（自然相对
    // 路径）；根缺失则零注入、纯脚本零开销
    if let Some(entries) = &req.embedded_scripts {
        // runtime 单文件形态：内嵌脚本表直装（pack 条目已解密——钥不进 Python 层）
        interp.enter(|vm| match rpy::install_module_finder_with_table(vm, entries.clone()) {
            Ok(0) => {}
            Ok(n) => log(&format!("[{name}] 内嵌脚本装表 {n} 个")),
            Err(e) => log_err(&format!("[{name}] 内嵌表装载失败: {e}")),
        });
    } else if req.module_root.is_some() {
        interp.enter(|vm| match rpy::install_module_finder(vm, &["."]) {
            Ok(0) => {}
            Ok(n) => log(&format!("[{name}] 模块表装载 {n} 个（基准 = main 目录）")),
            Err(e) => log_err(&format!("[{name}] 模块装载失败: {e}")),
        });
    }
    let t_font = Stopwatch::now();
    if host.cjk_preload() {
        log(&format!("[{name}] ②字体预载开始"));
        rpy::testhost::preload_cjk(name).await;
        log(&format!("[{name}] ②字体预载完 {}ms", t_font.ms()));
    } else {
        log(&format!(
            "[{name}] ②字体预载跳过（最小字体形态，{}ms）",
            t_font.ms()
        ));
    }
    // ── 创建期旗标预扫描（dev 解释器启发式）：TRANSPARENT 等创建期
    // 旗标只在建窗时生效（apply_window_request 的运行时面不覆盖；
    // 后端声明位同样"首次 set_mode 定终身"）——宿主壳预建窗须替脚本
    // 带上。脚本文本含词即置位：注释提及也会命中（保守误报可接受）；
    // 运行期旗标（RESIZABLE 等）不在此列，脚本 set_mode 经
    // apply_window_request 照常生效 ──
    let mut host_flags = 0u32;
    for (token, bit) in [
        ("TRANSPARENT", display::TRANSPARENT),
        ("DIRECTX", display::DIRECTX),
        ("VULKAN", display::VULKAN),
        ("OPENGLES", display::OPENGLES),
        ("OPENGL", display::OPENGL),
        ("HIDDEN", display::HIDDEN),
    ] {
        if req.code.contains(token) {
            host_flags |= bit;
        }
    }
    // ── 建窗（可见；GPU/交换链装配承载于窗口期——百 ms 级）──
    let t_gpu = Stopwatch::now();
    log(&format!("[{name}] ③建窗+GPU装配开始（旗标 {host_flags:#b}）"));
    // 壳窗尺寸：Android 嵌入 = 外部窗口实测值（attach 时记录）——引擎
    // 表面初始即满屏 1:1，脚本 set_mode 后由 GLES 缩放铺满（用户接受
    // 语义）；桌面/web = 800×600 惯例
    #[cfg(target_os = "android")]
    let (win_w, win_h) = starfish_we::embedded::external_size().unwrap_or((800, 600));
    #[cfg(not(target_os = "android"))]
    let (win_w, win_h) = (800u32, 600u32);
    if let Err(e) = display::set_mode_ex((win_w, win_h), host_flags).await {
        log_err(&format!("[{name}] set_mode 失败: {e}"));
        return 1;
    }
    log(&format!(
        "[{name}] ③建窗+GPU装配完 {}ms（创建期旗标 {host_flags:#b}）",
        t_gpu.ms()
    ));
    log(&format!(
        "[{name}] ④执行 {}（累计 {}ms）",
        req.name,
        t0.ms()
    ));
    // 装配 + 执行统一走 testhost 面（帧桥注入/协程驱动/traceback 全在内）
    if let Err(e) = rpy::testhost::run_script_in(interp, &req.code, &req.name, req.payload.clone().unwrap_or_default()).await {
        log_err(&format!("[{name}] {e}"));
        return 1;
    }
    0
}

/// python 标准 sys.argv 接线（argv[0] = "-c" / 脚本路径，余者透传）
fn set_argv(vm: &rustpython_vm::VirtualMachine, argv0: &str, rest: &[String]) {
    if let Ok(sys) = vm.import("sys", 0) {
        let mut items: Vec<rustpython_vm::PyObjectRef> =
            vec![vm.ctx.new_str(argv0.to_string()).into()];
        items.extend(rest.iter().map(|a| vm.ctx.new_str(a.clone()).into()));
        let _ = sys.set_attr("argv", vm.ctx.new_list(items), vm);
    }
}
