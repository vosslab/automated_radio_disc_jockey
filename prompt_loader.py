# Standard Library
import os
import subprocess


_PROMPT_CACHE = {}
_REPO_ROOT = ""


#============================================
def _run_git(args: list[str]) -> str:
	"""
	Run git and return stdout.
	"""
	result = subprocess.run(
		["git"] + args,
		capture_output=True,
		text=True,
		check=False,
	)
	if result.returncode != 0:
		err_text = result.stderr.strip() or "unknown git error"
		raise RuntimeError(f"git {' '.join(args)} failed: {err_text}")
	return result.stdout.strip()


#============================================
def _get_repo_root() -> str:
	"""
	Resolve the repository root path with git.
	"""
	global _REPO_ROOT
	if _REPO_ROOT:
		return _REPO_ROOT
	root = _run_git(["rev-parse", "--show-toplevel"])
	if not root:
		raise RuntimeError("git rev-parse --show-toplevel returned empty output")
	_REPO_ROOT = root
	return root


#============================================
def load_prompt(prompt_name: str) -> str:
	"""
	Load a prompt template from prompts/.
	"""
	if not prompt_name:
		raise ValueError("prompt_name is required")
	prompt_root = os.path.join(_get_repo_root(), "prompts")
	path = os.path.join(prompt_root, prompt_name)
	if path in _PROMPT_CACHE:
		return _PROMPT_CACHE[path]
	if not os.path.exists(path):
		raise FileNotFoundError(f"Prompt file not found: {path}")
	with open(path, "r", encoding="utf-8") as handle:
		text = handle.read()
	_PROMPT_CACHE[path] = text
	return text


#============================================
def render_prompt(template: str, values: dict[str, str]) -> str:
	"""
	Replace {{token}} placeholders with supplied values.
	"""
	if not template:
		return ""
	rendered = template
	for key, value in values.items():
		token = "{{" + key + "}}"
		replacement = value if value is not None else ""
		rendered = rendered.replace(token, replacement)
	return rendered
