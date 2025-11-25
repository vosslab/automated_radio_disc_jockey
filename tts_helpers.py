#!/usr/bin/env python3

# Standard Library
import os
import re
import time
import random

# PIP3 modules
import pygame
try:
	import pyttsx3
except ImportError:
	pyttsx3 = None
from gtts import gTTS

#============================================
def format_intro_for_tts(text: str) -> str:
	if not text:
		return ""
	normalized = text.replace("—", ". ").replace("..", ".").replace("...", ".")
	segments = re.split(r"[.!?]", normalized)
	clean_segments = []
	for segment in segments:
		segment = segment.strip()
		if not segment:
			continue
		if " and " in segment:
			parts = [part.strip() for part in segment.split(" and ") if part.strip()]
			clean_segments.extend(parts)
		else:
			clean_segments.append(segment)
	result = ". ".join(clean_segments)
	if not result.endswith("."):
		result += "."
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
	processed_mp3 = "temp_processed.mp3"
	if input_file.endswith(".mp3"):
		return _process_mp3_with_sox(input_file, processed_mp3, speed)
	return _process_wav_with_sox(input_file, processed_mp3, speed)

def _process_mp3_with_sox(input_file: str, output_file: str, speed: float) -> str:
	intermediate_wav = "temp_intermediate.wav"
	os.system(f"sox \"{input_file}\" \"{intermediate_wav}\"")
	os.system(f"sox \"{intermediate_wav}\" \"{output_file}\" tempo {speed} silence 1 0.1 1% -1 0.1 1%")
	if os.path.exists(intermediate_wav):
		os.remove(intermediate_wav)
	if os.path.exists(input_file):
		os.remove(input_file)
	return output_file

def _process_wav_with_sox(input_file: str, output_file: str, speed: float) -> str:
	os.system(f"sox \"{input_file}\" \"{output_file}\" tempo {speed} silence 1 0.1 1% -1 0.1 1%")
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
	else:
		raw_wav = text_to_speech_gtts(text)
	final_mp3 = process_audio_with_sox(raw_wav, speed)
	pygame.mixer.music.load(final_mp3)
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
		output_file = "output.mp3"
		os.rename(final_mp3, output_file)
		print(f"Saved audio to {output_file}")
	else:
		if os.path.exists(final_mp3):
			os.remove(final_mp3)

#============================================
def speak_dj_intro(prompt: str, speed: float) -> None:
	if not prompt or len(prompt.strip()) < 1:
		print("No intro text to speak; skipping TTS.")
		return
	clean_prompt = format_intro_for_tts(prompt)
	print(f"Speaking intro ({len(clean_prompt)} chars) at {speed}x speed...")
	try:
		speak_text(clean_prompt, engine="gtts", save=False, speed=speed)
	except Exception as error:
		print(f"TTS playback error: {error}")
		return
	while pygame.mixer.music.get_busy():
		time.sleep(1)
