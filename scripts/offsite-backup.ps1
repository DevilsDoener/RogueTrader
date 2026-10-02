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

    Nobody reads the log, so problems raise a visible Windows notification
    (toast, with balloon / msg.exe as fallbacks) and a non-zero exit code:
      0  ok (no notification)
      1  error   - no backup found, checksum mismatch, target missing,
                   any unexpected exception
      2  warning - newest local backup older than 30 hours (backup service
                   down); the copy is still made

    Run by the scheduled task "RogueTrader Offsite Backup" (see
    docs/operations.md, "Backups außer Haus"); safe to run by hand.

.PARAMETER Target
    Destination folder. Defaults to "$env:OneDrive\RogueTrader-Backups".

.PARAMETER KeepDays
    Copies older than this many days are removed from the target. Default 30.

.PARAMETER Source
    Folder holding the db-*.sqlite3 backups. Defaults to ..\backups next to
    this script. Mainly for tests.

.PARAMETER TestAlert
    Only show a sample alert (to check that notifications reach you) and exit.
#>
[CmdletBinding()]
param(
    [string]$Target = '',
    [int]$KeepDays = 30,
    [string]$Source = '',
    [switch]$TestAlert
)

$ErrorActionPreference = 'Stop'
$StaleHours = 30
# PowerShell's own AppUserModelID: already known to Windows, so toasts need no registration.
$ToastAppId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
$script:log = $null
$script:problems = New-Object System.Collections.ArrayList

function Write-Log([string]$message) {
    $line = '{0:yyyy-MM-dd HH:mm:ss} {1}' -f (Get-Date), $message
    if ($script:log) {
        try { Add-Content -Path $script:log -Value $line -Encoding utf8 } catch { }
    }
    Write-Host $line
}

function Show-Toast([string]$title, [string]$text) {
    [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
    [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
    $t = [System.Security.SecurityElement]::Escape($title)
    $b = [System.Security.SecurityElement]::Escape($text)
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml("<toast><visual><binding template=`"ToastGeneric`"><text>$t</text><text>$b</text></binding></visual></toast>")
    $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($ToastAppId)
    $notifier.Show($toast)
    $setting = [string]$notifier.Setting
    if ($setting -ne 'Enabled') { throw "Toast-Einstellung: $setting" }
}

function Show-Balloon([string]$title, [string]$text, [bool]$isError) {
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    $icon = New-Object System.Windows.Forms.NotifyIcon
    try {
        $icon.Icon = if ($isError) { [System.Drawing.SystemIcons]::Error } else { [System.Drawing.SystemIcons]::Warning }
        $icon.Visible = $true
        $icon.BalloonTipTitle = $title
        $icon.BalloonTipText = $text
        $icon.BalloonTipIcon = if ($isError) { 'Error' } else { 'Warning' }
        $icon.ShowBalloonTip(15000)
        Start-Sleep -Seconds 5
    } finally {
        $icon.Dispose()
    }
}

# Never throws: the alert must not be able to crash the script.
function Show-Alert([string]$title, [string]$text, [bool]$isError) {
    try {
        Show-Toast $title $text
        Write-Log 'Hinweis angezeigt (Toast)'
        return
    } catch {
        Write-Log "Toast fehlgeschlagen: $($_.Exception.Message)"
    }
    try {
        Show-Balloon $title $text $isError
        Write-Log 'Hinweis angezeigt (Ballon)'
        return
    } catch {
        Write-Log "Ballon fehlgeschlagen: $($_.Exception.Message)"
    }
    try {
        & msg.exe $env:USERNAME /TIME:600 "$title`r`n$text" 2>$null
        if ($LASTEXITCODE -ne 0) { throw "msg.exe Exitcode $LASTEXITCODE" }
        Write-Log 'Hinweis angezeigt (msg.exe)'
    } catch {
        Write-Log "msg.exe fehlgeschlagen: $($_.Exception.Message) - kein sichtbarer Hinweis möglich"
    }
}

function Add-Problem([string]$level, [string]$reason) {
    [void]$script:problems.Add([pscustomobject]@{ Level = $level; Reason = $reason })
}

if ($TestAlert) {
    Show-Alert 'Rogue Trader: Sicherung - Testmeldung' 'Das ist nur ein Test. Details: offsite-backup.log' $false
    exit 0
}

try {
    if (-not $Source) { $Source = Join-Path (Split-Path -Parent $PSScriptRoot) 'backups' }

    # Resolve the target; fall back to a local log if the target itself is unusable.
    $fallbackLog = Join-Path $env:LOCALAPPDATA 'RogueTrader-Backups\offsite-backup.log'
    $targetOk = $true
    if (-not $Target) {
        if ($env:OneDrive) {
            $Target = Join-Path $env:OneDrive 'RogueTrader-Backups'
        } else {
            $targetOk = $false
            Add-Problem 'error' 'OneDrive-Ordner nicht gefunden'
        }
    }
    if ($targetOk -and -not (Test-Path -LiteralPath $Target)) {
        $parent = Split-Path -Parent $Target
        if (-not $parent -or -not (Test-Path -LiteralPath $parent)) {
            $targetOk = $false
            Add-Problem 'error' "Zielordner nicht erreichbar ($Target)"
        } else {
            New-Item -ItemType Directory -Force -Path $Target | Out-Null
        }
    }
    if ($targetOk) {
        $script:log = Join-Path $Target 'offsite-backup.log'
    } else {
        try {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $fallbackLog) | Out-Null
            $script:log = $fallbackLog
        } catch { $script:log = $null }
        Write-Log "FEHLER: $($script:problems[-1].Reason) (Log hier: $fallbackLog)"
    }

    # Only finished copies: backup_db writes *.tmp first and renames on success.
    $newest = Get-ChildItem -Path $Source -Filter 'db-*.sqlite3' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $newest) {
        Write-Log "FEHLER: keine Sicherung in $Source gefunden"
        Add-Problem 'error' 'keine lokale Sicherung gefunden'
    } else {
        if ($newest.LastWriteTime -lt (Get-Date).AddHours(-$StaleHours)) {
            Write-Log "WARNUNG: neueste Sicherung $($newest.Name) ist älter als $StaleHours Stunden - läuft der backup-Dienst?"
            Add-Problem 'warning' "neueste Sicherung ist älter als $StaleHours Stunden (backup-Dienst?)"
        }

        if ($targetOk) {
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
                    Add-Problem 'error' 'Prüfsumme der Kopie stimmt nicht'
                } else {
                    Move-Item -Path $temp -Destination $destination -Force
                    Write-Log "kopiert: $($newest.Name) ($([math]::Round($newest.Length / 1KB)) KB, SHA256 $sourceHash)"
                }
            }
        }
    }

    if ($targetOk) {
        $cutoff = (Get-Date).AddDays(-$KeepDays)
        Get-ChildItem -Path $Target -Filter 'db-*.sqlite3' -File |
            Where-Object { $_.LastWriteTime -lt $cutoff } |
            ForEach-Object {
                Remove-Item $_.FullName -Force
                Write-Log "gelöscht (älter als $KeepDays Tage): $($_.Name)"
            }
    }
} catch {
    Write-Log "FEHLER: unerwartete Ausnahme: $($_.Exception.Message)"
    Add-Problem 'error' "unerwarteter Fehler: $($_.Exception.Message)"
}

$exitCode = 0
if ($script:problems.Count -gt 0) {
    $isError = @($script:problems | Where-Object { $_.Level -eq 'error' }).Count -gt 0
    $exitCode = if ($isError) { 1 } else { 2 }
    $title = if ($isError) { 'Rogue Trader: Sicherung fehlgeschlagen' } else { 'Rogue Trader: Sicherung veraltet' }
    $reasons = ($script:problems | ForEach-Object { $_.Reason }) -join '; '
    Show-Alert $title "$reasons. Details: offsite-backup.log" $isError
}
exit $exitCode
