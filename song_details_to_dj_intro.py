#!/usr/bin/env python3

# Standard Library
import argparse
import os

# Local repo modules
import audio_utils
import audio_file_to_details
import llm_wrapper

#============================================
class Colors:
	OKBLUE = "\033[94m"
	OKGREEN = "\033[92m"
	OKCYAN = "\033[96m"
	FAIL = "\033[91m"
	ENDC = "\033[0m"

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
#============================================
def prepare_intro_text(
	song: audio_utils.Song,
	prev_song: audio_utils.Song | None = None,
	model_name: str | None = None,
) -> str:
	"""
	Build a DJ prompt for a song, query the LLM, and extract the intro text.

	Args:
		song (audio_utils.Song): Song object for the current track.
		prev_song (audio_utils.Song | None): Optional previous song for transition.
		model_name (str | None): Name of the Ollama model to use. If None, the
			function will let llm_wrapper choose a model.

	Returns:
		str: Cleaned intro text inside <response> tags, or empty string on failure.
	"""
	print(f"{Colors.OKBLUE}Gathering song info and building prompt for {os.path.basename(song.path)}...{Colors.ENDC}")

	prompt = build_prompt(
		song=song,
		raw_text=None,
		prev_song=prev_song,
	)

	print(f"{Colors.OKBLUE}Sending prompt to LLM...{Colors.ENDC}")
	dj_intro = llm_wrapper.query_ollama_model(prompt, model_name)

	print(f"{Colors.OKGREEN}Received LLM output; extracting <response> block...{Colors.ENDC}")
	# Use the generic XML extractor for the response tag
	clean_intro = llm_wrapper.extract_xml_tag(dj_intro, "response")

	if clean_intro:
		print(f"Extracted intro length: {len(clean_intro)} characters.")
	else:
		print("No <response> block detected; intro text will be empty.")

	return clean_intro

#============================================
def build_prompt(
	song: audio_utils.Song | None,
	raw_text: str | None,
	prev_song: audio_utils.Song | None = None,
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
		"You are a charismatic radio DJ. "
		"Keep the intro natural and conversational. "
		"Do not mention any city, town, or location. "
		"Avoid brackets, parentheses, and em dashes. "
		"You must base your intro on concrete facts from the Song details section. "
		"Prefer human and creative context over statistics. "
		"Do not invent facts that are not supported by the Song details. "
	)

	if not raw_text and not song:
		raise ValueError("build_prompt requires raw_text or a valid song with metadata.")

	if raw_text:
		details_intro = "Use the text below as song details.\n\n"
		details_text = raw_text
	else:
		meta = audio_file_to_details.Metadata(song.path)
		meta.fetch_wikipedia_info()
		details_intro = "Use the details below about the song. Treat them as authoritative.\n\n"
		details_text = meta.get_results()

	ending = (
		"\n\nFirst, write exactly five lines that each start with 'FACT: '. "
		"Each FACT line must contain one specific factual detail drawn from the Song details. "
		"Prioritize personal or creative context over charts or awards, such as: "
		"how or why the song was written, stories from recording, changes in the band's sound, "
		"lyrical themes, tensions or milestones for the band, or how it fits into the album. "
		"Only use chart positions or awards if there is no stronger story available. "
		"After those five FACT lines, write the final spoken intro. "
		"In the intro, weave in at least two of the facts you listed. "
		"Make it sound like you are telling a brief story about the band around this track, "
		"not reading a press release. "
		"End by repeating the band name and song title. "
		"Keep the intro to 3-5 sentences. "
		"Wrap the final spoken intro inside <response>...</response>."
	)

	prompt = base

	if song:
		prompt += "Here is a brief file summary for context (do not read this verbatim on air):\n"
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
def main() -> None:
	args = parse_args()
	if not args.input_file and not args.text:
		raise ValueError("Provide a song file (-i) or raw text (-t).")
	song_obj = audio_utils.Song(args.input_file) if args.input_file else None
	prompt = build_prompt(song_obj, args.use_metadata, args.text)
	print(f"{Colors.OKBLUE}Sending prompt to LLM...{Colors.ENDC}")
	model_name = llm_wrapper.select_ollama_model()
	raw = llm_wrapper.query_ollama_model(prompt, model_name)
	intro = llm_wrapper.extract_response_text(raw)
	if intro:
		print(f"{Colors.OKGREEN}DJ Intro:{Colors.ENDC}")
		print(f"{Colors.OKCYAN}{intro}{Colors.ENDC}")
	else:
		print(f"{Colors.FAIL}No <response> block found in LLM output.{Colors.ENDC}")

#============================================
if __name__ == "__main__":
	main()
