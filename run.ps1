# The Artificial Chaperone -- PowerShell runner
# Usage:
#   .\run.ps1 -Validate            # check stimuli/config, no API calls
#   .\run.ps1 -DryRun              # show planned calls, no API calls
#   .\run.ps1 -Pilot               # 208 calls (2/cell)
#   .\run.ps1                      # full run: 5,200 calls (50/cell)
#   .\run.ps1 -Provider anthropic  # single provider
#
# If scripts are blocked:  powershell -ExecutionPolicy Bypass -File .\run.ps1

param(
    [switch]$Pilot,
    [switch]$DryRun,
    [switch]$Validate,
    [ValidateSet("", "anthropic", "openai")][string]$Provider = "",
    [string]$Config = "config.json"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- find Python ---
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { $pythonCmd = Get-Command py -ErrorAction SilentlyContinue }
if (-not $pythonCmd) {
    Write-Error "Python not found on PATH. Install Python 3.9+ from python.org (check 'Add python.exe to PATH')."
    exit 1
}

# --- create venv on first run ---
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment (.venv)..."
    & $pythonCmd.Source -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Error "venv creation failed."; exit 1 }
}

Write-Host "Installing dependencies..."
& $venvPython -m pip install --quiet --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed."; exit 1 }

# --- build args and run ---
$pyArgs = @("run_experiment.py", "--config", $Config)
if ($Pilot)    { $pyArgs += "--pilot" }
if ($DryRun)   { $pyArgs += "--dry-run" }
if ($Validate) { $pyArgs += "--validate" }
if ($Provider) { $pyArgs += @("--provider", $Provider) }

& $venvPython @pyArgs
exit $LASTEXITCODE
