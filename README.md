# Upscale Video

Ferramenta local para aumentar a resolução de vídeos com Real-ESRGAN e CUDA.

Ela foi pensada para uso simples: o comando padrão entra no modo `simple`, com nível médio por padrão, mas ainda permite controlar perfil, GPU, áudio e benchmark rapidamente.

## 1) Repositórios e dependência do Real-ESRGAN

Este projeto usa o fork do Real-ESRGAN como dependência externa via submodule:

- projeto principal: https://github.com/mattheusbr/upscale-video
- fork do Real-ESRGAN: https://github.com/mattheusbr/Real-ESRGAN
- upstream original: https://github.com/xinntao/Real-ESRGAN

Se você clonar este projeto do zero, o submodule precisa ser inicializado:

```powershell
git clone https://github.com/mattheusbr/upscale-video.git
cd upscale-video
git submodule update --init --recursive
```

Se você já clonou e quiser atualizar o submodule depois:

```powershell
git pull --recurse-submodules
git submodule update --init --recursive
```

## 2) Preparar o ambiente

No PowerShell, rode:

```powershell
.\scripts\bootstrap.ps1
```

Esse script cria o ambiente `.venv`, instala o PyTorch com CUDA 12.6, prepara o Real-ESRGAN e instala o FFmpeg/FFprobe local.

Para confirmar que tudo está funcionando:

```powershell
.\.venv\Scripts\python.exe -m upscaler doctor
```

## 3) Uso básico e modo simples

### Modo simples padrão

Se você rodar sem subcomando, o programa já entra em `simple` e usa `--nivel medio` por padrão.

```powershell
.\.venv\Scripts\python.exe -m upscaler input.mp4
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel baixo
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel medio
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel alto
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel max
```

Também dá para usar o subcomando explícito:

```powershell
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --nivel alto
```

Níveis disponíveis:

- `baixo`: até 1280 px no maior lado
- `medio`: até 1920 px no maior lado
- `alto`: até 3840 px no maior lado
- `max`: qualidade máxima, com saída pesada e detalhada

O modo simples:

- mantém a proporção do vídeo
- não faz crop
- não reduz a resolução original se ela já for grande
- salva o arquivo na mesma pasta, por exemplo `input_upscaled_medio.mp4`

### Perfil amigável e alias

O parâmetro `--profile` aceita nomes amigáveis e também aliases do modelo:

```powershell
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --profile clean --nivel medio
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --profile max --nivel max
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --profile compressed --nivel alto
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --profile anime --nivel medio
```

Aliases suportados:

- `clean`, `real`, `realesr`
- `max`, `high`, `heavy`
- `compressed`, `general`, `general-x4v3`
- `anime`, `anime-video`

Combinações válidas:

- `--profile` + `--nivel`
- `--profile` + `--benchmark`
- `--profile` + `--nivel` + `--benchmark`

### Modelos por perfil

```powershell
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel alto --profile clean
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel alto --profile compressed
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel alto --profile anime
```

Mapeamento:

- `clean` → `RealESRGAN_x4plus`
- `compressed` → `realesr-general-x4v3`
- `anime` → `realesr-animevideov3`
- `max` → `RealESRGAN_x4plus` em qualidade máxima

### Benchmark no modo simples

Você pode testar rapidamente um perfil com um trecho curto antes do processamento completo:

```powershell
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --profile max --nivel medio --benchmark
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --profile compressed --nivel alto --benchmark
```

Isso gera uma pasta de benchmark e um JSON com o resultado do trecho testado.

### Sem áudio no vídeo final

Se você quiser processar só a imagem e não mexer no áudio:

```powershell
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel alto --no-audio
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --profile anime --nivel medio --no-audio
```

### Escolher a GPU

Se a máquina tiver mais de uma GPU, você pode escolher qual dispositivo usar:

```powershell
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel max --device cuda:1
```

Também funciona com um índice puro:

```powershell
.\.venv\Scripts\python.exe -m upscaler input.mp4 --nivel medio --device 1
```

## 4) Modo avançado

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

## 5) Verificar o vídeo

Para inspecionar o arquivo antes de processar:

```powershell
.\.venv\Scripts\python.exe -m upscaler inspect input.mp4
```

## 6) Benchmark avançado

O benchmark testa um trecho curto do vídeo para comparar opções antes de processar o arquivo completo.

```powershell
.\.venv\Scripts\python.exe -m upscaler benchmark input.mp4 benchmark --seconds 5 --profiles clean compressed anime
```

Ele gera um relatório JSON na pasta indicada.

## 7) Interface TUI

A ferramenta também oferece uma interface interativa no terminal usando Textual:

```powershell
.\.venv\Scripts\python.exe -m upscaler tui
```

Opcionalmente você pode pré-carregar um arquivo:

```powershell
.\.venv\Scripts\python.exe -m upscaler tui --input input.mp4
```

A TUI permite:

- selecionar perfil e nível
- visualizar o progresso em tempo real
- iniciar o processamento com um único clique
- acompanhar status e mensagens do pipeline

## 8) Build e release

O projeto já inclui um script de empacotamento para release:

```powershell
.\scripts\build_release.ps1
```

Esse script:

- cria/usa o ambiente `.venv`
- instala as dependências de empacotamento
- roda `python -m build`
- produz artefatos em `dist/`

Após o build, você pode distribuir o pacote gerado com o comando:

```powershell
.\.venv\Scripts\python.exe -m pip install dist\upscale_video-*.whl
```

## 9) Dicas de qualidade

- Use `max` para o melhor resultado geral em vídeo realista.
- Use `compressed` para vídeos com artefatos/ruído.
- Use `anime` para conteúdo animado.
- O modo simples já é a opção mais fácil e segura para uso diário.
- O processamento mostra progresso no terminal e também na TUI.
