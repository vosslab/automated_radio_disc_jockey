#!/usr/bin/env python3

# Standard Library
import argparse
import os
import random
import re
import subprocess
import time

# Local repo modules
import audio_file_to_details
import llm_wrapper
import audio_utils
from audio_utils import Song

#============================================
class Colors:
	OKBLUE = "\033[94m"
	OKGREEN = "\033[92m"
	OKCYAN = "\033[96m"
	OKMAGENTA = "\033[95m"
	WARNING = "\033[93m"
	FAIL = "\033[91m"
	ENDC = "\033[0m"

#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse command-line arguments for selector.

	Returns:
		argparse.Namespace: Parsed args.
	"""
	parser = argparse.ArgumentParser(description="Select the next song given a current song and music directory.")
	parser.add_argument("-c", "--current", dest="current", required=True, help="Path to current song.")
	parser.add_argument("-d", "--directory", dest="directory", required=True, help="Music directory to sample from.")
	parser.add_argument("-n", "--sample-size", dest="sample_size", type=int, default=10, help="Number of candidates to consider.")
	return parser.parse_args()

#============================================
def list_ollama_models() -> list:
	return llm_wrapper.list_ollama_models()

#============================================
def get_vram_size_in_gb() -> int | None:
	return llm_wrapper.get_vram_size_in_gb()

#============================================
def select_ollama_model(vram_size_gb: int | None, available: list) -> str:
	return llm_wrapper.select_ollama_model(vram_size_gb, available)

#============================================
def query_ollama_model(prompt: str, vram_size_gb: int | None, available: list) -> str:
	return llm_wrapper.query_ollama_model(prompt, vram_size_gb, available)

#============================================
def extract_choice_reason(raw_text: str) -> tuple[str, str]:
	"""
	Extract choice and reason from LLM output with <choice> and <reason> tags.

	Args:
		raw_text (str): LLM output.

	Returns:
		tuple[str, str]: Chosen filename (or empty) and reason text.
	"""
	choice_match = re.findall(r"<choice[^>]*>(.*?)</choice[^>]*>", raw_text, re.IGNORECASE | re.DOTALL)
	reason_match = re.findall(r"<reason[^>]*>(.*?)</reason[^>]*>", raw_text, re.IGNORECASE | re.DOTALL)
	choice = choice_match[-1].strip() if choice_match else ""
	reason = reason_match[-1].strip() if reason_match else ""
	if not choice and "<choice" in raw_text and "</choice>" not in raw_text.lower():
		raw_text = f"{raw_text}</choice>"
		choice_match = re.findall(r"<choice[^>]*>(.*?)</choice[^>]*>", raw_text, re.IGNORECASE | re.DOTALL)
		if choice_match:
			choice = choice_match[-1].strip()
	if not reason and "<reason" in raw_text and "</reason>" not in raw_text.lower():
		raw_text = f"{raw_text}</reason>"
		reason_match = re.findall(r"<reason[^>]*>(.*?)</reason[^>]*>", raw_text, re.IGNORECASE | re.DOTALL)
		if reason_match:
			reason = reason_match[-1].strip()
	return choice, reason

#============================================
def choose_next_song(current_song: str, song_list: list, cache: dict, sample_size: int) -> str | None:
	"""
	Select the next song using an LLM over a sampled candidate pool.

	Args:
		current_song (str): Currently playing song.
		song_list (list): All available songs.
		cache (dict): Metadata cache.
		sample_size (int): Candidate pool size.

	Returns:
		str | None: Path to chosen next song.
	"""
	pool = [song for song in song_list if song != current_song]
	if not pool:
		return None

	def cached_meta(path: str) -> dict:
		if path in cache:
			return cache[path]
		# Prefer lightweight Song for cached fields
		song_obj = Song(path)
		cache[path] = {
			"title": song_obj.title,
			"artist": song_obj.artist,
			"album": song_obj.album,
		}
		return cache[path]

	last_meta = cached_meta(current_song)
	last_artist = last_meta.get("artist", "").lower()
	last_album = last_meta.get("album", "").lower()
	last_title = last_meta.get("title", "").lower()
	vram_size_gb = get_vram_size_in_gb()
	available_models = list_ollama_models()

	while True:
		if not pool:
			return None
		random.shuffle(pool)
		candidates = pool[: max(1, min(sample_size, len(pool)))]

		print(f"{Colors.OKMAGENTA}Candidates for next song:{Colors.ENDC}")
		for candidate in candidates:
			meta = cached_meta(candidate)
			song_obj = Song(candidate)
			print(song_obj.one_line_info())

		prompt = ""
		prompt += "You are selecting the next track for a radio show. "
		prompt += "Pick the single best candidate that flows naturally from the current song. "
		prompt += "Prefer similar era/genre/energy/tempo over drastic jumps; avoid the same artist back to back. "
		prompt += "Respond only with two XML tags and nothing else: "
		prompt += "<choice>FILENAME</choice><reason>WHY YOU PICKED IT</reason>\n"
		prompt += f"Current song: {os.path.basename(current_song)} | Artist: {last_artist} | Album: {last_album} | Title: {last_title}\n"
		prompt += "Candidates:\n"
		for candidate in candidates:
			meta = cached_meta(candidate)
			prompt += f"- {os.path.basename(candidate)} | Artist: {meta.get('artist')} | Album: {meta.get('album')} | Title: {meta.get('title')}\n"
		time.sleep(random.random())
		try:
			raw = query_ollama_model(prompt, vram_size_gb, available_models)
			choice, reason = extract_choice_reason(raw)
			if choice:
				print(f"{Colors.OKGREEN}LLM choice: {choice}{Colors.ENDC}")
			if reason:
				print(f"{Colors.OKMAGENTA}LLM reason: {reason}{Colors.ENDC}")
			for candidate in candidates:
				if os.path.basename(candidate).strip() == choice.strip():
					print(f"{Colors.OKCYAN}Final next song: {os.path.basename(candidate)}{Colors.ENDC}")
					return candidate
			print(f"{Colors.WARNING}LLM choice did not match candidates; sampling a new pool and retrying...{Colors.ENDC}")
			continue
		except Exception as error:
			print(f"{Colors.FAIL}LLM selection failed; sampling a new pool. Error: {error}{Colors.ENDC}")
			continue

#============================================
def main() -> None:
	args = parse_args()
	songs = audio_utils.get_song_list(args.directory)
	current = os.path.abspath(args.current)
	if current not in songs:
		print(f"{Colors.WARNING}Current song is not in directory list; adding it for context.{Colors.ENDC}")
		songs.append(current)

	pool = [s for s in songs if s != current]
	random.shuffle(pool)
	candidates = pool[: max(1, min(args.sample_size, len(pool)))]

	next_song = choose_next_song(current, songs, {}, args.sample_size)
	if next_song:
		print(f"{Colors.OKCYAN}Next song: {next_song}{Colors.ENDC}")
	else:
		print(f"{Colors.WARNING}No selection made.{Colors.ENDC}")

#============================================
if __name__ == "__main__":
	main()
