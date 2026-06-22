# install.ps1 - one-time setup helper for agency-memory-kit (Windows / PowerShell).
# Safe to re-run (idempotent). Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# What this does:
#   1. Finds (or offers to install, via winget) Python 3.
#   2. Tells you the EXACT command to type into the Claude Code plugin config
#      prompt ("Python command") when you install the plugin.
#   3. Checks the optional anthropic package (only the weekly consolidate.py needs it).
#   4. Prints the remaining setup steps.
#
# Verified on real Windows (Win10/cp1250, Python 3.13, py launcher). Still unverified:
# the winget INSTALL path (the test used a python.org install), and detection on a box
# where Python is reachable only as 'python'/'python3' with no 'py' launcher.
#
# The hooks are NOT wired here - they ship inside the plugin
# (plugins\agency-memory\hooks\hooks.json) and activate when you install the
# plugin in Claude Code.

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

Write-Host "agency-memory-kit setup (Windows)"
Write-Host "---------------------------------"

# --- 1. Find a working Python 3 -------------------------------------------------
# Returns the command string ('python' / 'python3' / 'py -3') that runs Python 3.x,
# or $null. We probe by running it; the version check guards against the Windows
# "python" stub that opens the Store.
function Find-Python {
    foreach ($cmd in @("python", "python3", "py -3")) {
        try {
            $parts = $cmd.Split(" ")
            $exe = $parts[0]
            # PowerShell: $parts[1..0] is a DESCENDING range for a single-token command,
            # which wrongly returns the command name. Guard for the single-token case.
            $rest = if ($parts.Length -gt 1) { $parts[1..($parts.Length - 1)] } else { @() }
            $ver = & $exe @rest -c "import sys; print(sys.version_info[0])" 2>$null
            if ($ver -eq "3") { return $cmd }
        } catch { }
    }
    return $null
}

$PyCmd = Find-Python

if (-not $PyCmd) {
    Write-Host "[!!] No Python 3 found on this machine."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host ""
        Write-Host "I can install Python 3 with:"
        Write-Host "    winget install -e --id Python.Python.3.13"
        $answer = Read-Host "Run it now? [y/N]"
        if ($answer -match "^(y|yes)$") {
            winget install -e --id Python.Python.3.13
            Write-Host ""
            Write-Host "Install ran. Close this window, open a NEW PowerShell, and re-run this script"
            Write-Host "(a fresh shell is needed so the new Python lands on your PATH)."
            exit 0
        } else {
            Write-Host "Skipped. Install Python 3 yourself, then re-run this script."
            exit 1
        }
    } else {
        Write-Host ""
        Write-Host "winget is not available. Install Python 3 from https://www.python.org/downloads/"
        Write-Host "(tick 'Add python.exe to PATH' in the installer), then re-run this script."
        exit 1
    }
}

# $PyCmd may be multi-token ("py -3"); split into exe + arg array once and reuse below.
$parts = $PyCmd.Split(" ")
$exe = $parts[0]
$rest = if ($parts.Length -gt 1) { $parts[1..($parts.Length - 1)] } else { @() }
$verStr = & $exe @rest --version 2>&1
Write-Host "[ok] Python 3 found:  $PyCmd  ($verStr)"

# --- 2. The value to enter in the plugin config --------------------------------
Write-Host ""
Write-Host ">>> When Claude Code asks for the `"Python command`" during plugin install,"
Write-Host ">>> enter exactly:   $PyCmd"
Write-Host ""

# --- 3. anthropic package (only the weekly consolidate.py needs it) ------------
# reuses $exe / $rest computed above
& $exe @rest -c "import anthropic" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[ok] anthropic package found (consolidate.py ready)"
} else {
    Write-Host "[--] anthropic package not installed. Only needed for weekly consolidate.py."
    Write-Host "     Install when you want weekly consolidation:  $PyCmd -m pip install anthropic"
}

# --- 4. API key for consolidate.py ---------------------------------------------
if ($env:ANTHROPIC_API_KEY) {
    Write-Host "[ok] ANTHROPIC_API_KEY is set in this shell"
} else {
    Write-Host "[--] ANTHROPIC_API_KEY not set. consolidate.py (weekly) needs it."
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1) Install the plugin in Claude Code:"
Write-Host "       /plugin marketplace add $Root"
Write-Host "       /plugin install agency-memory@agency-memory-kit"
Write-Host "     When asked for the Python command, enter:   $PyCmd"
Write-Host ""
Write-Host "  2) Set up a world (your data root) - or use this repo root as one:"
Write-Host "       Copy-Item -Recurse plugins\agency-memory\templates\world\* C:\path\to\my-world\"
Write-Host "     Then run Claude Code from your world folder."
Write-Host ""
Write-Host "  3) (Optional) Localize: copy system\memory\world.json.example to world.json and edit."
Write-Host ""
Write-Host "  4) Create your first client: copy the client template into your world's clients\ folder:"
Write-Host "       Copy-Item -Recurse plugins\agency-memory\templates\client C:\path\to\my-world\clients\acme-corp"
Write-Host ""
Write-Host "Weekly consolidation (optional but recommended):"
Write-Host "  consolidate.py calls the Claude API, so it needs ANTHROPIC_API_KEY."
Write-Host "  Set it (and your world root) as user vars so a scheduled task sees them:"
Write-Host "    setx ANTHROPIC_API_KEY `"sk-ant-...`""
Write-Host "    setx AGENCY_WORLD_ROOT `"C:\path\to\my-world`""
Write-Host ""
Write-Host "  Run it once, then schedule run-weekly.ps1 (see its header for the schtasks line):"
Write-Host "    `$env:AGENCY_WORLD_ROOT=`"C:\path\to\my-world`"; .\plugins\agency-memory\runners\run-weekly.ps1"
