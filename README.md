# Upscale Video

Ferramenta local para aumentar a resolução de vídeos com Real-ESRGAN e CUDA.

Ela foi pensada para uso simples: você escolhe um nível de qualidade e o programa cuida do resto.

## 1) Preparar o ambiente

No PowerShell, rode:

```powershell
.\scripts\bootstrap.ps1
```

Esse script cria o ambiente `.venv`, instala o PyTorch com CUDA 12.6, prepara o Real-ESRGAN e instala o FFmpeg/FFprobe local.

Para confirmar que tudo está funcionando:

```powershell
.\.venv\Scripts\python.exe -m upscaler doctor
```

## 2) Uso rápido

### Modo simples (padrão)

Se você rodar sem subcomando, o programa já entra no modo simples automaticamente.

```powershell
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel baixo
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel medio
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel alto
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel max
```

Você também pode usar o subcomando explícito:

```powershell
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --nivel alto
```

Níveis disponíveis:

- `baixo`: até 1280 px no maior lado
- `medio`: até 1920 px no maior lado
- `alto`: até 3840 px no maior lado
- `max`: usa qualidade máxima com o modelo principal

O modo simples:

- mantém a proporção do vídeo
- não faz crop
- não reduz a resolução original se ela já for grande
- salva o arquivo na mesma pasta, por exemplo `input_upscaled_medio.mp4`

### Escolher um modelo diferente

Além do nível, você pode escolher o modelo para a versão simples:

```powershell
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel alto --model RealESRGAN_x4plus
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel alto --model realesr-general-x4v3
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel alto --model realesr-animevideov3
```

Modelos disponíveis:

- `RealESRGAN_x4plus`: melhor opção geral para vídeo realista
- `realesr-general-x4v3`: melhor para vídeos comprimidos ou com ruído
- `realesr-animevideov3`: melhor para anime e ilustração

### Sem áudio no vídeo final

Se você quiser processar só a imagem e não mexer no áudio:

```powershell
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel alto --no-audio
```

Isso remove a etapa de recodificação do áudio e pode ajudar um pouco no processamento, mas o vídeo final sairá sem trilha de áudio.

## 3) Modo avançado

Use `run` quando quiser controlar mais detalhes do processo:

```powershell
.\.venv\Scripts\python.exe -m upscaler run input.mp4 output.mp4 --profile clean --tile 256 --preset slow --crf 17
```

Aqui você pode ajustar:

- perfil/modelo
- tamanho do tile
- CRF
- preset do encode
- alvo de saída
- etc.

Se quiser manter o formato original, não passe `--target`.

## 4) Verificar o vídeo

Para inspecionar o arquivo antes de processar:

```powershell
.\.venv\Scripts\python.exe -m upscaler inspect input.mp4
```

## 5) Perfis principais

Os perfis mais importantes do projeto são:

- `clean`: `RealESRGAN_x4plus` para vídeo realista e limpo
- `max`: alias para máxima qualidade usando o mesmo modelo principal
- `compressed`: `realesr-general-x4v3` para vídeo comprimido
- `anime`: `realesr-animevideov3` para animação

## 6) Benchmark

O benchmark testa um trecho curto do vídeo para comparar opções antes de processar o arquivo completo.

```powershell
.\.venv\Scripts\python.exe -m upscaler benchmark input.mp4 benchmark --seconds 5 --profiles clean compressed anime
```

Ele gera um relatório JSON na pasta indicada.

## 7) Dicas de qualidade

- Use `max` para o melhor resultado geral em vídeo realista.
- Use `compressed` para vídeos com artefatos/ruído.
- Use `anime` para conteúdo animado.
- O modo simples já é a opção mais fácil e segura para uso diário.
- O processamento mostra progresso no terminal enquanto o vídeo vai sendo processado.
