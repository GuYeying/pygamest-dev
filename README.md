# pygamest-dev

**pygame 的 python** —— pygame 全内置的开发解释器（`python.exe`）。

零 Rust 工具链：像用 python 一样写 pygame，拿到 `python.exe` 配任意
编辑器就能开发 pygame 游戏——`import pygame` 即用，所有子模块原生
内置（非 ctypes shim）。

## 特性

- **python 标准命令行**：REPL / `-c` / 脚本直跑（`sys.argv` 透传、
  退出码对齐、目录实参报错）
- **协程游戏门**：脚本定义 `async def main():` 即自动驱动帧循环，
  帧体 `await pygame.next_frame()`（无 main = 纯脚本顶层执行完即收，
  python 语义：定义 ≠ 调用）
- **pygame 全内置**：draw/font/image/mixer/mask/transform/… 22 子模块，
  外加 `pygame.egui`（egui 界面）与 `pygame_physics`（rapier 2D/3D）
- **能力轴 feature 化**：ozz / spine / live2d 动画三库与桌宠三口
  （click-through / skip-taskbar / tray）按 `--features` 显式裁剪——
  未启用的轴连编译都不参与，Python 面 import 即 `ModuleNotFoundError`
  （详见下方[构建](#构建三平台)）
- **透明窗口**：`set_mode(..., TRANSPARENT | DIRECTX)` 逐像素透明
  （DirectComposition + 预乘 alpha），桌宠/悬浮件形态
- **经典 traceback**：语法错/运行期异常输出与 CPython 一致
- **启动仪表**：阶段耗时打点（解释器/字体/建窗/首帧）+ 慢调用哨兵

## 用法

```
python                            交互式 REPL（quit()/exit() 退）
python -c "<代码>"                单行直跑
python <脚本.py> [参数...]         脚本直跑（任意脚本；cwd 自动切脚本目录）
```

最小游戏（协程门）：

```python
import pygame

async def main():
    screen = pygame.display.set_mode((400, 300))
    while True:
        screen.fill((30, 30, 46))
        pygame.display.flip()
        await pygame.next_frame()
```

## 构建（三平台）

### 前置

| 平台 | 工具链要求 |
|---|---|
| 全部 | **Rust nightly**（默认集含 ozz——上游 ozz-animation-rs 用 `std::simd`，stable 构建报 `core::simd` 错属预期）：`rustup toolchain install nightly` |
| Web | `rustup target add wasm32-unknown-unknown --toolchain nightly` + [wasm-bindgen-cli](https://crates.io/crates/wasm-bindgen-cli)（**版本与 Cargo.lock 严格一致**——`web/build.py` 自检，不一致按提示 `cargo install wasm-bindgen-cli --version <版本>`） |
| Android | Android SDK + NDK（`android/build.py` 默认寻 `D:/SDK/Android`）+ `cargo install cargo-ndk` + `rustup target add aarch64-linux-android --toolchain nightly` + JDK（javac/d8/zipalign/apksigner 走 build-tools） |

### 能力轴（features）

| feature | 默认 | 说明 |
|---|---|---|
| `gui` / `physics2d` / `physics3d` | ✅ | egui 界面 + rapier 2D/3D |
| `ozz` | ✅ | 3D 骨骼动画（**nightly 依赖的来源**） |
| `spine` | ⬜ | Spine 2D 骨骼动画（`--features spine` 按需叠加） |
| `live2d` | ⬜ | Live2D/Cubism（IP 许可敏感——同上按需） |
| `full` | ⬜ | stdlib 全量冻结（缺省 = Lib_min 裁剪版，`time`/`sys` 内建不受影响） |
| `click-through` / `skip-taskbar` / `tray` | ⬜ | 桌宠三口（Win32/macOS/Linux 实装；未启用 = 对应 API 不存在） |

未启用的轴 = 对应 Python 子模块**不存在**（`import` 即 `ModuleNotFoundError`）——
能力裁剪在编译期完成，运行期零开销。

### Windows 桌面

```
cargo +nightly build                                              # 默认形态 → target/debug/python.exe
cargo +nightly build --features "spine,live2d"                    # 叠加动画库
cargo +nightly build --features "spine,live2d,full,click-through,skip-taskbar,tray"   # 全量形态
cargo +nightly build --release                                    # 分发 → target/release/python.exe
```

运行（脚本目录自动切 cwd，相对路径 `assets/...` 相对脚本父目录）：

```
python.exe examples\hello_world.py
python.exe examples\font_test.py
```

贡献者（要改 pygamest/starfish 源码联调）：clone 仓库到同级目录后，在
本仓建 `.cargo/config.toml`（已 gitignore）。`paths` 覆盖只换构建不换
feature 校验——**新增 feature 的 crate 必须走 `[patch]` 整体换源**：

```toml
paths = [
  "../starfish/crates/starfish-std",
  "../starfish/crates/starfish-debug",
  "../starfish/crates/starfish-time",
  "../starfish/crates/starfish-permission",
  "../starfish/crates/starfish-io",
  "../starfish/crates/starfish-net",
  "../starfish/crates/starfish-dialog",
  "../starfish/crates/starfish-gamepad",
  "../starfish/crates/starfish-render",
  "../starfish/crates/starfish-gfx",
  "../starfish/crates/starfish-font",
  "../starfish/crates/starfish-audio",
  "../starfish/crates/starfish-video",
]

[patch."https://github.com/GuYeying/starfish"]
starfish-we = { path = "../starfish/crates/starfish-we" }
starfish-pygame = { path = "../starfish/crates/starfish-pygame" }

[patch."https://github.com/GuYeying/pygamest"]
pygamest = { path = "../pygame-rs" }
```

Windows MSVC 构建自动抬主线程栈（build.rs，RP 引导需要）。

### Web（wasm）

```
# bash 形态（PowerShell 用 $env:RUSTFLAGS="-C target-feature=+simd128"）
RUSTFLAGS="-C target-feature=+simd128" python web/build.py --nightly --features "spine,live2d"
```

- `--features` 逗号分隔透传 cargo；`--nightly` 走 nightly 工具链
  （默认集含 ozz → 实际上现在恒须 nightly + simd128）
- 产物：`web/index.html + python.js + python_bg.wasm`（host 一次编译，
  游戏免重编译）

测试（file:// 无效——fetch 受 CORS 限制，须静态服务）：

```
cd web && python -m http.server 8000        # 或本解释器内置服务器 python.exe serve
浏览器打开 index.html?script=<脚本名>       # 脚本须在 web/ 目录内
```

页面亦支持选本地 `.py` 单文件直跑。动画三库综合回归：
`?script=anim3_wasm_test.py`（资产在 `web/assets/`——与桌面
`examples/assets/`、Android filesDir 同构，相对路径三端字面一致）。

### Android（案例形式）

```
python android/build.py demo --nightly --features "spine,live2d"    # 案例 APK 全链（收集脚本+交叉编译+签名）
python android/build.py demo --install                              # 构建后 adb install -r 并启动
python android/build.py export --nightly                            # 纯 SDK 形态：各 ABI .so → dist/android/
```

- **案例形式**：demo 链路把 examples/ 全量脚本（48+ 案例）+ modules +
  模型资产（web/assets 单源）打进 APK——装上后启动器里**逐案例点选运行**
  （需对应能力轴：轴未启用的案例 import 即 ModuleNotFoundError，属预期
  裁剪语义）；产物 `target/apk/pygamestdev_demo.apk`
- `--features` 逗号分隔透传 cargo（`--nightly` 因默认集含 ozz 实际恒需）
- 构建 ID 注入（`ksys_log` 首行可查真机包新旧）；versionCode 随构建
  时间生成（防部分 ROM 覆盖安装静默跳过）
- ABI：demo 内置 arm64-v8a（x86_64 走 export 形态）

### 诊断

```
# 内存采样（3s 一拍：live_alloc / live_bytes / total_alloc / rss——
# 泄漏排查装置，方法论见 pygamest 仓 reference/如何调试寻找内存泄漏.md）
PYGAMEST_MEMTRACE=1 python.exe examples\font_test.py
```

## 架构（一句话）

[RustPython](https://github.com/RustPython/RustPython)（vendored，
零改动）+ [pygamest](https://github.com/GuYeying/pygamest) 原生绑定面
+ [starfish](https://github.com/GuYeying/starfish) 引擎（wgpu）。

## 定约与分工

- 入口严格 `async def main()`（跨平台统一——Web rAF 模型的硬约束）；
- 帧桥 `pygame.next_frame()`（待网络 awaitable 同机制扩展）；
- 与 [pygamest-runtime](https://github.com/GuYeying/pygamest-runtime)
  （分发载体，玩家单元）分工：本仓 = 开发解释器（python.exe 形态），
  那仓 = 入口加密嵌入 + 散文件清单的成品分发。

## 协议

MIT OR Apache-2.0 双协议（见 LICENSE-MIT / LICENSE-APACHE）。


## 生态仓库矩阵

| 仓库 | 角色 |
|---|---|
| [starfish](https://github.com/GuYeying/starfish) | 引擎本体（纯 Rust 跨平台库，零 Python 资产） |
| [pygamest](https://github.com/GuYeying/pygamest) | Python 绑定层（RustPython 内嵌 + 原生 pygame 面） |
| [pygamest-dev](https://github.com/GuYeying/pygamest-dev) | 开发解释器（本仓，python.exe 形态） |
| [pygamest-runtime](https://github.com/GuYeying/pygamest-runtime) | 游戏运行时（玩家单元，入口加密嵌入 + 散文件清单） |
| [egui-starfish-we](https://github.com/GuYeying/egui-starfish-we) | egui × starfish-we 适配（vendored egui-winit fork） |
| [rapier-starfish-debug](https://github.com/GuYeying/rapier-starfish-debug) | Rapier 物理适配 + 通用 debug 渲染 |
