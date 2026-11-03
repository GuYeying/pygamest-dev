//! Web 宿主实现（[`Host`](crate::host::Host) 的 wasm 分支）。
//!
//! **设计定约（2026-10-26 用户定夺）**：web 端 = **python 基本指令的
//! 对接映射**——
//! - `python <路径> [参数...]` ↔ `?script=<路径>&argv=<参数>&argv=...`
//!   （argv 重复键 = 参数列表，按序透传 `sys.argv`）→
//!   [`starfish_io::read`]（web 后端 = fetch，启动期一次）；
//! - `python -c "<代码>"` ↔ 页面文件选择/控制台注入：JS 读到的代码
//!   串经导出函数 [`load_code`] 直传（不落盘、无文件名语义）。
//!
//! 通道幂等守门（**进程一次契约**：本页只跑一个程序，换游戏刷新页面）。
//! 模块表：web 端 `module_root = None`（无文件系统扫描；wasm 的 bundle
//! 处理延后）——多模块游戏暂以桌面端开发调试为准。
//!
//! 入口 = `web_start`（`#[wasm_bindgen(start)]`，async 支持）；
//! `main` 为 wasm bin 的 rustc 存根（见 main.rs cfg 分支）。

// ── wasm 启动诊断（B0-B4 面包屑）：裸 console 外联——独立于
// starfish-debug 通道的可见性基准（2026-10-31 wasm trap 定位用）
#[cfg(target_arch = "wasm32")]
mod wasm_diag {
    use wasm_bindgen::prelude::*;
    #[wasm_bindgen]
    extern "C" {
        #[wasm_bindgen(js_namespace = console)]
        fn log(s: &str);
    }
    pub fn breadcrumb(s: &str) {
        log(&format!("[B] {s}"));
    }
}
#[cfg(target_arch = "wasm32")]
pub(crate) use wasm_diag::breadcrumb;

use crate::host::RunRequest;
use std::cell::RefCell;
use std::sync::atomic::{AtomicBool, Ordering};
use wasm_bindgen::prelude::wasm_bindgen;

/// `-c` 形态的代码槽（页面文件选择/控制台注入）
thread_local! {
    static CODE: RefCell<Option<String>> = const { RefCell::new(None) };
}

/// 平台参数（`?argv=` 重复键收集；`python <路径> [参数...]` 的映射——
/// 运行时经 Host::args 透传 sys.argv）
thread_local! {
    static ARGS: RefCell<Vec<String>> = const { RefCell::new(Vec::new()) };
}

/// 进程一次契约守门（本页只运行一个程序；换游戏 = 刷新页面）
static STARTED: AtomicBool = AtomicBool::new(false);

/// %XX 解码 + '+' → 空格（application/x-www-form-urlencoded 查询串
/// 标准语义——URL 规范化会把空格写作 '+'；字面 '+' 须编码为 %2B）
fn decode_percent(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'%' if i + 2 < bytes.len() => {
                if let Ok(v) = u8::from_str_radix(
                    std::str::from_utf8(&bytes[i + 1..i + 3]).unwrap_or(""),
                    16,
                ) {
                    out.push(v);
                    i += 3;
                    continue;
                }
                out.push(bytes[i]);
                i += 1;
            }
            b'+' => {
                out.push(b' ');
                i += 1;
            }
            c => {
                out.push(c);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// 查询串解析 → (script 路径, argv 参数列表)
fn parse_query() -> (Option<String>, Option<String>, Vec<String>) {
    let search = web_sys::window()
        .and_then(|w| w.location().search().ok())
        .unwrap_or_default();
    let mut code = None;
    let mut script = None;
    let mut argv = Vec::new();
    for kv in search.strip_prefix('?').unwrap_or("").split('&') {
        if kv.is_empty() {
            continue;
        }
        let (k, v) = match kv.split_once('=') {
            Some((k, v)) => (k, decode_percent(v)),
            None => (kv, String::new()),
        };
        match k {
            "code" if code.is_none() => code = Some(v),
            "script" if script.is_none() => script = Some(v),
            "argv" => argv.push(v),
            _ => {}
        }
    }
    (code, script, argv)
}

/// 路径形态宿主（`python <路径> [参数...]` 映射：io fetch 加载）
struct ScriptHost {
    script_url: String,
    argv: Vec<String>,
}

impl ScriptHost {
    fn new(script_url: String, argv: Vec<String>) -> Self {
        starfish_debug::log_info!(&format!(
            "[pygamest-dev] web 载荷 = {script_url}（fetch；argv {argv:?}）"
        ));
        Self { script_url, argv }
    }
}

impl crate::host::Host for ScriptHost {
    fn name(&self) -> &'static str {
        "pygamest-dev"
    }

    fn args(&self) -> Vec<String> {
        self.argv.clone()
    }

    async fn acquire(&self) -> Result<RunRequest, String> {
        let data = starfish_io::read(&self.script_url)
            .await
            .map_err(|e| format!("载荷下载失败 {}: {e}", self.script_url))?;
        let code = String::from_utf8(data)
            .map_err(|e| format!("载荷非 UTF-8（{}）: {e}", self.script_url))?;
        Ok(RunRequest {
            name: self.script_url.clone(),
            code,
            module_root: None,
                    embedded_scripts: None,
            payload: None,
        })
    }
}

/// `-c` 形态宿主（JS 直传代码串；args = 平台参数槽 + ?script= 首参——
/// python `-c` 同语义：`python -c "code" arg0` → sys.argv = ['-c', 'arg0']）
struct CodeHost {
    code: String,
    extra_args: Vec<String>,
}

impl crate::host::Host for CodeHost {
    fn name(&self) -> &'static str {
        "pygamest-dev"
    }

    fn args(&self) -> Vec<String> {
        self.extra_args.clone()
    }

    async fn acquire(&self) -> Result<RunRequest, String> {
        Ok(RunRequest {
            name: "<pygamest-dev -c>".to_string(),
            code: self.code.clone(),
            module_root: None,
                    embedded_scripts: None,
            payload: None,
        })
    }
}

/// 启动闸门（幂等，进程一次契约）：本页只允许一次运行；换游戏请刷新页面。
fn guard() -> bool {
    if STARTED.swap(true, Ordering::SeqCst) {
        starfish_debug::log_info!("[pygamest-dev] 进程一次契约：本页已运行过程序——换游戏请刷新页面");
        return false;
    }
    true
}

/// `-c` 形态运行（代码串 + 参数；python -c 映射）
fn start_code(code: String) {
    starfish_debug::log_info!("[pygamest-dev] 载荷 = -c 代码串（页面注入）");
    let extra_args = ARGS.with(|a| a.borrow().clone());
    wasm_bindgen_futures::spawn_local(async move {
        let host = CodeHost { code, extra_args };
        let code = crate::runtime::run(&host).await;
        if code != 0 {
            starfish_debug::log_info!(&format!("[pygamest-dev] 运行结束（退出码 {code}）"));
        }
    });
}

/// 路径形态运行（fetch 加载；python <路径> 映射）
fn start_fetch(url: String) {
    let argv = ARGS.with(|a| a.borrow().clone());
    crate::platform::web::breadcrumb("B1a start_fetch 进入");
    wasm_bindgen_futures::spawn_local(async move {
        crate::platform::web::breadcrumb("B1b 载荷 spawn_local 进入");
        let host = ScriptHost { script_url: url, argv };
        crate::platform::web::breadcrumb("B1c runtime::run 前");
        let code = crate::runtime::run(&host).await;
        if code != 0 {
            starfish_debug::log_info!(&format!("[pygamest-dev] 运行结束（退出码 {code}）"));
        }
    });
}

/// wasm 真入口（async 支持；wasm-bindgen start 属性）——**只装配，不
/// 分派**：载荷通道由页面 boot 逻辑裁决（暂存 > ?script= > 等待），
/// 消除"URL 参数与注入载荷竞争启动权"的双跑/抢占问题
///（2026-10-26 用户实测：?script= 重载残留导致强制 main.py + 悬空
/// OOB rejection 的根因）。
/// **无 start 属性**（2026-11-02 定约）：库不应声明 wasm 入口——此前带
/// start 的 web_start 被任何消费本库的 wasm 二进制（如 pygamest-runtime
/// 壳）继承，与消费方自己的 start 入口双注册抢占，runtime 壳被 dev 的
/// "等待载荷分派"宿主顶替（实测 runtime wasm 页面永不运行游戏）。
/// start 归各 **bin** 所有：dev bin = main.rs 的 `__dev_web_entry`；
/// runtime 壳 = app_entry! 的 `__starfish_app_entry`。
#[cfg(target_arch = "wasm32")]
pub async fn web_start() -> Result<(), wasm_bindgen::JsValue> {
    #[cfg(target_arch = "wasm32")]
    crate::platform::web::breadcrumb("B0 web_start 进入");
    // 单次闸门：web_start 在页面上会执行两次（wasm start 段自动执行 +
    // glue init 的 __wbindgen_start 显式调用——真机日志"就绪"×2 实证）。
    // body 幂等但双跑误诊，闸门归一
    static STARTED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
    if STARTED.swap(true, std::sync::atomic::Ordering::SeqCst) {
        return Ok(());
    }
    // panic 消息转发控制台（wasm32 panic=abort——默认只留 unreachable
    // 陷阱）。**必须走裸 console 通道**：starfish-debug 通道 web 未 init
    // 时的回退链路若自身失效 = panic 消息黑洞（2026-10-31 实测教训）
    std::panic::set_hook(Box::new(|info| {
        crate::platform::web::breadcrumb(&format!("[panic] {info}"));
    }));
    // 平台参数槽（?argv= 重复键——start_script / -c 宿主 args 用）
    let (_, _, argv) = parse_query();
    ARGS.with(|a| *a.borrow_mut() = argv);
    starfish_debug::log_info!("[pygamest-dev] web 宿主就绪（等待载荷分派）");
    Ok(())
}

/// 页面代码注入（`python -c` 映射）：JS 侧读入的代码串 + 参数列表直传
/// 运行。`exports.load_code(代码串, 参数列表)`——真 python `-c` 同语义：
/// sys.argv = [程序名, 参数...]；语法问题在运行期以 traceback 呈现。
#[wasm_bindgen]
pub fn load_code(code: String, args: Vec<String>) {
    if !guard() {
        return;
    }
    ARGS.with(|a| *a.borrow_mut() = args);
    start_code(code);
}

/// wasm 链接锚点（bin main 触碰用，零副作用——不调用任何函数）：
/// wasm-ld `--gc-sections` 以 main 可达为根，bin 入口若不引用本模块，
/// 全部 `#[wasm_bindgen]` 导出（web_start/load_code/start_script）连同
/// 自定义段描述一起被裁——python.js 只剩 default/initSync，页面
/// `import { load_code }` 静态导入链接错误，整页静默挂死（真机实测）。
/// 函数指针物化 = 代码段保留；web_start 为 async，构造其 Future 即达
/// 引用目的（不轮询无副作用）。
#[cfg(target_arch = "wasm32")]
pub fn link_anchors() {
    std::hint::black_box((
        load_code as fn(String, Vec<String>),
        start_script as fn(String, Vec<String>),
    ));
    std::hint::black_box(web_start());
}

/// 路径拉取运行（`python <路径>` 映射）：fetch 加载脚本。
/// `exports.start_script(路径, 参数列表)`——页面 boot 裁决后的显式入口。
/// args = 透传 sys.argv（Blob URL 本地文件通道同用——本地脚本与路径
/// 脚本同为**脚本形态**：建窗 + 帧桥齐备，2026-11-02 定约）
#[wasm_bindgen]
pub fn start_script(url: String, args: Vec<String>) {
    #[cfg(target_arch = "wasm32")]
    crate::platform::web::breadcrumb("B1 start_script 进入");
    if !args.is_empty() {
        ARGS.with(|a| *a.borrow_mut() = args);
    }
    if !guard() {
        return;
    }
    start_fetch(url);
}
