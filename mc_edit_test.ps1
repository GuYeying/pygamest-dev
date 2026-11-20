param([string]$Out = "D:\Projects\Rust\pygame-rs-dev\mc_run28.log")
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1
$env:STARFISH_FB_BMP = 'D:\Projects\Rust\pygame-rs-dev\mc_truth.bmp'
Start-Process -FilePath 'D:\Projects\Rust\pygame-rs-dev\target\debug\python.exe' `
    -ArgumentList 'D:\Projects\Rust\pygame-rs-dev\examples\voxel_mc_test.py' `
    -WorkingDirectory 'D:\Projects\Rust\pygame-rs-dev' `
    -RedirectStandardOutput $Out -RedirectStandardError 'D:\Projects\Rust\pygame-rs-dev\mc_err28.log'
Start-Sleep 9
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class W32 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
}
'@
$p = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if ($null -eq $p) { Write-Output 'NO_WINDOW'; exit 1 }
[W32]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep 1
# 俯视（准星对准地面）
for ($i = 0; $i -lt 6; $i++) { [W32]::mouse_event(1, 0, 30, 0, [UIntPtr]::Zero); Start-Sleep -m 60 }
Start-Sleep 1
# 删前 BMP 快照
Copy-Item 'D:\Projects\Rust\pygame-rs-dev\mc_truth.bmp' 'D:\Projects\Rust\pygame-rs-dev\mc_before.bmp' -Force
# 左键删
[W32]::mouse_event(2,0,0,0,[UIntPtr]::Zero); Start-Sleep -m 100; [W32]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
Start-Sleep 2
# 右键放
[W32]::mouse_event(8,0,0,0,[UIntPtr]::Zero); Start-Sleep -m 100; [W32]::mouse_event(16,0,0,0,[UIntPtr]::Zero)
Start-Sleep 2
# 删后 BMP 快照
Copy-Item 'D:\Projects\Rust\pygame-rs-dev\mc_truth.bmp' 'D:\Projects\Rust\pygame-rs-dev\mc_after.bmp' -Force
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Output 'TEST_DONE'
