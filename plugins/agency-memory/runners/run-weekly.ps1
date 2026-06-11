# run-weekly.ps1
# Windows (PowerShell) wrapper for the weekly consolidation. Parallels run-weekly.sh.
# Run by Task Scheduler or manually.
#
# Required env (set once as USER vars so a scheduled task sees them):
#   setx AGENCY_WORLD_ROOT "C:\path\to\your-world"     (clients\ + system\)
#   setx ANTHROPIC_API_KEY "sk-ant-..."                (consolidate.py reads it)
#   ...then reopen the shell so the vars load.
#
# Manual run:
#   $env:AGENCY_WORLD_ROOT="C:\path\to\world"; .\run-weekly.ps1
#
# Schedule it (Task Scheduler, Mondays 10:00):
#   schtasks /Create /TN "AgencyMemoryConsolidate" /SC WEEKLY /D MON /ST 10:00 ^
#     /TR "powershell -ExecutionPolicy Bypass -File C:\path\to\runners\run-weekly.ps1"
#   For a launchd-style catch-up of a missed run (machine was off), open the task in Task
#   Scheduler -> Settings -> tick "Run task as soon as possible after a scheduled start is
#   missed" (schtasks cannot set this flag; the GUI or an XML import can).

$ErrorActionPreference = "Stop"

# This script lives in <plugin>\runners\ ; go up one to the plugin root.
$PluginDir = Split-Path -Parent $PSScriptRoot
$World = $env:AGENCY_WORLD_ROOT
if (-not $World) {
    throw "Set AGENCY_WORLD_ROOT to your world root (clients\ + system\)"
}

# 'python' is the reliable launcher name on Windows (python.org + Microsoft Store).
python "$PluginDir\scripts\consolidate.py" --world "$World"
