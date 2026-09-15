# Upscale Video

Ferramenta local para aumentar a resolução de vídeos usando Real-ESRGAN e CUDA. O programa preserva o áudio, mantém o FPS nominal, mostra o progresso por frames e gera um vídeo final compatível com H.264, AAC e `yuv420p`.

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

## Uso rápido

### Opção simples

Use este modo quando não quiser configurar parâmetros técnicos. Informe o vídeo
e escolha o nível de upscale:

```powershell
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --nivel baixo
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --nivel medio
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --nivel alto
```

Os níveis usam o maior lado do vídeo como referência:

- `baixo`: até 1280 px.
- `medio`: até 1920 px.
- `alto`: até 3840 px, equivalente a 4K.

O modo simples nunca corta o vídeo, mantém a proporção e nunca reduz a
resolução original. Se o vídeo já tiver resolução igual ou superior ao nível
escolhido, ele será processado sem redução. A saída é criada na mesma pasta,
com nomes como `input_upscaled_medio.mp4`.

O processamento exibe `Processando vídeo...` e a porcentagem de frames
concluídos no terminal. Dependendo do tamanho do vídeo e da GPU, o primeiro
frame pode levar alguns segundos enquanto o modelo é carregado.

### Conferir um vídeo

Inspecionar o arquivo:

```powershell
.\.venv\Scripts\python.exe -m upscaler inspect input.mp4
```

### Opção avançada

Use `run` quando precisar definir perfil, resolução alvo, tile, qualidade do
encode ou outros parâmetros:

```powershell
.\.venv\Scripts\python.exe -m upscaler run input.mp4 output.mp4 --profile clean --target 1080x1920 --tile 256
```

O comando acima processa o vídeo completo e grava o resultado em `output.mp4`.

Neste modo, `--target` pode fazer crop central para ajustar o aspecto. Para
evitar crop e manter exatamente o formato original, não informe `--target`.

Para testar apenas alguns segundos antes de processar o vídeo completo:

```powershell
.\.venv\Scripts\python.exe -m upscaler preview input.mp4 output-preview.mp4 --seconds 5 --profile clean --tile 256
```

Perfis disponíveis:

- `clean`: `RealESRGAN_x4plus`, indicado para live-action limpo.
- `compressed`: `realesr-general-x4v3`, com `--denoise 0..1`.
- `anime`: `realesr-animevideov3`.

## Benchmark

O benchmark processa um trecho curto do vídeo com dois ou mais perfis e grava
um relatório JSON com o tempo, modelo, tile usado e status de cada execução.
Ele exige três informações:

1. O vídeo de entrada.
2. A pasta onde os resultados serão salvos.
3. A duração do trecho, usando `--seconds`.

Exemplo comparando todos os perfis disponíveis:

```powershell
.\.venv\Scripts\python.exe -m upscaler benchmark input.mp4 benchmark --seconds 5 --target 1080x1920
```

Esse comando cria arquivos como:

```text
benchmark/
	input_anime.mp4
	input_clean.mp4
	input_compressed.mp4
	benchmark.json
```

Para comparar apenas perfis específicos, informe-os com `--profiles`:

```powershell
.\.venv\Scripts\python.exe -m upscaler benchmark input.mp4 benchmark --seconds 5 --profiles clean compressed
```

O campo `--target` é opcional. Quando usado, o benchmark aplica o mesmo alvo
a todos os perfis. Sem ele, cada perfil mantém a resolução e o aspecto do
vídeo de entrada.

Consulte todos os argumentos disponíveis com:

```powershell
.\.venv\Scripts\python.exe -m upscaler benchmark -h
```

## Decisões de qualidade

- Um único processo por GPU.
- FP16 por padrão; `--fp32` somente para comparar resultados.
- Tile inicial 256, reduzindo automaticamente para 192, 128, 96, 64 ou 32 se houver OOM.
- FPS variável é rejeitado por padrão porque o backend frame-a-frame trabalha com FPS nominal.
- HDR é rejeitado no primeiro MVP até haver uma política explícita de tone mapping para BT.709.
- O áudio original é remapeado e recodificado para AAC no encode final.
