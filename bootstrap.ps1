param([switch]$Capture, [switch]$Download, [switch]$Remotion)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Install Python 3.11+ from python.org, then rerun.' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'Install FFmpeg: winget install --id Gyan.FFmpeg -e. Open a new terminal, then rerun.' }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22+: winget install --id OpenJS.NodeJS.LTS -e. Open a new terminal, then rerun.' }
function Invoke-Checked {
    param([scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE)" }
}
Invoke-Checked { python -m venv .venv }
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
Invoke-Checked { & $py -m pip install --upgrade pip }
$extras = @('video-use')
if ($Capture) { $extras += 'capture' }
if ($Download) { $extras += 'download' }
$spec = '.[' + ($extras -join ',') + ']'
Invoke-Checked { & $py -m pip install -e $spec }
Invoke-Checked { npm.cmd ci }
if ($Capture) { Invoke-Checked { & $py -m playwright install chromium } }
if ($Remotion) {
    Push-Location (Join-Path $PSScriptRoot 'examples\remotion')
    try { Invoke-Checked { npm.cmd ci } } finally { Pop-Location }
}
Invoke-Checked { & $py toolkit.py doctor }
Write-Host 'Ready. Try: .\.venv\Scripts\python.exe toolkit.py demo --graphics'
