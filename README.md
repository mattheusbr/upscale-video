# Upscale Video

Ferramenta local, orientada a qualidade, para upscale de vídeos usando a RTX 3060 Ti. O backend principal é o Real-ESRGAN oficial em CUDA/FP16. O programa faz a inspeção do vídeo, crop central para formatos como 1080x1920, fallback automático de tile em caso de falta de VRAM e encode final com H.264, AAC, BT.709, `yuv420p` e `faststart`.

## Preparação no Windows

Execute no PowerShell:

```powershell
.\scripts\bootstrap.ps1
```

O script cria `.venv`, instala PyTorch com CUDA 12.6, instala as dependências do Real-ESRGAN, baixa o checkout oficial em `vendor/Real-ESRGAN` e instala um build FFmpeg/FFprobe local em `tools/ffmpeg`.

Verifique a máquina:

```powershell
.\.venv\Scripts\python.exe -m upscaler doctor
```

## Uso

Inspecionar o arquivo:

```powershell
.\.venv\Scripts\python.exe -m upscaler inspect input.mp4
```

Fazer um preview vertical de cinco segundos:

```powershell
.\.venv\Scripts\python.exe -m upscaler preview input.mp4 output-preview.mp4 --profile clean --target 1080x1920 --tile 256
```

Processar o vídeo completo:

```powershell
.\.venv\Scripts\python.exe -m upscaler run input.mp4 output.mp4 --profile clean --target 1080x1920 --tile 256
```

Perfis disponíveis:

- `clean`: `RealESRGAN_x4plus`, indicado para live-action limpo.
- `compressed`: `realesr-general-x4v3`, com `--denoise 0..1`.
- `anime`: `realesr-animevideov3`.

Comparar os perfis em um trecho curto:

```powershell
.\.venv\Scripts\python.exe -m upscaler benchmark input.mp4 benchmark --seconds 5 --target 1080x1920
```

## Decisões de qualidade

- Um único processo por GPU.
- FP16 por padrão; `--fp32` somente para comparar resultados.
- Tile inicial 256, reduzindo automaticamente para 192, 128, 96, 64 ou 32 se houver OOM.
- FPS variável é rejeitado por padrão porque o backend frame-a-frame trabalha com FPS nominal.
- HDR é rejeitado no primeiro MVP até haver uma política explícita de tone mapping para BT.709.
- O áudio original é remapeado e recodificado para AAC no encode final.
