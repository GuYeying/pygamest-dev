# migrate_topology.awk —— gfxdraw push/set_color/set_wireframe/set_topology
# → draw_batch 参数自包含形态（2026-11-25 接口破坏定约批量迁移器）。
# 规则：
#   set_transform 行 —— 原样保留（持久变换语义，draw_batch None 分支沿用）
#   set_color 行     —— 删行，值入 pending（并入最近 push，one-shot 对齐）
#   set_wireframe 行 —— 删行，值入 pending
#   set_topology 行  —— 删行（拓扑随数据烤入 gen）
#   push 行          —— 重组 draw_batch 行（并入 pending color/wireframe）
#   reset_transform  —— 原样保留
# 用法：awk -f migrate_topology.awk file.py > out.py
{
    line = $0
    if (line ~ /pygame\.gfxdraw\.set_topology\(/) next
    if (line ~ /pygame\.gfxdraw\.set_color\(/) {
        pc = line
        sub(/^.*pygame\.gfxdraw\.set_color\(/, "", pc)
        sub(/\)[^)]*$/, "", pc)
        sub(/^[^,]+, */, "", pc)   # 剥会话首参（f/t）——余下即色元组
        next
    }
    if (line ~ /pygame\.gfxdraw\.set_wireframe\(/) {
        pw = line
        sub(/^.*pygame\.gfxdraw\.set_wireframe\(/, "", pw)
        sub(/\)[^)]*$/, "", pw)
        sub(/^[^,]+, */, "", pw)
        next
    }
    if (line ~ /pygame\.gfxdraw\.push\(/) {
        out = line
        sub(/pygame\.gfxdraw\.push\(/, "pygame.gfxdraw.draw_batch(", out)
        kw = ""
        if (pc != "") kw = kw ", color=" pc
        if (pw != "") kw = kw ", wireframe=" pw
        sub(/\)[^)]*$/, kw ")", out)
        print out
        pc = ""; pw = ""
        next
    }
    print line
}
