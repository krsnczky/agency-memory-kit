# run-weekly.ps1
# Windows (PowerShell) wrapper for the weekly consolidation. Parallels run-weekly.sh.
# Run by Task Scheduler or manually.
#
# Required:
#   AGENCY_WORLD_ROOT - your world root (clients\ + system\). Set once as a USER var so a
#                       scheduled task sees it:  setx AGENCY_WORLD_ROOT "C:\path\to\your-world"
#                       (then reopen the shell).
#   ANTHROPIC_API_KEY - consolidate.py reads it. If it is NOT set in the environment, this
#                       script reads it from a key file (parity with run-weekly.sh):
#                         <world>\.anthropic.env   or   %USERPROFILE%\.anthropic.env
#                       a line like:  export ANTHROPIC_API_KEY=sk-ant-...   (or without 'export')
#                       Using a key file (not setx) keeps the key out of the registry.
#   AGENCY_PYTHON     - (optional) the Python command for the scheduled run, e.g. "py -3",
#                       "python", or "python3". If unset, the script auto-detects (prefers
#                       'py -3' to dodge the Microsoft Store alias stub).
#
# Manual run:
#   $env:AGENCY_WORLD_ROOT="C:\path\to\world"; .\run-weekly.ps1
#
# Schedule it (PowerShell, Mondays 10:00, with launchd-style catch-up for missed runs):
#   $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
#     -Argument '-ExecutionPolicy Bypass -NoProfile -File "C:\path\to\runners\run-weekly.ps1"'
#   $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 10:00am
#   $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable   # runs a missed job on next wake
#   Register-ScheduledTask -TaskName "AgencyMemoryConsolidate" `
#     -Action $action -Trigger $trigger -Settings $settings -Force
# (schtasks.exe cannot set the catch-up flag; the PowerShell cmdlets above can.)

$ErrorActionPreference = "Stop"

# UTF-8 insurance: forces child Python to UTF-8 stdout on non-UTF-8 locales (e.g. cp1250).
$env:PYTHONUTF8 = "1"

# This script lives in <plugin>\runners\ ; go up one to the plugin root.
$PluginDir = Split-Path -Parent $PSScriptRoot
$World = $env:AGENCY_WORLD_ROOT
if (-not $World) {
    throw "Set AGENCY_WORLD_ROOT to your world root (clients\ + system\)"
}

# API key: if not in the environment, read it from a key file (parity with run-weekly.sh).
if (-not $env:ANTHROPIC_API_KEY) {
    foreach ($f in @("$World\.anthropic.env", "$env:USERPROFILE\.anthropic.env")) {
        if (Test-Path $f) {
            foreach ($line in Get-Content $f) {
                if ($line -match '^\s*(export\s+)?ANTHROPIC_API_KEY\s*=\s*(.+?)\s*$') {
                    $env:ANTHROPIC_API_KEY = $matches[2].Trim('"').Trim("'")
                    break
                }
            }
        }
        if ($env:ANTHROPIC_API_KEY) { break }
    }
}

# Pick the Python interpreter. A scheduled task has no plugin config, so detect here.
# Override with AGENCY_PYTHON (e.g. "py -3", "python", or "python3"). Prefer 'py -3': it
# dodges the Microsoft Store alias stub that 'python' can resolve to (silent failure).
$PyCmd = $env:AGENCY_PYTHON
if (-not $PyCmd) {
    foreach ($cand in @("py -3", "python", "python3")) {
        $cp = $cand.Split(" ")
        $cexe = $cp[0]
        $crest = if ($cp.Length -gt 1) { $cp[1..($cp.Length - 1)] } else { @() }
        try {
            $v = & $cexe @crest -c "import sys; print(sys.version_info[0])" 2>$null
            if ($v -eq "3") { $PyCmd = $cand; break }
        } catch { }
    }
}
if (-not $PyCmd) {
    throw "No Python 3 found. Set AGENCY_PYTHON to your Python command (e.g. 'py -3')."
}
$pp = $PyCmd.Split(" ")
$pexe = $pp[0]
$prest = if ($pp.Length -gt 1) { $pp[1..($pp.Length - 1)] } else { @() }
& $pexe @prest "$PluginDir\scripts\consolidate.py" --world "$World"
