param([int]$Window = 30)
$ErrorActionPreference = 'Continue'
$deploy = 'D:\projects\Rust\pygame-rs\deploy'
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

$out = "$deploy\mc_out2.log"
$err = "$deploy\mc_err2.log"
$p = Start-Process -FilePath "$deploy\python.exe" `
    -ArgumentList "$deploy\voxel_mc_test.py" `
    -WorkingDirectory $deploy `
    -RedirectStandardOutput $out -RedirectStandardError $err `
    -PassThru
Start-Sleep 3
if ($p.HasExited) { Write-Output "MC-EXITED-EARLY code=$($p.ExitCode)"; exit 1 }
Write-Output "MC-STARTED pid=$($p.Id)"

Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class W32b {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
}
'@
$wp = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if ($wp) {
    [W32b]::SetForegroundWindow($wp.MainWindowHandle) | Out-Null
    Start-Sleep 1
    [System.Windows.Forms.SendKeys]::SendWait('{TAB}')   # grab 态
    Start-Sleep 1
    # 俯视对准地面（放置/删除的射线落点）
    for ($i = 0; $i -lt 5; $i++) { [W32b]::mouse_event(1, 0, 25, 0, [UIntPtr]::Zero); Start-Sleep -m 60 }
} else { Write-Output 'NO-WINDOW (无前台——GPU 照常采样)' }

# 交互循环：左删/右放交替（射线检测操作态）
$swap = 0
$samples = @()
$cpus = @()
$end = (Get-Date).AddSeconds($Window)
while ((Get-Date) -lt $end) {
    if ($swap % 2 -eq 0) { [W32b]::mouse_event(2,0,0,0,[UIntPtr]::Zero); Start-Sleep -m 80; [W32b]::mouse_event(4,0,0,0,[UIntPtr]::Zero) }  # 左删
    else { [W32b]::mouse_event(8,0,0,0,[UIntPtr]::Zero); Start-Sleep -m 80; [W32b]::mouse_event(16,0,0,0,[UIntPtr]::Zero) }              # 右放
    $swap++
    $line = nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,temperature.gpu --format=csv,noheader,nounits 2>$null
    if ($line) { $samples += $line }
    $c = [math]::Round((Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue | Measure-Object -Property LoadPercentage -Average).Average, 0)
    if ($c -ge 0) { $cpus += $c }
    Start-Sleep 2
}

Write-Output "GPU-SAMPLES-INTERACTIVE:"
$samples | ForEach-Object { Write-Output "  $_" }
if ($samples.Count -gt 0) {
    $gpu = @($samples | ForEach-Object { [int]($_ -split ',')[0].Trim() })
    $mem = @($samples | ForEach-Object { [int]($_ -split ',')[2].Trim() })
    $avg = [math]::Round(($gpu | Measure-Object -Average).Average, 1)
    $max = ($gpu | Measure-Object -Maximum).Maximum
    $mavg = [math]::Round(($mem | Measure-Object -Average).Average, 0)
    $cavg = if ($cpus.Count) { [math]::Round(($cpus | Measure-Object -Average).Average, 0) } else { -1 }
    Write-Output "GPU-SUMMARY-INTERACTIVE avg=$avg% max=$max% vram_avg=${mavg}MB cpu_avg=${cavg}% n=$($samples.Count) ops=$swap"
}

if ($p.HasExited) { Write-Output "MC-EXITED-DURING code=$($p.ExitCode)" } else { Write-Output "MC-ALIVE-AT-END" }
Write-Output "OUT2-TAIL:"
Get-Content $out -Tail 6 -ErrorAction SilentlyContinue
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Output "BENCH2-DONE"
