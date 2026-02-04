# Standard Library
import os
import re
import shutil
import subprocess

# PIP3 modules
from rich import print
from rich.markup import escape

# Local repo modules
from cli_colors import Colors

DEFAULT_WHISPER_PATH = os.path.expanduser("~/nsh/whisper.cpp")
DEFAULT_MODEL_NAME = "ggml-medium.en.bin"
MODEL_URL_BASE = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"

# Local repo modules
import audio_wav

#============================================
def _resolve_whisper_cli() -> str | None:
	return shutil.which("whisper-cli")

#============================================
def _ensure_model(model_path: str, model_url: str, allow_download: bool) -> bool:
	if os.path.isfile(model_path):
		return True
	if not allow_download:
		print(f"{Colors.DARK_ORANGE}Whisper model missing: {escape(model_path)}{Colors.ENDC}")
		return False

	os.makedirs(os.path.dirname(model_path), exist_ok=True)
	curl_bin = shutil.which("curl")
	wget_bin = shutil.which("wget")
	if curl_bin:
		command = [curl_bin, "-L", "-f", "--output", model_path, model_url]
	elif wget_bin:
		command = [wget_bin, "-O", model_path, model_url]
	else:
		print(f"{Colors.FAIL}Model download requires curl or wget.{Colors.ENDC}")
		return False

	print(f"{Colors.SKY_BLUE}Downloading whisper model: {escape(os.path.basename(model_path))}{Colors.ENDC}")
	result = subprocess.run(command, capture_output=True, text=True)
	if result.returncode != 0:
		error_text = result.stderr.strip() or result.stdout.strip()
		print(f"{Colors.FAIL}Model download failed: {escape(error_text)}{Colors.ENDC}")
		return False
	return os.path.isfile(model_path)

#============================================
def _maybe_set_metal_resources(env: dict) -> None:
	if env.get("GGML_METAL_PATH_RESOURCES"):
		return
	brew_bin = shutil.which("brew")
	if not brew_bin:
		return
	result = subprocess.run([brew_bin, "--prefix", "whisper-cpp"], capture_output=True, text=True)
	if result.returncode != 0:
		return
	prefix = result.stdout.strip()
	if not prefix:
		return
	metal_path = os.path.join(prefix, "share", "whisper-cpp", "ggml-metal.metal")
	if os.path.isfile(metal_path):
		env["GGML_METAL_PATH_RESOURCES"] = os.path.dirname(metal_path)

#============================================
def transcribe_audio(
	audio_path: str,
	model_name: str | None = None,
	whisper_path: str | None = None,
	allow_download: bool = True,
) -> str | None:
	"""
	Transcribe an audio file to text using whisper.cpp's whisper-cli.
	"""
	if not audio_path:
		return None
	if not os.path.isfile(audio_path):
		print(f"{Colors.LIGHT_ORANGE}Audio file not found: {escape(audio_path)}{Colors.ENDC}")
		return None

	whisper_cli = _resolve_whisper_cli()
	if not whisper_cli:
		print(f"{Colors.DARK_ORANGE}whisper-cli not found in PATH; skipping lyrics.{Colors.ENDC}")
		return None

	whisper_root = os.path.expanduser(whisper_path or os.environ.get("WHISPER_PATH", "") or DEFAULT_WHISPER_PATH)
	model_name = model_name or os.environ.get("WHISPER_MODEL", "") or DEFAULT_MODEL_NAME
	model_path = os.path.join(whisper_root, "models", model_name)
	model_url = f"{MODEL_URL_BASE}/{model_name}"

	if not _ensure_model(model_path, model_url, allow_download):
		return None

	env = os.environ.copy()
	env["WHISPER_METAL"] = "1"
	_maybe_set_metal_resources(env)

	audio_wav_path = audio_wav.create_transcription_wav(audio_path)
	if not audio_wav_path:
		return None

	print(f"{Colors.SKY_BLUE}Transcribe with whisper.cpp{Colors.ENDC}")
	temp_dir = os.path.dirname(audio_wav_path)
	wav_name = os.path.basename(audio_wav_path)
	whisper_cmd = [
		whisper_cli,
		"--model",
		model_path,
		"--language",
		"en",
		"--output-txt",
		"--print-colors",
		wav_name,
	]
	whisper_result = subprocess.run(
		whisper_cmd,
		capture_output=True,
		text=True,
		errors="replace",
		env=env,
		cwd=temp_dir,
	)
	if whisper_result.returncode != 0:
		error_text = whisper_result.stderr.strip() or whisper_result.stdout.strip()
		print(f"{Colors.FAIL}Whisper transcription failed: {escape(error_text)}{Colors.ENDC}")
		try:
			os.unlink(audio_wav_path)
		except OSError:
			pass
		return None

	stderr_text = whisper_result.stderr or ""
	if re.search(r"metal backend|ggml_metal_init", stderr_text, flags=re.IGNORECASE):
		print(f"{Colors.LIME_GREEN}Metal backend: detected{Colors.ENDC}")
	else:
		print(f"{Colors.DARK_YELLOW}Metal backend: not detected{Colors.ENDC}")
		if not env.get("GGML_METAL_PATH_RESOURCES"):
			print(f"{Colors.DARK_YELLOW}Hint: set GGML_METAL_PATH_RESOURCES=\"$(brew --prefix whisper-cpp)/share/whisper-cpp\"{Colors.ENDC}")

	transcript_path = os.path.join(temp_dir, f"{wav_name}.txt")
	transcript = ""
	if os.path.isfile(transcript_path):
		with open(transcript_path, "r", encoding="utf-8") as handle:
			transcript = handle.read().strip()
		try:
			os.unlink(transcript_path)
		except OSError:
			pass
	try:
		os.unlink(audio_wav_path)
	except OSError:
		pass

	if not transcript:
		print(f"{Colors.LIGHT_ORANGE}No transcript produced for {escape(os.path.basename(audio_path))}.{Colors.ENDC}")
		return None
	return transcript
