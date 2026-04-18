# ATLAST ECP one-line installer (Windows PowerShell).
#
# Usage:
#   irm https://weba0.com/install.ps1 | iex
#   irm https://weba0.com/install.ps1 | iex -ArgumentList '--proxy'
#
# Works across:
#   - Windows + python.org Python
#   - Windows + Microsoft Store Python
#   - Windows + conda / venv / pyenv-win
#
# Exit codes: 0 = installed, 1 = no Python, 2 = install failed.

[CmdletBinding()]
param(
    [switch]$Proxy,
    [switch]$All,
    [switch]$Upgrade,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

$extras = ''
if ($Proxy) { $extras = '[proxy]' }
if ($All)   { $extras = '[all]' }
$upgradeFlag = if ($Upgrade) { '--upgrade' } else { '' }

function Log  { if (-not $Quiet) { Write-Host "  $($args -join ' ')" } }
function Bold { if (-not $Quiet) { Write-Host -ForegroundColor Cyan $args[0] } }
function Err  { Write-Error ($args -join ' ') }

Bold "ATLAST ECP installer (Windows)"

# ── 1. Locate Python 3.9+ ─────────────────────────────────────────────────
$py = $null
foreach ($cand in @('python', 'python3', 'py')) {
    try {
        $verStr = & $cand -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>$null
        if ($LASTEXITCODE -eq 0 -and $verStr) {
            $parts = $verStr.Trim().Split('.')
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 9) {
                $py = $cand
                Log "Python: $cand (v$($verStr.Trim()))"
                break
            }
        }
    } catch { }
}

if (-not $py) {
    Err "Python 3.9 or newer is required. Install from https://www.python.org/downloads/"
    exit 1
}

# ── 2. Determine install strategy ─────────────────────────────────────────
$inVenv = & $py -c 'import sys; print("1" if sys.prefix != sys.base_prefix else "0")'
$pkg = "atlast-ecp$extras"

function Try-Install {
    param([string]$tag, [string[]]$extraArgs)
    Log "Trying: $tag"
    $cmd = @('-m', 'pip', 'install', '--disable-pip-version-check')
    if ($upgradeFlag) { $cmd += $upgradeFlag }
    $cmd += $extraArgs
    $cmd += $pkg
    & $py @cmd 2>&1 | Tee-Object -Variable output | Out-Null
    return $LASTEXITCODE -eq 0
}

$installed = $false
if ($inVenv.Trim() -eq '1') {
    Log "Detected active virtual environment — installing into it."
    $installed = Try-Install 'venv install' @()
} else {
    $installed = Try-Install 'user install (--user)' @('--user')
    if (-not $installed) {
        $installed = Try-Install 'user install (--user --break-system-packages)' @('--user', '--break-system-packages')
    }
}

if (-not $installed) {
    Err "Could not install atlast-ecp."
    Err "Workarounds:"
    Err "  - Create a venv:   python -m venv %USERPROFILE%\.atlast-venv ; %USERPROFILE%\.atlast-venv\Scripts\Activate.ps1 ; pip install atlast-ecp"
    Err "  - Or use pipx:     pipx install atlast-ecp"
    exit 2
}

# ── 3. Verify ─────────────────────────────────────────────────────────────
$ver = & $py -c 'import atlast_ecp; print(atlast_ecp.__version__)' 2>$null
if ($LASTEXITCODE -ne 0) {
    Err "Installed but 'import atlast_ecp' failed."
    exit 2
}
Log "Version: atlast-ecp $($ver.Trim())"

if (-not $Quiet) {
    Write-Host ""
    Bold "Next steps"
    Write-Host "  atlast init       # create identity + wire Claude Code hooks"
    Write-Host "  atlast dashboard  # open the evidence dashboard"
    Write-Host "  atlast --help     # see all commands"
}
