#!/usr/bin/env python3

import re
import subprocess

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
def extract_xml_tag(raw_text: str, tag: str) -> str:
	"""
	Extract the last occurrence of a given XML-like tag.

	Args:
		raw_text (str): LLM output.
		tag (str): Tag name to extract, for example 'choice' or 'response'.

	Returns:
		str: Extracted text or empty string if not found.
	"""
	if not raw_text:
		return ""

	lower = raw_text.lower()
	open_token = f"<{tag}"
	close_token = f"</{tag}"

	# Find last opening tag
	start_idx = lower.rfind(open_token)
	if start_idx == -1:
		return ""

	# Find '>' that ends the opening tag
	gt_idx = raw_text.find(">", start_idx)
	if gt_idx == -1:
		return ""

	# Look for closing tag after the opening tag
	close_idx = lower.find(close_token, gt_idx + 1)

	if close_idx == -1:
		# No closing tag found; tolerate missing end tag and
		# take everything until the end of the string
		content = raw_text[gt_idx + 1 :]
		return content.strip()

	# Normal case: take content between opening '>' and closing tag
	content = raw_text[gt_idx + 1 : close_idx]
	return content.strip()


_raw = "<response>Hello</response>"
assert extract_xml_tag(_raw, "response") == "Hello"

_raw2 = "<response>\nYou know that Canadian indie rock super-group..."
assert extract_xml_tag(_raw2, "response").startswith("You know that Canadian")

#============================================
def get_vram_size_in_gb() -> int | None:
	"""
	Detect GPU VRAM or unified memory on macOS systems.

	Returns:
		int | None: Size in GB if detected.
	"""
	try:
		architecture = subprocess.check_output(["uname", "-m"], text=True).strip()
		is_apple_silicon = architecture.startswith("arm64")
		if is_apple_silicon:
			hardware_info = subprocess.check_output(
				["system_profiler", "SPHardwareDataType"],
				text=True,
			)
			match = re.search(r"Memory:\s(\d+)\s?GB", hardware_info)
			if match:
				return int(match.group(1))
		else:
			display_info = subprocess.check_output(
				["system_profiler", "SPDisplaysDataType"],
				text=True,
			)
			vram_match = re.search(r"VRAM.*?: (\d+)\s?MB", display_info)
			if vram_match:
				size_mb = int(vram_match.group(1))
				return size_mb // 1024
	except Exception:
		return None
	return None

#============================================
def list_ollama_models() -> list:
	"""
	List available Ollama models, raising if the service is unavailable.

	Returns:
		list: Model names.
	"""
	command = ["ollama", "list"]
	result = subprocess.run(command, capture_output=True, text=True)
	if result.returncode != 0:
		message = result.stderr.strip() or "Ollama service not responding."
		raise RuntimeError(f"Ollama unavailable: {message}")
	lines = result.stdout.strip().splitlines()
	models = []
	for line in lines[1:]:
		parts = line.split()
		if parts:
			models.append(parts[0])
	return models

#============================================
def select_ollama_model() -> str:
	"""
	Select an Ollama model based on VRAM or unified memory and local availability.

	Returns:
		str: Model name to use.

	Raises:
		RuntimeError: If the chosen model is not available.
	"""
	vram_size_gb = get_vram_size_in_gb()
	if vram_size_gb is None:
		raise ValueError("Unable to detect VRAM/unified memory for model selection.")
	available = list_ollama_models()

	model_name = "llama3.2:1b-instruct-q4_K_M"
	if vram_size_gb > 40:
		model_name = "gpt-oss:20b"
	elif vram_size_gb > 14:
		model_name = "phi4:14b-q4_K_M"
	elif vram_size_gb > 4:
		model_name = "llama3.2:3b-instruct-q5_K_M"

	if model_name not in available:
		available_display = ", ".join(available) if available else "none"
		raise RuntimeError(
			f"Required model '{model_name}' not found locally. "
			f"Available models: {available_display}. "
			f"Try: ollama pull {model_name}"
		)
	return model_name

#============================================
def query_ollama_model(prompt: str, model_name: str) -> str:
	"""
	Query Ollama with the given prompt, handling model selection.

	Args:
		prompt (str): Prompt text.
		model_name (str): Name of the Ollama model to use.

	Returns:
		str: Model response (may be empty on error).
	"""
	print(f"{Colors.OKBLUE}Sending prompt to LLM with model {model_name}...{Colors.ENDC}")
	print(f"{Colors.WARNING}Waiting for response...{Colors.ENDC}")
	command = ["ollama", "run", model_name, prompt]
	result = subprocess.run(command, capture_output=True, text=True)
	if result.returncode != 0:
		print(f"{Colors.FAIL}Ollama error: {result.stderr.strip()}{Colors.ENDC}")
		return ""
	output = result.stdout.strip()
	print(f"{Colors.OKGREEN}LLM response length: {len(output)} characters.{Colors.ENDC}")
	return output

#============================================
def extract_response_text(raw_text: str) -> str:
	"""
	Extract content inside <response> tags. Returns empty string if not found.

	Args:
		raw_text (str): LLM output.

	Returns:
		str: Cleaned response text or empty string.
	"""
	if not raw_text:
		return ""
	lowered = raw_text.lower()
	start_idx = lowered.rfind("<response")
	if start_idx == -1:
		return ""
	after_start = raw_text[start_idx:]
	if not after_start.rstrip().lower().endswith("</response>"):
		after_start = f"{after_start}</response>"
	match = re.search(
		r"<response[^>]*>(.*?)</response[^>]*>",
		after_start,
		re.IGNORECASE | re.DOTALL,
	)
	if not match:
		return ""
	return match.group(1).strip()
