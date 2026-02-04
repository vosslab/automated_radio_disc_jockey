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
try:
	from rich.console import Console
	RICH_CONSOLE = Console()
except ImportError:
	Console = None
	RICH_CONSOLE = None

DEFAULT_ENGINE = "say"
TTS_VOLUME_GAIN = 1.15

#============================================
def format_intro_for_tts(text: str) -> str:
	"""
	Normalize DJ intro text for TTS playback by splitting long sentences
	and adding newlines after periods and commas when it will not split short lists.

	Args:
		text (str): Raw DJ intro text.

	Returns:
		str: Cleaned text formatted for TTS.
	"""
	if not text:
		return ""

	trimmed = _strip_fact_trivia_lines(text)
	trimmed = _strip_boilerplate_intro(trimmed)
	if not trimmed:
		return ""

	# Normalize some punctuation and ellipsis variants
	normalized = trimmed.replace("\u2014", ". ")
	normalized = normalized.replace("...", ".")
	normalized = normalized.replace("..", ".")

	segments = re.split(r"[.!?]", normalized)
	clean_segments = []
	for segment in segments:
		segment = segment.strip()
		if not segment:
			continue
		# Split long "X and Y" sentences into smaller chunks
		#if " and " in segment:
		#	parts = [part.strip() for part in segment.split(" and ") if part.strip()]
		#	clean_segments.extend(parts)
		#else:
		clean_segments.append(segment)

	if not clean_segments:
		return ""

	# Rebuild as sentences first
	result = ". ".join(clean_segments)
	result = result.strip()
	if not result.endswith("."):
		result += "."

	# Add newlines after commas when it is not a short list.
	result = _insert_pacing_linebreaks(result)
	result = result.replace(". ", ". \n")

	return result

#============================================
def _strip_fact_trivia_lines(text: str) -> str:
	"""
	Remove FACT/TRIVIA lines so they are not spoken.
	"""
	if not text:
		return ""
	lines = []
	for line in text.splitlines():
		strip_line = line.strip()
		if re.match(r"^(fact|trivia)\s*:", strip_line, flags=re.IGNORECASE):
			continue
		lines.append(line)
	return "\n".join(lines).strip()

#============================================
def _strip_boilerplate_intro(text: str) -> str:
	"""
	Remove the repetitive "Ladies and gentlemen, welcome to the show" opener.
	"""
	if not text:
		return ""
	pattern = r"^\s*ladies and gentlemen,?\s*welcome to[^.!?]*[.!?]\s*"
	return re.sub(pattern, "", text, flags=re.IGNORECASE).lstrip()

#============================================
def _print_say_command(command: list[str], text: str, show_text: bool = False) -> None:
	command_prefix = " ".join(command[:-1] if command and text and command[-1] == text else command)
	if RICH_CONSOLE:
		RICH_CONSOLE.print(f"[say] running: {command_prefix}")
	else:
		print(f"[say] running: {command_prefix}")

#============================================
def _insert_pacing_linebreaks(text: str) -> str:
	"""
	Insert line breaks after commas when they are not part of short item lists.
	"""
	if not text:
		return ""

	result_chars = []
	index = 0
	while index < len(text):
		char = text[index]
		if char == "," and index + 1 < len(text) and text[index + 1] == " ":
			tail = _slice_to_sentence_end(text[index + 1:])
			if _comma_is_list_like(tail):
				result_chars.append(", ")
			else:
				result_chars.append(", \n")
			index += 2
			continue
		result_chars.append(char)
		index += 1
	return "".join(result_chars)

#============================================
def _slice_to_sentence_end(text: str) -> str:
	"""
	Return text up to the next sentence-ending punctuation mark.
	"""
	match = re.search(r"[.!?]", text)
	if match:
		return text[:match.start()]
	return text

#============================================
def _comma_is_list_like(tail: str) -> bool:
	"""
	Heuristic for short lists like "apples, bananas, and pears".
	"""
	lookahead = tail[:40]
	if re.match(r"\s*(and|or)\s+\w+", lookahead):
		return True
	if "," in lookahead:
		return True
	if re.search(r"\b(and|or)\b", lookahead):
		return True
	return False

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
	output_file = "temp_processed.wav"
	command = (
		f"sox \"{input_file}\" \"{output_file}\" "
		f"tempo {speed} vol {TTS_VOLUME_GAIN} silence 1 0.1 1% -1 0.9 1%"
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
	_print_say_command(command, text)
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
