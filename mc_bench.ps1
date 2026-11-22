param([int]$Window = 30)
$ErrorActionPreference = 'Continue'
$deploy = 'D:\projects\Rust\pygame-rs\deploy'
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

# 1) 启动 MC（stdout/stderr 重定向采集 voxel-mc 打点）
$out = "$deploy\mc_out.log"
$err = "$deploy\mc_err.log"
$p = Start-Process -FilePath "$deploy\python.exe" `
    -ArgumentList "$deploy\voxel_mc_test.py" `
    -WorkingDirectory $deploy `
    -RedirectStandardOutput $out -RedirectStandardError $err `
    -PassThru
Start-Sleep 3
if ($p.HasExited) { Write-Output "MC-EXITED-EARLY code=$($p.ExitCode)"; Get-Content $err -Tail 10; exit 1 }
Write-Output "MC-STARTED pid=$($p.Id)"

# 2) GPU 采样（每 2 秒 × Window 秒）
$samples = @()
$end = (Get-Date).AddSeconds($Window)
while ((Get-Date) -lt $end) {
    $line = nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,temperature.gpu --format=csv,noheader,nounits 2>$null
    if ($line) { $samples += $line }
    Start-Sleep 2
}

# 3) 汇总采样
Write-Output "GPU-SAMPLES:"
$samples | ForEach-Object { Write-Output "  $_" }
if ($samples.Count -gt 0) {
    $gpu = @($samples | ForEach-Object { [int]($_ -split ',')[0].Trim() })
    $mem = @($samples | ForEach-Object { [int]($_ -split ',')[2].Trim() })
    $avg = [math]::Round(($gpu | Measure-Object -Average).Average, 1)
    $max = ($gpu | Measure-Object -Maximum).Maximum
    $min = ($gpu | Measure-Object -Minimum).Minimum
    $mavg = [math]::Round(($mem | Measure-Object -Average).Average, 0)
    Write-Output "GPU-SUMMARY avg=$avg% min=$min% max=$max% vram_avg=${mavg}MB n=$($samples.Count)"
}

# 4) 进程状态 + 日志尾
if ($p.HasExited) { Write-Output "MC-EXITED-DURING code=$($p.ExitCode)" } else { Write-Output "MC-ALIVE-AT-END" }
Write-Output "STDOUT-TAIL:"
Get-Content $out -Tail 15 -ErrorAction SilentlyContinue
Write-Output "STDERR-TAIL:"
Get-Content $err -Tail 8 -ErrorAction SilentlyContinue

# 5) 收口
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Output "BENCH-DONE"
