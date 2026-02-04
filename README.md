# Automated Radio Disc Jockey

Automated Radio Disc Jockey is an AI-powered local DJ for people who want a radio-style playback loop: it reads local audio files, builds a spoken intro with an LLM, speaks it with TTS, and plays the track while queuing the next selection.

## Documentation
- [docs/INSTALL.md](docs/INSTALL.md): Setup and dependencies.
- [docs/USAGE.md](docs/USAGE.md): CLI usage and examples.
- [docs/CHANGELOG.md](docs/CHANGELOG.md): User-facing changes by date.
- [docs/REPO_STYLE.md](docs/REPO_STYLE.md): Repo conventions.
- [docs/PYTHON_STYLE.md](docs/PYTHON_STYLE.md): Python style rules.
- [docs/MARKDOWN_STYLE.md](docs/MARKDOWN_STYLE.md): Markdown rules for this repo.

## Quick start
```bash
python3.12 -m pip install -r requirements.txt
./disc_jockey.py -d /path/to/music -n 5 --tts-engine say --testing
```

## Testing
- `./test_steps.sh`
