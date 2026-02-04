import os
import re
import time
import hashlib
import datetime
import subprocess

# PIP3 modules
from rich import print
from rich.markup import escape

# Local repo modules
from cli_colors import Colors

#============================================
LLM_LOG_PATH = os.path.join("output", "llm_responses.log")

#============================================
def _log_llm_exchange(
	prompt: str,
	response: str,
	backend: str,
	model_name: str | None,
	elapsed: float,
	error_text: str | None = None,
) -> None:
	"""
	Append a formatted LLM exchange entry to the log file.
	"""
	try:
		log_dir = os.path.dirname(LLM_LOG_PATH)
		if log_dir:
			os.makedirs(log_dir, exist_ok=True)
		timestamp = datetime.datetime.now().isoformat(timespec="seconds")
		prompt_text = prompt or ""
		response_text = response or ""
		prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
		with open(LLM_LOG_PATH, "a", encoding="utf-8") as handle:
			handle.write("=" * 72 + "\n")
			handle.write(f"Timestamp: {timestamp}\n")
			handle.write(f"Backend: {backend}\n")
			handle.write(f"Model: {model_name or 'n/a'}\n")
			handle.write(f"Elapsed: {elapsed:.2f}s\n")
			handle.write(f"Prompt SHA256: {prompt_hash}\n")
			if error_text:
				handle.write(f"Error: {error_text}\n")
			handle.write("Prompt:\n")
			handle.write(prompt_text.strip() + "\n")
			handle.write("Response:\n")
			handle.write(response_text.strip() + "\n")
			handle.write("=" * 72 + "\n\n")
	except Exception:
		return

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
		# system_profiler is macOS-only; this will fail on Linux/Windows.
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
	env_model = os.environ.get("OLLAMA_MODEL", "").strip()
	if env_model:
		return env_model

	vram_size_gb = get_vram_size_in_gb()
	available = list_ollama_models()

	model_name = "llama3.2:1b-instruct-q4_K_M"
	if vram_size_gb is None:
		# Non-macOS or unknown VRAM: pick a reasonable default and validate availability.
		model_name = "llama3.2:3b-instruct-q5_K_M"
	else:
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
	print(f"{Colors.OKBLUE}Sending prompt to LLM with model {escape(model_name)}...{Colors.ENDC}")
	print(f"{Colors.WARNING}Waiting for response...{Colors.ENDC}")
	command = ["ollama", "run", model_name, prompt]
	start_time = time.time()
	result = subprocess.run(command, capture_output=True, text=True)
	elapsed = time.time() - start_time
	if result.returncode != 0:
		print(f"{Colors.FAIL}Ollama error: {escape(result.stderr.strip())}{Colors.ENDC}")
		return ""
	output = result.stdout.strip()
	print(
		f"{Colors.OKGREEN}LLM response length: {len(output)} characters "
		f"({elapsed:.2f}s).{Colors.ENDC}"
	)
	return output

#============================================
def is_apple_model_available() -> bool:
	"""
	Check whether Apple Foundation Models is available and enabled.

	Returns:
		bool: True if AFM can be used on this machine.
	"""
	try:
		import config_apple_models
		return config_apple_models.apple_models_available()
	except Exception:
		return False

#============================================
def get_llm_backend(preferred: str | None = None) -> str:
	"""
	Resolve which LLM backend to use.

	Priority:
		1) preferred argument
		2) DJ_LLM_BACKEND env var
		3) auto (AFM if available, else Ollama)

	Valid values: auto, afm, ollama
	"""
	value = (preferred or os.environ.get("DJ_LLM_BACKEND", "auto")).strip().lower()
	if value in ("auto", "afm", "ollama"):
		return value
	raise ValueError("DJ_LLM_BACKEND must be one of: auto, afm, ollama")

#============================================
def get_default_model_name(backend: str | None = None) -> str | None:
	"""
	Get a default model name for the active backend.

	Returns:
		str | None: Ollama model name, or None for AFM.
	"""
	chosen = get_llm_backend(backend)
	if chosen == "afm":
		return None
	if chosen == "auto" and is_apple_model_available():
		return None
	return select_ollama_model()

#============================================
def run_llm(
	prompt: str,
	model_name: str | None = None,
	backend: str | None = None,
	max_tokens: int | None = None,
) -> str:
	"""
	Run an LLM call using the configured backend.

	Args:
		prompt (str): Prompt text.
		model_name (str | None): Ollama model to use (ignored by AFM).
		backend (str | None): Override backend (auto/afm/ollama).
		max_tokens (int | None): Backend-specific generation limit.

	Returns:
		str: Raw model output (may be empty on error).
	"""
	chosen = get_llm_backend(backend)
	if chosen == "auto":
		chosen = "afm" if is_apple_model_available() else "ollama"

	start_time = time.time()
	response = ""
	error_text = ""
	resolved_model = model_name

	if chosen == "afm":
		try:
			import config_apple_models
			print(f"{Colors.OKBLUE}Sending prompt to Apple Foundation Models...{Colors.ENDC}")
			print(f"{Colors.WARNING}Waiting for response...{Colors.ENDC}")
			response = config_apple_models.run_apple_model(
				prompt,
				max_tokens=max_tokens or 1200,
			)
		except Exception as error:
			error_text = str(error)
			print(f"{Colors.FAIL}AFM error: {escape(error_text)}{Colors.ENDC}")
	else:
		resolved_model = resolved_model or select_ollama_model()
		response = query_ollama_model(prompt, resolved_model)

	elapsed = time.time() - start_time
	_log_llm_exchange(prompt, response, chosen, resolved_model, elapsed, error_text or None)

	if error_text:
		return ""
	return response

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
