<#
  KaviBOT "Daylight" theme installer for Open WebUI (pip install on SETHS-PC).
  v2: installs theme CSS + KaviBOT logo into the venv's static dir.
  - Downloads fresh copies from the public seth-dashboard repo
  - Backs up the existing custom.css first (snapshot before change)
  - Verifies both files are actually served (HTTP checks)
  - Prints a plain-language scorecard + rollback
  Run: paste the one-line bootstrap from chat into PowerShell.
  Rollback: copy the printed .bak file back over custom.css, delete
  kavibot-logo.png from the static dir, then hard-refresh.
  NOTE: this file must stay pure ASCII (PS 5.1 misreads BOM-less
  UTF-8 as ANSI). It is saved with a UTF-8 BOM.
#>
$ErrorActionPreference = "Stop"

$themeDir = "C:\AI\webui-theme"
$repoBase = "https://cdn.jsdelivr.net/gh/kellner-dot/seth-dashboard@7d015d2bdaa89ad94a500218553c2be63df641ac/webui-theme"
$venv     = "C:\AI\venvs\webui"

Write-Output "=== KaviBOT Daylight theme installer (v2) ==="

# 1. fresh files from repo
New-Item -ItemType Directory -Force -Path $themeDir | Out-Null
$cssLocal  = Join-Path $themeDir "kavibot-daylight.css"
$logoLocal = Join-Path $themeDir "kavibot-logo.png"
Write-Output "[1/6] Fetching fresh theme files from repo..."
Invoke-WebRequest -Uri "$repoBase/kavibot-daylight.css" -OutFile $cssLocal
Invoke-WebRequest -Uri "$repoBase/kavibot-logo.png" -OutFile $logoLocal
$cssText = Get-Content $cssLocal -Raw
if ($cssText -notmatch "KAVIBOT-DAYLIGHT-v3") { throw "CSS failed marker check - aborting." }
Write-Output "      OK: theme CSS (v2) + logo fetched."

# 2. locate the venv's static dir
Write-Output "[2/6] Locating Open WebUI static dir..."
$staticDir = Join-Path $venv "Lib\site-packages\open_webui\static"
if (-not (Test-Path $staticDir)) {
  $found = Get-ChildItem -Path $venv -Recurse -Directory -Filter "static" -ErrorAction SilentlyContinue |
           Where-Object { $_.FullName -like "*open_webui*" } | Select-Object -First 1
  if ($null -eq $found) { throw "Could not find open_webui static dir under $venv - aborting." }
  $staticDir = $found.FullName
}
Write-Output "      OK: $staticDir"

# 3. backup + install CSS
Write-Output "[3/6] Installing theme CSS (backup first)..."
$target = Join-Path $staticDir "custom.css"
if (Test-Path $target) {
  $bak = Join-Path $themeDir ("custom.css.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  Copy-Item $target $bak
  Write-Output "      Backup saved: $bak"
}
Copy-Item $cssLocal $target -Force
Write-Output "      Theme installed."

# 4. install logo
Write-Output "[4/6] Installing KaviBOT logo..."
Copy-Item $logoLocal (Join-Path $staticDir "kavibot-logo.png") -Force
Write-Output "      Logo installed."

# 5. verify both are served
Write-Output "[5/6] Verifying the theme is served..."
Start-Sleep -Seconds 2
try {
  $served = (Invoke-WebRequest -Uri "http://127.0.0.1:3000/static/custom.css" -UseBasicParsing).Content
  $logo   = Invoke-WebRequest -Uri "http://127.0.0.1:3000/static/kavibot-logo.png" -UseBasicParsing
} catch {
  throw "Could not reach Open WebUI at 127.0.0.1:3000 - is it running? Aborting."
}
if ($served -match "KAVIBOT-DAYLIGHT-v3") {
  Write-Output "      OK: server is serving the Daylight v2 theme."
} else {
  throw "Server responded but is NOT serving the new theme - aborting."
}
if ($logo.StatusCode -eq 200) {
  Write-Output "      OK: server is serving the KaviBOT logo."
} else {
  throw "Logo did not serve correctly - aborting."
}

Write-Output "[6/6] Done."
Write-Output ""
Write-Output "=== DONE - scorecard ==="
Write-Output "  Theme  : Daylight v2 installed + verified serving"
Write-Output "  Logo   : KaviBOT mark installed + verified serving"
Write-Output "  Backup : snapshot saved in $themeDir"
Write-Output "  Inference: untouched (llama.cpp / Qwen stack not modified)"
Write-Output ""
Write-Output "Finish in your browser (1 minute):"
Write-Output "  1. Hard-refresh Open WebUI: Ctrl+Shift+R (keep its LIGHT theme on)"
Write-Output "  2. Look at the sidebar: KaviBOT logo + name, indigo send button."
Write-Output "  3. Send a test chat message to confirm everything works."
Write-Output ""
Write-Output "Screenshot it and Kavi compares against the concept picture."
Write-Output "Rollback: copy the .bak file above back over custom.css, delete"
Write-Output "kavibot-logo.png from the static dir, then Ctrl+Shift+R."
