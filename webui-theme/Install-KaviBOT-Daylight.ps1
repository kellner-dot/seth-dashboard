<#
  KaviBOT "Daylight" theme installer for Open WebUI (pip install on SETHS-PC).
  - Downloads kavibot-daylight.css from the kavibot repo (fresh copy, never stale)
  - Backs up the existing custom.css first (snapshot before change)
  - Installs the theme into the venv's open_webui/static/custom.css
  - Verifies the theme is actually being served (HTTP check for the marker)
  - Downloads kavibot-logo.png for the manual Admin logo upload step
  Run: paste the one-line bootstrap from chat into PowerShell.
  Rollback: copy the printed .bak file back over custom.css, then hard-refresh.
#>
$ErrorActionPreference = "Stop"

$themeDir = "C:\AI\webui-theme"
$repoBase = "https://raw.githubusercontent.com/kellner-dot/seth-dashboard/main/webui-theme"
$venv     = "C:\AI\venvs\webui"

Write-Output "=== KaviBOT Daylight theme installer ==="

# 1. theme dir + fresh CSS from repo
New-Item -ItemType Directory -Force -Path $themeDir | Out-Null
$cssLocal = Join-Path $themeDir "kavibot-daylight.css"
Write-Output "[1/5] Fetching fresh theme CSS from repo..."
Invoke-WebRequest -Uri "$repoBase/kavibot-daylight.css" -OutFile $cssLocal
$cssText = Get-Content $cssLocal -Raw
if ($cssText -notmatch "KAVIBOT-DAYLIGHT-v1") { throw "Downloaded CSS failed marker check — aborting." }
Write-Output "      OK: theme CSS fetched, marker verified."

# 2. locate the venv's static dir
Write-Output "[2/5] Locating Open WebUI static dir..."
$staticDir = Join-Path $venv "Lib\site-packages\open_webui\static"
if (-not (Test-Path $staticDir)) {
  $found = Get-ChildItem -Path $venv -Recurse -Directory -Filter "static" -ErrorAction SilentlyContinue |
           Where-Object { $_.FullName -like "*open_webui*" } | Select-Object -First 1
  if ($null -eq $found) { throw "Could not find open_webui static dir under $venv — aborting." }
  $staticDir = $found.FullName
}
Write-Output "      OK: $staticDir"

# 3. backup + install
Write-Output "[3/5] Installing theme (backup first)..."
$target = Join-Path $staticDir "custom.css"
if (Test-Path $target) {
  $bak = Join-Path $themeDir ("custom.css.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  Copy-Item $target $bak
  Write-Output "      Backup saved: $bak"
}
Copy-Item $cssLocal $target -Force
Write-Output "      Theme installed."

# 4. verify it is served
Write-Output "[4/5] Verifying the theme is served..."
Start-Sleep -Seconds 2
try {
  $served = (Invoke-WebRequest -Uri "http://127.0.0.1:3000/static/custom.css" -UseBasicParsing).Content
} catch {
  throw "Could not reach Open WebUI at 127.0.0.1:3000 — is it running? Aborting."
}
if ($served -match "KAVIBOT-DAYLIGHT-v1") {
  Write-Output "      OK: server is serving the Daylight theme."
} else {
  throw "Server responded but is NOT serving the new theme — check for a second WebUI install. Aborting."
}

# 5. logo asset for the manual admin step
Write-Output "[5/5] Fetching logo for the Admin upload step..."
$logoLocal = Join-Path $themeDir "kavibot-logo.png"
Invoke-WebRequest -Uri "$repoBase/kavibot-logo.png" -OutFile $logoLocal
Write-Output "      OK: $logoLocal"

Write-Output ""
Write-Output "=== DONE — scorecard ==="
Write-Output "  Theme file : installed + verified serving (KAVIBOT-DAYLIGHT-v1)"
Write-Output "  Backup     : snapshot saved in $themeDir"
Write-Output "  Inference  : untouched (llama.cpp / Qwen stack not modified)"
Write-Output ""
Write-Output "Finish in your browser (2 minutes):"
Write-Output "  1. Hard-refresh Open WebUI: Ctrl+Shift+R  (keep its LIGHT theme on)"
Write-Output "  2. Click your avatar -> Admin Panel -> Settings: upload"
Write-Output "     $logoLocal  as the logo"
Write-Output "  3. Send a test chat message to confirm everything works."
Write-Output ""
Write-Output "If anything looks off, screenshot it and Kavi tightens the CSS (v2)."
Write-Output "Rollback: copy the .bak file above back over custom.css, then Ctrl+Shift+R."
