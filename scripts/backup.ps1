<#
.SYNOPSIS
    Take a consistent backup of the running portal's SQLite database.

.DESCRIPTION
    Runs SQLite's online backup API (the same mechanism as the `.backup`
    dot-command) against the *live* database inside the running
    "portal" container, so the portal does not need to be stopped.

    Writes two files into the explicitly supplied -Destination directory:
      - db-<UTC timestamp>.sqlite3           (the backup itself)
      - db-<UTC timestamp>.sqlite3.manifest.json  (timestamp + SHA-256 + integrity result)

    The destination directory must already exist. This script never
    creates directory trees and never deletes anything on the host.

.PARAMETER Destination
    Directory that will receive the backup file and its manifest. Must
    already exist.

.PARAMETER Service
    docker compose service name to back up. Defaults to "portal".

.EXAMPLE
    .\scripts\backup.ps1 -Destination D:\backups\rogue-trader-portal
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Destination,

    [string]$Service = "portal"
)

$ErrorActionPreference = "Stop"

function Fail($Message) {
    Write-Error $Message
    exit 1
}

$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {
    Fail "Destination directory does not exist: $Destination. Create it explicitly first; this script will not create directory trees for you."
}
$Destination = (Resolve-Path -LiteralPath $Destination).Path

Push-Location $RepoRoot
try {
    $runningServices = (docker compose ps --services --filter "status=running") -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to query docker compose service status. Run this from a host with docker compose access."
    }
    if (-not ($runningServices -contains $Service)) {
        Fail "Service '$Service' is not running. Start it first with: docker compose up -d $Service"
    }

    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
    $backupFileName = "db-$timestamp.sqlite3"
    $containerTempPath = "/tmp/backup-$timestamp.sqlite3"
    $destFile = Join-Path $Destination $backupFileName
    $manifestFile = "$destFile.manifest.json"

    if (Test-Path -LiteralPath $destFile) {
        Fail "Refusing to overwrite existing file: $destFile"
    }

    # Online backup via Python's sqlite3 module (same underlying SQLite
    # backup API as the `.backup` CLI dot-command), then an integrity
    # check of the *copy* so a corrupt live database is never masked by
    # a "successful" backup.
    $backupScript = @"
import sqlite3
import sys

source = sqlite3.connect("/data/db.sqlite3")
destination = sqlite3.connect("$containerTempPath")
try:
    with destination:
        source.backup(destination)
finally:
    source.close()

result = destination.execute("PRAGMA integrity_check").fetchone()[0]
destination.close()

if result != "ok":
    sys.stderr.write("integrity check failed: " + result + "\n")
    sys.exit(1)

print(result)
"@

    $output = docker compose exec -T $Service python -c $backupScript
    $backupExitCode = $LASTEXITCODE
    if ($backupExitCode -ne 0) {
        docker compose exec -T $Service rm -f $containerTempPath | Out-Null
        Fail "Backup failed inside the container (exit code $backupExitCode): $output"
    }
    $integrityResult = ($output | Select-Object -Last 1).Trim()

    docker compose cp "${Service}:${containerTempPath}" $destFile
    if ($LASTEXITCODE -ne 0) {
        docker compose exec -T $Service rm -f $containerTempPath | Out-Null
        Fail "Failed to copy the backup out of the container."
    }

    docker compose exec -T $Service rm -f $containerTempPath | Out-Null

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $destFile).Hash.ToLower()
    $sizeBytes = (Get-Item -LiteralPath $destFile).Length

    $manifest = [ordered]@{
        timestamp_utc   = $timestamp
        database_file   = $backupFileName
        sha256          = $hash
        size_bytes      = $sizeBytes
        integrity_check = $integrityResult
        source_service  = $Service
    }
    $manifest | ConvertTo-Json | Set-Content -LiteralPath $manifestFile -Encoding utf8

    Write-Host "Backup complete:"
    Write-Host "  Database : $destFile"
    Write-Host "  Manifest : $manifestFile"
    Write-Host "  SHA-256  : $hash"
    Write-Host "  Integrity: $integrityResult"
}
finally {
    Pop-Location
}
