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
# Chi 1 trigger AtStartup. Khong dung trigger lap 5 phut: run_app.cmd da tu vong lap restart Streamlit khi crash,
# con trigger lap lam Last Run Time/Last Result bi ghi de bang 0x800710E0 (IgnoreNew) -> khong doc duoc ket qua luc boot.
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
