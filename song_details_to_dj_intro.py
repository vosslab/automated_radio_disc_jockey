#!/usr/bin/env python3

# Standard Library
import argparse
import os

# Local repo modules
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
def build_prompt(path: str | None, use_metadata: bool, raw_text: str | None) -> str:
	"""
	Build the LLM prompt from song metadata or a simple summary.

	Args:
		path (str | None): Song file path.
		use_metadata (bool): Whether to use detailed metadata prompt.
		raw_text (str | None): Raw description to use directly.

	Returns:
		str: Prompt text.
	"""
	if raw_text:
		prompt = ""
		prompt += "You are a radio DJ introducing the following song details. "
		prompt += "Do not add locations. Keep sentences short and natural. "
		prompt += "Wrap the final intro inside <response>...</response>. "
		prompt += f"Details: {raw_text}"
		return prompt
	if use_metadata and path:
		meta = audio_file_to_details.Metadata(path)
		meta.fetch_wikipedia_info()
		prompt = ""
		prompt += "You're a charismatic radio DJ. Keep it short and natural (3-4 sentences). "
		prompt += "Do not mention any city, town, or location. "
		prompt += "Avoid brackets/parentheses and em dashes. "
		prompt += "Include 1-2 interesting facts from the details below. "
		prompt += "Respond only with the final spoken intro inside <response>...</response>.\n\n"
		prompt += "Song details:\n"
		prompt += meta.get_results()
	else:
		name = os.path.basename(path) if path else "Unknown song"
		prompt = ""
		prompt += "Imagine you are a radio disc jockey introducing a song. "
		prompt += f"Start with the band and song name: {name}. "
		prompt += "Give two quick facts, then repeat the band and song name. "
		prompt += " Keep it to 3-4 sentences. "
		prompt += "Wrap the final intro inside <response>...</response>."
	return prompt

#============================================
def main() -> None:
	args = parse_args()
	if not args.input_file and not args.text:
		raise ValueError("Provide a song file (-i) or raw text (-t).")
	prompt = build_prompt(args.input_file, args.use_metadata, args.text)
	print(f"{Colors.OKBLUE}Sending prompt to LLM...{Colors.ENDC}")
	raw = llm_wrapper.query_ollama_model(prompt)
	intro = llm_wrapper.extract_response_text(raw)
	if intro:
		print(f"{Colors.OKGREEN}DJ Intro:{Colors.ENDC}")
		print(f"{Colors.OKCYAN}{intro}{Colors.ENDC}")
	else:
		print(f"{Colors.FAIL}No <response> block found in LLM output.{Colors.ENDC}")

#============================================
if __name__ == "__main__":
	main()
