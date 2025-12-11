#!/usr/bin/env python3

# Standard Library
import argparse
import os
import re
import time
import random
import subprocess
import warnings

# PIP3 modules
warnings.filterwarnings("ignore", category=UserWarning, module="pkg_resources")
import pygame
try:
	import pyttsx3
except ImportError:
	pyttsx3 = None
from gtts import gTTS

DEFAULT_ENGINE = "say"

#============================================
def format_intro_for_tts(text: str) -> str:
	"""
	Normalize DJ intro text for TTS playback by splitting long sentences
	and adding newlines after periods and commas.

	Args:
		text (str): Raw DJ intro text.

	Returns:
		str: Cleaned text formatted for TTS.
	"""
	if not text:
		return ""

	# Normalize some punctuation and ellipsis variants
	normalized = text.replace("\u2014", ". ")
	normalized = normalized.replace("...", ".")
	normalized = normalized.replace("..", ".")

	segments = re.split(r"[.!?]", normalized)
	clean_segments = []
	for segment in segments:
		segment = segment.strip()
		if not segment:
			continue
		# Split long "X and Y" sentences into smaller chunks
		if " and " in segment:
			parts = [part.strip() for part in segment.split(" and ") if part.strip()]
			clean_segments.extend(parts)
		else:
			clean_segments.append(segment)

	if not clean_segments:
		return ""

	# Rebuild as sentences first
	result = ". ".join(clean_segments)
	result = result.strip()
	if not result.endswith("."):
		result += "."

	# Add newlines after commas and periods to help TTS pacing
	result = result.replace(", ", ", \n")
	result = result.replace(". ", ". \n")

	return result

#============================================
def _ensure_mixer_initialized() -> None:
	if not pygame.mixer.get_init():
		pygame.mixer.init()

#============================================
def text_to_speech_pyttsx3(text: str, speed: float) -> str:
	raw_wav = "temp_raw.wav"
	engine = pyttsx3.init(driverName='nsss')
	voices = engine.getProperty("voices")
	english_voices = [voice.id for voice in voices if any(lang in voice.id for lang in ["en-", "en_", "en."])]
	if not english_voices:
		raise RuntimeError("[ERROR] No English voices found!")
	selected_voice = random.choice(english_voices)
	engine.setProperty("voice", selected_voice)
	target_wpm = int(150 * speed)
	engine.setProperty("rate", target_wpm)
	engine.save_to_file(text, raw_wav)
	engine.runAndWait()
	if not os.path.exists(raw_wav):
		raise FileNotFoundError(f"[ERROR] pyttsx3 failed to generate {raw_wav}")
	return raw_wav

#============================================
def text_to_speech_gtts(text: str) -> str:
	raw_mp3 = "temp_raw.mp3"
	tts = gTTS(text=text, lang="en", slow=False)
	tts.save(raw_mp3)
	if not os.path.exists(raw_mp3):
		raise FileNotFoundError("[ERROR] gTTS failed to generate audio.")
	return raw_mp3

#============================================
def process_audio_with_sox(input_file: str, speed: float) -> str:
	processed_wav = "temp_processed.wav"
	if input_file.endswith(".mp3"):
		return _process_mp3_with_sox(input_file, processed_wav, speed)
	return _process_wav_with_sox(input_file, processed_wav, speed)

def _process_mp3_with_sox(input_file: str, output_file: str, speed: float) -> str:
	intermediate_wav = "temp_intermediate.wav"
	_command_to_wav = f"sox \"{input_file}\" \"{intermediate_wav}\""
	print(f"[sox] { _command_to_wav }")
	os.system(_command_to_wav)
	_command_process = (
		f"sox \"{intermediate_wav}\" \"{output_file}\" "
		f"tempo {speed} silence 1 0.1 1% -1 0.4 1%"
	)
	print(f"[sox] { _command_process }")
	os.system(_command_process)
	if os.path.exists(intermediate_wav):
		os.remove(intermediate_wav)
	if os.path.exists(input_file):
		os.remove(input_file)
	return output_file

def _process_wav_with_sox(input_file: str, output_file: str, speed: float) -> str:
	command = (
		f"sox \"{input_file}\" \"{output_file}\" "
		f"tempo {speed} silence 1 0.1 1% -1 0.4 1%"
	)
	print(f"[sox] {command}")
	os.system(command)
	if os.path.exists(input_file):
		os.remove(input_file)
	return output_file

#============================================
def speak_text(text: str, engine: str, save: bool, speed: float):
	_ensure_mixer_initialized()
	if engine == "pyttsx3":
		if pyttsx3 is None:
			raise RuntimeError("pyttsx3 is not installed.")
		raw_wav = text_to_speech_pyttsx3(text, speed=speed)
	elif engine == "say":
		raw_wav = text_to_speech_say(text, speed=speed)
	else:
		raw_wav = text_to_speech_gtts(text)
	print(f"[tts] Converting '{raw_wav}' via sox at {speed}x...")
	final_audio = process_audio_with_sox(raw_wav, speed)
	print(f"[tts] Playback source: {final_audio}")
	pygame.mixer.music.load(final_audio)
	pygame.mixer.music.play()
	max_duration = len(text.split()) * 0.5 * 2
	timeout = time.time() + max_duration
	while pygame.mixer.music.get_busy():
		if time.time() > timeout:
			print("Warning: Playback timeout reached. Stopping audio.")
			pygame.mixer.music.stop()
			break
		time.sleep(0.5)
	if save:
		output_file = "output.wav"
		os.rename(final_audio, output_file)
		print(f"Saved audio to {output_file}")
	else:
		if os.path.exists(final_audio):
			os.remove(final_audio)

#============================================
def speak_dj_intro(prompt: str, speed: float, engine: str | None = None) -> None:
	if not prompt or len(prompt.strip()) < 1:
		print("No intro text to speak; skipping TTS.")
		return
	engine_name = engine or DEFAULT_ENGINE
	clean_prompt = format_intro_for_tts(prompt)
	clean_prompt = re.sub(r"^[^A-Za-z0-9]+", "", clean_prompt.strip())
	clean_prompt = re.sub(r"[^A-Za-z0-9]+$", "", clean_prompt).strip()
	print(f"Speaking intro ({len(clean_prompt)} chars) at {speed}x speed...")
	try:
		speak_text(clean_prompt, engine=engine_name, save=False, speed=speed)
	except Exception as error:
		print(f"TTS playback error: {error}")
		return
	while pygame.mixer.music.get_busy():
		time.sleep(1)
def text_to_speech_say(text: str, speed: float) -> str:
	raw_aiff = "temp_say.aiff"
	target_wpm = max(80, int(150 * speed))
	command = [
		"say",
		"-r",
		str(target_wpm),
		"-o",
		raw_aiff,
		text,
	]
	print(f"[say] running: {' '.join(command)}")
	try:
		subprocess.run(command, check=True)
	except FileNotFoundError as error:
		raise RuntimeError("say command not found on this system.") from error
	if not os.path.exists(raw_aiff):
		raise RuntimeError("say command did not produce an audio file.")
	return raw_aiff

#============================================
def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Speak text using the repo TTS helpers.")
	parser.add_argument("-t", "--text", dest="text", help="Raw text to speak.")
	parser.add_argument("-f", "--file", dest="file", help="Path to a file containing text to speak.")
	parser.add_argument("--engine", choices=["say", "gtts", "pyttsx3"], default=DEFAULT_ENGINE, help="TTS engine to use.")
	parser.add_argument("--speed", type=float, default=1.2, help="Playback speed multiplier (default 1.2).")
	parser.add_argument("--save", action="store_true", help="Save the generated audio as output.mp3.")
	return parser.parse_args()

#============================================
def main() -> None:
	args = parse_args()
	text = args.text or ""
	if args.file:
		with open(args.file, "r", encoding="utf-8") as handle:
			text += (" " if text else "") + handle.read()
	if not text.strip():
		raise ValueError("Provide text via --text or --file.")
	print(f"Using engine '{args.engine}' at speed {args.speed}.")
	try:
		speak_text(text.strip(), engine=args.engine, save=args.save, speed=args.speed)
	except Exception as error:
		print(f"TTS error: {error}")

#============================================
if __name__ == "__main__":
	main()
