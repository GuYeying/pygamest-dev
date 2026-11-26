param([string]$Bmp = "_diag_small.bmp", [int]$Y0 = 4, [int]$Y1 = 100)
$b = [IO.File]::ReadAllBytes($Bmp)
$w = [BitConverter]::ToInt32($b, 18)
$h = [BitConverter]::ToInt32($b, 22)
$bpp = [BitConverter]::ToInt16($b, 28)
$off = [BitConverter]::ToInt32($b, 10)
$rowSize = [Math]::Ceiling($w * $bpp / 8)
$pad = (4 - ($rowSize % 4)) % 4
Write-Host "w=$w h=$h bpp=$bpp off=$off rowSize=$rowSize pad=$pad"
for ($y = $Y0; $y -lt $Y1; $y += 2) {
    $row = ""
    for ($x = 0; $x -lt $w; $x += 6) {
        $i = $off + (($h - 1 - $y) * ($rowSize + $pad)) + $x * 3
        if ($b[$i] -gt 90 -or $b[$i + 1] -gt 90 -or $b[$i + 2] -gt 90) { $row += "X" } else { $row += "." }
    }
    if ($row.Contains("X")) { Write-Host ("y=" + $y + " " + $row) }
}
