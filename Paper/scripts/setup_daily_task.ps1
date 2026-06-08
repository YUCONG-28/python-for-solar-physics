[CmdletBinding()]
param(
    [string]$TaskName = "PaperDailyRecommendation",
    [string]$RunTime = "08:30"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$templatePath = Join-Path $scriptRoot "paper_daily_recommendation_task.xml"
$tempPath = Join-Path $env:TEMP "paper_daily_recommendation_task_resolved.xml"
$runnerPath = Join-Path $scriptRoot "paper_daily_recommendation.ps1"

$xml = Get-Content -Raw -Encoding UTF8 -Path $templatePath
$xml = $xml.Replace("__TASK_NAME__", $TaskName)
$startBoundary = ("{0}T{1}:00" -f (Get-Date -Format "yyyy-MM-dd"), $RunTime)
$xml = $xml.Replace("__START_BOUNDARY__", $startBoundary)
$xml = $xml.Replace("__SCRIPT_PATH__", $runnerPath.Replace("&", "&amp;"))
$xml = $xml.Replace("__WORKDIR__", $projectRoot.Replace("&", "&amp;"))

$encoding = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($tempPath, $xml, $encoding)

schtasks.exe /Create /TN $TaskName /XML $tempPath /F | Out-Host
Write-Host "Task created or updated: $TaskName"
