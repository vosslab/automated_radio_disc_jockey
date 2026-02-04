# USAGE.md

## Full loop
```bash
./disc_jockey.py -d /path/to/music -n 10 --tts-engine say --testing
```

## Metadata lookup
```bash
./audio_file_to_details.py -i /path/to/song.mp3
```

## DJ intro generation
```bash
./song_details_to_dj_intro.py -i /path/to/song.mp3
./song_details_to_dj_intro.py -t "A paragraph of song info"
```

## Next-song selection only
```bash
./next_song_selector.py -c current.mp3 -d /path/to/music -n 10
```

## TTS smoke test
```bash
./tts_helpers.py -t "Hello listeners" --engine say --speed 1.2
```

## LLM backend selection
- `DJ_LLM_BACKEND=auto` uses Apple Foundation Models if available, else Ollama.
- `DJ_LLM_BACKEND=afm` forces Apple Foundation Models.
- `DJ_LLM_BACKEND=ollama` forces Ollama.
- `OLLAMA_MODEL=your-model-name` overrides the default Ollama model selection.
