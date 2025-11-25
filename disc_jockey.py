#!/usr/bin/env python3

# Standard Library
import argparse
import os
import time

# PIP3 modules
import pygame
from gtts import gTTS

# Local repo modules
import audio_file_to_details
import next_song_selector
import llm_wrapper
import audio_utils
from speak_something import format_intro_for_tts

#============================================
# Simple history logger
class HistoryLogger:
	"""
	Append played songs and DJ intros to a history file.
	"""
	def __init__(self, path: str = "history.log"):
		self.path = path

	def log(self, song_path: str, intro_text: str) -> None:
		line_song = f"SONG: {os.path.basename(song_path)}\n"
		line_intro = f"INTRO: {intro_text}\n"
		with open(self.path, "a", encoding="utf-8") as f:
			f.write(line_song)
			f.write(line_intro)
			f.write("-" * 40 + "\n")

#============================================
# Simple ANSI color helpers
class Colors:
	HEADER = "\033[95m"
	OKBLUE = "\033[94m"
	OKCYAN = "\033[96m"
	OKGREEN = "\033[92m"
	OKMAGENTA = "\033[95m"
	WARNING = "\033[93m"
	FAIL = "\033[91m"
	ENDC = "\033[0m"
	BOLD = "\033[1m"
	UNDERLINE = "\033[4m"

#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse command-line arguments.

	Returns:
		argparse.Namespace: Parsed CLI arguments.
	"""
	parser = argparse.ArgumentParser(description="AI disc jockey for local music files.")
	parser.add_argument(
		"-d",
		"--directory",
		dest="directory",
		required=True,
		help="Path to music directory containing audio files.",
	)
	parser.add_argument(
		"-n",
		"--sample-size",
		dest="sample_size",
		type=int,
		default=10,
		help="How many random songs to sample for initial choice and next suggestion.",
	)
	parser.add_argument(
		"-r",
		"--tts-speed",
		dest="tts_speed",
		type=float,
		default=1.2,
		help="Playback speed multiplier for the DJ intro (gTTS + sox).",
	)
	parser.add_argument(
		"-t",
		"--testing",
		dest="testing",
		action="store_true",
		help="Testing mode: play only the first 20 seconds of each song.",
	)
	parser.add_argument(
		"-m",
		"--metadata-prompt",
		dest="metadata_prompt",
		action="store_true",
		help="Use metadata-based prompt builder.",
	)
	parser.add_argument(
		"-s",
		"--simple-prompt",
		dest="metadata_prompt",
		action="store_false",
		help="Use basic Wikipedia summary prompt.",
	)
	parser.set_defaults(metadata_prompt=True)
	args = parser.parse_args()
	return args

#============================================
def _ensure_mixer_initialized() -> None:
	"""
	Initialize pygame mixer if not already initialized.
	"""
	if not pygame.mixer.get_init():
		pygame.mixer.init()

#============================================
def speak_dj_intro(prompt: str, speed: float) -> None:
	"""
	Convert text to speech, play it, and clean up temp file.

	Args:
		prompt (str): Intro text.
		speed (float): Speed multiplier for playback (tempo).
	"""
	if not prompt or len(prompt.strip()) < 1:
		print("No intro text to speak; skipping TTS.")
		return
	clean_prompt = format_intro_for_tts(prompt)
	print(f"{Colors.OKCYAN}Speaking intro ({len(clean_prompt)} chars) at {speed}x speed...{Colors.ENDC}")
	try:
		from speak_something import speak_text
		speak_text(clean_prompt, engine="gtts", save=False, speed=speed)
	except Exception as error:
		print(f"{Colors.FAIL}TTS playback error: {error}{Colors.ENDC}")
		return

#============================================
def play_song(song_path: str) -> None:
	"""
	Start playback of a song file via pygame mixer (non-blocking).

	Args:
		song_path (str): Path to audio file.
	"""
	_ensure_mixer_initialized()
	print(f"{Colors.OKGREEN}Playing song: {os.path.basename(song_path)}{Colors.ENDC}")
	pygame.mixer.music.load(song_path)
	pygame.mixer.music.play()

#============================================
def wait_for_song_end(testing: bool, poll_seconds: float = 1.0, preview_seconds: int = 20) -> None:
	"""
	Block until current playback finishes.

	Args:
		testing (bool): If True, stop after preview_seconds.
		poll_seconds (float): Sleep interval while waiting.
		preview_seconds (int): How long to play in testing mode.
	"""
	start_time = time.time()
	while pygame.mixer.music.get_busy():
		if testing and (time.time() - start_time) >= preview_seconds:
			print(f"Testing mode: stopping playback after {preview_seconds} seconds.")
			pygame.mixer.music.stop()
			break
		time.sleep(poll_seconds)
	print(f"{Colors.OKBLUE}Song finished playing.{Colors.ENDC}")

#============================================
def query_ollama_model(prompt: str) -> str:
	"""
	Query the selected Ollama model with the prompt.

	Args:
		prompt (str): DJ prompt text.

	Returns:
		str: Model response (may be empty on error).
	"""
	output = llm_wrapper.query_ollama_model(prompt)
	print(f"{Colors.OKMAGENTA}LLM raw output (truncated to 400 chars):{Colors.ENDC}")
	print(output[:400])
	return output

#============================================
def prepare_intro_text(song_path: str, use_metadata_prompt: bool, previous_title: str | None = None) -> str:
	"""
	Build prompt, call LLM, and extract the intro text.

	Args:
		song_path (str): Path to song file.
		use_metadata_prompt (bool): Whether to use detailed metadata prompt.
		previous_title (str | None): Title of the previously played song for transition.

	Returns:
		str: Cleaned intro text (may be empty on failure).
	"""
	print(f"{Colors.OKBLUE}Gathering song info and building prompt for {os.path.basename(song_path)}...{Colors.ENDC}")
	prompt = basic_prompt(song_path)
	if use_metadata_prompt:
		prompt = build_prompt_with_metadata(song_path)
	if previous_title:
		prompt += f"\nPrevious song was {previous_title}. Add a smooth transition reference."
	print(f"{Colors.OKBLUE}Sending prompt to LLM...{Colors.ENDC}")
	print(f"{Colors.WARNING}Waiting for response...{Colors.ENDC}")
	dj_intro = query_ollama_model(prompt)
	print(f"{Colors.OKGREEN}Received LLM output; extracting <response> block...{Colors.ENDC}")
	clean_intro = llm_wrapper.extract_response_text(dj_intro)
	if clean_intro:
		print(f"Extracted intro length: {len(clean_intro)} characters.")
	else:
			print("No <response> block detected; intro text will be empty.")
	return clean_intro

#============================================
def build_prompt_with_metadata(song_path: str) -> str:
	"""
	Build a DJ prompt using metadata lookup helper.

	Args:
		song_path (str): Path to song.

	Returns:
		str: Prompt text.
	"""
	metadata = audio_file_to_details.Metadata(song_path)
	try:
		metadata.fetch_wikipedia_info()
	except Exception as error:
		print(f"Wikipedia lookup failed: {error}. Falling back to basic prompt.")
		return basic_prompt(song_path)
	prompt = ""
	prompt += "You're a charismatic radio DJ. Keep it short and natural. "
	prompt += "Do not mention any city, town, or location. "
	prompt += "Avoid brackets/parentheses and em dashes. "
	prompt += "Respond only with the final spoken intro inside <response>...</response>.\n\n"
	prompt += "Song details:\n"
	prompt += metadata.get_results()
	return prompt

#============================================
def basic_prompt(song_path: str) -> str:
	"""
	Build a simple prompt from Wikipedia summary only.

	Args:
		song_path (str): Path to song.

	Returns:
		str: Prompt text.
	"""
	song_name = os.path.basename(song_path)
	info = "No Wikipedia summary available."
	prompt = ""
	prompt += "Imagine you are a radio disc jockey introducing a song. "
	prompt += "You are broadcasting to a small suburb audience, but do not say any location on air. "
	prompt += f"Start with the band and song name: {song_name}. "
	prompt += f"Here are some facts: {info}. "
	prompt += f"Close by repeating {song_name} before playing."
	prompt += " Do not mention any location or town name aloud."
	prompt += " Respond only with the final spoken intro inside <response>...</response>."
	return prompt

#============================================
def choose_similar_song(last_song: str, song_list: list, cache: dict, sample_size: int) -> str | None:
	"""
	Choose a similar song based on artist, album, and title overlap, with LLM justification.

	Args:
		last_song (str): Recently played song.
		song_list (list): All available songs.
		cache (dict): Metadata cache.
		sample_size (int): Number of random candidates to consider (also used for initial pick).
		vram_size_gb (int | None): Detected memory size for LLM selection.
		available_models (list): Available Ollama models.

	Returns:
		str | None: Path to suggested song.
	"""
	return next_song_selector.choose_next_song(last_song, song_list, cache, sample_size)

#============================================
def main() -> None:
	"""
	Run the AI disc jockey loop.
	"""
	args = parse_args()
	song_list = audio_utils.get_song_list(args.directory)
	print(f"{Colors.WARNING}Found {len(song_list)} audio files in {args.directory}.{Colors.ENDC}")
	metadata_cache = {}
	current_song = audio_utils.select_song(song_list, args.sample_size)
	print(f"{Colors.OKGREEN}Starting with user-selected song: {os.path.basename(current_song)}{Colors.ENDC}")
	queued_intro = ""
	previous_title = None
	history = HistoryLogger()

	while True:
		chosen_song = current_song
		if queued_intro:
			intro_text = queued_intro
			queued_intro = ""
			print(f"{Colors.OKCYAN}Using queued intro for current track.{Colors.ENDC}")
		else:
			intro_text = prepare_intro_text(
				chosen_song,
				args.metadata_prompt,
				previous_title=previous_title,
			)
		if intro_text and len(intro_text.strip()) > 5:
			print(f"{Colors.BOLD}{Colors.OKMAGENTA}DJ Introduction:{Colors.ENDC}")
			print(f"{Colors.OKCYAN}{intro_text}{Colors.ENDC}")
			speak_dj_intro(intro_text, args.tts_speed)
			history.log(chosen_song, intro_text)
		else:
			print(f"{Colors.WARNING}No usable intro text; skipping TTS.{Colors.ENDC}")
		play_song(chosen_song)
		next_song = choose_similar_song(
			chosen_song,
			song_list,
			metadata_cache,
			args.sample_size,
		)
		if next_song:
			print(f"{Colors.OKBLUE}Preparing next song: {os.path.basename(next_song)}{Colors.ENDC}")
			queued_intro = prepare_intro_text(
				next_song,
				args.metadata_prompt,
				previous_title=os.path.basename(chosen_song),
			)
		else:
			print(f"{Colors.WARNING}No next song available to prepare.{Colors.ENDC}")
		wait_for_song_end(args.testing)
		if not next_song:
			print(f"{Colors.FAIL}No next song available. Ending session.{Colors.ENDC}")
			break
		if queued_intro and len(queued_intro.strip()) > 5:
			print(f"{Colors.OKGREEN}Queued intro ready for next track.{Colors.ENDC}")
		else:
			print(f"{Colors.WARNING}Next intro missing or too short; will skip TTS for next track.{Colors.ENDC}")
		current_song = next_song
		previous_title = os.path.basename(chosen_song)

#============================================
if __name__ == "__main__":
	main()
