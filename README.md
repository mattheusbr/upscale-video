<h1 align="center">Welcome to upscale-video 👋</h1>

<p align="center">
  <a href="https://github.com/mattheusbr/upscale-video"><img src="https://img.shields.io/badge/version-0.2.0-38bdf8.svg?cacheSeconds=2592000" alt="version"></a>
  <img src="https://img.shields.io/badge/python->=3.12-3776AB.svg?logo=python&logoColor=white" alt="python">
  <img src="https://img.shields.io/badge/CUDA-12.6-76B900.svg?logo=nvidia&logoColor=white" alt="cuda">
  <img src="https://img.shields.io/badge/AI-Real--ESRGAN-FF6F00.svg" alt="real-esrgan">
  <img src="https://img.shields.io/badge/tests-29%20passed-10b981.svg" alt="tests">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="license"></a>
</p>

<p align="center">
  <strong><a href="#english">English</a></strong> • <strong><a href="#português">Português</a></strong>
</p>

> Local, quality-first video upscaling pipeline powered by Real-ESRGAN, CUDA, and an interactive cyberpunk terminal UI (VidiScale).

<p align="center">
  <img src="assets/screenshots/tui_screenshot.svg" alt="VidiScale TUI" width="100%">
</p>

---

## English

### 🏠 Homepage
[https://github.com/mattheusbr/upscale-video](https://github.com/mattheusbr/upscale-video)

### Prerequisites
- Windows 10/11 (64-bit)
- NVIDIA GPU with CUDA support
- Python `>= 3.12`
- Git (with submodule support)

### Install
Clone the repository recursively and run the bootstrap script:

```powershell
git clone --recurse-submodules https://github.com/mattheusbr/upscale-video.git
cd upscale-video
.\scripts\bootstrap.ps1
```

Verify your environment setup:
```powershell
.\.venv\Scripts\python.exe -m upscaler doctor
```

### Usage

#### 🖥️ Interactive Terminal UI (TUI)
Launch the cyberpunk dashboard to configure profiles and process videos with live hardware telemetry:
```powershell
.\.venv\Scripts\python.exe -m upscaler tui
```
*(Optionally preload a video: `.\.venv\Scripts\python.exe -m upscaler tui --input video.mp4`)*

#### ⚡ CLI Quick Start (Simple Mode)
```powershell
# Upscale using defaults (profile: clean, level: medio / 1080p)
.\.venv\Scripts\python.exe -m upscaler input.mp4

# Custom profile & resolution level
.\.venv\Scripts\python.exe -m upscaler input.mp4 --profile max --nivel alto

# Benchmark before full render
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --profile clean --benchmark
```

#### 🎛️ Profiles & Levels

| Profile | AI Model | Best For |
| :--- | :--- | :--- |
| `clean` *(default)* | `RealESRGAN_x4plus` | Real-world footage, live-action |
| `compressed` | `realesr-general-x4v3` | Videos with artifacts and compression noise |
| `anime` | `realesr-animevideov3` | 2D animation, cartoons, illustrations |
| `max` | `RealESRGAN_x4plus` | Highest fidelity (heavy compute) |

| Level (`--nivel`) | Max Dimension | Target Resolution |
| :--- | :--- | :--- |
| `baixo` | 1280 px | 720p HD |
| `medio` *(default)* | 1920 px | 1080p Full HD |
| `alto` | 3840 px | 4K UHD |
| `max` | 4x native | Pure 4x model inference |

#### 🔧 Advanced CLI Mode
```powershell
.\.venv\Scripts\python.exe -m upscaler run input.mp4 output.mp4 --profile clean --tile 256 --preset slow --crf 17
```

### Run tests
```powershell
.\.venv\Scripts\python.exe -m unittest discover tests
```

---

## Português

### 🏠 Página Inicial
[https://github.com/mattheusbr/upscale-video](https://github.com/mattheusbr/upscale-video)

### Pré-requisitos
- Windows 10/11 (64-bit)
- Placa de vídeo NVIDIA com suporte a CUDA
- Python `>= 3.12`
- Git (com suporte a submódulos)

### Instalação
Clone o repositório recursivamente e execute o script de inicialização:

```powershell
git clone --recurse-submodules https://github.com/mattheusbr/upscale-video.git
cd upscale-video
.\scripts\bootstrap.ps1
```

Confirme se o ambiente está pronto:
```powershell
.\.venv\Scripts\python.exe -m upscaler doctor
```

### Uso

#### 🖥️ Interface Interativa de Terminal (TUI)
Inicie o painel interativo cyberpunk com monitoramento de GPU/CPU em tempo real:
```powershell
.\.venv\Scripts\python.exe -m upscaler tui
```
*(Ou carregue direto com um arquivo: `.\.venv\Scripts\python.exe -m upscaler tui --input video.mp4`)*

#### ⚡ CLI Rápido (Modo Simples)
```powershell
# Upscale padrão (perfil: clean, nível: medio / 1080p)
.\.venv\Scripts\python.exe -m upscaler input.mp4

# Perfil e resolução customizados
.\.venv\Scripts\python.exe -m upscaler input.mp4 --profile max --nivel alto

# Benchmark antes do processamento completo
.\.venv\Scripts\python.exe -m upscaler simple input.mp4 --profile clean --benchmark
```

#### 🎛️ Perfis e Níveis

| Perfil | Modelo de IA | Indicação |
| :--- | :--- | :--- |
| `clean` *(padrão)* | `RealESRGAN_x4plus` | Vídeos realistas em geral |
| `compressed` | `realesr-general-x4v3` | Vídeos com ruído ou artefatos de compressão |
| `anime` | `realesr-animevideov3` | Desenhos, animes e animações 2D |
| `max` | `RealESRGAN_x4plus` | Detalhe máximo e maior fidelidade |

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

### Executar testes
```powershell
.\.venv\Scripts\python.exe -m unittest discover tests
```

---

### Author / Autor
👤 **Matheus Bruno**
- GitHub: [@mattheusbr](https://github.com/mattheusbr)

### 🤝 Contributing / Contribuição
Contribuições, issues e sugestões de melhorias são muito bem-vindas!  
Sinta-se à vontade para abrir uma [issue](https://github.com/mattheusbr/upscale-video/issues).

### Show your support / Apoie o projeto
Deixe uma ⭐️ se este projeto te ajudou!

### 📝 License / Licença
Copyright © 2026 [Matheus Bruno](https://github.com/mattheusbr).  
Distribuído sob a licença [MIT](LICENSE).
