#!/usr/bin/env bash
# 桌面回归矩阵：v3.1 全显式批次（20s/案例，双判据）
cd /d/Projects/Rust/pygame-rs-dev
PASS=(); FAIL=(); DEMO=()
run_case() {
  local name="$1" expect="$2" dur="${3:-20}"
  ./target/debug/python.exe "examples/$name" > "/tmp/reg_$name.log" 2>&1 &
  local pid=$!
  sleep "$dur"
  kill $pid 2>/dev/null; wait $pid 2>/dev/null
  local log="/tmp/reg_$name.log"
  if grep -qE "panicked|Validation Error|thread '" "$log"; then
    FAIL+=("$name(panic)"); echo "[FAIL-panic] $name"
  elif [ "$expect" = "1" ]; then
    if grep -qE "SUMMARY PASS|汇总: 全部通过" "$log"; then
      PASS+=("$name"); echo "[PASS] $name"
    else
      FAIL+=("$name(no-summary)"); echo "[FAIL] $name — $(grep -E 'FAIL|SUMMARY|汇总|异常|Error' "$log" | tail -2)"
    fi
  else
    DEMO+=("$name"); echo "[demo-ok] $name"
  fi
}
run_case fluid2d_test.py 1
run_case fluid_test.py 1
run_case cube_rotate.py 1
run_case math_test.py 1
run_case font_test.py 1
run_case draw_test.py 1
run_case render_unify_demo.py 1
run_case mesh_builder_demo.py 1
run_case gfx3d_demo.py 0
run_case center_origin_demo.py 0
run_case blit_transform_demo.py 0
run_case custom_pipeline_demo.py 0
run_case compute_probe.py 0
run_case leak_e_writes.py 0
run_case leak_f_render.py 0
run_case leak_i_gfx3d.py 0
run_case egui_test_windowed.py 1 22
run_case fluid3d_game.py 0
echo "=== 汇总: PASS=${#PASS[@]} demo=${#DEMO[@]} FAIL=${#FAIL[@]} ==="
printf '%s\n' "${FAIL[@]}"
