param([string]$OutDir = "D:\projects\Rust\pygame-rs\deploy")
$ErrorActionPreference = 'Continue'
$deploy = 'D:\projects\Rust\pygame-rs\deploy'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Snap([string]$path) {
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen(0, 0, 0, 0, $bmp.Size)
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Write-Output "SAVED $path"
}

Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

$p = Start-Process -FilePath "$deploy\python.exe" `
    -ArgumentList "$deploy\voxel_mc_test.py" `
    -WorkingDirectory $deploy `
    -PassThru
Start-Sleep 6

# 阶段 1：tick + 时钟锁 1200（锁频态）
nvidia-smi -lgc 1200,1200 | Out-Null
Start-Sleep 6
Snap "$OutDir\shot1_locked.png"
Write-Output "STAGE1: nvidia-smi =" (nvidia-smi --query-gpu=utilization.gpu,clocks.sm --format=csv,noheader)

# 阶段 2：解锁时钟（DVFS 态——假象可视化）
nvidia-smi -rgc | Out-Null
Start-Sleep 10
Snap "$OutDir\shot2_dvfs.png"
Write-Output "STAGE2: nvidia-smi =" (nvidia-smi --query-gpu=utilization.gpu,clocks.sm --format=csv,noheader)

# 阶段 3：锁回
nvidia-smi -lgc 1200,1200 | Out-Null
Start-Sleep 8
Snap "$OutDir\shot3_relocked.png"
Write-Output "STAGE3: nvidia-smi =" (nvidia-smi --query-gpu=utilization.gpu,clocks.sm --format=csv,noheader)

Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Write-Output "SHOTS-DONE"
