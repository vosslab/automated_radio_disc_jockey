#!/usr/bin/env python3

# Standard Library
import argparse
import os
import re
from dataclasses import dataclass

# PIP3 modules
from rich import print
from rich.markup import escape

# Local repo modules
from cli_colors import Colors
import llm_wrapper
import audio_utils
from audio_utils import Song
import prompt_loader

#============================================
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
#============================================
def _reason_has_score_shorthand(reason: str) -> bool:
	"""
	Detect score-only or shorthand reason formats that are not human-readable.
	"""
	if not reason:
		return False
	pattern = r"\bP\s*,\s*G\s*,\s*I\s*,\s*S\s*,\s*T\s*,\s*M\s*,\s*CA\b"
	if re.search(pattern, reason, flags=re.IGNORECASE):
		return True
	pattern_with_values = r"\bP\s*,\s*G\s*,\s*I\s*,\s*S\s*,\s*T\s*,\s*M\s*,\s*CA\s*=\s*\d"
	if re.search(pattern_with_values, reason, flags=re.IGNORECASE):
		return True
	return False

#============================================
def is_reason_acceptable(reason: str, candidates: list[Song]) -> bool:
	"""
	Validate the LLM reason is human-readable.
	"""
	if not reason:
		return False

	stripped = reason.strip()
	if not stripped:
		return False

	upper = stripped.upper()
	if "WHY YOU PICKED" in upper or "FILENAME.MP3" in upper:
		return False

	if _reason_has_score_shorthand(stripped):
		return False

	letters = re.sub(r"[^A-Za-z]", "", stripped)
	if len(letters) < 20:
		return False

	return True

#============================================
def _preview_reason(reason: str, max_chars: int = 160) -> str:
	"""
	Return a short, single-line preview of the reason text.
	"""
	if not reason:
		return ""
	cleaned = re.sub(r"\s+", " ", reason.strip())
	if len(cleaned) <= max_chars:
		return cleaned
	return cleaned[: max_chars - 3].rstrip() + "..."

#============================================
def build_fallback_reason(choice_text: str, chosen_song: Song | None, candidates: list[Song]) -> str:
	"""
	Build a short, human-readable fallback reason when the LLM output is unusable.
	"""
	if not choice_text:
		return ""

	choice_label = choice_text
	artist_note = ""
	if chosen_song and chosen_song.artist:
		artist_note = f" by {chosen_song.artist}"

	return (
		f"Picked {choice_label}{artist_note} to keep the flow steady after the current track. "
		"That choice keeps the energy consistent and the transition smooth. "
		"It should feel like a natural continuation rather than a hard pivot."
	)

#============================================
def build_selection_prompt(current_song: Song, candidates: list[Song]) -> str:
	"""
	Build the LLM prompt for next-song selection.
	"""
	last_artist = current_song.artist.lower()
	last_album = current_song.album.lower()
	last_title = current_song.title.lower()

	current_song_line = (
		f"{os.path.basename(current_song.path)} | "
		f"Artist: {last_artist} | Album: {last_album} | Title: {last_title}"
	)
	candidate_lines = []
	for song in candidates:
		candidate_lines.append(
			f"- {os.path.basename(song.path)} | "
			f"Artist: {song.artist} | Album: {song.album} | Title: {song.title}"
		)
	template = prompt_loader.load_prompt("next_song_selection.txt")
	return prompt_loader.render_prompt(
		template,
		{
			"current_song_line": current_song_line,
			"candidate_lines": "\n".join(candidate_lines),
		},
	)

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

	no_prefix = re.sub(r"^[\s\-_]*\d{1,4}[\s\-_\.]+", "", normalized).strip()
	if no_prefix and no_prefix.lower() != normalized.lower():
		keys.update(_candidate_key_variants(no_prefix))

	if "-" in no_prefix:
		title_part = no_prefix.split("-", 1)[1].strip()
		if title_part:
			keys.update(_candidate_key_variants(title_part))

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
		lines = [song.one_line_info(color=True) for song in candidate_songs]
		lines.sort()
		print('\n'.join(lines))

	prompt = build_selection_prompt(current_song, candidate_songs)

	raw = llm_wrapper.run_llm(prompt, model_name=model_name)
	raw_choice = llm_wrapper.extract_xml_tag(raw, "choice")
	choice = clean_llm_choice(raw_choice)
	reason = llm_wrapper.extract_xml_tag(raw, "reason")

	if not is_reason_acceptable(reason, candidate_songs):
		preview = _preview_reason(reason)
		if preview:
			print(f"{Colors.WARNING}LLM reason rejected: {escape(preview)}{Colors.ENDC}")
		else:
			print(f"{Colors.WARNING}LLM reason rejected: (empty){Colors.ENDC}")
		print(f"{Colors.WARNING}LLM reason was placeholder or shorthand; retrying for a readable explanation.{Colors.ENDC}")
		retry_prompt = build_selection_prompt(current_song, candidate_songs)
		raw_retry = llm_wrapper.run_llm(retry_prompt, model_name=model_name)
		raw_choice_retry = llm_wrapper.extract_xml_tag(raw_retry, "choice")
		choice_retry = clean_llm_choice(raw_choice_retry)
		reason_retry = llm_wrapper.extract_xml_tag(raw_retry, "reason")
		if not is_reason_acceptable(reason_retry, candidate_songs):
			preview_retry = _preview_reason(reason_retry)
			if preview_retry:
				print(f"{Colors.WARNING}Retry reason rejected: {escape(preview_retry)}{Colors.ENDC}")
			else:
				print(f"{Colors.WARNING}Retry reason rejected: (empty){Colors.ENDC}")
		if is_reason_acceptable(reason_retry, candidate_songs):
			if choice_retry:
				choice = choice_retry
				raw_choice = raw_choice_retry
			reason = reason_retry

	if choice:
		print(f"{Colors.OKGREEN}LLM selection result: {escape(choice)}{Colors.ENDC}")
	elif raw_choice:
		print(f"{Colors.WARNING}LLM choice text was unusable: {escape(raw_choice)}{Colors.ENDC}")
	if reason:
		print(f"{Colors.OKMAGENTA}LLM reason: {escape(reason)}{Colors.ENDC}")
	elif raw_choice:
		print(f"{Colors.WARNING}LLM reason was unusable; continuing without it.{Colors.ENDC}")

	chosen_song = match_candidate_choice(choice, candidate_songs)
	if not is_reason_acceptable(reason, candidate_songs):
		reason = build_fallback_reason(choice, chosen_song, candidate_songs)
	if chosen_song:
		base_name = escape(os.path.basename(chosen_song.path).strip())
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
	print(current_song.one_line_info(color=True))
	print("="*60)

	result = choose_next_song(current_song, song_paths, args.sample_size, model_name=model_name)
	next_song = result.song
	if next_song:
		print(f"{Colors.OKCYAN}Next song: {escape(next_song.path)}{Colors.ENDC}")
	else:
		print(f"{Colors.WARNING}No selection made.{Colors.ENDC}")

#============================================
if __name__ == "__main__":
	main()
