#!/usr/bin/env python3

# Standard Library
import argparse
import os
import re

# Local repo modules
import audio_utils
import audio_file_to_details
import llm_wrapper

#============================================
class Colors:
	OKBLUE = "\033[94m"
	OKGREEN = "\033[92m"
	OKCYAN = "\033[96m"
	WARNING = "\033[93m"
	FAIL = "\033[91m"
	ENDC = "\033[0m"

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
def _starts_with_boilerplate(text: str) -> bool:
	if not text:
		return False
	pattern = r"^\s*ladies and gentlemen,?\s*welcome to"
	return re.match(pattern, text, flags=re.IGNORECASE) is not None

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
		print(f"{Colors.WARNING}Intro missing song title; allowing output.{Colors.ENDC}")
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
	prompt = (
		"You are rewriting a DJ intro to fix issues. "
		"Use only the provided facts and rephrase the text. "
		"Use plain text with simple formatting. "
		"Keep it lively and non-repetitive. "
		"Start with a song-specific line to get the audience engaged immediately. "
		"Keep it to 5-7 sentences. "
		"Return only the revised intro text.\n\n"
		f"Issue: {reason}\n"
		"Intro text:\n"
		f"{text}\n"
	)
	refined = llm_wrapper.run_llm(prompt, model_name=model_name)
	if not refined:
		return None
	refined = _strip_code_fences(refined)
	return refined.strip() or None

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
	strict_reminder: bool = False,
	allow_fallback: bool = True,
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
	print(f"{Colors.OKBLUE}Gathering song info and building prompt for {os.path.basename(song.path)}...{Colors.ENDC}")

	prompt = build_prompt(
		song=song,
		raw_text=None,
		prev_song=prev_song,
		details_text=details_text,
	)
	if strict_reminder:
		prompt += "\n(**) IMPORTANT VALIDATION RULES:\n"
		prompt += "- Put the FACT/TRIVIA lines inside <facts>...</facts>, outside <response>.\n"
		prompt += "- The <response> must contain ONLY the final spoken intro.\n"
		prompt += "- The <response> must be 3-10 sentences and at least 200 characters.\n"
		prompt += f"- Aim for {TARGET_SENTENCE_MIN}-{TARGET_SENTENCE_MAX} sentences.\n"
		prompt += "- The <response> contains only the intro text; FACT/TRIVIA lines belong in <facts>.\n"
		prompt += "- Output only <facts> and <response> tags, nothing else.\n"

	print(f"{Colors.OKBLUE}Sending prompt to LLM...{Colors.ENDC}")
	dj_intro = llm_wrapper.run_llm(prompt, model_name=model_name)

	print(f"{Colors.OKGREEN}Received LLM output; extracting <response> block...{Colors.ENDC}")
	def _use_relaxed_intro(reason: str) -> str | None:
		if not allow_fallback:
			return None
		relaxed_intro = _build_relaxed_intro(dj_intro, song)
		if relaxed_intro:
			print(f"{Colors.WARNING}{reason} Using relaxed intro fallback.{Colors.ENDC}")
			return relaxed_intro
		return None

	# Use the generic XML extractor for the response tag
	facts_block = llm_wrapper.extract_xml_tag(dj_intro, "facts")
	if not facts_block:
		print(f"{Colors.WARNING}No <facts> block detected; continuing anyway.{Colors.ENDC}")
	facts_ok, facts_reason = _validate_facts_block(facts_block)
	if not facts_ok:
		print(f"{Colors.WARNING}Invalid <facts> block ({facts_reason}); continuing anyway.{Colors.ENDC}")

	clean_intro = llm_wrapper.extract_xml_tag(dj_intro, "response")

	if clean_intro:
		final_intro = _finalize_intro_text(clean_intro, song, model_name, allow_fallback)
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
	base = (
		"(**) You are a charismatic radio DJ. "
		"Keep the intro natural and conversational. "
		"Focus on song and artist details, particular specific facts. "
		"Use plain human readable sentences with standard punctuation and ascii/ISO 8859-1 characters. "
		"You must base your intro on concrete facts from the Song details section. "
		"Keep it lively and non-repetitive. "
		"Use plain text with simple formatting. "
		"Open with a song-specific line to get the audience engaged immediately. "
		"Make the first sentence tie directly to the song details. "
		"Prefer human and creative context over statistics. "
		"Use only facts supported by the Song details. "
	)

	if not raw_text and not song:
		raise ValueError("build_prompt requires raw_text or a valid song with metadata.")

	if raw_text:
		details_intro = "Use the text below as song details.\n\n"
		details_text = raw_text
	else:
		if details_text is None:
			details_text = fetch_song_details(song)
		details_intro = "Use the details below about the song. Treat them as authoritative.\n\n"

	ending = (
		"\n\n(**) First, write exactly five lines that each start with 'FACT: ' or 'TRIVIA: '. "
		"Each FACT/TRIVIA line must contain one specific factual detail drawn from the Song details. "
		"Prioritize personal or creative context over charts or awards, such as: "
		"how or why the song was written, stories from recording, changes in the band's sound, "
		"lyrical themes, tensions or milestones for the band, or how it fits into the album. "
		"Only use chart positions or awards if there is no stronger story available. "
		"Wrap those five lines inside <facts>...</facts> tags. "
		"\n(**) After the <facts> block, write the final spoken intro. "
		"In the intro, weave in at least two of the facts you listed. "
		"Make it sound like you are telling a brief story about the band around this track, "
		"not reading a press release. "
		"Write the intro with a sense of rise and fall. Begin with a lively opening line, "
		"follow with a softer or more reflective line, then lift the energy again before "
		"the final handoff to the song. "
		"End by repeating the song title if it fits naturally, and feel free to mention the artist. "
		"Keep the intro to 3-10 sentences, aiming for "
		f"{TARGET_SENTENCE_MIN}-{TARGET_SENTENCE_MAX} sentences. "
		"The <response> block must contain ONLY the final intro text. "
		"Place FACT/TRIVIA lines only inside <facts> and keep <response> for the intro. "
		"The <response> must be at least 200 characters. "
		"Wrap the final spoken intro inside <response>...</response>. "
		"Output only the <facts> and <response> tags."
	)

	prompt = base

	if song:
		prompt += "(**) Here is a brief file summary for context (do not read this verbatim on air):\n"
		prompt += song.one_line_info() + "\n\n"
	if prev_song:
		prompt += "The previous song was (you may reference it briefly):\n"
		prompt += prev_song.one_line_info() + "\n\n"

	prompt += details_intro
	prompt += "Song details:\n"
	prompt += details_text + "\n\n"

	prompt += "Write a specific, concrete intro with small stories; "
	prompt += "facts and small stories are more important than hype.\n"

	if song:
		prompt += "Again here is a brief file summary.\n"
		prompt += song.one_line_info() + "\n\n"

	prompt += ending + "\n\n"

	return prompt

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
		prompt = build_prompt(song=song_obj, raw_text=None, prev_song=prev_song, details_text=details_text)

	print(f"{Colors.OKBLUE}Sending prompt to LLM...{Colors.ENDC}")
	raw = llm_wrapper.run_llm(prompt)
	intro = llm_wrapper.extract_response_text(raw)
	if intro:
		print(f"{Colors.OKGREEN}DJ Intro:{Colors.ENDC}")
		print(f"{Colors.OKCYAN}{intro}{Colors.ENDC}")
	else:
		print(f"{Colors.FAIL}No <response> block found in LLM output.{Colors.ENDC}")

#============================================
if __name__ == "__main__":
	main()
