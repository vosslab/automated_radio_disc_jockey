# Agents and Scripts Overview

This repo is split into small scripts that can be run independently or orchestrated by `disc_jockey.py`.

## Core Modules
- `audio_utils.py`
  - `Song` class caches metadata (title/artist/album/compilation/length/size).
  - `get_song_list`, `select_song` for discovery and sampling.
- `audio_file_to_details.py`
  - Extracts tags and fetches Wikipedia/Last.fm/AllMusic summaries for song/artist/album.
  - Prints results only (no prompt generation).
- `llm_wrapper.py`
  - VRAM/model detection, Ollama query, `<response>` extraction.
- `next_song_selector.py`
  - Standalone CLI to pick the next song via LLM given `--current`, `--directory`, `-n`.
  - Uses `Song` for candidate info and `llm_wrapper` for model selection/query.
- `song_details_to_dj_intro.py`
  - Builds a DJ intro prompt from a song file (metadata) or raw text, sends to LLM, and prints the `<response>` intro.
- `speak_something.py`
  - TTS utilities (gTTS/pyttsx3 + SoX tempo) and `format_intro_for_tts`.

## Orchestrator
- `disc_jockey.py`
  - Glues the modules: list/select songs (`audio_utils`), build prompt (`song_details_to_dj_intro` logic is mirrored here via metadata/basic prompt), query LLM (`llm_wrapper`), TTS/playback (`speak_something`), and next-song selection (`next_song_selector`).
  - Testing flag stops playback after a short preview.

## Helpers / Tests
- `test_steps.sh` exercises the steps: metadata lookup, DJ intro generation, next-song selection, and TTS smoke test.
- `get_random_song.sh`, `get_details.sh` are shell helpers for quick sampling.

## Usage Highlights
- Metadata only: `./audio_file_to_details.py -i song.mp3`
- DJ intro (no playback): `./song_details_to_dj_intro.py -i song.mp3` or `-t "info paragraph"`
- Next-song choice: `./next_song_selector.py -c current.mp3 -d /path/to/music -n 10`
- TTS test: `./speak_something.py -t "Hello" --speed 1.2`
- Full loop: `./disc_jockey.py -d /path/to/music -n 10 --testing`
