# install-voice-relay.ps1 -- one-paste installer for the KaviBOT voice reverse-tunnel relay (PC side).
#
# Run in an ELEVATED PowerShell (Run as Administrator). The one-paste snippet
# downloads this file plus voice-relay.py and rollback-voice-relay.ps1 from a
# pinned jsDelivr commit, then runs this script.
#
# What it does:
#   1. Verifies admin, python, tailscale.
#   2. Installs C:\AI\voice-relay\voice-relay.py (+ rollback script).
#   3. Creates scheduled task "KaviVoiceRelay" (SYSTEM, at startup, auto-restart).
#   4. Starts the relay and checks http://127.0.0.1:8092/relay/health.
#   5. Points tailscale serve https://<pc>:8443 at the relay (--bg = survives reboot).
#   6. Prints a plain-language scorecard.
#
# It never touches port 8899 or any existing serve mapping except 8443.
# Rollback: run C:\AI\voice-relay\rollback-voice-relay.ps1
#
# Pure ASCII (PS 5.1 safe).

param(
    [string]$RelayPath = "",
    [string]$RollbackPath = ""
)

$ErrorActionPreference = "Stop"
$Dir = "C:\AI\voice-relay"
$TaskName = "KaviVoiceRelay"
$Pass = 0; $Fail = 0
function Step($name, $ok, $detail) {
    if ($ok) { $script:Pass++; Write-Host ("[PASS] " + $name) -ForegroundColor Green }
    else { $script:Fail++; Write-Host ("[FAIL] " + $name + " -- " + $detail) -ForegroundColor Red }
    if ($detail -and $ok) { Write-Host ("       " + $detail) -ForegroundColor Gray }
}

Write-Host ""
Write-Host "KaviBOT voice relay installer" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

# 1. admin check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Step "Running as Administrator" $isAdmin "needed for the scheduled task and tailscale serve"
if (-not $isAdmin) { Write-Host "ABORTED: re-run PowerShell as Administrator, then paste again." -ForegroundColor Red; exit 1 }

# 2. source files present
$haveRelay = ($RelayPath -ne "") -and (Test-Path $RelayPath)
$haveRollback = ($RollbackPath -ne "") -and (Test-Path $RollbackPath)
Step "Relay source downloaded" $haveRelay $RelayPath
Step "Rollback script downloaded" $haveRollback $RollbackPath
if (-not ($haveRelay -and $haveRollback)) { Write-Host "ABORTED: missing source files." -ForegroundColor Red; exit 1 }

# 3. python
$py = $null
foreach ($c in @("python", "py")) {
    try { $v = & $c --version 2>&1; if ($LASTEXITCODE -eq 0) { $py = $c; break } } catch {}
}
if ($c -eq "py" -and $py) { $pyArgs = @("-3") } else { $pyArgs = @() }
Step "Python available" ($py -ne $null) $(if ($py) { (& $py @pyArgs --version 2>&1) } else { "install Python 3 first" })
if (-not $py) { Write-Host "ABORTED: Python 3 not found on PATH." -ForegroundColor Red; exit 1 }
$pyw = $py; if ($py -eq "python") { $pyw = "pythonw" }

# 4. tailscale
$ts = $null
try { & tailscale version 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { $ts = $true } } catch {}
Step "Tailscale CLI available" ($ts -eq $true) "needed for tailscale serve"
if (-not $ts) { Write-Host "ABORTED: tailscale not on PATH." -ForegroundColor Red; exit 1 }

# 5. install files
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
Copy-Item $RelayPath (Join-Path $Dir "voice-relay.py") -Force
Copy-Item $RollbackPath (Join-Path $Dir "rollback-voice-relay.ps1") -Force
& $py @pyArgs -m py_compile (Join-Path $Dir "voice-relay.py")
Step "Relay installed to $Dir" ($LASTEXITCODE -eq 0) "voice-relay.py compiles clean"

# 6. scheduled task (SYSTEM, at startup, restart on failure)
try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    $action = New-ScheduledTaskAction -Execute $pyw -Argument "`"$Dir\voice-relay.py`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 6
    $task = Get-ScheduledTask -TaskName $TaskName
    Step "Scheduled task KaviVoiceRelay" ($task.State -ne "Disabled") ("state: " + $task.State)
} catch {
    Step "Scheduled task KaviVoiceRelay" $false $_.Exception.Message
}

# 7. relay health (loopback)
$healthy = $false
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8092/relay/health" -TimeoutSec 10
    $healthy = ($h.ok -eq $true)
} catch { $healthy = $false }
Step "Relay answering on 127.0.0.1:8092" $healthy "GET /relay/health"

# 8. tailscale serve --https=8443 -> relay (--bg survives reboot)
$before = ""
try { $before = (tailscale serve status 2>&1 | Out-String) } catch {}
$had8443 = $before -match "8443"
tailscale serve --bg --https=8443 http://127.0.0.1:8092 2>&1 | Out-Null
Start-Sleep -Seconds 3
$after = ""
try { $after = (tailscale serve status 2>&1 | Out-String) } catch {}
$serveOk = $after -match "8443" -and ($after -match "8092")
Step "Tailscale serve :8443 -> relay" $serveOk $(if ($had8443) { "replaced the previous 8443 mapping" } else { "new 8443 mapping" })

# 9. scorecard
Write-Host ""
Write-Host "---------------- SCOREBOARD ----------------" -ForegroundColor Cyan
Write-Host ("PASS: " + $Pass + "   FAIL: " + $Fail)
if ($Fail -eq 0) {
    Write-Host ""
    Write-Host "Voice relay is LIVE." -ForegroundColor Green
    Write-Host "iPhone URL (Safari, Tailscale connected):"
    Write-Host "  https://seths-pc.tail1cffd9.ts.net:8443/v1/voice/" -ForegroundColor Yellow
    Write-Host "The VM poller pairs automatically within a minute; no API key needed on the phone."
} else {
    Write-Host ""
    Write-Host "Something failed -- see [FAIL] lines above. The relay may be partially installed." -ForegroundColor Red
}
Write-Host ""
Write-Host "Notes:"
Write-Host "  - Port 8899 was not touched."
Write-Host "  - Old Ctrl+C serve mapping on 8443 (if any) was replaced by this one."
Write-Host "  - Rollback any time: powershell -File C:\AI\voice-relay\rollback-voice-relay.ps1"
Write-Host "  - Relay log: C:\AI\voice-relay\relay.log"
Write-Host "--------------------------------------------"
if ($Fail -gt 0) { exit 1 }
