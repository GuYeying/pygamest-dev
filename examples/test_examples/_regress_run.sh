#!/usr/bin/env bash
# _regress_run.sh —— 断言案例回归网 runner（stdout 断言聚合——v1）
# 惯例：案例内 `[xxx-test] PASS/FAIL 名称` 控制台断言（draw_test 先例）。
# 本 runner 逐案限时运行（断言在前几帧打印完）→ 捕获 stdout → 解析
# 聚合 → 红绿汇总。FAIL/Traceback 任何一例 = 总出口码 1。
# 用法：bash examples/_regress_run.sh [case1 case2 ...]（缺省 = 全集）
# 每案会短暂开窗——回归运行常态。
PY="/d/Projects/Rust/pygame-rs-dev/target/release/python.exe"
DIR="$(cd "$(dirname "$0")" && pwd)"
T="${REGRESS_T:-6}"   # 每案限时秒数（env REGRESS_T 可调）

DEFAULT_CASES="draw_test font_test math_test image_test io_test input_test
parity_test pip_test tasks_test rapier_test rapier3d_test fluid_test
fluid2d_test transparent_test egui_test egui_test_windowed"
CASES="${*:-$DEFAULT_CASES}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 重案例加时表（300 帧模拟压线——连开 16 窗负载下 6s 不够）
case_t() {
  case "$1" in
    fluid_test|fluid2d_test|rapier_test|rapier3d_test) echo 12 ;;
    *) echo "${REGRESS_T:-6}" ;;
  esac
}

total_pass=0; total_fail=0; bad_cases=""
summary=""

for c in $CASES; do
  f="$DIR/$c.py"
  if [ ! -f "$f" ]; then
    summary+="  ◇ $c 缺文件（跳过）"$'\n'; continue
  fi
  timeout --signal=KILL "$(case_t "$c")" "$PY" "$f" > "$TMP/$c.out" 2>&1
  ec=$?
  p=$(grep -cE "\] PASS|SUMMARY PASS|断言 PASS" "$TMP/$c.out")
  fl=$(grep -cE "\] FAIL|SUMMARY FAIL|断言 FAIL" "$TMP/$c.out")
  tb=$(grep -c "Traceback" "$TMP/$c.out")
  total_pass=$((total_pass + p))
  total_fail=$((total_fail + fl + tb))
  if [ "$fl" -gt 0 ] || [ "$tb" -gt 0 ]; then
    bad_cases+="$c "
    summary+="  ✗ $c  PASS=$p FAIL=$fl 异常=$tb"$'\n'
    grep -E "\] FAIL|Traceback" "$TMP/$c.out" | head -3 | sed 's/^/      /'
  else
    summary+="  ✓ $c  PASS=$p"$'\n'
  fi
done

echo "══════ 回归网汇总 ══════"
echo -n "$summary"
echo "══════ 断言: PASS $total_pass / FAIL $total_fail ══════"
if [ -n "$bad_cases" ]; then
  echo "✗ 异常案例: $bad_cases"
  echo "[regress] FAIL"
  exit 1
fi
echo "[regress] ALL GREEN"
