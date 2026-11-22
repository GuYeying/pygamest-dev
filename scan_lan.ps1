$alive = @()
$jobs = @()
foreach ($i in 1..254) {
    $ip = "192.168.1.$i"
    $jobs += Start-Job -ScriptBlock { param($ip) Test-Connection -ComputerName $ip -Count 1 -TimeoutSeconds 1 -Quiet -ErrorAction SilentlyContinue; if ($?) { $ip } } -ArgumentList $ip
}
$jobs | Wait-Job -Timeout 30 | Out-Null
foreach ($j in $jobs) {
    $r = Receive-Job $j -ErrorAction SilentlyContinue
    if ($r -and $r -match '^192\.') { $alive += $r }
    Remove-Job $j -Force -ErrorAction SilentlyContinue
}
Write-Output "ALIVE: $($alive -join ', ')"
