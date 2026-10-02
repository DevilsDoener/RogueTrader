<#
.SYNOPSIS
    Copy the newest daily database backup off this machine.

.DESCRIPTION
    The `backup` compose service writes verified copies to .\backups on the
    same disk as the live database. This script copies the newest one to a
    second location (by default the OneDrive folder, which syncs it to the
    cloud), skips files already copied, and deletes copies in the target that
    are older than -KeepDays. It only reads .\backups and never touches the
    live database or the containers.

    Run by the scheduled task "RogueTrader Offsite Backup" (see
    docs/operations.md, "Backups außer Haus"); safe to run by hand.

.PARAMETER Target
    Destination folder. Defaults to "$env:OneDrive\RogueTrader-Backups".

.PARAMETER KeepDays
    Copies older than this many days are removed from the target. Default 30.
#>
[CmdletBinding()]
param(
    [string]$Target = (Join-Path $env:OneDrive 'RogueTrader-Backups'),
    [int]$KeepDays = 30
)

$ErrorActionPreference = 'Stop'
$source = Join-Path (Split-Path -Parent $PSScriptRoot) 'backups'
$log = Join-Path $Target 'offsite-backup.log'

function Write-Log([string]$message) {
    $line = '{0:yyyy-MM-dd HH:mm:ss} {1}' -f (Get-Date), $message
    Add-Content -Path $log -Value $line -Encoding utf8
    Write-Output $line
}

if (-not $env:OneDrive -and -not $PSBoundParameters.ContainsKey('Target')) {
    throw 'No OneDrive folder found ($env:OneDrive is empty); pass -Target.'
}
New-Item -ItemType Directory -Force -Path $Target | Out-Null

# Only finished copies: backup_db writes *.tmp first and renames on success.
$newest = Get-ChildItem -Path $source -Filter 'db-*.sqlite3' -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $newest) {
    Write-Log "FEHLER: keine Sicherung in $source gefunden"
    exit 1
}
if ($newest.LastWriteTime -lt (Get-Date).AddHours(-30)) {
    Write-Log "WARNUNG: neueste Sicherung $($newest.Name) ist älter als 30 Stunden - läuft der backup-Dienst?"
}

$destination = Join-Path $Target $newest.Name
if (Test-Path $destination) {
    Write-Log "bereits kopiert: $($newest.Name)"
} else {
    $temp = "$destination.partial"
    Copy-Item -Path $newest.FullName -Destination $temp -Force
    $sourceHash = (Get-FileHash -Path $newest.FullName -Algorithm SHA256).Hash
    $copyHash = (Get-FileHash -Path $temp -Algorithm SHA256).Hash
    if ($sourceHash -ne $copyHash) {
        Remove-Item $temp -Force
        Write-Log "FEHLER: Prüfsumme der Kopie stimmt nicht ($($newest.Name))"
        exit 1
    }
    Move-Item -Path $temp -Destination $destination -Force
    Write-Log "kopiert: $($newest.Name) ($([math]::Round($newest.Length / 1KB)) KB, SHA256 $sourceHash)"
}

$cutoff = (Get-Date).AddDays(-$KeepDays)
Get-ChildItem -Path $Target -Filter 'db-*.sqlite3' -File |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
        Remove-Item $_.FullName -Force
        Write-Log "gelöscht (älter als $KeepDays Tage): $($_.Name)"
    }
