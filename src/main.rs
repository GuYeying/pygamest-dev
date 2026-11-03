//! pygamest-dev —— **pygame 的 python**（开发解释器）：pygame 全内置、
//! 零 Rust 工具链，拿到 `python.exe` 配任意编辑器就能开发 pygame 游戏。
//!
//! 本文件 = 桌面 bin 入口薄壳（全部逻辑在库 `pygamest_dev` 内——
//! host trait / runtime 通用驱动 / platform 各平台实现，Android 调试壳
//! example 与桌面 CLI 共用同一库）。

/// 桌面入口：desktop 平台实现（CLI/REPL/serve 三分派 + 退出码）
#[cfg(not(target_arch = "wasm32"))]
fn main() {
    pygamest_dev::platform::desktop::desktop_main();
}

/// wasm bin 的 rustc 存根 + **bin 专属 start 入口**——真入口链 =
/// `__dev_web_entry`（bin 侧 start 属性）→ `platform::web::web_start`。
/// start 属性曾在库侧（platform/web.rs）——被消费本库的其它 wasm bin
/// 继承抢占（runtime 壳实测），2026-11-02 起归各 bin 所有。存根**必须
/// 触碰** web 模块（link_anchors——零副作用引用）：wasm-ld --gc-sections
/// 以 main 可达为根，空 main 会把全部 wasm_bindgen 导出连同 start 一起
/// 裁掉（python.js 只剩 default/initSync，页面 load_code 链接错整页挂
/// ——真机实测），见 platform::web::link_anchors 文档
#[cfg(target_arch = "wasm32")]
fn main() {
    pygamest_dev::platform::web::link_anchors();
}

#[cfg(target_arch = "wasm32")]
use wasm_bindgen::prelude::wasm_bindgen;

#[cfg(target_arch = "wasm32")]
#[wasm_bindgen(start)]
pub async fn __dev_web_entry() -> Result<(), wasm_bindgen::JsValue> {
    pygamest_dev::platform::web::web_start().await
}
