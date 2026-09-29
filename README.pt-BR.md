<h1 align="center">Bem-vindo ao upscale-video 👋</h1>

<p align="center">
  <a href="https://github.com/mattheusbr/upscale-video"><img src="https://img.shields.io/badge/versão-0.2.0-38bdf8.svg?cacheSeconds=2592000" alt="versão"></a>
  <img src="https://img.shields.io/badge/python->=3.12-3776AB.svg?logo=python&logoColor=white" alt="python">
  <img src="https://img.shields.io/badge/CUDA-12.6-76B900.svg?logo=nvidia&logoColor=white" alt="cuda">
  <img src="https://img.shields.io/badge/IA-Real--ESRGAN-FF6F00.svg" alt="real-esrgan">
  <img src="https://img.shields.io/badge/testes-29%20aprovados-10b981.svg" alt="testes">
  <a href="LICENSE"><img src="https://img.shields.io/badge/licença-MIT-green.svg" alt="licença"></a>
</p>

<p align="center">
  <a href="README.md">English</a> • <strong>Português (Brasil)</strong>
</p>

> Pipeline local e de alta qualidade para upscale de vídeos utilizando Real-ESRGAN, aceleração por hardware CUDA e uma interface interativa de terminal cyberpunk (VidiScale).

<p align="center">
  <img src="assets/screenshots/tui_screenshot.svg" alt="VidiScale TUI" width="100%">
</p>

---

### 🏠 Página Inicial
[https://github.com/mattheusbr/upscale-video](https://github.com/mattheusbr/upscale-video)

### Pré-requisitos
- **Sistema Operacional**: Windows 10/11 (64-bit)
- **Placa de Vídeo**: GPU NVIDIA com suporte a CUDA
- **Python**: `>= 3.12`
- **Git**: Git com suporte a submódulos ativado

### Instalação
Clone o repositório de forma recursiva com todos os submódulos e execute o script de inicialização automática:

```powershell
git clone --recurse-submodules https://github.com/mattheusbr/upscale-video.git
cd upscale-video
.\scripts\bootstrap.ps1
```

Confirme se todas as dependências e o driver da GPU estão prontos:
```powershell
.\.venv\Scripts\python.exe -m upscaler doctor
```

### Gerar o executável Windows
Com Python 3.12 instalado e o submódulo Real-ESRGAN inicializado, gere a distribuição com:
```powershell
git submodule update --init --recursive
.\scripts\build_exe.ps1
```
O resultado fica em `dist\upscale\`. Distribua a **pasta inteira**, não apenas `upscale.exe` — ela contém o runtime CUDA, os modelos, o Real-ESRGAN e o FFmpeg.

```powershell
.\dist\upscale\upscale.exe tui
.\dist\upscale\upscale.exe video.mp4
.\dist\upscale\upscale.exe doctor
```

### Uso

#### 🖥️ Interface Interativa de Terminal (TUI)
Inicie o painel interativo cyberpunk com telemetria em tempo real de CPU/GPU e controle dinâmico do pipeline:
```powershell
.\.venv\Scripts\python.exe -m upscaler tui
```
*(Ou pré-carregue um vídeo diretamente: `.\.venv\Scripts\python.exe -m upscaler tui --input video.mp4`)*

#### ⚡ CLI Rápido (Modo Simples)
```powershell
# Upscale com configurações padrão (perfil: clean, nível: medio / 1080p)
.\.venv\Scripts\python.exe -m upscaler input.mp4

# Perfil e nível de resolução customizados
.\.venv\Scripts\python.exe -m upscaler input.mp4 --profile max --nivel alto

# Teste prévio com benchmark rápido antes da renderização completa
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --profile clean --benchmark
```

#### 🎛️ Perfis e Níveis

| Perfil | Modelo de IA | Indicação |
| :--- | :--- | :--- |
| `clean` *(padrão)* | `RealESRGAN_x4plus` | Vídeos realistas em geral, filmagens e gravações |
| `compressed` | `realesr-general-x4v3` | Vídeos com ruído visual ou artefatos de compressão |
| `anime` | `realesr-animevideov3` | Desenhos, animes e animações 2D |
| `max` | `RealESRGAN_x4plus` | Fidelidade e detalhamento máximos (processamento pesado) |

| Nível (`--nivel`) | Resolução Máxima | Alvo |
| :--- | :--- | :--- |
| `baixo` | 1280 px | 720p HD |
| `medio` *(padrão)* | 1920 px | 1080p Full HD |
| `alto` | 3840 px | 4K UHD |
| `max` | Escala nativa (4x) | Inferência direta 4x do modelo |

#### 🔧 Modo Avançado
```powershell
.\.venv\Scripts\python.exe -m upscaler run input.mp4 output.mp4 --profile clean --tile 256 --preset slow --crf 17
```

### Executar Testes
```powershell
.\.venv\Scripts\python.exe -m unittest discover tests
```

### Autor
👤 **Matheus Bruno**
- GitHub: [@mattheusbr](https://github.com/mattheusbr)

### 🤝 Contribuição
Contribuições, issues e sugestões de melhorias são muito bem-vindas!  
Sinta-se à vontade para abrir uma [issue](https://github.com/mattheusbr/upscale-video/issues).

### Apoie o projeto
Deixe uma ⭐️ se este projeto te ajudou!

### 📝 Licença
- **upscale-video**: Este projeto é distribuído sob a [Licença MIT](LICENSE) © 2026 Matheus Bruno.
- **Fork do Real-ESRGAN**: O submódulo integrado do [fork do Real-ESRGAN](https://github.com/mattheusbr/Real-ESRGAN) (projeto original: [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)) é distribuído sob a [Licença BSD 3-Clause](vendor/Real-ESRGAN/LICENSE) © 2021 Xintao Wang.
