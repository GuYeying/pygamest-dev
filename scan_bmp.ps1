Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap('D:\Projects\Rust\pygame-rs-dev\mc_truth.bmp')
Write-Output ("SIZE " + $bmp.Width + "x" + $bmp.Height)

function Scan-Color {
    param([string]$Name, [byte]$rMin, [byte]$rMax, [byte]$gMin, [byte]$gMax, [byte]$bMin, [byte]$bMax, [int]$yFrom, [int]$yTo)
    $minx = 999999; $maxx = -1; $miny = 999999; $maxy = -1; $n = 0
    for ($y = $yFrom; $y -lt $yTo; $y++) {
        for ($x = 0; $x -lt $bmp.Width; $x++) {
            $c = $bmp.GetPixel($x, $y)
            if ($c.R -ge $rMin -and $c.R -le $rMax -and $c.G -ge $gMin -and $c.G -le $gMax -and $c.B -ge $bMin -and $c.B -le $bMax) {
                $n++
                if ($x -lt $minx) { $minx = $x }
                if ($x -gt $maxx) { $maxx = $x }
                if ($y -lt $miny) { $miny = $y }
                if ($y -gt $maxy) { $maxy = $y }
            }
        }
    }
    Write-Output ($Name + " n=" + $n + " x[" + $minx + ".." + $maxx + "] y[" + $miny + ".." + $maxy + "]")
}

Scan-Color 'RED-L1' 220 255 0 80 0 80 0 400
Scan-Color 'GREEN-L2' 0 120 200 255 0 120 0 400
Scan-Color 'BLUE-L3' 0 120 100 220 200 255 0 400
Scan-Color 'WHITE-CROSS' 235 255 235 255 235 255 900 1280
$bmp.Dispose()
