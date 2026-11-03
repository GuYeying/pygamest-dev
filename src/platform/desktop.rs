//! 桌面宿主实现（首个 [`Host`](crate::host::Host) 实现者）：CLI 解析、
//! 载荷读盘、REPL 交互形态、内置静态服务器分派。
//!
//! 载荷获取 = std::fs 同步读；模块根 = 脚本父目录（运行时切 cwd——
//! python sys.path[0] 同语义）。
// RP 嵌入 API 经 pygamest re-export（vendored path 在 pygamest 仓内）
use pygamest::rustpython_vm as rustpython_vm;


use crate::host::RunRequest;
use pygamest::rpy;
use rustpython_vm::VirtualMachine;

/// 桌面入口（REPL/serve/运行 三分派 + 退出码；`-> !` 不返回）
pub fn desktop_main() -> ! {
    // 日志统一入口（starfish-debug log 模块）：文件全量 + 告警以上直出
    starfish_debug::log::init(starfish_debug::log::LogConfig {
        level: starfish_debug::log::Level::Debug,
        file: Some(std::path::PathBuf::from("starfish.log")),
        remote: None,
        console: Some(starfish_debug::log::Level::Warn),
    });
    starfish_std::app::block_on(async move {
        let host = DesktopHost::from_env();
        if host.wants_repl() {
            repl_mode(); // 桌面专属交互形态（不返回）
        }
        if let Some((dir, port)) = host.serve_request() {
            crate::serve::serve(&dir, port); // 内置静态服务器（不返回）
        }
        let code = crate::runtime::run(&host).await;
        // 无条件 exit（0 也走）：block_on 返回即运行终结——落到底部的
        // unreachable 会把成功收尾变成 panic 101（正常返回型脚本首跑实证）
        std::process::exit(code);
    });
    unreachable!("block_on 完成后必经 exit 或分支不返回")
}


/// CLI 解析结果（python 标准命令行三形态 + serve 子命令）
enum Mode {
    /// 无参 = 交互式 REPL（桌面专属交互，main 直入、不经 acquire）
    Repl,
    /// `-c "<代码>"`（不建窗；纯脚本）
    Eval(String),
    /// `<脚本.py>`（余参透传 sys.argv）
    File(String),
    /// `serve [目录] [端口]`：内置静态服务器（web 宿主页面的零依赖
    /// 打开方式——file:// 下 ES module 被 CORS 拦截）
    Serve { dir: String, port: u16 },
}

pub struct DesktopHost {
    mode: Mode,
    rest: Vec<String>,
}

impl DesktopHost {
    /// 从进程参数装配（python 标准：首个参数 = -c 或脚本路径，余者透传）。
    /// `--assets <目录>`：资源根指向 bundle/散文件目录（starfish_io
    /// BASE_DIR——游戏相对路径落该目录，存档等绝对路径不受影响）。可出现
    /// 在任意位置，解析后从参数面剥离、不影响脚本识别；**立即绝对化**——
    /// 驱动随后会 chdir 到脚本父目录，相对值会漂移。
    /// 加密/明文的开关在**编译期**：build.rs 见 assets.key → 嵌入钥 →
    /// 本二进制走解密链；无 key 构建 = 纯明文形态（io 层透传）。
    pub fn from_env() -> Self {
        let mut argv: Vec<String> = std::env::args().skip(1).collect();
        let mut i = 0;
        while i < argv.len() {
            if argv[i] == "--assets" {
                let dir = match argv.get(i + 1) {
                    Some(d) => d.clone(),
                    None => usage(),
                };
                let p = std::path::PathBuf::from(&dir);
                let abs = if p.is_absolute() {
                    p
                } else {
                    std::env::current_dir().unwrap_or_default().join(p)
                };
                starfish_io::set_base_dir(&abs);
                starfish_debug::log_info!(format!("[assets] 资源根 = {}", abs.display()));
                argv.drain(i..=i + 1);
            } else {
                i += 1;
            }
        }
        let mut argv = argv.into_iter();
        match argv.next() {
            None => Self { mode: Mode::Repl, rest: Vec::new() },
            Some(first) => match first.as_str() {
                "-c" => {
                    let code = match argv.next() {
                        Some(c) => c,
                        None => usage(),
                    };
                    Self { mode: Mode::Eval(code), rest: argv.collect() }
                }
                "serve" => {
                    let dir = argv.next().unwrap_or_else(|| "web".to_string());
                    let port = argv
                        .next()
                        .and_then(|p| p.parse::<u16>().ok())
                        .unwrap_or(8123);
                    Self { mode: Mode::Serve { dir, port }, rest: Vec::new() }
                }
                path => Self { mode: Mode::File(path.to_string()), rest: argv.collect() },
            },
        }
    }

    /// REPL 专属：无参调用 = 交互模式（main 据此直入 repl_mode）
    pub fn wants_repl(&self) -> bool {
        matches!(self.mode, Mode::Repl)
    }

    /// serve 专属：静态服务请求（main 据此进入内置服务器，不返回）
    pub fn serve_request(&self) -> Option<(String, u16)> {
        match &self.mode {
            Mode::Serve { dir, port } => Some((dir.clone(), *port)),
            _ => None,
        }
    }
}

impl crate::host::Host for DesktopHost {
    fn name(&self) -> &'static str {
        "pygamest-dev"
    }

    fn args(&self) -> Vec<String> {
        self.rest.clone()
    }

    async fn acquire(&self) -> Result<RunRequest, String> {
        match &self.mode {
            Mode::Repl => unreachable!("REPL 由 main 直入 repl_mode，不经 acquire"),
            Mode::Serve { .. } => unreachable!("serve 由 main 直入 serve::serve，不经 acquire"),
            Mode::Eval(code) => Ok(RunRequest {
                name: "<pygamest-dev -c>".to_string(),
                code: code.clone(),
                module_root: None,
                    embedded_scripts: None,
            payload: None, // -c 无基准目录、不注入模块表
            }),
            Mode::File(path) => {
                let sp = std::path::PathBuf::from(path);
                if sp.is_dir() {
                    return Err(format!(
                        "{path}: 是目录——请传脚本文件（目录工程传其入口，如 main.py）"
                    ));
                }
                let script = std::fs::read_to_string(&sp)
                    .map_err(|e| format!("无法读取 {path}: {e}"))?;
                let sp_abs = sp.canonicalize().unwrap_or(sp);
                let module_root = Some(
                    sp_abs
                        .parent()
                        .map(|p| p.to_string_lossy().to_string())
                        .filter(|s| !s.is_empty())
                        .unwrap_or_else(|| ".".to_string()),
                );
                Ok(RunRequest {
                    name: path.clone(),
                    code: script,
                    module_root,
                    embedded_scripts: None,
                    payload: None,
                })
            }
        }
    }
}

/// REPL（逐行；表达式值回显）——桌面专属交互形态
pub fn repl_mode() -> ! {
    println!("pygamest-dev REPL（pygame 全内置；quit() 退出）");
    let interp = rpy::new_interpreter();
    let scope = enter_setup(&interp);
    let stdin = std::io::stdin();
    loop {
        print!(">>> ");
        use std::io::Write;
        let _ = std::io::stdout().flush();
        let mut line = String::new();
        if stdin.read_line(&mut line).unwrap_or(0) == 0 {
            break; // EOF
        }
        let line = line.trim_end();
        if line.is_empty() {
            continue;
        }
        if line == "quit()" || line == "exit()" {
            break;
        }
        // 表达式优先（Single 语义：值回显）；非表达式降级 Exec
        match vm_compile_eval(&interp, line) {
            Some(c) => {
                interp.enter(|vm| match vm.run_code_obj(c, scope.clone()) {
                    Ok(v) => {
                        if !vm.is_none(&v) {
                            if let Ok(r) = v.repr(vm) {
                                println!("{}", r);
                            }
                        }
                    }
                    Err(e) => eprintln!("{}", format_tb(vm, &e)),
                });
            }
            None => match vm_compile_exec(&interp, line) {
                Some(c) => {
                    interp.enter(|vm| {
                        if let Err(e) = vm.run_code_obj(c, scope.clone()) {
                            eprintln!("{}", format_tb(vm, &e));
                        }
                    });
                }
                None => eprintln!("SyntaxError: 语句编译失败"),
            },
        }
    }
    std::process::exit(0);
}

fn format_tb(
    vm: &VirtualMachine,
    exc: &rustpython_vm::builtins::PyBaseExceptionRef,
) -> String {
    let mut buf = std::io::Cursor::new(Vec::<u8>::new());
    let _ = vm.write_exception(&mut rustpython_vm::py_io::IoWriter(&mut buf), exc);
    String::from_utf8_lossy(buf.get_ref()).trim_end().to_string()
}

/// 装配（解释器 enter 内模块注入）——返回 scope 供 REPL 用。
/// （stdio 接线退役：RP "stdio" feature 桌面 = std::io 直通，print
/// 天然行缓冲出控制台；曾试 TextIOWrapper(io.FileIO) 接线，frozen
/// `_io` 无 FileIO——多此一举且必败，2026-10-26 实测定约。）
fn enter_setup(interp: &rustpython_vm::Interpreter) -> rustpython_vm::scope::Scope {
    let scope = std::cell::RefCell::new(None);
    interp.enter(|vm| {
        let sc = vm.new_scope_with_builtins();
        rpy::install_modules(vm);
        *scope.borrow_mut() = Some(sc);
    });
    scope.into_inner().expect("enter 必然装配 scope")
}

/// Single 模式编译（REPL 值回显用）
fn vm_compile_eval(
    interp: &rustpython_vm::Interpreter,
    source: &str,
) -> Option<rustpython_vm::PyRef<rustpython_vm::builtins::PyCode>> {
    interp.enter(|vm| {
        vm.compile(
            source,
            rustpython_vm::compiler::Mode::Eval,
            "<pygamest-dev repl>".to_string(),
        )
        .ok()
    })
}

/// Exec 模式编译（REPL 语句降级用）
fn vm_compile_exec(
    interp: &rustpython_vm::Interpreter,
    source: &str,
) -> Option<rustpython_vm::PyRef<rustpython_vm::builtins::PyCode>> {
    interp.enter(|vm| {
        vm.compile(
            source,
            rustpython_vm::compiler::Mode::Exec,
            "<pygamest-dev repl>".to_string(),
        )
        .ok()
    })
}

fn usage() -> ! {
    eprintln!(
        "pygamest-dev —— pygame 的 python（开发解释器）\n\
\n\
用法（python 标准命令行）：\n\
  pygamest-dev                            交互式 REPL\n\
  pygamest-dev -c \"<代码>\"                单行直跑\n\
  pygamest-dev <脚本.py> [参数...]         脚本直跑（async def main 协程自动驱动）\n\
  pygamest-dev serve [目录] [端口]          内置静态服务器（web 宿主页面，缺省 web/:8123）\n\
\n\
bundle 消费：\n\
  pygamest-dev --assets <bundle目录> <脚本.py>     资源根指向加密散文件 bundle\n\
                                                    （密钥 = 编译期 assets.key；\n\
                                                      无 key 构建 = 纯明文形态）\n\
\n\
pygame 全内置（import pygame 即用）；-c 不建窗，脚本形态预建渲染窗。"
    );
    std::process::exit(2);
}
