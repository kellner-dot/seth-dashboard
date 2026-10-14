# rollback-voice-relay.ps1 -- removes the KaviBOT voice reverse-tunnel relay (PC side).
#
# Run in an ELEVATED PowerShell. Does:
#   1. tailscale serve --https=8443 off   (removes ONLY the 8443 mapping; other
#      serve entries like the viewer on 443 are left alone)
#   2. Stops + unregisters the KaviVoiceRelay scheduled task
#   3. Kills any running voice-relay.py process
# Keeps C:\AI\voice-relay\ files and logs for forensics; delete the folder
# manually for full removal.
#
# Pure ASCII (PS 5.1 safe).

$ErrorActionPreference = "Continue"
$Dir = "C:\AI\voice-relay"
$TaskName = "KaviVoiceRelay"

Write-Host ""
Write-Host "KaviBOT voice relay rollback" -ForegroundColor Cyan
Write-Host "============================" -ForegroundColor Cyan

Write-Host "[1/3] Removing tailscale serve mapping for :8443 (only this port)..."
try {
    tailscale serve --https=8443 off 2>&1 | Out-Null
    Write-Host "      done (other serve entries untouched)"
} catch { Write-Host ("      tailscale call failed: " + $_.Exception.Message) }

Write-Host "[2/3] Removing scheduled task $TaskName ..."
try {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "      done"
} catch { Write-Host ("      " + $_.Exception.Message) }

Write-Host "[3/3] Stopping relay process..."
try {
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*voice-relay.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ("      stopped PID " + $_.ProcessId) }
    Write-Host "      done"
} catch { Write-Host ("      " + $_.Exception.Message) }

Write-Host ""
Write-Host "Rollback complete." -ForegroundColor Green
Write-Host "Files kept at $Dir (relay.log, relay-pin.txt) -- delete the folder manually for full removal."
Write-Host "To re-install, re-run the one-paste installer."
