param(
    [Parameter(Mandatory = $true)]
    [string]$ImageDirectory,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [int]$FirstPage = 1,
    [int]$LastPage = 408
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Runtime.WindowsRuntime

function Await-WinRT {
    param(
        [Parameter(Mandatory = $true)]$Operation,
        [Parameter(Mandatory = $true)][Type]$ResultType
    )

    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and
            $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1
        } |
        Select-Object -First 1

    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType = WindowsRuntime] | Out-Null

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) {
    throw 'Windows OCR engine is unavailable for the configured user languages.'
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

for ($page = $FirstPage; $page -le $LastPage; $page++) {
    $imagePath = Join-Path $ImageDirectory ('page{0:D3}_0.jpg' -f $page)
    $outputPath = Join-Path $OutputDirectory ('page{0:D3}.txt' -f $page)

    if (-not (Test-Path -LiteralPath $imagePath)) {
        throw "Missing image: $imagePath"
    }

    $file = Await-WinRT ([Windows.Storage.StorageFile]::GetFileFromPathAsync($imagePath)) ([Windows.Storage.StorageFile])
    $stream = Await-WinRT ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    try {
        $decoder = Await-WinRT ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await-WinRT ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        try {
            $result = Await-WinRT ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
            $lineText = ($result.Lines | ForEach-Object { $_.Text }) -join [Environment]::NewLine
            [System.IO.File]::WriteAllText($outputPath, $lineText, [System.Text.UTF8Encoding]::new($false))
        }
        finally {
            if ($bitmap -is [System.IDisposable]) {
                $bitmap.Dispose()
            }
        }
    }
    finally {
        $stream.Dispose()
    }

    Write-Output ('OCR {0}/{1}: page {2}' -f ($page - $FirstPage + 1), ($LastPage - $FirstPage + 1), $page)
}
