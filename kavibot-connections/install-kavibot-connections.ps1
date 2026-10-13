<#
KaviBOT connections layer - one-paste installer (STAGING).
Run on SETHS-PC. Downloads the staging drop from the public
kellner-dot/seth-dashboard mirror (jsDelivr, pinned commit SHA) into
C:\AI\connections. Verifies every file landed and the test suite passes.

STAGING ONLY: installs the code; does not touch phase2/releases, does not
restart any service. Production wiring needs Seth's separate approval.

The deploying agent MUST mirror the staging files to seth-dashboard first,
then fill in the -Sha parameter below. The script refuses to run with the
placeholder.
#>
param(
    [string]$Sha = "41c1dcb6bbcfe214e33354474cb01a29a33a7fb2"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ($Sha -eq "MIRRORED_SHA_PLACEHOLDER" -or [string]::IsNullOrWhiteSpace($Sha)) {
    Write-Host "ERROR: commit SHA not set."
    Write-Host "The deploying agent must mirror staging/connections to"
    Write-Host "kellner-dot/seth-dashboard, then re-run with -Sha <commit>."
    exit 1
}

$Base = "https://cdn.jsdelivr.net/gh/kellner-dot/seth-dashboard@$Sha/kavibot-connections"
$Dest = "C:\AI\connections"
$Files = @(
    "DESIGN.md",
    "connections.json",
    "connection.py",
    "oauth2.py",
    "secret_store.py",
    "gcal.py",
    "gmail.py",
    "drive.py",
    "apple_music.py",
    "manager.py",
    "kavibot-connect.py",
    "tests/__init__.py",
    "tests/test_connections.py"
)

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
New-Item -ItemType Directory -Force -Path "$Dest\tests" | Out-Null
New-Item -ItemType Directory -Force -Path "$Dest\profiles" | Out-Null

$failed = @()
foreach ($f in $Files) {
    $url = "$Base/$f"
    $out = Join-Path $Dest ($f -replace "/", "\")
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
        $size = (Get-Item $out).Length
        if ($size -lt 100) { throw "suspiciously small ($size bytes)" }
        Write-Host "OK  $f ($size bytes)"
    } catch {
        Write-Host "FAIL $f : $_"
        $failed += $f
    }
}

if ($failed.Count -gt 0) {
    Write-Host "ERROR: $($failed.Count) file(s) failed to download."
    exit 1
}

# Syntax-check every Python file, then run the mocked test suite.
$py = "python"
try { & $py --version | Out-Null } catch {
    Write-Host "ERROR: python not found on PATH."
    exit 1
}

Push-Location $Dest
try {
    & $py kavibot-connect.py selftest
    if ($LASTEXITCODE -ne 0) { throw "selftest failed" }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "CONNECTIONS STAGING INSTALLED at $Dest"
Write-Host "Next (Seth):"
Write-Host "  1. python C:\AI\connections\kavibot-connect.py connect gcal"
Write-Host "     (browser opens - approve, then you're connected)"
Write-Host "  2. python C:\AI\connections\kavibot-connect.py import apple_music C:\path\to\Library.xml"
Write-Host "  3. python C:\AI\connections\kavibot-connect.py call gcal list_events"
Write-Host "Done."
