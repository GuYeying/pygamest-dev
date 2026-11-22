#!/usr/bin/perl
# 程序化重排：voxel_mc_async.py 主循环 → logic/render 双协程（行边界确定）
use strict; use warnings;
my $f = 'D:/Projects/Rust/pygame-rs-dev/examples/voxel_mc_async.py';
open my $fh, '<', $f or die $!; my @L = <$fh>; close $fh; print "TOTAL=", scalar(@L), " SLICE=", scalar(@L[556..675]), "
";

# 行索引（0-based）：段1 = [556..675]（logic：while True+事件+漫游+step+HUD 数据更新）
#                  段2 = [676..721]（render：with screen.render/raw/HUD 直绘）
#                  段3 = [722..744]（打点——logic 尾）
#                  段4 = [744..765]（flip/tick/统计/next_frame——render 尾）
my @seg1 = @L[556..675];   # while True 起到 draw_hud()+空行
my @seg2 = @L[676..721];   # with screen.render 起到 raw HUD 绘制完
my @seg3 = @L[722..743];   # 打点注释起到 st(...)
my @seg4 = @L[744..765];   # 空行+flip 到 await next_frame

# 段1 首两行是 "    while True:" + "        for e..."——保留（logic_task 的 while）
# 缩进函数：非空行加 4 空格
sub ind4 { my @o; for (@_) { if (/^\s*$/) { push @o, $_ } else { s/^/    /; push @o, $_ } } @o }

my $head_head = "    # ── 异步双协程拆分（设计定约 2026-11-22）──────────────────\n"
    . "    # logic = 事件/漫游/物理 accumulator/交互；render = 绘制/flip/限帧\n"
    . "    # 帧泵统一推进（协作式）；让出原语改名后 = tasks.yield_now()\n"
    . "    # 共享状态经闭包（单线程协作式，零竞态）────────────────────\n";

my $out = $head_head;
$out .= "    async def logic_task():\n";
$out .= "        nonlocal grabbed, last_pos, info, debug_on, fluid_on, fluid_world, fluid_fh, frame\n";
$out .= "        while True:\n";
my @s1 = ind4(@L[557..675]);
print "S1-RET=", scalar(@s1), "\n";
$out .= join("", @s1);
$out .= ind4(@seg3);          # 打点（logic 尾）
$out .= "            await pygame.next_frame()   # 让出（改名后 tasks.yield_now）\n\n";

$out .= "    async def render_task():\n";
$out .= "        while True:\n";
$out .= ind4(@seg2);          # 渲染段
$out .= ind4(@L[744..765]);   # flip/tick/统计（段4）
$out .= "            await pygame.next_frame()   # 让出（改名后 tasks.yield_now）\n\n";

$out .= "    pygame.tasks.spawn(logic_task())\n";
$out .= "    pygame.tasks.spawn(render_task())\n";
$out .= "    while True:                          # 保活泵（任务帧泵自动推进）\n";
$out .= "        for e in pygame.event.get():\n";
$out .= "            if e.type == pygame.event.QUIT:\n";
$out .= "                return\n";
$out .= "        await pygame.next_frame()\n";

# 头部（1..555 原样）+ 新尾段
my @head = @L[0..555];
open my $o, '>', $f or die $!;
print $o @head, $out;
close $o;
print "REARRANGED: logic=", scalar(@L[557..675]), " render=", scalar(@L[676..721]), " lines\n";
