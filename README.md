# Automated Radio Disc Jockey 🎵🤖

An AI-powered virtual DJ that curates and announces songs like a real radio host using local music files, Wikipedia/Last.fm lookups, an Ollama LLM prompt, and text-to-speech.

## Features
- Reads `.mp3`, `.flac`, `.wav`, `.ogg` files from a directory.
- Samples N songs (default 5) for you to choose; guards against bad input.
- Gathers song/artist/album info from Wikipedia with Last.fm fallback and AllMusic search links.
- Builds a DJ-style intro prompt (metadata-aware) and sends it to an Ollama model chosen automatically.
- Speaks the intro (gTTS/pygame) then plays the track.
- Suggests the next track based on simple artist/album similarity.

## Requirements
- Python 3.10+
- System packages: `sox` (for TTS post-processing in `speak_something.py`), `ffmpeg` if you plan to add more codecs.
- Python packages: `gtts`, `mutagen`, `pygame`, `wikipedia` (install with `pip install -r requirements.txt`).
- Ollama running locally; model selection is automatic via `llm_wrapper.py` (defaults to `llama3.2:1b-instruct-q4_K_M` and scales up with VRAM).

## Setup
```bash
pip install -r requirements.txt
# optional: brew install sox ffmpeg   # macOS example
```

Place your music files in a directory you will point the scripts at (defaults are not hard-coded).

## Usage
- Full DJ loop:
  ```bash
  ./disc_jockey.py /path/to/music --sample-size 5
  # add --no-metadata-prompt to skip detailed metadata prompt building
  # add --testing to stop songs after ~20s
  ```
- Build a DJ prompt for one file:
  ```bash
  ./audio_file_to_details.py -i /path/to/song.mp3
  # add -d for verbose lookups
  ```
- Generate a DJ intro for a file or raw text:
  ```bash
  ./song_details_to_dj_intro.py -i /path/to/song.mp3
  # or
  ./song_details_to_dj_intro.py -t "A paragraph of song info"
  ```
- Speak arbitrary text (TTS test):
  ```bash
  ./speak_something.py -t "Hello listeners" --engine gtts --speed 1.2
  ```
- Shell helpers:
  - `./get_random_song.sh` selects a random mp3 from `$HOME/Documents/ipod/`.
  - `./get_details.sh` runs the metadata/prompt builder on that random pick.

## Flow
1) Scan music directory and sample N songs for user selection.  
2) Extract metadata, fetch Wikipedia/Last.fm info, and build a DJ prompt.  
3) Choose an Ollama model automatically and generate intro text.  
4) Speak the intro via TTS, then play the selected track.  
5) Suggest a similar next track using artist/album overlap.  
6) Repeat the loop.  

## Notes
- Metadata parsing for similarity and prompts works best with MP3/FLAC tags; other formats fall back to filenames.
- If Wikipedia lookups fail, Last.fm wiki pages are tried; otherwise, AllMusic search links are provided.
- Temporary audio files (e.g., `temp_raw.*`, `dj_intro.mp3`) are created during TTS; clean up as needed.

## Testing individual steps
- Run `./test_steps.sh` to exercise:
  1) Metadata lookup
  2) DJ intro generation
  3) Next-song selection via LLM
  4) TTS smoke test
