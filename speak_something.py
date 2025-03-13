#!/usr/bin/env python3

import io
import os
import re
import time
import random
import argparse
import subprocess

import pygame
try:
	import pyttsx3
except ImportError:
	pass
from gtts import gTTS

#============================================
def get_input_text(args) -> str:
	"""
	Handles text input from CLI, file, or interactive multiline mode.
	"""
	if args.file:
		with open(args.file, "r", encoding="utf-8") as f:
			return f.read().strip()
	elif args.text:
		return args.text.strip()
	elif args.interactive:
		print("Enter your text (Press Enter twice on a blank line to submit):")
		lines = []
		blank_count = 0
		while True:
			line = input()
			if line.strip() == "":
				blank_count += 1
				if blank_count == 2:
					break
			else:
				blank_count = 0
				lines.append(line)
		return "\n".join(lines).strip()
	else:
		raise ValueError("Provide text with -t, a file with -f, or use -i for interactive mode.")

#============================================
def clean_text(text: str, raw: bool) -> str:
	"""
	Cleans the text by removing non-spoken elements unless --raw is specified.
	"""
	if raw:
		return text
	text = text.replace("\n", ". ")
	text = text.replace("..", ".")
	text = re.sub(r"\(.*?\)|\[.*?\]", "", text)  # Remove brackets/parentheses
	text = text.replace("—", ", ")
	return text.strip()

#============================================
def text_to_speech_pyttsx3(text: str, speed: float) -> str:
	"""
	Converts text to speech using pyttsx3 and saves it as a WAV file.
	"""
	raw_wav = "temp_raw.wav"

	print("[INFO] Initializing pyttsx3 engine...")
	engine = pyttsx3.init(driverName='nsss')

	# List available voices and filter for English
	voices = engine.getProperty("voices")
	english_voices = [voice.id for voice in voices if any(lang in voice.id for lang in ["en-", "en_", "en."])]

	if not english_voices:
		raise RuntimeError("[ERROR] No English voices found!")

	# Select a random English voice
	selected_voice = random.choice(english_voices)
	engine.setProperty("voice", selected_voice)
	print(f"[INFO] Using voice: {selected_voice}")

	# Set speed (default ~150 WPM, adjust based on speed multiplier)
	target_wpm = int(150 * speed)
	engine.setProperty("rate", target_wpm)

	print(f"[INFO] Saving speech to {raw_wav}...")
	engine.save_to_file(text, raw_wav)
	engine.runAndWait()

	# Ensure WAV file exists before conversion
	if not os.path.exists(raw_wav):
		raise FileNotFoundError(f"[ERROR] pyttsx3 failed to generate {raw_wav}")

	return raw_wav

#============================================
def text_to_speech_gtts(text: str) -> str:
	"""Converts text to speech using gTTS and saves it as an MP3 file."""
	raw_mp3 = "temp_raw.mp3"

	print("[INFO] Generating speech with gTTS...")
	tts = gTTS(text=text, lang="en", slow=False)
	tts.save(raw_mp3)

	if not os.path.exists(raw_mp3):
		raise FileNotFoundError("[ERROR] gTTS failed to generate audio.")

	return raw_mp3

def process_audio_with_sox(input_file: str, speed: float) -> str:
	"""Processes audio with SoX: adjusts tempo and removes silence."""
	processed_mp3 = "temp_processed.mp3"

	print("[INFO] Processing audio with SoX...")

	# Check if input is MP3 (gTTS case) or WAV (pyttsx3 case)
	if input_file.endswith(".mp3"):
		intermediate_wav = "temp_intermediate.wav"

		# Convert MP3 to WAV before SoX processing
		subprocess.run(["sox", input_file, intermediate_wav], check=True)

		# Ensure WAV file exists before proceeding
		if not os.path.exists(intermediate_wav):
			raise FileNotFoundError("[ERROR] Failed to convert MP3 to WAV for SoX processing.")

		input_file = intermediate_wav  # Now process as WAV

	# SoX processing: Adjust tempo and remove silence
	sox_cmd = [
		"sox", input_file, processed_mp3,
		"tempo", str(speed),
		"silence", "1", "0.1", "1%", "-1", "0.1", "1%"
	]
	subprocess.run(sox_cmd, check=True)

	# Cleanup: Remove intermediate WAV only if it was created
	if input_file == "temp_intermediate.wav" and os.path.exists(input_file):
		os.remove(input_file)

	# Cleanup: Remove original input file (raw WAV or MP3)
	if os.path.exists(input_file):
		os.remove(input_file)

	return processed_mp3

#============================================
def speak_text(text: str, engine: str, save: bool, speed: float):
	"""
	Converts text to speech using the chosen engine, applies tempo adjustment,
	and plays the audio.

	Args:
		text (str): Text to be spoken.
		engine (str): Selected TTS engine (pyttsx3 or gTTS).
		save (bool): Whether to save the generated speech.
		speed (float): Playback speed multiplier.
	"""
	pygame.mixer.init()

	# Convert text to speech based on selected engine
	if engine == "pyttsx3":
		raw_wav = text_to_speech_pyttsx3(text, speed=speed)
	else:  # Default to gTTS
		raw_wav = text_to_speech_gtts(text)

	# Process with SoX
	final_mp3 = process_audio_with_sox(raw_wav, speed)

	# Load and play the processed audio
	pygame.mixer.music.load(final_mp3)
	pygame.mixer.music.play()

	# Timeout settings (estimate: 0.5 sec per word, doubled)
	max_duration = len(text.split()) * 0.5 * 2
	timeout = time.time() + max_duration

	# Wait until playback is complete or timeout occurs
	while pygame.mixer.music.get_busy():
		if time.time() > timeout:
			print("Warning: Playback timeout reached. Stopping audio.")
			pygame.mixer.music.stop()
			break
		time.sleep(0.5)

	# Optionally save the final output
	if save:
		output_file = "output.mp3"
		os.rename(final_mp3, output_file)
		print(f"Saved audio to {output_file}")
	else:
		# Clean up temp files
		os.remove(final_mp3)

#============================================
def main():
	# Set up argument parsing
	parser = argparse.ArgumentParser(description="Convert text to speech with gTTS or pyttsx3.")

	# Input methods
	parser.add_argument("-t", "--text", type=str, help="Text to speak.")
	parser.add_argument("-f", "--file", type=str, help="File containing text to speak.")
	parser.add_argument("-i", "--interactive", action="store_true", help="Enter interactive multiline input mode.")

	# Options
	parser.add_argument("-s", "--save", action="store_true", help="Save speech to 'output.mp3'.")
	parser.add_argument("--speed", type=float, default=1.25, help="Playback speed multiplier (e.g., 1.3 for faster speech).")
	parser.add_argument("--raw", action="store_true", help="Disable text cleaning.")

	# Engine choice
	parser.add_argument(
		"--engine", choices=["gtts", "pyttsx3"], default="gtts",
		help="Choose speech engine: 'gtts' (default) or 'pyttsx3'."
	)

	args = parser.parse_args()

	# Get input text
	text = get_input_text(args)

	# Clean text unless --raw is specified
	text = text.strip()
	cleaned_text = clean_text(text, args.raw)
	if not args.raw and cleaned_text != text:
		print(f"Cleaned text: {cleaned_text}")
		text = cleaned_text

	# Speak the text
	speak_text(text, args.engine, args.save, args.speed)

#============================================
if __name__ == "__main__":
	main()
