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
	cleaned = re.sub(r"<facts[^>]*>.*?</facts[^>]*>", " ", text, flags=re.IGNORECASE | re.DOTALL)
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
	cleaned = _append_title_if_missing(cleaned, song.title or "")
	cleaned = _trim_intro(cleaned, MAX_INTRO_CHARS)
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
		prompt += "- Do not include the strings 'FACT:' or 'TRIVIA:' inside <response>.\n"
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
		print(f"{Colors.WARNING}No <facts> block detected; rejecting output.{Colors.ENDC}")
		relaxed_intro = _use_relaxed_intro("Missing <facts> block.")
		if relaxed_intro:
			return relaxed_intro
		return None
	facts_ok, facts_reason = _validate_facts_block(facts_block)
	if not facts_ok:
		print(f"{Colors.WARNING}Invalid <facts> block ({facts_reason}); rejecting output.{Colors.ENDC}")
		relaxed_intro = _use_relaxed_intro("Invalid <facts> block.")
		if relaxed_intro:
			return relaxed_intro
		return None

	clean_intro = llm_wrapper.extract_xml_tag(dj_intro, "response")

	if clean_intro:
		intro_length = len(clean_intro)
		print(f"Extracted intro length: {intro_length} characters.")
		if intro_length > MAX_INTRO_CHARS:
			print(
				f"{Colors.WARNING}Intro too long ({intro_length} chars); "
				f"rejecting and retrying.{Colors.ENDC}"
			)
			relaxed_intro = _use_relaxed_intro("Intro too long.")
			if relaxed_intro:
				return relaxed_intro
			return None
		lowered = clean_intro.lower()
		if "fact:" in lowered or "trivia:" in lowered:
			print(f"{Colors.WARNING}Intro contains FACT/TRIVIA lines; rejecting output.{Colors.ENDC}")
			relaxed_intro = _use_relaxed_intro("Intro contains FACT/TRIVIA lines.")
			if relaxed_intro:
				return relaxed_intro
			return None
		if "<" in clean_intro and ">" in clean_intro:
			print(f"{Colors.WARNING}Intro contains markup; rejecting output.{Colors.ENDC}")
			relaxed_intro = _use_relaxed_intro("Intro contains markup.")
			if relaxed_intro:
				return relaxed_intro
			return None
		sentence_count = _estimate_sentence_count(clean_intro)
		if sentence_count < MIN_INTRO_SENTENCES or sentence_count > MAX_INTRO_SENTENCES:
			print(
				f"{Colors.WARNING}Intro sentence count out of range ({sentence_count}); "
				f"rejecting output.{Colors.ENDC}"
			)
			relaxed_intro = _use_relaxed_intro("Intro sentence count out of range.")
			if relaxed_intro:
				return relaxed_intro
			return None
		if _has_excessive_repetition(clean_intro):
			print(f"{Colors.WARNING}Intro repeats sentences; rejecting output.{Colors.ENDC}")
			relaxed_intro = _use_relaxed_intro("Intro repeats sentences.")
			if relaxed_intro:
				return relaxed_intro
			return None
		if not _title_is_mentioned(clean_intro, song.title or ""):
			print(f"{Colors.WARNING}Intro missing song title; allowing output.{Colors.ENDC}")
			if allow_fallback and song.title:
				amended = _append_title_if_missing(clean_intro, song.title)
				if amended != clean_intro:
					if len(amended) <= MAX_INTRO_CHARS:
						clean_intro = amended
					else:
						print(f"{Colors.WARNING}Intro title append would exceed max length; keeping original.{Colors.ENDC}")
	else:
		print("No <response> block detected; intro text will be empty.")
		relaxed_intro = _use_relaxed_intro("No <response> block detected.")
		if relaxed_intro:
			return relaxed_intro

	return clean_intro

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
		"Do not mention any city, town, or location. "
		"Avoid brackets, parentheses, and em dashes. "
		"You must base your intro on concrete facts from the Song details section. "
		"Do not open with 'Ladies and gentlemen' or a generic welcome-to-the-show line. "
		"Make the first sentence tie directly to the song details. "
		"Prefer human and creative context over statistics. "
		"Do not invent facts that are not supported by the Song details. "
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
		"Do NOT include any 'FACT:' or 'TRIVIA:' lines inside <response>. "
		"The <response> must be at least 200 characters. "
		"Wrap the final spoken intro inside <response>...</response>. "
		"Output only the <facts> and <response> tags, and nothing else."
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

	prompt += "Do not write a vague or generic intro; "
	prompt += "specific facts and small stories are more important than hype.\n"

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
