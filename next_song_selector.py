#!/usr/bin/env python3

# Standard Library
import argparse
import os
import re

# Local repo modules
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
	parser.add_argument("-n", "--sample-size", dest="sample_size", type=int, default=16, help="Number of candidates to consider.")
	return parser.parse_args()

#============================================
def choose_next_song(current_song: Song, song_list: list[str], sample_size: int, model_name: str | None = None) -> Song | None:
	"""
	Select the next song using an LLM over a sampled candidate pool.

	Args:
		current_song (Song): Currently playing song with metadata.
		song_list (list[str]): List of all available song file paths.
		sample_size (int): Number of candidate songs to consider.

	Returns:
		Song | None: Chosen next Song object, or None if selection fails.
	"""
	if len(song_list) <= 1:
		return None

	# Pick a candidate list and resample if it contains the current song
	candidate_paths = audio_utils.select_song_list(song_list, sample_size)
	while current_song.path in candidate_paths and len(song_list) > 1:
		candidate_paths = audio_utils.select_song_list(song_list, sample_size)

	# Build Song objects only for the small candidate set
	candidates = []
	for path in candidate_paths:
		song = Song(path)
		if song.artist == current_song.artist:
			continue
		candidates.append(song)

	if not candidates:
		return None

	print(f"{Colors.OKMAGENTA}Candidates for next song:{Colors.ENDC}")
	for song in candidates:
		print(song.one_line_info())

	last_artist = current_song.artist.lower()
	last_album = current_song.album.lower()
	last_title = current_song.title.lower()

	prompt = ""
	prompt += "You are selecting the next track for a radio show. "
	prompt += "(1) Score each candidate song in the following categories. "
	prompt += "Popularity 1 mainstream, 3 niche or indie, 4 obscure, 5 very obscure. "
	prompt += "Genre similarity 1 totally different, 3 adjacent traits, 5 same or very close. "
	prompt += "Energy similarity 1 very mismatched intensity, 3 moderate match, 5 very similar intensity. "
	prompt += "Style similarity 1 very different vibe, 3 partial overlap, 5 strong alignment. "
	prompt += "Mood similarity 1 opposite emotional color, 3 partial match, 5 strong emotional match. "
	prompt += "Tempo similarity 1 very different speed, 3 moderately different, 5 very close. "
	prompt += "These scores are for internal reasoning. Do not display them or your calculations. "
	prompt += "(2) From the candidates, identify the four best matches for the current song. "
	prompt += "(3) Rank those four by how well they fit after the current track. "
	prompt += "Use genre, energy, style, and tempo as the primary factors. "
	prompt += "If the current band is indie or obscure, avoid jumping to a very mainstream band. "
	prompt += "(4) After ranking the top four choices, choose the single best track as the next song. "
	prompt += "(5) In your reasoning, briefly explain why the other rejected tracks are weaker fits "
	prompt += "than the final choice. "
	prompt += "(6) Use the file names exactly as shown in the candidate list. "
	prompt += "(7) Respond only with two XML tags and nothing else: "
	prompt += "<choice>FILENAME</choice>"
	prompt += "<reason>WHY YOU PICKED IT AND WHY THE OTHER TWO WERE REJECTED</reason>\n"
	prompt += (
		f"Current song: {os.path.basename(current_song.path)} | "
		f"Artist: {last_artist} | Album: {last_album} | Title: {last_title}\n"
	)
	prompt += "Candidates:\n"
	for song in candidates:
		prompt += (
			f"- {os.path.basename(song.path)} | "
			f"Artist: {song.artist} | Album: {song.album} | Title: {song.title}\n"
		)

	model = model_name or llm_wrapper.select_ollama_model()
	raw = llm_wrapper.query_ollama_model(prompt, model)
	choice = llm_wrapper.extract_xml_tag(raw, "choice")
	choice = choice.replace(" ", "_")
	choice = re.sub("^The_", "", choice)
	reason = llm_wrapper.extract_xml_tag(raw, "reason")

	if choice:
		print(f"{Colors.OKGREEN}LLM selection result: {choice}{Colors.ENDC}")
	if reason:
		print(f"{Colors.OKMAGENTA}LLM reason: {reason}{Colors.ENDC}")

	chosen_song = None
	for song in candidates:
		base_name = os.path.basename(song.path).strip()
		if base_name == choice.strip():
			print(f"{Colors.OKCYAN}Final next song: {base_name}{Colors.ENDC}")
			chosen_song = song
			break

	if chosen_song is None:
		print(f"{Colors.WARNING}LLM choice did not match any candidate; no selection made.{Colors.ENDC}")

	return chosen_song

#============================================
def main() -> None:
	args = parse_args()

	# Keep library as paths, cheap
	song_paths = audio_utils.get_song_list(args.directory)
	model_name = llm_wrapper.select_ollama_model()

	current_path = os.path.abspath(args.current)
	if current_path not in song_paths:
		print(f"{Colors.WARNING}Current song is not in directory list; adding it for context.{Colors.ENDC}")
		song_paths.append(current_path)

	current_song = Song(current_path)  # only one heavy metadata load here
	print("CURRENT SONG:")
	print(current_song.one_line_info())
	print("="*60)

	next_song = choose_next_song(current_song, song_paths, args.sample_size, model_name=model_name)
	if next_song:
		print(f"{Colors.OKCYAN}Next song: {next_song.path}{Colors.ENDC}")
	else:
		print(f"{Colors.WARNING}No selection made.{Colors.ENDC}")

#============================================
if __name__ == "__main__":
	main()
