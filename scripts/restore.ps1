<#
.SYNOPSIS
    Restore the portal's SQLite database from a backup file.

.DESCRIPTION
    Accepts both kinds of backup copies:

      - a copy made by scripts\backup.ps1: db-<timestamp>.sqlite3 with a
        db-<timestamp>.sqlite3.manifest.json next to it. The SHA-256 in the
        manifest is verified before anything else happens.
      - a daily copy made by the "backup" service (manage.py backup_db):
        db-YYYYMMDD-HHMMSS.sqlite3 WITHOUT a manifest. There is nothing to
        verify the checksum against, so that step is skipped -- loudly. The
        integrity check below still runs. A file without a manifest whose
        name does not look like a daily copy is refused.

    The database must not be in use, so BOTH the "portal" and the "backup"
    service must be stopped first (the backup service holds the volume
    mounted read-only, and a restart loop of it would race the restore).
    Steps:

      1. Refuses to run while the portal or the backup service is running
         (or restarting/paused) and says what to stop.
      2. Validates the backup file's SHA-256 against its manifest (only for
         copies that have one).
      3. Runs PRAGMA integrity_check against the backup file itself, using a
         disposable one-off container so this works even while the
         services are stopped.
      4. Copies the *current* live database -- and any db.sqlite3-journal,
         -wal and -shm next to it -- to the recovery set
         db.sqlite3.recovery-<timestamp>[-journal|-wal|-shm] before touching
         anything, so a bad restore is itself always reversible.
      5. Copies the validated backup next to the live database, removes the
         stale journal/-wal/-shm files (they belong to the OLD database and
         would be replayed onto the restored one) and renames the copy over
         db.sqlite3. Finally the live file's SHA-256 is compared with the
         backup's.

    Never infers which backup to use (the file must be given explicitly) and
    never deletes anything except those stale sidecar files, which were
    moved into the recovery set first. The recovery set is left in place for
    the operator to remove once the restore is confirmed good.

    Login sessions: daily copies contain none, so after restoring one
    everybody has to log in again. Copies from backup.ps1 are plain copies
    and still contain the sessions that existed at backup time.

.PARAMETER BackupFile
    Path to the db-<timestamp>.sqlite3 file to restore.

.PARAMETER Service
    docker compose service name to restore into. Defaults to "portal".

.PARAMETER BackupService
    docker compose service name of the daily backup job that must also be
    stopped. Defaults to "backup".

.PARAMETER ProjectName
    docker compose project name (docker compose -p). Defaults to empty, i.e.
    the normal project of this checkout. Set it to restore into a throwaway
    project, e.g. when practising the restore.

.PARAMETER ComposeFile
    Compose file to use (docker compose -f). Defaults to the compose.yaml of
    this checkout. Only needed together with -ProjectName for a drill with a
    modified copy of the compose file (other host port, own backups folder).

.EXAMPLE
    docker compose stop portal backup
    .\scripts\restore.ps1 -BackupFile .\backups\db-20260101-020000.sqlite3
    docker compose up -d portal backup

.EXAMPLE
    # Practise against a throwaway project (see docs/operations.md)
    .\scripts\restore.ps1 -BackupFile D:\drill\backups\db-20260101-020000.sqlite3 -ProjectName rtdrill -ComposeFile D:\drill\compose.yaml
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,

    [string]$Service = "portal",

    [string]$BackupService = "backup",

    [string]$ProjectName = "",

    [string]$ComposeFile = ""
)

$ErrorActionPreference = "Stop"

function Fail($Message) {
    Write-Error $Message
    exit 1
}

$RepoRoot = Split-Path -Parent $PSScriptRoot

# Global options for every "docker compose" call below.
$ComposeArgs = @()
if ($ComposeFile) {
    if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) {
        Fail "Compose file does not exist: $ComposeFile"
    }
    $ComposeArgs += @("-f", (Resolve-Path -LiteralPath $ComposeFile).Path)
}
if ($ProjectName) {
    $ComposeArgs += @("-p", $ProjectName)
}
# Runs a Python snippet in a disposable one-off container of $Service. The
# code goes in via stdin ("python -"), not as a -c argument: Windows PowerShell
# 5.1 strips the double quotes out of arguments passed to native programs.
function Invoke-ContainerPython([string]$Code, [string[]]$RunArgs) {
    $Code | docker compose @ComposeArgs run --rm --no-deps -T @RunArgs $Service python -
}
$ComposeHint = if ($ComposeArgs.Count -gt 0) { "docker compose $($ComposeArgs -join ' ')" } else { "docker compose" }

if (-not (Test-Path -LiteralPath $BackupFile -PathType Leaf)) {
    Fail "Backup file does not exist: $BackupFile"
}
$BackupFile = (Resolve-Path -LiteralPath $BackupFile).Path
$manifestFile = "$BackupFile.manifest.json"
$hasManifest = Test-Path -LiteralPath $manifestFile -PathType Leaf
if (-not $hasManifest) {
    # Daily copies from `manage.py backup_db` never have a manifest. Anything
    # else without one stays unverifiable and is refused.
    if ((Split-Path -Leaf $BackupFile) -notmatch '^db-\d{8}-\d{6}\.sqlite3$') {
        Fail "No manifest next to $BackupFile and the name is not that of a daily backup (db-YYYYMMDD-HHMMSS.sqlite3). Refusing to restore an unverified database file."
    }
}

Push-Location $RepoRoot
try {
    # --- 1. Neither the portal nor the backup job may be running. ----
    $active = @()
    foreach ($state in @("running", "restarting", "paused")) {
        $names = (docker compose @ComposeArgs ps --services --filter "status=$state") -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        if ($LASTEXITCODE -ne 0) {
            Fail "Failed to query docker compose service status. Run this from a host with docker compose access."
        }
        $active += @($names)
    }
    $blocking = @($Service, $BackupService) | Where-Object { $active -contains $_ }
    if ($blocking.Count -gt 0) {
        Fail "Still running: $($blocking -join ', '). The database must not be in use during a restore (the backup job mounts the same volume). Stop it first with: $ComposeHint stop $Service $BackupService"
    }

    # --- 2. Manifest / SHA-256 validation (backup.ps1 copies only). ----
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BackupFile).Hash.ToLower()
    if ($hasManifest) {
        $manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
        if (-not $manifest.sha256) {
            Fail "Manifest is missing a sha256 field: $manifestFile"
        }
        $expectedHash = $manifest.sha256.ToLower()
        if ($actualHash -ne $expectedHash) {
            Fail "Backup file does not match its manifest checksum. Expected $expectedHash, got $actualHash. Refusing to restore a possibly-corrupt or tampered file."
        }
        Write-Host "Backup kind : backup.ps1 copy with manifest"
        Write-Host "Checksum    : SHA-256 matches the manifest ($actualHash)"
    }
    else {
        Write-Host "Backup kind : daily copy (manage.py backup_db) WITHOUT manifest"
        Write-Host "Checksum    : NOT VERIFIED - there is no manifest to compare against; only the integrity check below protects against a damaged file."
        Write-Host "              SHA-256 of the file as read now: $actualHash"
    }

    # --- 3. Integrity check of the backup itself, via a disposable ----
    #        one-off container (works even with the services stopped). --
    # immutable=1: the candidate is mounted read-only and nothing else
    # touches it, so SQLite must not try to create -wal/-shm files for it.
    $integrityScript = @"
import sqlite3
conn = sqlite3.connect("file:/tmp/restore-candidate.sqlite3?immutable=1", uri=True)
print(conn.execute("PRAGMA integrity_check").fetchone()[0])
"@
    $mountArg = "${BackupFile}:/tmp/restore-candidate.sqlite3:ro"
    $integrityOutput = Invoke-ContainerPython $integrityScript @("-v", $mountArg)
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to run the integrity check container."
    }
    $integrityResult = ($integrityOutput | Select-Object -Last 1).Trim()
    if ($integrityResult -ne "ok") {
        Fail "Backup file failed PRAGMA integrity_check: $integrityResult. Refusing to restore it."
    }
    Write-Host "Integrity   : $integrityResult"

    # --- 4. Preserve whatever database currently exists in the volume, -
    #        including journal/-wal/-shm, as one recovery set. ---------
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
    $recoveryScript = @"
import os
import shutil

live = "/data/db.sqlite3"
recovery = live + ".recovery-$timestamp"
if not os.path.exists(live):
    print("no-existing-database-to-preserve")
else:
    shutil.copy2(live, recovery)
    kept = [recovery]
    for suffix in ("-journal", "-wal", "-shm"):
        if os.path.exists(live + suffix):
            shutil.copy2(live + suffix, recovery + suffix)
            kept.append(recovery + suffix)
    print("recovery-set-created:" + ",".join(kept))
"@
    $recoveryOutput = Invoke-ContainerPython $recoveryScript @()
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to preserve the existing database before restoring. Aborting without touching /data/db.sqlite3."
    }
    Write-Host "Recovery    : $(($recoveryOutput | Select-Object -Last 1).Trim())"

    # --- 5. Only now replace the live database. ------------------------
    # The copy is staged next to the live file, the old sidecars are removed
    # (they are already in the recovery set) and the staged file is renamed
    # over db.sqlite3 in one step. Finally the result is compared with the
    # source by SHA-256.
    $replaceScript = @"
import hashlib
import os
import shutil

live = "/data/db.sqlite3"
staged = live + ".restoring"
source = "/tmp/restore-candidate.sqlite3"


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


try:
    shutil.copy2(source, staged)
    if digest(staged) != digest(source):
        raise SystemExit("staged copy differs from the backup")
    removed = []
    for suffix in ("-journal", "-wal", "-shm"):
        if os.path.exists(live + suffix):
            os.remove(live + suffix)
            removed.append("db.sqlite3" + suffix)
    os.replace(staged, live)
finally:
    if os.path.exists(staged):
        os.remove(staged)

if digest(live) != digest(source):
    raise SystemExit("restored database differs from the backup")
print("restored; stale files removed: " + (",".join(removed) or "none"))
"@
    $replaceOutput = Invoke-ContainerPython $replaceScript @("-v", $mountArg)
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to copy the validated backup into place. The recovery set from step 4 (if created) is still available in the volume."
    }
    Write-Host "Replace     : $(($replaceOutput | Select-Object -Last 1).Trim())"

    Write-Host ""
    Write-Host "Restore complete from: $BackupFile"
    if ($hasManifest) {
        Write-Host "Sessions: this copy was made by backup.ps1 and still contains the login sessions of its time; users whose session has since expired log in again."
    }
    else {
        Write-Host "Sessions: daily backups contain NO login sessions - after this restore everybody has to log in again."
    }
    Write-Host "Start the services with: $ComposeHint up -d $Service $BackupService"
    Write-Host "Then check /healthz/ and spot-check recent data. The recovery set db.sqlite3.recovery-$timestamp* stays in the data volume until you remove it."
}
finally {
    Pop-Location
}
