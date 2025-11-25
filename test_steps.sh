#!/usr/bin/env bash

set -euo pipefail

MUSIC_DIR="${MUSIC_DIR:-$HOME/Documents/ipod}"
SAMPLE_FILE="$(ls "$MUSIC_DIR"/*.mp3 2>/dev/null | sort -R | head -n 1 || true)"

if [[ -z "$SAMPLE_FILE" ]]; then
	echo "No mp3 files found in $MUSIC_DIR" >&2
	exit 1
fi

echo "Using sample file: $SAMPLE_FILE"

echo "Step 1: Extended Metadata gathering"
./audio_file_to_details.py -i "$SAMPLE_FILE" -p

echo "Step 2: prompt generation from metadata for DJ intro"
./song_details_to_dj_intro.py -i "$SAMPLE_FILE"

echo "Step 3: Next song selector (LLM) from directory"
./next_song_selector.py -c "$SAMPLE_FILE" -d "$MUSIC_DIR" -n 15

echo "Step 4: TTS smoke test"
./speak_something.py -t "Radio check, one two three." --engine gtts --speed 1.2 --raw
