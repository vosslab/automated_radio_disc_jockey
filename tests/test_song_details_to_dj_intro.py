from types import SimpleNamespace

import song_details_to_dj_intro


#============================================
def test_estimate_sentence_count_ignores_short_fragments() -> None:
	text = "Hi there. Ok? This is a test."
	assert song_details_to_dj_intro._estimate_sentence_count(text) == 1


#============================================
def test_normalize_sentence_simplifies_text() -> None:
	text = "Hello, WORLD!"
	assert song_details_to_dj_intro._normalize_sentence(text) == "hello world"


#============================================
def test_normalize_fact_line_removes_prefix() -> None:
	text = "FACT: This is a detail."
	assert song_details_to_dj_intro._normalize_fact_line(text) == "this is a detail"


#============================================
def test_validate_facts_block_accepts_five_lines() -> None:
	block = "\n".join(
		[
			"FACT: One detail.",
			"TRIVIA: Two detail.",
			"FACT: Three detail.",
			"TRIVIA: Four detail.",
			"FACT: Five detail.",
		]
	)
	ok, reason = song_details_to_dj_intro._validate_facts_block(block)
	assert ok is True
	assert reason == ""


#============================================
def test_validate_facts_block_rejects_duplicates() -> None:
	block = "\n".join(
		[
			"FACT: Same.",
			"TRIVIA: Same.",
			"FACT: Same.",
			"TRIVIA: Same.",
			"FACT: Same.",
		]
	)
	ok, reason = song_details_to_dj_intro._validate_facts_block(block)
	assert ok is False
	assert "duplicate" in reason


#============================================
def test_title_tokens_filters_stopwords() -> None:
	title = "The Soundtrack of Our Lives (Remastered 2019)"
	assert song_details_to_dj_intro._title_tokens(title) == ["our", "lives", "2019"]


#============================================
def test_title_is_mentioned_accepts_partial_match() -> None:
	title = "A Spoonful of Sugar"
	intro = "We have a spoonful sugar waiting for you tonight."
	assert song_details_to_dj_intro._title_is_mentioned(intro, title) is True


#============================================
def test_append_title_if_missing_adds_period() -> None:
	text = "Now playing a classic"
	title = "Supercalifragilisticexpialidocious"
	result = song_details_to_dj_intro._append_title_if_missing(text, title)
	assert result.endswith(f"{title}.")


#============================================
def test_sanitize_intro_text_strips_facts_and_tags() -> None:
	raw = (
		"<facts>FACT: One detail.</facts>\n"
		"<response>Here is the intro.</response>\n"
		"TRIVIA: Another detail."
	)
	cleaned = song_details_to_dj_intro._sanitize_intro_text(raw)
	assert "FACT:" not in cleaned
	assert "<facts" not in cleaned
	assert "<response" not in cleaned
	assert "Here is the intro." in cleaned


#============================================
def test_sanitize_intro_text_strips_code_fences() -> None:
	raw = "```xml\nHello there\n```"
	cleaned = song_details_to_dj_intro._sanitize_intro_text(raw)
	assert "Hello there" in cleaned


#============================================
def test_starts_with_boilerplate_detects_welcome() -> None:
	text = "Ladies and gentlemen, welcome to the show."
	assert song_details_to_dj_intro._starts_with_boilerplate(text) is True
	stripped = song_details_to_dj_intro._strip_leading_boilerplate_sentence(
		"Ladies and gentlemen, welcome to the show. Here we go."
	)
	assert stripped == "Here we go."


#============================================
def test_finalize_intro_text_accepts_clean_intro() -> None:
	song = SimpleNamespace(title="Magic")
	text = "A bright tune carries the story forward. It glows with warmth. The night turns to Magic."
	result = song_details_to_dj_intro._finalize_intro_text(text, song, None, False)
	assert result is not None


#============================================
def test_trim_intro_cuts_at_word_boundary() -> None:
	text = "hello world again"
	assert song_details_to_dj_intro._trim_intro(text, 10) == "hello"


#============================================
def test_build_relaxed_intro_appends_title() -> None:
	raw = "A bright tune tells a small story. It ends with soft light."
	song = SimpleNamespace(title="Magic")
	result = song_details_to_dj_intro._build_relaxed_intro(raw, song)
	assert result is not None
	assert "Magic" in result
