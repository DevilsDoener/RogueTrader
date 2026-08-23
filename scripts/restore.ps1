<#
.SYNOPSIS
    Restore the portal's SQLite database from a backup made by backup.ps1.

.DESCRIPTION
    Requires the "portal" container to be stopped first (a restore while
    the app is writing to the database would corrupt it). Steps:

      1. Refuses to run if the service is currently running.
      2. Validates the backup file's SHA-256 against its manifest.
      3. Runs PRAGMA integrity_check against the backup file itself,
         using a disposable one-off container so this works even while
         the "portal" service is stopped.
      4. Copies the *current* live database to a recovery filename
         (db.sqlite3.recovery-<timestamp>) before touching anything,
         so a bad restore is itself always reversible.
      5. Only then copies the validated backup over the live database.

    Never infers which backup to use (the file must be given explicitly)
    and never deletes anything -- the recovery copy from step 4 is left
    in place for the operator to remove once the restore is confirmed
    good.

.PARAMETER BackupFile
    Path to the db-<timestamp>.sqlite3 file to restore. A matching
    "<BackupFile>.manifest.json" (written by backup.ps1) must sit next to it.

.PARAMETER Service
    docker compose service name to restore. Defaults to "portal".

.EXAMPLE
    docker compose stop portal
    .\scripts\restore.ps1 -BackupFile D:\backups\rogue-trader-portal\db-20260101-020000.sqlite3
    docker compose up -d portal
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,

    [string]$Service = "portal"
)

$ErrorActionPreference = "Stop"

function Fail($Message) {
    Write-Error $Message
    exit 1
}

$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $BackupFile -PathType Leaf)) {
    Fail "Backup file does not exist: $BackupFile"
}
$BackupFile = (Resolve-Path -LiteralPath $BackupFile).Path
$manifestFile = "$BackupFile.manifest.json"
if (-not (Test-Path -LiteralPath $manifestFile -PathType Leaf)) {
    Fail "Manifest file not found next to backup: $manifestFile. Refusing to restore an unverified database file."
}

Push-Location $RepoRoot
try {
    # --- 1. The service must already be stopped. ---------------------
    $runningServices = (docker compose ps --services --filter "status=running") -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to query docker compose service status. Run this from a host with docker compose access."
    }
    if ($runningServices -contains $Service) {
        Fail "Service '$Service' is still running. Stop it first with: docker compose stop $Service"
    }

    # --- 2. Manifest / SHA-256 validation. -----------------------------
    $manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
    if (-not $manifest.sha256) {
        Fail "Manifest is missing a sha256 field: $manifestFile"
    }
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BackupFile).Hash.ToLower()
    $expectedHash = $manifest.sha256.ToLower()
    if ($actualHash -ne $expectedHash) {
        Fail "Backup file does not match its manifest checksum. Expected $expectedHash, got $actualHash. Refusing to restore a possibly-corrupt or tampered file."
    }

    # --- 3. Integrity check of the backup itself, via a disposable ----
    #        one-off container (works even with the service stopped). --
    $integrityScript = @"
import sqlite3
conn = sqlite3.connect("/tmp/restore-candidate.sqlite3")
print(conn.execute("PRAGMA integrity_check").fetchone()[0])
"@
    $mountArg = "${BackupFile}:/tmp/restore-candidate.sqlite3:ro"
    $integrityOutput = docker compose run --rm --no-deps -v $mountArg $Service python -c $integrityScript
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to run the integrity check container."
    }
    $integrityResult = ($integrityOutput | Select-Object -Last 1).Trim()
    if ($integrityResult -ne "ok") {
        Fail "Backup file failed PRAGMA integrity_check: $integrityResult. Refusing to restore it."
    }

    # --- 4. Preserve whatever database currently exists in the volume. -
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
    $recoveryScript = @"
import os
import shutil

if os.path.exists("/data/db.sqlite3"):
    shutil.copy2("/data/db.sqlite3", "/data/db.sqlite3.recovery-$timestamp")
    print("recovery-copy-created:/data/db.sqlite3.recovery-$timestamp")
else:
    print("no-existing-database-to-preserve")
"@
    $recoveryOutput = docker compose run --rm --no-deps $Service python -c $recoveryScript
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to preserve the existing database before restoring. Aborting without touching /data/db.sqlite3."
    }
    Write-Host "  $(($recoveryOutput | Select-Object -Last 1).Trim())"

    # --- 5. Only now replace the live database. ------------------------
    $replaceScript = @"
import shutil
shutil.copy2("/tmp/restore-candidate.sqlite3", "/data/db.sqlite3")
print("restored")
"@
    $replaceOutput = docker compose run --rm --no-deps -v $mountArg $Service python -c $replaceScript
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to copy the validated backup into place. The recovery copy from step 4 (if created) is still available in the volume."
    }

    Write-Host "Restore complete from: $BackupFile"
    Write-Host "Integrity check: $integrityResult"
    Write-Host "Start the service with: docker compose up -d $Service"
}
finally {
    Pop-Location
}
