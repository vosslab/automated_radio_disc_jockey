#!/usr/bin/env python3

# Standard Library
import argparse
import os
import re
from dataclasses import dataclass

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
@dataclass
class SelectionResult:
	song: Song | None
	choice_text: str
	reason: str
	raw_choice: str

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
def clean_llm_choice(choice_text: str | None) -> str:
	"""
	Strip obvious noise from the LLM <choice> tag so we can match it to a file.
	"""
	if not choice_text:
		return ""
	text = choice_text.replace("\\", "/").split("/")[-1]
	text = text.strip().strip("\"'`")
	text = re.sub(r"[\n\r\t]+", " ", text)
	text = re.sub(r"\s+", " ", text)
	text = re.sub(r"^[\-\*\#\d\.\)\]]+\s*", "", text)
	return text.strip()

#============================================
def _candidate_key_variants(value: str) -> set[str]:
	"""
	Build normalized forms of a candidate filename so we can compare against messy input.
	"""
	base = os.path.basename(value.strip())
	base = base.strip().strip("\"'`")
	if not base:
		return set()

	normalized = re.sub(r"\s+", " ", base)
	keys = {normalized, normalized.lower()}

	underscore = normalized.replace(" ", "_")
	keys.update({underscore, underscore.lower()})

	dashed = normalized.replace("_", " ").replace("-", " ")
	dashed = re.sub(r"\s+", " ", dashed)
	keys.update({dashed, dashed.lower()})

	root, _ = os.path.splitext(normalized)
	if root:
		root_norm = re.sub(r"\s+", " ", root.strip())
		keys.update({root_norm, root_norm.lower()})

	compact = re.sub(r"[ _\-]+", "", normalized.lower())
	if compact:
		keys.add(compact)

	alnum = re.sub(r"[^a-z0-9]", "", normalized.lower())
	if alnum:
		keys.add(alnum)

	article = re.sub(r"^(?:the|a|an)[\s_\-]+", "", normalized, flags=re.IGNORECASE).strip()
	if article and article.lower() != normalized.lower():
		keys.update({article, article.lower()})
		article_compact = re.sub(r"[^a-z0-9]", "", article.lower())
		if article_compact:
			keys.add(article_compact)

	return {k for k in keys if k}

#============================================
def match_candidate_choice(choice_text: str, candidates: list[Song]) -> Song | None:
	"""
	Attempt to match the sanitized LLM choice against the sampled candidates.
	"""
	if not choice_text:
		return None

	choice_keys = _candidate_key_variants(choice_text)
	lower_choice = choice_text.lower()

	for song in candidates:
		base_name = os.path.basename(song.path).strip()
		if base_name == choice_text or base_name.lower() == lower_choice:
			return song

	for song in candidates:
		candidate_keys = _candidate_key_variants(os.path.basename(song.path))
		if choice_keys.intersection(candidate_keys):
			return song

	return None

#============================================
def build_candidate_songs(current_song: Song, song_list: list[str], sample_size: int) -> list[Song]:
	"""
	Build a filtered and metadata-enriched candidate pool for the selector.
	"""
	if len(song_list) <= 1:
		return []
	candidate_paths = audio_utils.select_song_list(song_list, sample_size)
	while current_song.path in candidate_paths and len(song_list) > 1:
		candidate_paths = audio_utils.select_song_list(song_list, sample_size)

	candidates = []
	for path in candidate_paths:
		song = Song(path)
		if song.artist == current_song.artist:
			continue
		candidates.append(song)
	return candidates

#============================================
def choose_next_song(current_song: Song, song_list: list[str], sample_size: int, model_name: str | None = None, candidates: list[Song] | None = None, show_candidates: bool = True) -> SelectionResult:
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
		return SelectionResult(None, "", "", "")

	candidate_songs = candidates if candidates is not None else build_candidate_songs(current_song, song_list, sample_size)
	if not candidate_songs:
		return SelectionResult(None, "", "", "")

	if show_candidates:
		print(f"{Colors.OKMAGENTA}Candidates for next song:{Colors.ENDC}")
		lines = [song.one_line_info() for song in candidate_songs]
		lines.sort()
		print('\n'.join(lines))

	last_artist = current_song.artist.lower()
	last_album = current_song.album.lower()
	last_title = current_song.title.lower()

	prompt = ""
	prompt += "You are selecting the next track for a radio show. "
	prompt += "\n(1) Score each candidate song in the following categories. "
	prompt += "(P) Popularity 1 mainstream, 3 niche or indie, 4 obscure, 5 very obscure. Obscure is preferred."
	prompt += "(G) Genre similarity 1 totally different, 3 adjacent traits, 5 same or very close. "
	prompt += "(I) Intensity similarity 1 very mismatched intensity, 3 moderate match, 5 very similar intensity. "
	prompt += "(S) Style similarity 1 very different vibe, 3 partial overlap, 5 strong alignment. "
	prompt += "(T) Tempo similarity 1 very different speed, 3 moderately different, 5 very close. "
	prompt += "(M) Mood similarity 1 opposite emotional color, 3 partial match, 5 strong emotional match. "
	prompt += "(CA) Critical acclaim 1 very different stature than the current song, 3 somewhat similar, 5 very close. "
	prompt += "Score acclaim relative to the current track and base it on artistic influence or reputation. "
	prompt += "You may display only a seven number summary per candidate: P,G,I,S,T,M,CA. No explanations. "
	prompt += "The order of the scores above is the ranking or weight of each category, from highest to lowest. "
	prompt += "\n(2) From the candidates, identify the four best matches for the current song. "
	prompt += "\n(3) Rank those four by how well they fit after the current track. "
	prompt += "Use the numerical rankings as the primary factors. "
	prompt += "\n(4) After ranking the top four choices, choose the single best track as the next song. "
	prompt += "\n(5) In your reasoning, be moderately detailed but strictly bounded. "
	prompt += "Inside <reason>, write 2-4 sentences (max 80 words). "
	prompt += "You must include: "
	prompt += "(a) the final pick's 7-number summary as 'P,G,I,S,T,M,CA = x,x,x,x,x,x,x', and "
	prompt += "(b) exactly two runner-up filenames and one short clause for each explaining why they lost. "
	prompt += "\n(6) Use the file names exactly as shown in the candidate list. "
	prompt += "\n(7) select the least jarring and the most 'this DJ knows what they are doing' choice."
	prompt += "\n(8) Keep your output tightly structured and short."
	prompt += "\n(9) Respond with these two specific XML tags for processing "
	prompt += "<choice>FILENAME.mp3</choice>"
	prompt += "<reason>WHY YOU PICKED IT AND BREAKDOWN OF WHY THE OTHER TOP SONGS WERE REJECTED</reason>\n"
	prompt += (
		f"Current song: {os.path.basename(current_song.path)} | "
		f"Artist: {last_artist} | Album: {last_album} | Title: {last_title}\n"
	)
	prompt += "Candidates:\n"
	for song in candidate_songs:
		prompt += (
			f"- {os.path.basename(song.path)} | "
			f"Artist: {song.artist} | Album: {song.album} | Title: {song.title}\n"
		)

	raw = llm_wrapper.run_llm(prompt, model_name=model_name)
	raw_choice = llm_wrapper.extract_xml_tag(raw, "choice")
	choice = clean_llm_choice(raw_choice)
	reason = llm_wrapper.extract_xml_tag(raw, "reason")

	if choice:
		print(f"{Colors.OKGREEN}LLM selection result: {choice}{Colors.ENDC}")
	elif raw_choice:
		print(f"{Colors.WARNING}LLM choice text was unusable: {raw_choice}{Colors.ENDC}")
	if reason:
		print(f"{Colors.OKMAGENTA}LLM reason: {reason}{Colors.ENDC}")

	chosen_song = match_candidate_choice(choice, candidate_songs)
	if chosen_song:
		base_name = os.path.basename(chosen_song.path).strip()
		print(f"{Colors.OKCYAN}Final next song: {base_name}{Colors.ENDC}")
	if chosen_song is None:
		print(f"{Colors.WARNING}LLM choice did not match any candidate; no selection made.{Colors.ENDC}")

	return SelectionResult(chosen_song, choice, reason or "", raw_choice or "")

#============================================
def main() -> None:
	args = parse_args()

	# Keep library as paths, cheap
	song_paths = audio_utils.get_song_list(args.directory)
	model_name = llm_wrapper.get_default_model_name()

	current_path = os.path.abspath(args.current)
	if current_path not in song_paths:
		print(f"{Colors.WARNING}Current song is not in directory list; adding it for context.{Colors.ENDC}")
		song_paths.append(current_path)

	current_song = Song(current_path)  # only one heavy metadata load here
	print("CURRENT SONG:")
	print(current_song.one_line_info())
	print("="*60)

	result = choose_next_song(current_song, song_paths, args.sample_size, model_name=model_name)
	next_song = result.song
	if next_song:
		print(f"{Colors.OKCYAN}Next song: {next_song.path}{Colors.ENDC}")
	else:
		print(f"{Colors.WARNING}No selection made.{Colors.ENDC}")

#============================================
if __name__ == "__main__":
	main()
