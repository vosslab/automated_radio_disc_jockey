#!/usr/bin/env python3

# Standard Library
import argparse
import os
import re
import unicodedata

# PIP3 modules
from rich import print
from rich.markup import escape

# Local repo modules
from cli_colors import Colors
import audio_utils
import audio_file_to_details
import llm_wrapper
import transcribe_audio
import prompt_loader

#============================================
#============================================
MAX_INTRO_CHARS = 1200
MIN_INTRO_SENTENCES = 3
MAX_INTRO_SENTENCES = 10
TARGET_SENTENCE_MIN = 5
TARGET_SENTENCE_MAX = 7
MIN_RELAXED_SENTENCES = 2
MIN_RELAXED_WORDS = 12
MAX_REPEAT_SENTENCE = 2
EXPECTED_FACT_LINES = 5
MAX_LYRICS_CHARS = 1200
TITLE_STOPWORDS = {
	"a",
	"an",
	"and",
	"by",
	"edit",
	"feat",
	"featuring",
	"for",
	"from",
	"in",
	"instrumental",
	"live",
	"mix",
	"mono",
	"of",
	"original",
	"reprise",
	"remaster",
	"remastered",
	"remix",
	"score",
	"soundtrack",
	"stereo",
	"the",
	"theme",
	"version",
	"vol",
	"volume",
	"with",
}
MAX_REFINE_ATTEMPTS = 1

#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse command-line arguments.

	Returns:
		argparse.Namespace: Parsed CLI args.
	"""
	parser = argparse.ArgumentParser(description="Generate a DJ intro from song details via LLM.")
	parser.add_argument("-i", "--input", dest="input_file", help="Path to the song file (for metadata lookup).")
	parser.add_argument("-t", "--text", dest="text", help="Raw paragraph about a song to use directly (skips metadata lookup).")
	parser.add_argument("--simple", dest="use_metadata", action="store_false", help="Use simple prompt (no metadata).")
	parser.add_argument("--metadata", dest="use_metadata", action="store_true", help="Use metadata-based prompt (default).")
	parser.set_defaults(use_metadata=True)
	return parser.parse_args()

#============================================
def _estimate_sentence_count(text: str) -> int:
	"""
	Estimate sentence count with a simple punctuation heuristic.
	"""
	parts = re.split(r"[.!?]+", text)
	count = 0
	for part in parts:
		words = part.strip().split()
		if len(words) >= 3:
			count += 1
	return count

#============================================
def _normalize_sentence(text: str) -> str:
	"""
	Normalize sentence text for repetition checks.
	"""
	normalized = text.lower()
	normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
	normalized = re.sub(r"\s+", " ", normalized).strip()
	return normalized

#============================================
def _strip_code_fences(text: str) -> str:
	if not text:
		return ""
	text = re.sub(r"```[a-z0-9]*\s*(.*?)```", r"\1", text, flags=re.IGNORECASE | re.DOTALL)
	text = re.sub(r"```", " ", text)
	return text.replace("`", " ")

#============================================
def _sanitize_lyrics_text(text: str) -> str:
	if not text:
		return ""
	ascii_text = _to_aggressive_ascii(text)
	ascii_text = ascii_text.replace("\r\n", "\n").replace("\r", "\n")
	lines = []
	current_len = 0
	for raw_line in ascii_text.splitlines():
		line = raw_line.strip()
		if not line:
			continue
		line = re.sub(r"\s+", " ", line)
		if not line:
			continue
		if current_len + len(line) + 1 > MAX_LYRICS_CHARS:
			remaining = MAX_LYRICS_CHARS - current_len
			if remaining > 10:
				lines.append(line[:remaining].rstrip())
			break
		lines.append(line)
		current_len += len(line) + 1
	return "\n".join(lines).strip()

#============================================
def _to_aggressive_ascii(text: str) -> str:
	if text is None:
		return ""
	if isinstance(text, bytes):
		udata = text.decode("utf-8", errors="ignore")
	else:
		udata = str(text)

	replacements = {
		"\u2018": "'",
		"\u2019": "'",
		"\u201c": "\"",
		"\u201d": "\"",
		"\u2013": "-",
		"\u2014": "-",
		"\u2026": "...",
		"\u00a0": " ",
	}
	for old, new in replacements.items():
		udata = udata.replace(old, new)

	try:
		import transliterate
		try:
			udata = transliterate.translit(udata, reversed=True)
		except Exception:
			pass
	except Exception:
		pass

	try:
		nfkd_form = unicodedata.normalize("NFKD", udata)
	except Exception:
		nfkd_form = udata

	ascii_text = nfkd_form.encode("ASCII", "ignore").decode("ASCII")
	ascii_text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]+", " ", ascii_text)
	ascii_text = ascii_text.replace("\t", " ")
	ascii_text = re.sub(r"[ ]{2,}", " ", ascii_text)
	return ascii_text.strip()

#============================================
def _starts_with_boilerplate(text: str) -> bool:
	if not text:
		return False
	patterns = [
		r"^\s*ladies and gentlemen,?\s*welcome to",
		r"^\s*hey there,?\s*(?:disney fans|music lovers|folks|everyone)\b",
		r"^\s*hello,?\s*(?:disney fans|music lovers|folks|everyone)\b",
		r"^\s*hi there,?\s*(?:disney fans|music lovers|folks|everyone)\b",
	]
	for pattern in patterns:
		if re.match(pattern, text, flags=re.IGNORECASE):
			return True
	return False

#============================================
def _strip_leading_boilerplate_sentence(text: str) -> str:
	if not text:
		return ""
	if not _starts_with_boilerplate(text):
		return text
	match = re.search(r"[.!?]\s+", text)
	if match:
		return text[match.end():].lstrip()
	return ""

#============================================
def _finalize_intro_text(
	text: str,
	song: audio_utils.Song,
	model_name: str | None,
	allow_refine: bool,
	reason_hint: str = "",
) -> str | None:
	if not text:
		return None
	clean_intro = _strip_code_fences(text).strip()
	if not clean_intro:
		return None
	lowered = clean_intro.lower()
	if "fact:" in lowered or "trivia:" in lowered:
		return _refine_or_none(clean_intro, song, model_name, allow_refine, "contains FACT/TRIVIA")
	if "<" in clean_intro and ">" in clean_intro:
		return _refine_or_none(clean_intro, song, model_name, allow_refine, "contains markup")
	if len(clean_intro) > MAX_INTRO_CHARS:
		return _refine_or_none(clean_intro, song, model_name, allow_refine, "too long")
	if _starts_with_boilerplate(clean_intro):
		clean_intro = _strip_leading_boilerplate_sentence(clean_intro)
		if not clean_intro:
			return _refine_or_none(text, song, model_name, allow_refine, "boilerplate opening")
	sentence_count = _estimate_sentence_count(clean_intro)
	if sentence_count < MIN_INTRO_SENTENCES or sentence_count > MAX_INTRO_SENTENCES:
		return _refine_or_none(clean_intro, song, model_name, allow_refine, "sentence count out of range")
	if _has_excessive_repetition(clean_intro):
		return _refine_or_none(clean_intro, song, model_name, allow_refine, "repetition")

	if not _title_is_mentioned(clean_intro, song.title or ""):
		print(f"{Colors.DARK_YELLOW}Intro missing song title; allowing output.{Colors.ENDC}")
	if song.title:
		amended = _append_title_if_missing(clean_intro, song.title)
		if len(amended) <= MAX_INTRO_CHARS:
			clean_intro = amended

	return clean_intro

#============================================
def _refine_or_none(
	text: str,
	song: audio_utils.Song,
	model_name: str | None,
	allow_refine: bool,
	reason: str,
) -> str | None:
	if not allow_refine:
		return None
	refined = _refine_intro_with_llm(text, song, model_name, reason)
	if refined:
		return _finalize_intro_text(refined, song, model_name, False, reason_hint=reason)
	return None

#============================================
def _refine_intro_with_llm(
	text: str,
	song: audio_utils.Song,
	model_name: str | None,
	reason: str,
) -> str | None:
	if not text:
		return None
	print(f"{Colors.NAVY}Intro before:{Colors.ENDC}")
	print(f"{Colors.NAVY}{escape(text)}{Colors.ENDC}")
	template = prompt_loader.load_prompt("dj_intro_refine.txt")
	prompt = prompt_loader.render_prompt(
		template,
		{
			"issue": reason,
			"intro_text": text,
		},
	)
	refined = llm_wrapper.run_llm(prompt, model_name=model_name)
	if not refined:
		return None
	extracted = llm_wrapper.extract_xml_tag(refined, "response")
	candidate = extracted or refined
	candidate = _strip_code_fences(candidate)
	candidate = re.sub(r"</?\s*intro\s*text\s*>", " ", candidate, flags=re.IGNORECASE)
	candidate = re.sub(
		r"^\s*here is the rewritten intro text\s*:?\s*",
		"",
		candidate,
		flags=re.IGNORECASE,
	).strip()
	candidate = candidate.strip("\"'").strip()
	if not candidate:
		print(f"{Colors.WARNING}Cleanup LLM returned empty output; keeping original intro.{Colors.ENDC}")
	return candidate or None

#============================================
def polish_intro_for_reading(
	intro_text: str,
	song: audio_utils.Song,
	model_name: str | None,
) -> str | None:
	"""
	Run a final LLM cleanup pass after the referee selects an intro.
	"""
	if not intro_text:
		return None

	print(f"{Colors.SKY_BLUE}Cleaning selected intro with LLM to reduce fluff...{Colors.ENDC}")
	before_chars, before_words, before_sentences = _intro_stats(intro_text)
	refined = _refine_intro_with_llm(
		intro_text,
		song,
		model_name,
		"final pass before playback",
	)
	if refined:
		after_chars, after_words, after_sentences = _intro_stats(refined)
		print(
			f"{Colors.NAVY}Intro stats (before/after): "
			f"chars {before_chars}->{after_chars}, "
			f"words {before_words}->{after_words}, "
			f"sentences {before_sentences}->{after_sentences}{Colors.ENDC}"
		)

	candidate = refined or intro_text
	final_intro = _finalize_intro_text(candidate, song, model_name, False)
	if not final_intro and refined:
		final_intro = _finalize_intro_text(intro_text, song, model_name, False)
	return final_intro or candidate

#============================================
def _title_tokens(title: str) -> list[str]:
	normalized = _normalize_sentence(title or "")
	if not normalized:
		return []
	tokens = []
	for token in normalized.split():
		if token in TITLE_STOPWORDS:
			continue
		if len(token) < 3 and not token.isdigit():
			continue
		tokens.append(token)
	return tokens

#============================================
def _title_is_mentioned(intro: str, title: str) -> bool:
	if not title:
		return True
	intro_norm = _normalize_sentence(intro or "")
	if not intro_norm:
		return False
	title_norm = _normalize_sentence(title)
	if title_norm and title_norm in intro_norm:
		return True
	tokens = _title_tokens(title)
	if not tokens:
		return True
	intro_tokens = set(intro_norm.split())
	matches = sum(1 for token in tokens if token in intro_tokens)
	if len(tokens) <= 2:
		return matches >= 1
	if len(tokens) <= 4:
		return matches >= 2
	needed = max(2, int(round(len(tokens) * 0.4)))
	return matches >= needed

#============================================
def _has_excessive_repetition(text: str) -> bool:
	"""
	Detect repeated sentences that indicate a looping response.
	"""
	parts = re.split(r"[.!?]+", text)
	counts = {}
	for part in parts:
		normalized = _normalize_sentence(part)
		if not normalized:
			continue
		if len(normalized.split()) < 3:
			continue
		count = counts.get(normalized, 0) + 1
		counts[normalized] = count
		if count > MAX_REPEAT_SENTENCE:
			return True
	return False

#============================================
def _normalize_fact_line(text: str) -> str:
	normalized = text.lower()
	normalized = re.sub(r"^(fact|trivia)\s*:\s*", "", normalized)
	normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
	normalized = re.sub(r"\s+", " ", normalized).strip()
	return normalized

#============================================
#============================================
def _validate_facts_block(text: str) -> tuple[bool, str]:
	"""
	Ensure <facts> contains exactly five unique FACT/TRIVIA lines.
	"""
	lines = [line.strip() for line in text.splitlines() if line.strip()]
	if len(lines) != EXPECTED_FACT_LINES:
		return (False, f"facts line count {len(lines)} != {EXPECTED_FACT_LINES}")

	normalized_lines = []
	for line in lines:
		if not re.match(r"^(fact|trivia)\s*:", line, flags=re.IGNORECASE):
			return (False, "facts lines must start with FACT: or TRIVIA:")
		normalized = _normalize_fact_line(line)
		if not normalized:
			return (False, "empty fact line")
		normalized_lines.append(normalized)

	if len(set(normalized_lines)) != len(normalized_lines):
		return (False, "duplicate FACT/TRIVIA lines")

	return (True, "")

#============================================
def _trim_intro(text: str, max_len: int) -> str:
	if len(text) <= max_len:
		return text
	trimmed = text[:max_len].rstrip()
	if " " in trimmed:
		trimmed = trimmed.rsplit(" ", 1)[0]
	return trimmed.rstrip()

#============================================
def _sanitize_intro_text(text: str) -> str:
	if not text:
		return ""
	cleaned = _strip_code_fences(text)
	cleaned = re.sub(r"<facts[^>]*>.*?</facts[^>]*>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
	cleaned = re.sub(r"</?facts[^>]*>", " ", cleaned, flags=re.IGNORECASE)
	cleaned = re.sub(r"</?response[^>]*>", " ", cleaned, flags=re.IGNORECASE)
	cleaned = re.sub(r"<[^>]+>", " ", cleaned)
	lines = []
	for line in cleaned.splitlines():
		stripped = line.strip()
		if not stripped:
			continue
		lowered = stripped.lower()
		if lowered.startswith("fact:") or lowered.startswith("trivia:"):
			continue
		lines.append(stripped)
	cleaned = " ".join(lines)
	cleaned = re.sub(r"\s+", " ", cleaned).strip()
	return cleaned

#============================================
def _append_title_if_missing(text: str, song_title: str) -> str:
	if not song_title:
		return text
	intro_norm = _normalize_sentence(text)
	title_norm = _normalize_sentence(song_title)
	if not title_norm or title_norm in intro_norm:
		return text
	if text and text[-1] not in ".!?":
		text = text.rstrip() + "."
	if text:
		return f"{text} {song_title}."
	return f"{song_title}."

#============================================
def _intro_stats(text: str) -> tuple[int, int, int]:
	if not text:
		return (0, 0, 0)
	chars = len(text)
	words = len(text.split())
	sentences = _estimate_sentence_count(text)
	return (chars, words, sentences)

#============================================
def _build_relaxed_intro(raw_text: str, song: audio_utils.Song) -> str | None:
	cleaned = _sanitize_intro_text(raw_text)
	if not cleaned:
		return None
	if _starts_with_boilerplate(cleaned):
		return None
	cleaned = _append_title_if_missing(cleaned, song.title or "")
	cleaned = _trim_intro(cleaned, MAX_INTRO_CHARS)
	if _has_excessive_repetition(cleaned):
		return None
	if len(cleaned.split()) < MIN_RELAXED_WORDS:
		return None
	if _estimate_sentence_count(cleaned) < MIN_RELAXED_SENTENCES:
		return None
	return cleaned

#============================================
def prepare_intro_text(
	song: audio_utils.Song,
	prev_song: audio_utils.Song | None = None,
	model_name: str | None = None,
	details_text: str | None = None,
	allow_fallback: bool = True,
	lyrics_text: str | None = None,
) -> str | None:
	"""
	Build a DJ prompt for a song, query the LLM, and extract the intro text.

	Args:
		song (audio_utils.Song): Song object for the current track.
		prev_song (audio_utils.Song | None): Optional previous song for transition.
		model_name (str | None): Name of the Ollama model to use. If None, the
			function will let llm_wrapper choose a model.

	Returns:
		str | None: Cleaned intro text inside <response> tags, or None on failure.
	"""
	file_name = escape(os.path.basename(song.path))
	print(f"{Colors.OKBLUE}Gathering song info and building prompt for {file_name}...{Colors.ENDC}")

	if lyrics_text is None and song:
		file_name = escape(os.path.basename(song.path))
		print(f"{Colors.OKBLUE}Transcribing lyrics for {file_name}...{Colors.ENDC}")
		lyrics_text = transcribe_audio.transcribe_audio(song.path)

	prompt = build_prompt(
		song=song,
		raw_text=None,
		prev_song=prev_song,
		details_text=details_text,
		lyrics_text=lyrics_text,
	)

	print(f"{Colors.SKY_BLUE}Sending prompt to LLM...{Colors.ENDC}")
	dj_intro = llm_wrapper.run_llm(prompt, model_name=model_name)

	print(f"{Colors.LIME_GREEN}Received LLM output; extracting <response> block...{Colors.ENDC}")
	def _use_relaxed_intro(reason: str) -> str | None:
		if not allow_fallback:
			return None
		relaxed_intro = _build_relaxed_intro(dj_intro, song)
		if relaxed_intro:
			print(f"{Colors.WARNING}{escape(reason)} Using relaxed intro fallback.{Colors.ENDC}")
			return relaxed_intro
		return None

	# Use the generic XML extractor for the response tag
	facts_block = llm_wrapper.extract_xml_tag(dj_intro, "facts")
	if not facts_block:
		print(f"{Colors.DARK_YELLOW}No <facts> block detected; continuing anyway.{Colors.ENDC}")
	facts_ok, facts_reason = _validate_facts_block(facts_block)
	if not facts_ok:
		print(f"{Colors.DARK_YELLOW}Invalid <facts> block ({escape(facts_reason)}); continuing anyway.{Colors.ENDC}")

	clean_intro = llm_wrapper.extract_xml_tag(dj_intro, "response")

	if clean_intro:
		print(f"{Colors.SKY_BLUE}Cleaning intro with LLM to reduce fluff...{Colors.ENDC}")
		before_chars, before_words, before_sentences = _intro_stats(clean_intro)
		refined_intro = _refine_intro_with_llm(
			clean_intro,
			song,
			model_name,
			"polish for clarity and remove filler",
		)
		if refined_intro:
			after_chars, after_words, after_sentences = _intro_stats(refined_intro)
			print(
				f"{Colors.NAVY}Intro stats (before/after): "
				f"chars {before_chars}->{after_chars}, "
				f"words {before_words}->{after_words}, "
				f"sentences {before_sentences}->{after_sentences}{Colors.ENDC}"
			)
		candidate_intro = refined_intro or clean_intro
		final_intro = _finalize_intro_text(candidate_intro, song, model_name, False)
		if not final_intro and refined_intro:
			final_intro = _finalize_intro_text(clean_intro, song, model_name, False)
		if final_intro:
			print(f"Extracted intro length: {len(final_intro)} characters.")
			return final_intro
		relaxed_intro = _use_relaxed_intro("Intro failed validation.")
		if relaxed_intro:
			return relaxed_intro
		return None
	else:
		print("No <response> block detected; intro text will be empty.")
		relaxed_intro = _use_relaxed_intro("No <response> block detected.")
		if relaxed_intro:
			return relaxed_intro

	return None

#============================================
def build_prompt(
	song: audio_utils.Song | None,
	raw_text: str | None,
	prev_song: audio_utils.Song | None = None,
	details_text: str | None = None,
	lyrics_text: str | None = None,
) -> str:
	"""
	Build the LLM prompt from song metadata or a simple summary.

	Args:
		song (audio_utils.Song | None): Song object with file and tag info.
		raw_text (str | None): Raw description to use directly.
		prev_song (audio_utils.Song | None): Previous song for transition.

	Returns:
		str: Prompt text.

	Raises:
		ValueError: If neither raw_text nor usable metadata is available.
	"""
	if not raw_text and not song:
		raise ValueError("build_prompt requires raw_text or a valid song with metadata.")

	if raw_text:
		details_intro = "Use the text below as song details.\n\n"
		details_text = raw_text
	else:
		if details_text is None:
			details_text = fetch_song_details(song)
		details_intro = "Use the details below about the song. Treat them as authoritative.\n\n"

	file_summary_block = ""
	file_summary_repeat = ""
	if song:
		file_summary_block = "(**) Here is a brief file summary for context (do not read this verbatim on air):\n"
		file_summary_block += song.one_line_info() + "\n\n"
		file_summary_repeat = "Again here is a brief file summary.\n"
		file_summary_repeat += song.one_line_info() + "\n\n"

	previous_song_block = ""
	if prev_song:
		previous_song_block = "The previous song was (you may reference it briefly):\n"
		previous_song_block += prev_song.one_line_info() + "\n\n"

	lyrics_block = ""
	if lyrics_text:
		clean_lyrics = _sanitize_lyrics_text(lyrics_text)
		if clean_lyrics:
			print(
				f"{Colors.TEAL}Lyrics chars (raw/clean): "
				f"{len(lyrics_text)} / {len(clean_lyrics)}{Colors.ENDC}"
			)
			preview_words = clean_lyrics.split()[:8]
			preview_text = " ".join(preview_words)
			if preview_text:
				print(f"{Colors.TEAL}Lyrics preview: {preview_text}{Colors.ENDC}")
			lyrics_block = "Lyrics (auto-transcribed from audio; partial):\n"
			lyrics_block += clean_lyrics + "\n\n"

	template = prompt_loader.load_prompt("dj_intro.txt")
	return prompt_loader.render_prompt(
		template,
		{
			"file_summary_block": file_summary_block,
			"previous_song_block": previous_song_block,
			"details_intro": details_intro,
			"details_text": details_text,
			"lyrics_block": lyrics_block,
			"file_summary_repeat": file_summary_repeat,
			"target_sentence_min": str(TARGET_SENTENCE_MIN),
			"target_sentence_max": str(TARGET_SENTENCE_MAX),
		},
	)

#============================================
def fetch_song_details(song: audio_utils.Song) -> str:
	meta = audio_file_to_details.Metadata(song.path)
	meta.fetch_wikipedia_info()
	return meta.get_results()

#============================================
def main() -> None:
	args = parse_args()
	if not args.input_file and not args.text:
		raise ValueError("Provide a song file (-i) or raw text (-t).")
	song_obj = audio_utils.Song(args.input_file) if args.input_file else None
	prev_song = None

	if args.text:
		prompt = build_prompt(song=None, raw_text=args.text, prev_song=prev_song, details_text=None)
	else:
		details_text = None
		if not args.use_metadata and song_obj:
			details_text = song_obj.one_line_info()
		lyrics_text = None
		if song_obj:
			file_name = escape(os.path.basename(song_obj.path))
			print(f"{Colors.OKBLUE}Transcribing lyrics for {file_name}...{Colors.ENDC}")
			lyrics_text = transcribe_audio.transcribe_audio(song_obj.path)
		prompt = build_prompt(
			song=song_obj,
			raw_text=None,
			prev_song=prev_song,
			details_text=details_text,
			lyrics_text=lyrics_text,
		)

	print(f"{Colors.SKY_BLUE}Sending prompt to LLM...{Colors.ENDC}")
	raw = llm_wrapper.run_llm(prompt)
	intro = llm_wrapper.extract_response_text(raw)
	if intro:
		print(f"{Colors.PURPLE}DJ Intro:{Colors.ENDC}")
		print(f"{Colors.WHITE}{escape(intro)}{Colors.ENDC}")
	else:
		print(f"{Colors.FAIL}No <response> block found in LLM output.{Colors.ENDC}")

#============================================
if __name__ == "__main__":
	main()
