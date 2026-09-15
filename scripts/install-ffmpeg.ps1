param(
    [string]$InstallRoot = "tools\ffmpeg"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Destination = Join-Path $Root $InstallRoot
$Work = Join-Path ([System.IO.Path]::GetTempPath()) "upscale-video-ffmpeg"
$Archive = Join-Path $Work "ffmpeg-release-essentials.7z"
$Url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z"
$HashUrl = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.1-essentials_build.7z.sha256"

New-Item -ItemType Directory -Force $Work | Out-Null
New-Item -ItemType Directory -Force $Destination | Out-Null
& curl.exe -L --fail --retry 3 --output $Archive $Url
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao baixar o pacote FFmpeg"
}
$Expected = ((& curl.exe -L --fail --silent --show-error $HashUrl) -split "\s+")[0].ToLowerInvariant()
$Sha = [System.Security.Cryptography.SHA256]::Create()
$Actual = (-join ($Sha.ComputeHash([System.IO.File]::ReadAllBytes($Archive)) | ForEach-Object { $_.ToString("x2") })).ToLowerInvariant()
$Sha.Dispose()
if ($Actual -ne $Expected) {
    throw "SHA-256 do FFmpeg não confere. Esperado: $Expected; obtido: $Actual"
}

$Extract = Join-Path $Work "extract"
if (Test-Path -LiteralPath $Extract) {
    Remove-Item -LiteralPath $Extract -Recurse -Force
}
New-Item -ItemType Directory -Force $Extract | Out-Null
& tar.exe -xf $Archive -C $Extract
if ($LASTEXITCODE -ne 0) {
    throw "Não foi possível extrair o pacote FFmpeg com bsdtar"
}
$Ffmpeg = Get-ChildItem -LiteralPath $Extract -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
$Ffprobe = Get-ChildItem -LiteralPath $Extract -Recurse -Filter "ffprobe.exe" | Select-Object -First 1
if (-not $Ffmpeg -or -not $Ffprobe) {
    throw "O arquivo do FFmpeg não contém ffmpeg.exe e ffprobe.exe"
}
Copy-Item -LiteralPath $Ffmpeg.FullName -Destination (Join-Path $Destination "ffmpeg.exe") -Force
Copy-Item -LiteralPath $Ffprobe.FullName -Destination (Join-Path $Destination "ffprobe.exe") -Force
Write-Host "FFmpeg instalado em $Destination"
