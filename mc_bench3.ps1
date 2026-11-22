param([int]$Window = 20, [switch]$NoTick)
$ErrorActionPreference = 'Continue'
$deploy = 'D:\projects\Rust\pygame-rs\deploy'
$script = "$deploy\voxel_mc_test.py"
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

# tick 开关（脚本内注释/恢复 clock.tick）
$raw = Get-Content $script -Raw
if ($NoTick) {
    $raw = $raw -replace '(?m)^(\s*)clock\.tick\(120\)', '$1#clock.tick(120)'
} else {
    $raw = $raw -replace '(?m)^(\s*)#clock\.tick\(120\)', '$1clock.tick(120)'
}
Set-Content $script $raw -Encoding UTF8

$out = "$deploy\mc_a.log"
$p = Start-Process -FilePath "$deploy\python.exe" `
    -ArgumentList $script `
    -WorkingDirectory $deploy `
    -RedirectStandardOutput $out -RedirectStandardError "$deploy\mc_a_err.log" `
    -PassThru
Start-Sleep 4
if ($p.HasExited) { Write-Output "EXITED-EARLY code=$($p.ExitCode)"; exit 1 }

$samples = @()
$end = (Get-Date).AddSeconds($Window)
while ((Get-Date) -lt $end) {
    $line = nvidia-smi --query-gpu=utilization.gpu,clocks.sm,power.draw --format=csv,noheader,nounits 2>$null
    if ($line) { $samples += $line }
    Start-Sleep -m 500
}
if ($p.HasExited) { Write-Output "EXITED-DURING code=$($p.ExitCode)" } else { Stop-Process -Id $p.Id -Force -EA SilentlyContinue }

$gpu = @($samples | ForEach-Object { [int]($_ -split ',')[0].Trim() })
$clk = @($samples | ForEach-Object { [int]($_ -split ',')[1].Trim() })
$avg = [math]::Round(($gpu | Measure-Object -Average).Average, 1)
$mn = ($gpu | Measure-Object -Minimum).Minimum
$mx = ($gpu | Measure-Object -Maximum).Maximum
$csd = if ($clk.Count -gt 1) { [math]::Round([math]::Sqrt((($clk | ForEach-Object { $_ * $_ } | Measure-Object -Sum).Sum - $clk.Count * [math]::Pow(($clk | Measure-Object -Average).Average, 2)) / ($clk.Count - 1)), 0) } else { 0 }
$tag = if ($NoTick) { 'NO-TICK' } else { 'TICK-120' }
Write-Output "$tag GPU avg=$avg% min=$mn max=$mx clkStd=$csd samples=$($gpu.Count) raw=[$($gpu -join ',')]"
Get-Content $out -Tail 2 -EA SilentlyContinue
