"""
Apple Foundation Models integration.

This module assumes an Apple Silicon Mac running macOS 26+ with Apple
Intelligence enabled. It provides a small wrapper so the rest of the
pipeline can request a single text generation without managing sessions.
"""

# Standard Library
import platform
import time

from applefoundationmodels import Session, apple_intelligence_available

MIN_MACOS_MAJOR = 26


#============================================
def _parse_macos_version() -> tuple[int, int, int]:
	"""Return the macOS version as a tuple (major, minor, patch)."""
	version_str = platform.mac_ver()[0]
	parts = [int(p) for p in version_str.split(".") if p.isdigit()]
	while len(parts) < 3:
		parts.append(0)
	if len(parts) >= 3:
		return parts[0], parts[1], parts[2]
	return (0, 0, 0)


#============================================
def _require_apple_intelligence():
	"""Validate architecture, OS version, and Apple Intelligence availability."""
	arch = platform.machine().lower()
	if arch != "arm64":
		raise RuntimeError("Apple Intelligence is only supported on Apple Silicon (arm64).")

	major, minor, patch = _parse_macos_version()
	if major < MIN_MACOS_MAJOR:
		raise RuntimeError(
			f"macOS {MIN_MACOS_MAJOR}.0 or later is required (detected {major}.{minor}.{patch})."
		)

	if not apple_intelligence_available():
		# Try to provide the framework's reason if available.
		try:
			reason = Session.get_availability_reason()
		except Exception:  # pylint: disable=broad-exception-caught
			reason = "Apple Intelligence not available or not enabled."
		raise RuntimeError(str(reason))

#============================================
def apple_models_available() -> bool:
	"""
	Check whether Apple Foundation Models is available on this machine.

	Returns:
		bool: True if AFM can be used, otherwise False.
	"""
	try:
		_require_apple_intelligence()
		return True
	except Exception:
		return False


#============================================
def unit_test():
	"""Simple unit test for the Apple Foundation Models backend."""
	import random

	print("Running Apple Foundation Models unit test...")
	_require_apple_intelligence()
	num1 = random.randint(10, 99)
	num2 = random.randint(10, 99)
	expected_answer = num1 + num2
	prompt = f"What is {num1} + {num2}? Provide just the integer answer with no punctuation or explanation."
	response = run_apple_model(prompt)
	try:
		ai_answer = int(response.strip())
	except ValueError:
		raise RuntimeError(f"Response was not a valid number -> {response}")

	if ai_answer != expected_answer:
		raise RuntimeError(f"Expected {expected_answer}, but got {ai_answer}")
	print(f"SUCCESS! {num1} + {num2} = {ai_answer}")


#============================================
def run_apple_model(
	prompt: str,
	instructions: str | None = None,
	max_retries: int = 2,
	max_tokens: int = 1200,
	temperature: float = 0.2,
) -> str:
	"""
	Generate a response using the Apple Foundation Models backend.

	Args:
		prompt: Full text prompt.
		instructions: Session-level instructions for the model.
		max_retries: Retry attempts on transient errors.
		max_tokens: Maximum tokens to generate.
		temperature: Generation temperature.

	Returns:
		Response text.
	"""
	_require_apple_intelligence()
	last_error: Exception | None = None
	session_instructions = instructions if instructions is not None else ""

	for attempt in range(1, max_retries + 1):
		start_time = time.time()
		try:
			with Session(instructions=session_instructions) as session:
				response = session.generate(
					prompt,
					max_tokens=max_tokens,
					temperature=temperature,
				)
			elapsed = time.time() - start_time
			print(f"Apple Foundation Models completed in {elapsed:.2f} seconds (attempt {attempt})")
			return response.text.strip()
		except Exception as exc:  # pylint: disable=broad-exception-caught
			last_error = exc
			print(f"Apple Foundation Models call failed on attempt {attempt}: {exc}")
			time.sleep(attempt)

	raise RuntimeError(f"Apple Foundation Models failed after {max_retries} attempts.") from last_error
