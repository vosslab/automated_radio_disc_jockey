# INSTALL.md

This repo expects Python 3.12 and local audio tooling for TTS playback.

## Requirements
- Python 3.12.
- `sox` for TTS post-processing.
- `ffmpeg` if you need extra audio codecs.
- Python dependencies listed in [requirements.txt](../requirements.txt).

## Python dependencies
```bash
python3.12 -m pip install -r requirements.txt
```

## LLM backends
- Ollama (local) is supported via the `ollama` CLI.
- Apple Foundation Models require Apple Silicon, macOS 26+, and Apple Intelligence enabled (see [config_apple_models.py](../config_apple_models.py)).
