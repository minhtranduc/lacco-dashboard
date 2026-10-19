# Dang ky Scheduled Task backup MySQL hang tuan (Chu Nhat 2:00 sang) (chay PowerShell voi quyen Administrator).
# Chay duoc lai nhieu lan (idempotent). Script backup: backup_mysql.ps1 (buoc 7.3).
$ErrorActionPreference = "Stop"
$TaskName = "LACCO Dashboard Backup"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Repo\scripts\deploy\backup_mysql.ps1`"" `
    -WorkingDirectory $Repo
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "02:00"
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
# StartWhenAvailable: may tat luc 2:00 Chu Nhat -> chay bu khi may bat lai
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 1) -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State,
    @{ n = "NextRunTime"; e = { (Get-ScheduledTaskInfo -TaskName $TaskName).NextRunTime } }
