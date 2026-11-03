//! 构建脚本：Windows(MSVC) 主线程栈 Reserve 抬高（RP 的 with_recursion
//! 守卫量真实 C 栈指针——debug 构建引导冻结 importlib 的原生帧深
//! >768KB 即撞默认 1MB 栈 → essential initialization failed）。
//! Reserve ≠ Commit，不用不占内存；CPython 的 python.exe 同款做法。
//!
//! 资源加密密钥嵌入（2026-11-01）：源码树根的 `assets.key`（64 位 hex，
//! encrypt_assets.py 产出）存在时 → 编译期嵌入（`ASSET_KEY_HEX` env）——
//! **分发物零密钥文件**（密钥只进二进制）；文件不存在 = 明文形态（dev）。

fn main() {
    let os = std::env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let env = std::env::var("CARGO_CFG_TARGET_ENV").unwrap_or_default();
    if os == "windows" && env == "msvc" {
        println!("cargo:rustc-link-arg-bins=/STACK:16777216");
    }
    // 资源加密密钥编译期嵌入（option_env 消费——见 platform/desktop.rs 等宿主入口）
    let key_file = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("assets.key");
    if key_file.is_file() {
        println!("cargo:rustc-env=ASSET_KEY_HEX={}", std::fs::read_to_string(&key_file).unwrap_or_default().trim());
        println!("cargo:rustc-env=ASSET_MAGIC=SFXE1");
        println!("cargo:rerun-if-changed=assets.key");
    }
}
