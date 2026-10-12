# KaviBOT PC-side mailbox lister
# Run this on SETHS-PC to list the kavi-mail folder and save results
# where KaviBOT can read them. Workaround for sandbox RVG credential block.
# One-paste: copy the entire script block below into PowerShell.

$mailDir = "C:\Users\sethr\kavi-mail"
$outFile = Join-Path $mailDir ("pc-listing-" + (Get-Date -Format "yyyyMMdd-HHmm") + ".md")

"Listing files in $mailDir..."

$files = Get-ChildItem -LiteralPath $mailDir -File | Sort-Object LastWriteTime -Descending |
    Select-Object Name, @{N="SizeKB";E={[math]::Round($_.Length/1KB,1)}},
        @{N="Modified";E={$_.LastWriteTime.ToString("yyyy-MM-dd HH:mm")}}

$lines = @()
$lines += "# PC kavi-mail listing"
$lines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$lines += "Path: $mailDir"
$lines += ""
$lines += "| File | Size KB | Modified |"
$lines += "|------|---------|----------|"
foreach ($f in $files) {
    $lines += "| $($f.Name) | $($f.SizeKB) | $($f.Modified) |"
}
$lines += ""
$lines += "Total: $($files.Count) files"

$lines | Out-File -LiteralPath $outFile -Encoding UTF8

"Done. Wrote $($files.Count) files to:"
$outFile
""
"KaviBOT can now read this file from the kavi-mail folder."
