# Dang ky LACCO Dashboard nhu 1 Scheduled Task chay luc khoi dong may (chay PowerShell voi quyen Administrator).
# Chay duoc lai nhieu lan (idempotent). Ly do chon Task Scheduler thay NSSM: xem HD-22.
$ErrorActionPreference = "Stop"
$TaskName = "LACCO Dashboard"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

# MySQL phai tu khoi dong cung may
Set-Service -Name MySQL80 -StartupType Automatic

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Repo\scripts\deploy\run_app.cmd`"" -WorkingDirectory $Repo
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = "PT1M"   # cho MySQL + mang len truoc
# Watchdog: neu cmd wrapper bi kill, task chay lai moi 5 phut (MultipleInstances IgnoreNew nen khong nhan doi khi dang chay)
$watchdog = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($trigger,$watchdog) -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
