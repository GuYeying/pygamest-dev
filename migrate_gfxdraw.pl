#!/usr/bin/perl
# 一次性迁移脚本：gfxdraw 图元函数族 → gen_* + push 统一口（perl 版）
use strict;
use warnings;

my @files = grep { $_ !~ /draw_test\.py$/ } glob("examples/*.py");
my %stats;

for my $f (@files) {
    open my $fh, '<', $f or die "$f: $!";
    local $/;
    my $src = <$fh>;
    close $fh;
    my $hit = 0;

    # box(t, (x, y, w, h)) → transform 中心 + push(gen_rect(w, h))
    $src =~ s{
        ^(\s*)pygame\.gfxdraw\.box\((\w+),\s*\(([^()]+),\s*([^()]+),\s*([^()]+),\s*([^()]+)\)\)$
    }{
        my ($i, $t, $x, $y, $w, $h) = ($1, $2, $3, $4, $5, $6);
        $hit++;
        "${i}pygame.gfxdraw.set_transform($t, pygame.math.mat4_translation(($x) + ($w) // 2, ($y) + ($h) // 2, 0))\n"
        . "${i}pygame.gfxdraw.push($t, pygame.gfxdraw.gen_rect($w, $h))"
    }gmxe;

    # rectangle(t, (x, y, w, h)) → 周界线（lines 拓扑对 + gen_rect_outline）
    $src =~ s{
        ^(\s*)pygame\.gfxdraw\.rectangle\((\w+),\s*\(([^()]+),\s*([^()]+),\s*([^()]+),\s*([^()]+)\)\),?\s*(#[^\n]*)?$
    }{
        my ($i, $t, $x, $y, $w, $h, $cmt) = ($1, $2, $3, $4, $5, $6, $7 // "");
        $hit++;
        "${i}pygame.gfxdraw.set_topology($t, \"lines\")\n"
        . "${i}pygame.gfxdraw.set_transform($t, pygame.math.mat4_translation(($x) + ($w) // 2, ($y) + ($h) // 2, 0))\n"
        . "${i}pygame.gfxdraw.push($t, pygame.gfxdraw.gen_rect_outline($w, $h)) $cmt\n"
        . "${i}pygame.gfxdraw.set_topology($t, \"default\")"
    }gmxe;

    # filled_circle(t, x, y, r) → transform + push(gen_circle(r))
    $src =~ s{
        ^(\s*)pygame\.gfxdraw\.filled_circle\((\w+),\s*([^()]+?),\s*([^()]+?),\s*([^()]+?)\)$
    }{
        my ($i, $t, $x, $y, $r) = ($1, $2, $3, $4, $5);
        $hit++;
        "${i}pygame.gfxdraw.set_transform($t, pygame.math.mat4_translation($x, $y, 0))\n"
        . "${i}pygame.gfxdraw.push($t, pygame.gfxdraw.gen_circle($r))"
    }gmxe;

    # circle(t, x, y, r)（1px 描边）→ lines 拓扑对 + gen_circle_outline
    $src =~ s{
        ^(\s*)pygame\.gfxdraw\.circle\((\w+),\s*([^()]+?),\s*([^()]+?),\s*([^()]+?)\)$
    }{
        my ($i, $t, $x, $y, $r) = ($1, $2, $3, $4, $5);
        $hit++;
        "${i}pygame.gfxdraw.set_topology($t, \"lines\")\n"
        . "${i}pygame.gfxdraw.set_transform($t, pygame.math.mat4_translation($x, $y, 0))\n"
        . "${i}pygame.gfxdraw.push($t, pygame.gfxdraw.gen_circle_outline($r))\n"
        . "${i}pygame.gfxdraw.set_topology($t, \"default\")"
    }gmxe;

    # line(t, x1, y1, x2, y2) → lines 拓扑对 + gen_line
    $src =~ s{
        ^(\s*)pygame\.gfxdraw\.line\((\w+),\s*([^()]+?),\s*([^()]+?),\s*([^()]+?),\s*([^()]+?)\)$
    }{
        my ($i, $t, $x1, $y1, $x2, $y2) = ($1, $2, $3, $4, $5, $6);
        $hit++;
        "${i}pygame.gfxdraw.set_topology($t, \"lines\")\n"
        . "${i}pygame.gfxdraw.push($t, pygame.gfxdraw.gen_line($x1, $y1, $x2, $y2))\n"
        . "${i}pygame.gfxdraw.set_topology($t, \"default\")"
    }gmxe;

    if ($hit) {
        open my $out, '>', $f or die "$f: $!";
        print $out $src;
        close $out;
        $stats{$f} = $hit;
    }
}
printf("%s: %d 处\n", $_, $stats{$_}) for sort keys %stats;
print "done\n";
