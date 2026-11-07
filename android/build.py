#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pygamest-dev Android 平台构建（SDK 导出 + 参考 demo APK 双形态）。

用法：
  python android/build.py export            # 纯 SDK：交叉编译 .so 归集
                                            #   → dist/android/<abi>/（宿主
                                            #   app 并入 jniLibs 即集成）
  python android/build.py demo [--skip-build] [--install]
                                            # 参考宿主 demo APK 全链

demo 链路（无 NativeActivity，自有 Java UI 的嵌入式 .so 参考宿主）：
  1. 收集全量示例脚本 → android-project/assets/scripts/（.py 全量打进 APK）
  2. cargo ndk 交叉编译 android_host .so（gui/physics2d/physics3d 轴随
     pygamest-dev default 全量）
  3. javac（-release 11，classpath android.jar）
  4. d8 → classes.dex
  5. aapt2 link（-A assets 打进资源表）
  6. 组装 base + classes.dex + .so（.so 恒 DEFLATED、条目恒正斜杠）
  7. zipalign 4 + apksigner（debug.keystore）
产物：target/apk/pygamestdev_demo.apk（包名 pygamestdev）
"""

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CRATE = Path(__file__).resolve().parent.parent
ANDROID = CRATE / "android"          # 平台目录（自包含：工程 + jniLibs + 本脚本）
DEMO = ANDROID / "android-project"
ASSETS = DEMO / "assets"
JNI_LIBS = ANDROID / "jniLibs"
ABIS = ("arm64-v8a", "x86_64")
SDK_OUT = CRATE / "dist" / "android"  # export 产物（纯 SDK 形态）
ABI = "arm64-v8a"                     # demo APK 内置 ABI（x86_64 走 export 形态）
OUT_DIR = CRATE / "target" / "apk"
WORK = CRATE / "target" / "apk_demo_build"
FINAL_NAME = "pygamestdev_demo.apk"
SO_NAME = "libandroid_host.so"
PKG = "pygame.rsdev"  # manifest 包（两段强制）；Java 类包独立 = pygamestdev（JNI 对齐）
ACTIVITY = f"{PKG}/.MainActivity"
# 全量脚本源（本仓 examples 单源——旧世代 pygamest/examples 已退役，
# 勿回加：遗留脚本会"复活"进 APK；递归 games/ 形态暂不收）
SCRIPT_SOURCES = [
    Path(__file__).resolve().parent.parent / "examples",
]


def sh(cmd, cwd=None, tail=0):
    print("+", " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        sys.exit(f"[FAIL] 命令失败: {cmd[0]} …")
    out = (r.stdout + r.stderr).strip()
    if tail:
        print("\n".join(out.splitlines()[-tail:]))
    return out


def best_subdir(base: Path, prefix: str) -> Path:
    cands = [p for p in base.glob(f"{prefix}*") if p.is_dir()] if base.is_dir() else []
    if not cands:
        sys.exit(f"[FAIL] 未找到 {base}/{prefix}*（检查 SDK 安装）")
    return max(cands, key=lambda p: [int(x) if x.isdigit() else 0 for x in p.name.split(".")])


def sdk_tools():
    """SDK 工具面（ndk bin / build-tools / android.jar）——export 与 demo 共用"""
    sdk = Path("D:/SDK/Android")
    ndk = best_subdir(sdk / "ndk", "")
    bt = best_subdir(sdk / "build-tools", "")
    jar = best_subdir(sdk / "platforms", "android-") / "android.jar"
    ndk_bin = ndk / "toolchains" / "llvm" / "prebuilt" / "windows-x86_64" / "bin"
    return ndk_bin, bt, jar


def ndk_build(abi: str, nightly: bool = False, features: str = ""):
    """cargo ndk 交叉编译 android_host .so → jniLibs/<abi>/（release 铁律；
    nightly/features 透传——ozz 需 nightly，能力轴 feature 按需叠加）"""
    cargo = ["cargo", "+nightly"] if nightly else ["cargo"]
    cmd = cargo + ["ndk", "-t", abi, "-P", "26", "-o", str(JNI_LIBS),
                   "--", "build", "--release", "--example", "android_host"]
    if features:
        cmd += ["--features", features]
    sh(cmd, cwd=CRATE, tail=1)
    so = JNI_LIBS / abi / SO_NAME
    if not so.is_file():
        sys.exit(f"[FAIL] .so 缺失: {so}")
    return so


def cmd_export(_args):
    """纯 SDK 形态：各 ABI 交叉编译 + 归集 → dist/android/<abi>/"""
    ndk_bin, _, _ = sdk_tools()
    for abi in ABIS:
        print(f"=== export [{abi}] cargo ndk build ===")
        so = ndk_build(abi, nightly=_args.nightly, features=_args.features or "")
        sh([str(ndk_bin / "llvm-strip"), str(so)])
        dst = SDK_OUT / abi / SO_NAME
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(so, dst)
        print(f"[OK] {dst}（{dst.stat().st_size // 1024 // 1024} MB）")
    print(f"\n[DONE] {SDK_OUT}\n"
          f"  宿主 app 集成：dist/android/<abi>/ 并入工程 jniLibs 即可\n"
          f"  （JNI 面：loadCode / attachSurface / injectTouch）")


def cmd_demo(args):
    ndk_bin, bt, jar = sdk_tools()

    # 1) 全量脚本收集（整目录重建——与仓库 examples 严格一致；老式
    # 仅清 *.py 会漏网杂散文件，曾混入 python.exe 打进 APK）
    print("=== 1/7 收集全量脚本 → assets/scripts ===")
    scripts_dir = ASSETS / "scripts"
    if scripts_dir.is_dir():
        shutil.rmtree(scripts_dir)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in SCRIPT_SOURCES:
        for py in sorted(src.glob("*.py")):
            (scripts_dir / py.name).write_bytes(py.read_bytes())
            count += 1
    print(f"[OK] 打包脚本 {count} 个")
    # 1b) 模块文件夹收集（examples/modules/ → assets/modules/，递归保留
    # 子包结构）：多文件工程约定（与桌面 mod_demo 同构）——脚本侧
    # `import modules.xxx`；APK 侧由 ScriptActivity.prepareFiles 落盘
    # io 基准目录，模块表装载后自然路径可达
    mods_dir = ASSETS / "modules"
    if mods_dir.is_dir():
        shutil.rmtree(mods_dir)
    mods_dir.mkdir(parents=True, exist_ok=True)
    mcount = 0
    for src in SCRIPT_SOURCES:
        msrc = src / "modules"
        if msrc.is_dir():
            for py in sorted(msrc.rglob("*.py")):
                rel = py.relative_to(msrc)
                dst = mods_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(py.read_bytes())
                mcount += 1
    print(f"[OK] 打包模块 {mcount} 个")
    # 1c) 模型/图集资产收集（web/assets 单源 → APK assets/assets/——与
    #     桌面 CWD assets/、web 服务根 assets/ 同构；三端脚本相对路径
    #     "assets/..." 字面一致，ScriptActivity.copyAssetDir 递归落盘）
    ast_src = CRATE / "web" / "assets"
    ast_dst = ASSETS / "assets"
    if ast_dst.is_dir():
        shutil.rmtree(ast_dst)
    if ast_src.is_dir():
        shutil.copytree(ast_src, ast_dst)
        n = sum(1 for f in ast_dst.rglob("*") if f.is_file())
        print(f"[OK] 打包模型资产 {n} 个（spineboy + Hiyori）")
    else:
        print("[WARN] web/assets 缺失——动画资产脚本在端上将找不到文件")

    # 2) 交叉编译 .so（release 铁律）
    so_name = SO_NAME
    jni_libs = JNI_LIBS
    so = jni_libs / ABI / so_name
    if not args.skip_build:
        print(f"=== 2/7 cargo ndk build ({ABI}) ===")
        so = ndk_build(ABI, nightly=args.nightly, features=args.features or "")
    if not so.is_file():
        sys.exit(f"[FAIL] .so 缺失: {so}")
    sh([str(ndk_bin / "llvm-strip"), str(so)])
    nm = sh([str(ndk_bin / "llvm-nm"), "-D", str(so)])
    for sym in ("Java_pygamestdev_PygameRsDev_loadCode",
                "Java_pygamestdev_PygameRsDev_attachSurface",
                "Java_pygamestdev_PygameRsDev_injectTouch"):
        if f"T {sym}" not in nm:
            sys.exit(f"[FAIL] JNI 符号未导出: {sym}")
    print("[nm] JNI 符号面完整 ✓")

    # 3) javac（构建 ID 注入：SdLog.BUILD 占位符 → 构建时刻——ksys_log
    #    首行即可判真机包新旧；"还是老样子"两次无法判定的教训）
    print("=== 3/7 javac ===")
    build_id = "v0.2.2-" + __import__("time").strftime("%Y%m%d-%H%M%S")
    obj = WORK / "obj"
    if obj.is_dir():
        shutil.rmtree(obj)
    obj.mkdir(parents=True)
    java_srcs = list((DEMO / "java").rglob("*.java"))
    staged = []
    for s in java_srcs:
        rel = s.relative_to(DEMO / "java")
        staged_path = WORK / "java" / rel
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path.write_text(
            s.read_text(encoding="utf-8").replace("__BUILD_ID__", build_id),
            encoding="utf-8",
        )
        staged.append(str(staged_path))
    sh(["javac", "--release", "11", "-classpath", str(jar), "-d", str(obj),
        *staged])
    print(f"[OK] 构建ID = {build_id}（ksys_log 首行可查）")

    # 4) d8 → classes.dex
    print("=== 4/7 d8 ===")
    dex_out = WORK / "dex"
    if dex_out.is_dir():
        shutil.rmtree(dex_out)
    dex_out.mkdir(parents=True)
    class_files = [str(p) for p in obj.rglob("*.class")]
    sh([str(bt / "d8.bat"), "--release", "--lib", str(jar), "--min-api", "26",
        "--output", str(dex_out), *class_files])
    dex = dex_out / "classes.dex"
    if not dex.is_file():
        sys.exit("[FAIL] classes.dex 未产出")

    # 5) aapt2 link（-A assets 打进资源表）。versionCode/Name 随构建
    #    注入（manifest 占位符替换——aapt2 flag 不覆盖 manifest 显式
    #    属性，实测无效）：恒定 versionCode 会让部分 ROM 的覆盖安装
    #    静默跳过——提示"安装成功"实际系统保留旧应用（真机教训：文件
    #    新/装了/日期对，三样都真，跑的还是旧 .so 旧脚本）
    print("=== 5/7 aapt2 link ===")
    WORK.mkdir(parents=True, exist_ok=True)
    ver_code = __import__("time").strftime("%m%d%H%M%S")  # int32 安全（10 位）
    mtext = (DEMO / "AndroidManifest.xml").read_text(encoding="utf-8")
    mtext = mtext.replace("__VERSION_CODE__", ver_code).replace(
        "__VERSION_NAME__", build_id).replace(
        "__ORIENTATION__", getattr(args, "orientation", "sensorLandscape"))
    manifest = WORK / "AndroidManifest.xml"
    manifest.write_text(mtext, encoding="utf-8")
    base_apk = WORK / "base.apk"
    sh([str(bt / "aapt2.exe"), "link", "--manifest", str(manifest),
        "-I", str(jar), "-A", str(ASSETS), "-o", str(base_apk)])

    # 6) 组装（dex + so；DEFLATED + 正斜杠条目）
    print("=== 6/7 组装 ===")
    final = OUT_DIR / FINAL_NAME
    tmp_full = WORK / "full.apk"
    with zipfile.ZipFile(base_apk) as zb, zipfile.ZipFile(tmp_full, "w") as zout:
        for item in zb.infolist():
            zout.writestr(item, zb.read(item.filename))
        zout.writestr("classes.dex", dex.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
        zout.writestr(f"lib/{ABI}/{so_name}", so.read_bytes(),
                      compress_type=zipfile.ZIP_DEFLATED)

    # 7) zipalign + 签名 + 验证
    print("=== 7/7 zipalign + apksigner ===")
    aligned = WORK / "aligned.apk"
    sh([str(bt / "zipalign.exe"), "-f", "4", str(tmp_full), str(aligned)])
    ks = Path.home() / ".android" / "debug.keystore"
    if not ks.is_file():
        sys.exit(f"[FAIL] 未找到签名 keystore: {ks}")
    sh([str(bt / "apksigner.bat"), "sign", "--ks", str(ks), "--ks-pass", "pass:android",
        "--out", str(final), str(aligned)])
    sh([str(bt / "apksigner.bat"), "verify", str(final)])
    tmp_full.unlink(missing_ok=True)
    aligned.unlink(missing_ok=True)
    print(f"[OK] {final}  ({final.stat().st_size // 1024 // 1024} MB；脚本 {count} 个)")

    if args.install:
        adb = "D:/android-tools/platform-tools/adb.exe"
        sh([adb, "install", "-r", str(final)], tail=1)
        sh([adb, "shell", "am", "start", "-n", "pygamestdev/.MainActivity"], tail=1)


def main():
    ap = argparse.ArgumentParser(description="pygamest-dev Android 平台构建")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_export = sub.add_parser("export", help="纯 SDK：各 ABI .so 归集 → dist/android/")
    p_demo = sub.add_parser("demo", help="参考宿主 demo APK 全链")
    p_demo.add_argument("--skip-build", action="store_true", help="复用现有 jniLibs .so（调试迭代用）")
    for p in (p_export, p_demo):
        p.add_argument("--nightly", action="store_true",
                       help="cargo +nightly（ozz 轴必需）")
        p.add_argument("--features", default="",
                       help="cargo --features（逗号分隔，如 ozz,click-through,skip-taskbar,tray）")
    p_demo.add_argument("--install", action="store_true", help="构建后 adb install -r 并启动")
    # 横竖屏（Android 原生 screenOrientation 取值）——与 runtime 的
    # pack.toml [android] orientation 同语义（行为一致定约）
    p_demo.add_argument("--orientation", default="sensorLandscape",
                        help="landscape / portrait / sensorLandscape / sensorPortrait…")
    args = ap.parse_args()
    {"export": cmd_export, "demo": cmd_demo}[args.cmd](args)


if __name__ == "__main__":
    main()
