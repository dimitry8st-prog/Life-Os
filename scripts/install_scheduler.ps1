param([string]$Time = "07:30")

$ErrorActionPreference = "Stop"
$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = (Get-Command python).Source
$Action = New-ScheduledTaskAction -Execute $Python -Argument 'discover.py' -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time -DaysInterval 3
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "Life OS Article Discovery" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Поиск свежих статей для Life OS каждые 3 дня" -Force
Write-Host "Задача установлена: каждые 3 дня в $Time."
