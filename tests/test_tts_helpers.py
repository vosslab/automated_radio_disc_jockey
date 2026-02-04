import pytest

pytest.importorskip("pygame")
pytest.importorskip("gtts")

import tts_helpers


#============================================
def test_strip_fact_trivia_lines_removes_prefixes() -> None:
	text = "FACT: One\nTRIVIA: Two\nKeep this line."
	assert tts_helpers._strip_fact_trivia_lines(text) == "Keep this line."


#============================================
def test_strip_boilerplate_intro_removes_opening() -> None:
	text = "Ladies and gentlemen, welcome to the show! And now the track."
	assert tts_helpers._strip_boilerplate_intro(text) == "And now the track."
	text = "Ladies and gentlemen, welcome to the magical world of Disney music! Here we go."
	assert tts_helpers._strip_boilerplate_intro(text) == "Here we go."
	text = "Ladies and gentlemen, welcome to another fantastic hour of music magic on our station. Next up."
	assert tts_helpers._strip_boilerplate_intro(text) == "Next up."
	text = "Ladies and gentlemen, welcome to another enchanting journey through the world of Disney magic. Next up."
	assert tts_helpers._strip_boilerplate_intro(text) == "Next up."
	text = "Ladies and gentlemen, welcome to another enchanting journey through the world of Disney magic! Next up."
	assert tts_helpers._strip_boilerplate_intro(text) == "Next up."


#============================================
def test_slice_to_sentence_end() -> None:
	assert tts_helpers._slice_to_sentence_end(" hello world. rest") == " hello world"


#============================================
def test_comma_is_list_like_detects_and() -> None:
	assert tts_helpers._comma_is_list_like(" and pears") is True
	assert tts_helpers._comma_is_list_like(" rolling through the night") is False


#============================================
def test_insert_pacing_linebreaks_keeps_lists() -> None:
	text = "apples, bananas, and pears."
	assert tts_helpers._insert_pacing_linebreaks(text) == text


#============================================
def test_insert_pacing_linebreaks_adds_pause() -> None:
	text = "Hello, world."
	assert ", \n" in tts_helpers._insert_pacing_linebreaks(text)


#============================================
def test_format_intro_for_tts_filters_fact_lines() -> None:
	text = "FACT: One detail.\nLadies and gentlemen, welcome to the show. Hello there."
	normalized = tts_helpers.format_intro_for_tts(text)
	assert "FACT:" not in normalized
	assert "Ladies and gentlemen" not in normalized
	assert "Hello there." in normalized
