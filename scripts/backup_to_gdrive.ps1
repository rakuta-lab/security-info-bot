<#
.SYNOPSIS
    D:\Develop\security-bot のソース一式を日付付きZIPにしてGoogleドライブへバックアップします。
.DESCRIPTION
    .git や .venv などの不要な一時フォルダは除外して圧縮し、古いバックアップは直近10世代を残して自動削除します。
#>

param(
    [string]$SourceDir = "D:\Develop\security-bot",
    [string]$BackupDir = "G:\マイドライブ\個人\起業・独立\アプリ開発\情報収集Bot_バックアップ",
    [int]$KeepGenerations = 10
)

if (-not (Test-Path $SourceDir)) {
    Write-Error "作業フォルダが見つかりません: $SourceDir"
    exit 1
}

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

$dateStr = Get-Date -Format "yyyyMMdd_HHmmss"
$zipPath = Join-Path $BackupDir "security-bot_$dateStr.zip"
$tempDir = Join-Path $env:TEMP "security-bot-backup-$dateStr"

try {
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

    # .git / .venv / __pycache__ を除外して一時フォルダへコピー
    $excludeDirs = @(".git", ".venv", "venv", "__pycache__")
    Get-ChildItem -Path $SourceDir -Force | Where-Object {
        $excludeDirs -notcontains $_.Name
    } | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $tempDir -Recurse -Force
    }

    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipPath -CompressionLevel Optimal -Force
    Write-Host "バックアップを作成しました: $zipPath"

    # 古い世代の削除
    $oldFiles = Get-ChildItem -Path $BackupDir -Filter "security-bot_*.zip" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $KeepGenerations

    foreach ($file in $oldFiles) {
        Remove-Item -Path $file.FullName -Force
        Write-Host "古いバックアップを削除しました: $($file.Name)"
    }
}
finally {
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force
    }
}
