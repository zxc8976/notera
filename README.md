# NOTERA

**Open-source local-first multimodal AI note generation platform.**

NOTERA turns videos and images into structured notes using OCR and vision-language models. It is designed for developers, students, and researchers who want a self-hosted document/media understanding workflow without sending source material to a mandatory hosted AI service.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](ops/docker/docker-compose.yml)
[![Vue 3](https://img.shields.io/badge/Vue-3-42b883.svg)](source/frontend)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688.svg)](source/backend)

## Why NOTERA?

Many AI note tools depend on hosted services or text-only extraction. NOTERA provides a local-first pipeline for multimodal learning material, including lecture videos, screenshots, code, Japanese/Chinese/English text, and mixed visual content.

Its VLM-first pipeline combines scene extraction, OCR, visual understanding, filtering, deduplication, and structured note generation while remaining self-hostable.

## Features

- Video processing with scene detection, OCR, and visual summarization
- Image understanding with PaddleOCR-VL and multimodal models
- VLM-first note generation for code, slides, and mixed-language content
- Structured note generation and content deduplication
- Chinese, Japanese, and English content support
- Local model execution through Ollama
- GPU acceleration with safe CPU fallback
- Vue 3 web interface
- FastAPI backend and diagnostic endpoints
- Docker Compose deployment

## Architecture

```text
Input video / images
        |
        v
Scene extraction + OCR
        |
        v
Vision-language model analysis
        |
        v
Filtering + deduplication
        |
        v
Structured note generation
        |
        v
Vue web interface / generated output
```

The default local model is `qwen3-vl:4b`. Systems with additional VRAM can use a larger compatible model. See `docs/VLM_FIRST_ARCHITECTURE.md` and `docs/ARCHITECTURE.md` for implementation details.

## Quick start

### Requirements

- Docker and Docker Compose
- Sufficient disk space for local models
- NVIDIA GPU recommended but not required

### Start NOTERA

```bash
git clone https://github.com/zxc8976/auto-note-guardian.git
cd auto-note-guardian
cp .env.example .env
bash ops/scripts/setup_llm_services.sh
```

Alternatively, start the stack directly:

```bash
docker compose -f ops/docker/docker-compose.yml up -d
```

Then open the frontend and API documentation using the ports configured for your environment.

Useful checks:

```bash
curl http://localhost:11434/api/tags
curl http://localhost:18000/api/diagnose
```

## Repository structure

| Path | Purpose |
| --- | --- |
| `source/backend/` | FastAPI application and multimodal note pipeline |
| `source/frontend/` | Vue 3 web application |
| `ops/docker/` | Docker and Compose deployment files |
| `ops/scripts/` | Setup, diagnostics, model, and maintenance scripts |
| `docs/` | Architecture, operation, and troubleshooting documentation |
| `openspec/` | Specifications and change proposals |
| `data/` | Local models and external assets; excluded from Git |
| `var/` | Runtime output; excluded from source distribution where applicable |

## Model configuration

NOTERA is local-first. The default workflow uses Ollama with `qwen3-vl:4b`. Model selection and runtime behavior can be changed in the application configuration. See `docs/MODEL_CONFIGURATION.md` for details.

The safe environment template is available in `.env.example`. Never commit API keys, credentials, personal documents, or production secrets.

## Development

Frontend:

```bash
cd source/frontend
npm install
npm run dev
```

Frontend tests:

```bash
npm test
```

Backend entry point:

```bash
uvicorn source.backend.app.main:app --reload
```

Before contributing, read [CONTRIBUTING.md](CONTRIBUTING.md). AI-assisted contributions are welcome when reviewed and tested by the contributor.

## Documentation

- [VLM-first architecture](docs/VLM_FIRST_ARCHITECTURE.md)
- [Project structure](docs/PROJECT_STRUCTURE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Technical documentation](docs/TECHNICAL_DOCS.md)
- [Model configuration](docs/MODEL_CONFIGURATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Changelog](docs/CHANGELOG.md)

## Security

NOTERA processes user-provided files and local model workloads. Please read [SECURITY.md](SECURITY.md) before reporting vulnerabilities. Do not submit private documents, credentials, API keys, or proprietary material in issues or pull requests.

## Contributing

Bug reports, documentation improvements, model/provider compatibility work, tests, and focused feature contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

NOTERA is released under the [MIT License](LICENSE).

## Maintainer

Maintained by Lin Chiacheng (`zxc8976`).
