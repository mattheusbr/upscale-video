param(
    [string]$Python = "python",
    [string]$Venv = ".venv",
    [switch]$SkipFfmpeg
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPath = Join-Path $Root $Venv
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$RealEsrganPath = Join-Path $Root "vendor\Real-ESRGAN"

if (-not (Test-Path $VenvPython)) {
    & $Python -m venv $VenvPath
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
& $VenvPython -m pip install -r (Join-Path $Root "requirements\runtime.txt")

if (-not (Test-Path (Join-Path $RealEsrganPath "inference_realesrgan_video.py"))) {
    New-Item -ItemType Directory -Force (Split-Path $RealEsrganPath) | Out-Null
    git clone --depth 1 https://github.com/xinntao/Real-ESRGAN.git $RealEsrganPath
}

& $VenvPython -m pip install --no-build-isolation -e $RealEsrganPath
& $VenvPython -m pip install --no-build-isolation -e $Root

if (-not $SkipFfmpeg -and -not (Test-Path (Join-Path $Root "tools\ffmpeg\ffmpeg.exe"))) {
    & (Join-Path $Root "scripts\install-ffmpeg.ps1")
}

Write-Host "Environment ready. Run:"
Write-Host "  .\.venv\Scripts\python.exe -m upscaler doctor"
