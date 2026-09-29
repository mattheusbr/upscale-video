param(
    [string]$Python = "python",
    [switch]$SkipFfmpeg
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$RealEsrgan = Join-Path $Root "vendor\Real-ESRGAN\inference_realesrgan_video.py"
if (-not (Test-Path $RealEsrgan)) {
    throw "Real-ESRGAN não encontrado. Inicialize o submódulo: git submodule update --init --recursive"
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    & $Python -m venv (Join-Path $Root ".venv")
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar pip" }
& $VenvPython -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar PyTorch CUDA 12.6" }
& $VenvPython -m pip install -r (Join-Path $Root "requirements\runtime.txt")
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências do projeto" }
& $VenvPython -m pip install --no-build-isolation -e (Join-Path $Root "vendor\Real-ESRGAN")
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar Real-ESRGAN" }
& $VenvPython -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar PyInstaller" }

$Ffmpeg = Join-Path $Root "tools\ffmpeg\ffmpeg.exe"
if (-not $SkipFfmpeg -and -not (Test-Path $Ffmpeg)) {
    & (Join-Path $Root "scripts\install-ffmpeg.ps1")
}
$PyInstallerArgs = @(
    "--noconfirm", "--clean", "--onedir", "--name", "upscale",
    "--collect-all", "torch",
    "--collect-all", "torchvision",
    "--collect-all", "basicsr",
    "--collect-all", "realesrgan",
    "--collect-all", "facexlib",
    "--collect-all", "textual",
    "--collect-all", "ffmpeg",
    "--collect-all", "cv2",
    "--hidden-import", "socket",
    "--hidden-import", "_socket",
    "--hidden-import", "multiprocessing",
    "--add-data", "vendor\Real-ESRGAN;vendor\Real-ESRGAN",
    "--add-data", "upscaler\ui\tui.tcss;upscaler\ui"
)
if (Test-Path $Ffmpeg) {
    $PyInstallerArgs += @("--add-data", "tools\ffmpeg;tools\ffmpeg")
}
elseif (-not $SkipFfmpeg) {
    throw "FFmpeg não encontrado. Instale-o ou use -SkipFfmpeg para depender do PATH do sistema."
}
$PyInstallerArgs += "upscale_entry.py"

$ExistingExe = Join-Path $Root "dist\upscale\upscale.exe"
$RunningBuild = Get-Process -Name "upscale" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path -eq $ExistingExe }
if ($RunningBuild) {
    throw "Feche o upscale.exe que está aberto antes de gerar uma nova versão: $ExistingExe"
}

& $VenvPython -m PyInstaller @PyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller falhou com código $LASTEXITCODE"
}

Write-Host "Build concluído: $Root\dist\upscale\upscale.exe"
