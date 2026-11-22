param([string]$ScriptFile, [int]$Window = 60)
$ErrorActionPreference = 'Continue'
$deploy = 'D:\projects\Rust\pygame-rs\deploy'
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

$out = "$deploy\mc_ab.log"
$p = Start-Process -FilePath "$deploy\python.exe" `
    -ArgumentList $ScriptFile `
    -WorkingDirectory $deploy `
    -RedirectStandardOutput $out -RedirectStandardError "$deploy\mc_ab_err.log" `
    -PassThru
Start-Sleep 4
if ($p.HasExited) { Write-Output "EXITED-EARLY"; Get-Content "$deploy\mc_ab_err.log" -Tail 5; exit 1 }

$samples = @()
$end = (Get-Date).AddSeconds($Window)
Start-Sleep 10
while ((Get-Date) -lt $end) {
    $line = nvidia-smi --query-gpu=utilization.gpu,clocks.sm,power.draw --format=csv,noheader,nounits 2>$null
    if ($line) { $samples += $line }
    Start-Sleep -m 500
}
Stop-Process -Id $p.Id -Force -EA SilentlyContinue

$gpu = @($samples | ForEach-Object { [int]($_ -split ',')[0].Trim() })
$clk = @($samples | ForEach-Object { [int]($_ -split ',')[1].Trim() })
$avg = [math]::Round(($gpu | Measure-Object -Average).Average, 1)
$mn = ($gpu | Measure-Object -Minimum).Minimum
$mx = ($gpu | Measure-Object -Maximum).Maximum
$csd = if ($clk.Count -gt 1) { [math]::Round([math]::Sqrt((($clk | ForEach-Object { $_ * $_ } | Measure-Object -Sum).Sum - $clk.Count * [math]::Pow(($clk | Measure-Object -Average).Average, 2)) / ($clk.Count - 1)), 0) } else { 0 }
Write-Output "$ScriptFile GPU avg=$avg% min=$mn max=$mx clkStd=$csd raw=[$($gpu -join ',')]"
