import os

import pytest

import audio_utils
import llm_wrapper
import next_song_selector
import song_details_to_dj_intro


#============================================
def _bool_env(name: str) -> bool:
	value = os.environ.get(name, "").strip().lower()
	return value in {"1", "true", "yes", "on"}


#============================================
if not _bool_env("LLM_SMOKE"):
	pytest.skip("Set LLM_SMOKE=1 to run live LLM smoke tests.", allow_module_level=True)


#============================================
def _get_env_path(name: str) -> str:
	value = os.environ.get(name, "").strip()
	if not value:
		pytest.skip(f"Set {name} to run LLM smoke tests.", allow_module_level=True)
	return value


#============================================
def test_llm_smoke_next_song_selection() -> None:
	music_dir = _get_env_path("LLM_SMOKE_DIR")
	current_path = _get_env_path("LLM_SMOKE_CURRENT")

	song_paths = audio_utils.get_song_list(music_dir)
	if current_path not in song_paths:
		song_paths.append(current_path)

	current_song = audio_utils.Song(current_path)
	model_name = llm_wrapper.get_default_model_name()

	result = next_song_selector.choose_next_song(
		current_song,
		song_paths,
		sample_size=8,
		model_name=model_name,
		show_candidates=False,
	)

	assert result.song is not None
	assert result.choice_text
	assert result.reason
	assert "WHY YOU PICKED" not in result.reason.upper()


#============================================
def test_llm_smoke_dj_intro() -> None:
	current_path = _get_env_path("LLM_SMOKE_CURRENT")
	song = audio_utils.Song(current_path)
	model_name = llm_wrapper.get_default_model_name()

	intro = song_details_to_dj_intro.prepare_intro_text(
		song,
		model_name=model_name,
		allow_fallback=True,
	)

	assert intro
	assert "```" not in intro
	assert "<facts" not in intro.lower()
	assert song_details_to_dj_intro._estimate_sentence_count(intro) >= 2

	title_norm = song_details_to_dj_intro._normalize_sentence(song.title)
	intro_norm = song_details_to_dj_intro._normalize_sentence(intro)
	assert not title_norm or title_norm in intro_norm
