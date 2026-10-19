# Backup MySQL database "lacco" (buoc 7.3): mysqldump -> .zip -> copy sang thu muc OneDrive -> giu 8 ban moi nhat.
# Chay duoc lai nhieu lan (idempotent): moi lan tao 1 file theo timestamp, roi don cac ban cu.
# Duoc Task Scheduler goi hang tuan (xem install_backup_task.ps1). Log ra logs\backup.log (*.log da nam trong .gitignore).
# Doc tu .env: BACKUP_MYSQL_USER, BACKUP_MYSQL_PASSWORD, BACKUP_OFFSITE_DIR, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE.
$ErrorActionPreference = "Stop"
$Keep = 8   # so ban giu lai o moi noi (hang tuan -> ~2 thang)
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BackupDir = Join-Path $Repo "backups"
$LogDir = Join-Path $Repo "logs"
$LogFile = Join-Path $LogDir "backup.log"
New-Item -ItemType Directory -Force -Path $BackupDir, $LogDir | Out-Null

function Write-Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Output $line
}

function Read-DotEnv([string]$Path) {
    $vars = @{}
    foreach ($line in Get-Content -Path $Path -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $vars[$Matches[1]] = $Matches[2].Trim('"').Trim("'")
        }
    }
    return $vars
}

# Giu lai $Keep file lacco_*.zip moi nhat trong $Dir (ten file co timestamp nen sap theo ten = sap theo thoi gian)
function Remove-OldBackups([string]$Dir) {
    Get-ChildItem -Path $Dir -Filter "lacco_*.zip" -File | Sort-Object Name -Descending |
        Select-Object -Skip $Keep | ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force
            Write-Log "Xoa ban cu: $($_.FullName)"
        }
}

$defaultsFile = $null
$sqlFile = $null
try {
    $envVars = Read-DotEnv (Join-Path $Repo ".env")
    foreach ($k in "BACKUP_MYSQL_USER", "BACKUP_MYSQL_PASSWORD", "BACKUP_OFFSITE_DIR") {
        if (-not $envVars[$k]) { throw "Thieu bien $k trong .env" }
    }
    $dbHost = if ($envVars["MYSQL_HOST"]) { $envVars["MYSQL_HOST"] } else { "localhost" }
    $dbPort = if ($envVars["MYSQL_PORT"]) { $envVars["MYSQL_PORT"] } else { "3306" }
    $dbName = if ($envVars["MYSQL_DATABASE"]) { $envVars["MYSQL_DATABASE"] } else { "lacco" }
    $offsiteDir = $envVars["BACKUP_OFFSITE_DIR"]

    # mysqldump thuong khong co trong PATH -> fallback ve thu muc cai MySQL Server
    $mysqldump = (Get-Command mysqldump.exe -ErrorAction SilentlyContinue).Source
    if (-not $mysqldump) { $mysqldump = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe" }
    if (-not (Test-Path $mysqldump)) { throw "Khong tim thay mysqldump.exe ($mysqldump)" }

    # Mat khau qua file defaults tam (khong dua len command line -> khong lo qua danh sach process)
    $defaultsFile = Join-Path $env:TEMP ("lacco_backup_{0}.cnf" -f [guid]::NewGuid().ToString("N"))
    Set-Content -Path $defaultsFile -Encoding ASCII -Value @(
        "[client]", "user=$($envVars['BACKUP_MYSQL_USER'])", "password=$($envVars['BACKUP_MYSQL_PASSWORD'])",
        "host=$dbHost", "port=$dbPort")

    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $sqlFile = Join-Path $BackupDir "lacco_$stamp.sql"
    $zipFile = Join-Path $BackupDir "lacco_$stamp.zip"
    Write-Log "Bat dau backup database '$dbName' -> $zipFile"

    # --result-file thay vi redirect '>': PowerShell 5.1 redirect se ghi UTF-16, hong file dump
    # --no-tablespaces: MySQL 8 doi quyen PROCESS de dump tablespace, user backup khong can quyen nay
    & $mysqldump "--defaults-extra-file=$defaultsFile" --single-transaction --routines --triggers --events `
        --no-tablespaces --set-gtid-purged=OFF --default-character-set=utf8mb4 "--result-file=$sqlFile" $dbName
    if ($LASTEXITCODE -ne 0) { throw "mysqldump that bai (exit code $LASTEXITCODE)" }
    if ((Get-Item $sqlFile).Length -eq 0) { throw "File dump rong: $sqlFile" }

    Compress-Archive -LiteralPath $sqlFile -DestinationPath $zipFile -Force
    Remove-Item -LiteralPath $sqlFile -Force
    Write-Log ("Nen xong: {0} ({1:N0} KB)" -f $zipFile, ((Get-Item $zipFile).Length / 1KB))

    New-Item -ItemType Directory -Force -Path $offsiteDir | Out-Null
    Copy-Item -LiteralPath $zipFile -Destination $offsiteDir -Force
    Write-Log "Copy sang ban thu 2: $offsiteDir"

    Remove-OldBackups $BackupDir
    Remove-OldBackups $offsiteDir
    Write-Log "Backup thanh cong"
}
catch {
    Write-Log "LOI: $($_.Exception.Message)"
    exit 1
}
finally {
    if ($defaultsFile -and (Test-Path $defaultsFile)) { Remove-Item -LiteralPath $defaultsFile -Force }
    # Dump loi giua chung -> khong de lai file .sql chua nen
    if ($sqlFile -and (Test-Path $sqlFile)) { Remove-Item -LiteralPath $sqlFile -Force }
}
