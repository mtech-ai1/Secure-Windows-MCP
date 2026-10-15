# One-time hardening + autostart for Secure-Windows-MCP on the Rivhit VM.
# Run over SSH as the admin user. The auth token is read from a temp file, which is deleted
# immediately (never passed on the command line).
param([Parameter(Mandatory)][string]$TokenFile)
$ErrorActionPreference = 'Stop'
$root = 'C:\Tools\Secure-Windows-MCP'
$uv = "$env:USERPROFILE\.local\bin\uv.exe"

# 1. Auth token -> user environment (only this user and admins can read it)
$token = (Get-Content -Raw $TokenFile).Trim()
Remove-Item $TokenFile -Force
if ($token.Length -lt 32) { throw 'auth token file empty' }
[Environment]::SetEnvironmentVariable('WINDOWS_MCP_AUTH_KEY', $token, 'User')

# 2. Block ALL outbound traffic from the Python interpreters that run the server.
#    Loopback (the SSH tunnel) is not filtered by Windows Firewall, so MCP still works.
$base = (& "$root\.venv\Scripts\python.exe" -c "import sys; print(sys._base_executable)").Trim()
$pythons = @("$root\.venv\Scripts\python.exe", "$root\.venv\Scripts\pythonw.exe", $base,
             (Join-Path (Split-Path $base) 'pythonw.exe')) | Where-Object { Test-Path $_ } | Select-Object -Unique
Get-NetFirewallRule -DisplayName 'SWMCP block outbound*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
$i = 0
foreach ($p in $pythons) {
    $i++
    New-NetFirewallRule -DisplayName "SWMCP block outbound $i" -Direction Outbound -Action Block `
        -Program $p -Profile Any | Out-Null
}

# 3. Launcher: loopback only, token required, risky tools removed
@"
`$env:Path = '$env:USERPROFILE\.local\bin;' + `$env:Path
Set-Location '$root'
& '$uv' run --frozen --no-sync windows-mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 ``
    --exclude-tools Scrape,Registry,PowerShell,FileSystem *>> C:\Tools\swmcp.log
"@ | Set-Content C:\Tools\start-swmcp.ps1 -Encoding UTF8

# 4. Autostart inside the interactive desktop session at logon
$a = New-ScheduledTaskAction -Execute powershell.exe `
    -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\Tools\start-swmcp.ps1'
$t = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'Secure-Windows-MCP' -Action $a -Trigger $t -Principal $p -Settings $s -Force | Out-Null

# 5. "Disconnect, keep running": hand the RDP session to the console so the desktop keeps rendering
@'
$id = (Get-Process -Id $PID).SessionId
& tscon.exe $id /dest:console
'@ | Set-Content C:\Tools\keep-desktop.ps1 -Encoding UTF8
$a2 = New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\Tools\keep-desktop.ps1'
$p2 = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName 'Keep-Desktop-Running' -Action $a2 -Principal $p2 -Force | Out-Null
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$env:USERPROFILE\Desktop\Disconnect (keep running).lnk")
$lnk.TargetPath = 'C:\Windows\System32\schtasks.exe'
$lnk.Arguments = '/run /tn Keep-Desktop-Running'
$lnk.IconLocation = 'C:\Windows\System32\mstsc.exe,0'
$lnk.Save()

Get-NetFirewallRule -DisplayName 'SWMCP block outbound*' | Get-NetFirewallApplicationFilter | Select-Object Program
'setup-ok'
