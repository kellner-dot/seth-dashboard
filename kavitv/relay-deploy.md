# KaviTV Relay — Production Deployment

How the relay runs in production on Seth's PC (Windows, no AI required).

## What runs

- **Process:** `pythonw.exe relay.py` (no console window)
- **Port:** 8100 (all interfaces)
- **Working dir:** `C:\Users\sethr\kavitv\`
- **Python:** `C:\Users\sethr\AppData\Local\Programs\Python\Python312\pythonw.exe`
- **Config:** `C:\Users\sethr\kavitv\config\` (timeline.json, emby.key, schedules.json)

## Scheduled tasks (both as SYSTEM)

### KaviTV-relay
- **Trigger:** At system startup
- **Action:** Start pythonw with `C:\Users\sethr\kavitv\relay.py`
- **Purpose:** Ensures the relay starts on boot, no login required

### KaviTV Watchdog
- **Trigger:** Every 5 minutes
- **Action:** `powershell -ExecutionPolicy Bypass -File C:\Users\sethr\kavitv\kavitv-watchdog.ps1`
- **Purpose:** Health checks, auto-restart (max 3/hr), schedule refresh,
  disk monitoring, status.json + dashboard.html

## Manual operations

**Start the relay:**
```powershell
Start-ScheduledTask -TaskName "KaviTV-relay"
```

**Stop the relay:**
```powershell
Get-Process pythonw | Where-Object {
  (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -like "*relay.py*"
} | Stop-Process -Force
```

**Restart everything:**
```powershell
# Stop
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force
# Start (watchdog will also do this within 5 min if relay is down)
Start-ScheduledTask -TaskName "KaviTV-relay"
```

**Check health:**
```powershell
Invoke-RestMethod http://127.0.0.1:8100/api/deep-health | ConvertTo-Json -Depth 3
```

## Rollback

If v2.1 misbehaves, the pre-cutover relay is backed up at:
```
C:\Users\sethr\kavitv\relay.py.v010-live-20261005.bak
```
To roll back: stop the relay, copy the .bak over relay.py, start the relay.

## Logs

- `C:\Users\sethr\kavitv\logs\relay.log` — relay output
- `C:\Users\sethr\kavitv\logs\watchdog.log` — watchdog decisions
- `C:\Users\sethr\kavitv\logs\rclone-t.log` — T: mount (shared log dir)

## Dependencies

- Python 3.12 (stdlib only — no pip packages required for the relay)
- `tzdata` pip package (only for export_iptv.py, not the relay)
- ffmpeg in PATH (relay shells out to it per channel)
- Port 8100 free, Emby API key in `config/emby.key`
