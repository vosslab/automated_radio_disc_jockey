#!/usr/bin/env python3

import io
import os
import re
import time
import random
import argparse
import subprocess

import pygame
import pyttsx3
#from gtts import gTTS

#============================================
def get_input_text(args) -> str:
	"""
	Handles text input from CLI, file, or interactive multiline mode.
	Ends interactive input when the user enters two blank lines in a row.
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
				blank_count = 0  # Reset counter if a non-blank line is entered
				lines.append(line)

		return "\n".join(lines).strip()
	else:
		raise ValueError("Must provide text with -t, a file with -f, or use interactive mode with -i.")

#============================================
def clean_text(text: str, raw: bool) -> str:
	"""
	Cleans the text by removing non-spoken elements unless --raw is specified.

	Args:
		text (str): The raw input text.
		raw (bool): If True, skip cleaning.

	Returns:
		str: Cleaned text.
	"""
	if raw:
		return text

	# Remove text in parentheses and brackets, replace em-dashes with ", "
	text = text.replace("\n", ". ")
	text = text.replace("..", ".")
	text = re.sub(r"\(.*?\)|\[.*?\]", "", text)
	text = text.replace("—", ", ")
	return text.strip()

def text_to_speech(text: str, speed: float = 1.0) -> str:
	"""
	Converts text to speech using pyttsx3, saves as WAV, then converts to MP3.
	"""
	raw_wav = "temp_raw.wav"
	output_mp3 = "temp_raw.mp3"

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

	# Convert WAV → MP3
	print(f"[INFO] Converting {raw_wav} to MP3...")
	subprocess.run(["sox", raw_wav, output_mp3], check=True)

	# Cleanup WAV file after conversion
	os.remove(raw_wav)

	return output_mp3

#============================================
def process_audio_with_sox(input_mp3: str, speed: float) -> str:
	"""
	Processes an audio file using SoX to adjust tempo.

	Args:
		input_mp3 (str): Path to the input MP3 file.
		speed (float): Playback speed multiplier.

	Returns:
		str: Path to the processed MP3 file.
	"""
	if speed == 1.0:
		return input_mp3  # No processing needed

	processed_mp3 = "temp_processed.mp3"
	print("Processing audio with SoX")
	subprocess.run(["sox", input_mp3, processed_mp3, "tempo", str(speed)], check=True)
	return processed_mp3

#============================================
def speak_text(text: str, save: bool, speed: float):
	"""
	Converts text to speech, applies tempo adjustment using SoX, and plays the audio.

	Args:
		text (str): Text to be spoken.
		save (bool): Whether to save the generated speech.
		speed (float): Playback speed multiplier.
	"""
	pygame.mixer.init()

	# Convert text to speech
	raw_mp3 = text_to_speech(text, speed=speed)

	# Adjust speed using SoX if necessary
	audio_file = process_audio_with_sox(raw_mp3, speed)

	# Load and play the processed audio
	pygame.mixer.music.load(audio_file)
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
		os.rename(audio_file, output_file)
		print(f"Saved audio to {output_file}")

	# Clean up temporary files
	for f in [raw_mp3, "temp_processed.mp3"]:
		if os.path.exists(f):
			os.remove(f)

#============================================
def main():
	# Set up argument parsing
	parser = argparse.ArgumentParser(description="Convert text to speech using gTTS.")
	parser.add_argument("-t", "--text", type=str, help="Text to speak.")
	parser.add_argument("-f", "--file", type=str, help="File containing text to speak.")
	parser.add_argument("-i", "--interactive", action="store_true", help="Enter interactive multiline input mode.")
	parser.add_argument("-s", "--save", action="store_true", help="Save speech to 'output.mp3'.")
	parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier (e.g., 1.3 for faster speech).")
	parser.add_argument("--raw", action="store_true", help="Disable text cleaning.")

	args = parser.parse_args()

	# Get input text
	text = get_input_text(args)

	# Clean text unless --raw is specified
	text = text.strip()
	cleaned_text = clean_text(text, args.raw)
	if not args.raw and cleaned_text != text:
		print(f"Cleaned text: {cleaned_text}")
		text = cleaned_text

	# Speak the text with optional saving and speed adjustment
	speak_text(text, args.save, args.speed)

#============================================
if __name__ == "__main__":
	main()
