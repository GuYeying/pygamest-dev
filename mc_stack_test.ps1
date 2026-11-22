param([string]$Log = "D:\Projects\Rust\pygame-rs-dev\mc_run39.log")
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1
Start-Process -FilePath 'D:\Projects\Rust\pygame-rs-dev\target\debug\python.exe' `
    -ArgumentList 'D:\Projects\Rust\pygame-rs-dev\examples\voxel_mc_test.py' `
    -WorkingDirectory 'D:\Projects\Rust\pygame-rs-dev' `
    -RedirectStandardOutput $Log -RedirectStandardError 'D:\Projects\Rust\pygame-rs-dev\mc_err39.log'
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
[System.Windows.Forms.SendKeys]::SendWait('{TAB}')   # grab 态（用户已拆拖拽转向）
Start-Sleep 1
# 俯视对准地面
for ($i = 0; $i -lt 5; $i++) { [W32]::mouse_event(1, 0, 25, 0, [UIntPtr]::Zero); Start-Sleep -m 60 }
Start-Sleep 1
# 竖直堆叠：右键×6（每次命中新块顶面 = 向上堆）
for ($i = 0; $i -lt 6; $i++) {
    [W32]::mouse_event(8,0,0,0,[UIntPtr]::Zero); Start-Sleep -m 120
    [W32]::mouse_event(16,0,0,0,[UIntPtr]::Zero)
    Start-Sleep 400
}
powershell.exe -File 'D:\Projects\Rust\pygame-rs-dev\shot_pw.ps1' -Title 'x' -Out 'D:\Projects\Rust\pygame-rs-dev\mc_stack.png'
# 逐个移除：左键×6
for ($i = 0; $i -lt 6; $i++) {
    [W32]::mouse_event(2,0,0,0,[UIntPtr]::Zero); Start-Sleep -m 120
    [W32]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
    Start-Sleep 400
}
powershell.exe -File 'D:\Projects\Rust\pygame-rs-dev\shot_pw.ps1' -Title 'x' -Out 'D:\Projects\Rust\pygame-rs-dev\mc_removed.png'
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Output 'REPRO_DONE'
