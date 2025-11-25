Automated Radio Disc Jockey
===========================

Overview
--------
An AI-powered virtual DJ that reads local audio files, gathers song/artist/album details, generates a radio-style introduction via an LLM, speaks the intro with TTS, and plays the track. The system also selects subsequent songs using an LLM to keep era/genre/energy consistent.

Features
--------
- Reads `.mp3`, `.flac`, `.wav`, `.ogg` files from a directory.
- Samples N songs for initial choice; subsequent picks are LLM-guided to match energy/tempo without repeating artists back-to-back.
- Retrieves metadata/summaries from Wikipedia with Last.fm and AllMusic fallbacks.
- Builds DJ intros via an LLM and speaks them using TTS.
- Threaded prep for the next song/intro while the current track plays.

Requirements
------------
- Python 3.10+
- System: `sox` (for TTS post-processing), `ffmpeg` if additional codecs are needed.
- Python: `gtts`, `mutagen`, `pygame`, `wikipedia` (`pip install -r requirements.txt`).
- Ollama running locally; model selection is automatic (`llm_wrapper.py`).

Key Modules
-----------
- `audio_utils.py`: `Song` class (metadata cache, colored display), song discovery/selection.
- `audio_file_to_details.py`: fetches Wikipedia/Last.fm/AllMusic summaries for song/artist/album.
- `llm_wrapper.py`: VRAM/model detection, model selection, LLM query, XML tag extraction.
- `next_song_selector.py`: LLM-based next-song selection (CLI and library), uses `Song` objects.
- `song_details_to_dj_intro.py`: builds and runs DJ intro prompts from a `Song` or raw text, returns `<response>` intro.
- `tts_helpers.py`: TTS utilities (gTTS/pyttsx3 + SoX) and `speak_dj_intro`.
- `playback_helpers.py`: playback utilities for pygame.
- `disc_jockey.py`: `DiscJockey` class orchestrates the loop, holds state, runs threaded next-track prep.

Usage
-----
- Full loop:
  ```
  ./disc_jockey.py /path/to/music --sample-size 5 --testing
  ```
- Metadata lookup:
  ```
  ./audio_file_to_details.py -i /path/to/song.mp3
  ```
- DJ intro generation:
  ```
  ./song_details_to_dj_intro.py -i /path/to/song.mp3
  # or
  ./song_details_to_dj_intro.py -t "A paragraph of song info"
  ```
- Next-song selection only:
  ```
  ./next_song_selector.py -c current.mp3 -d /path/to/music -n 10
  ```
- TTS smoke test:
  ```
  ./tts_helpers.py -t "Hello listeners" --engine gtts --speed 1.2
  ```

Flow
----
- Scan music directory, sample N songs for user selection (first track only).
- Extract metadata and fetch Wikipedia/Last.fm/AllMusic info.
- Choose an Ollama model automatically and generate the DJ intro via LLM.
- Speak the intro with TTS, then play the track.
- Select the next track via LLM using era/genre/energy/tempo cues, avoid same-artist repeats.
- Repeat with threaded prep for the following track.

Testing Steps
-------------
Run `./test_steps.sh` to exercise:
1) Metadata lookup
2) DJ intro generation
3) Next-song selection via LLM
4) TTS smoke test

Notes
-----
- Metadata-based selection and prompts work best with tagged MP3/FLAC files; other formats fall back to filenames.
- Temporary audio files (e.g., `temp_raw.*`, `dj_intro.mp3`) are generated during TTS; clean up as needed.
