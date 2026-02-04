# Changelog

## 2026-02-04
- Stop rejecting DJ intros that omit the artist name while still requiring the song title.
- Allow DJ intros up to 10 sentences instead of 6.
- Add relaxed intro fallback so TTS can proceed when strict validation rejects all options.
- Tell the LLM to aim for 5-7 sentences when the limit is 10.
- Return None on intro validation failures so retry logic can distinguish intentional rejects.
- Relax song title validation to avoid rejecting intros with different title formatting.
- Fix mixed tab/space indentation in `tts_helpers.py`.
- Add unit tests for `audio_utils`, `llm_wrapper`, `song_details_to_dj_intro`, and `tts_helpers`.
- Broaden DJ intro boilerplate stripping to drop "Ladies and gentlemen, welcome to ..." variants.
- Add a boilerplate stripping test for the "another fantastic hour of music magic" variant.
- Refresh `README.md` and add `docs/INSTALL.md` and `docs/USAGE.md`.
- Add repo-root import setup to `tests/conftest.py` so tests run without PYTHONPATH.
- Tell the LLM to avoid generic welcome openings and tie the first sentence to song details.
- Add boilerplate stripping tests for "another enchanting journey" variants.
- Highlight the `[say]` command output block with `rich` to improve readability.
- Show the filtered intro text once and stop reprinting it in the `[say]` block.
- Update docs to reference `pip_requirements.txt` after renaming dependencies file.
- Format spoken DJ intro output with borders, indentation, and color in terminal output.
- Use `rich` for DJ intro terminal formatting.
- Add `rich` to `pip_requirements.txt`.

## 2026-02-03
- Replace the wikipedia package with direct API calls and remove the BeautifulSoup dependency.
- Scan music folders recursively so nested audio files are discovered.
- Make TTS intro formatting less aggressive with comma-separated lists.
- Improve next-song choice matching for filenames with track-number prefixes or missing artist prefixes.
- Strip FACT/TRIVIA lines before TTS playback so they are not read aloud.
- Require LLM FACT/TRIVIA lines to be wrapped in <facts> tags and keep only <facts>/<response> output.
- Reject DJ intros that exceed the maximum character limit.
- Add intro validation for sentence count, repetition, and FACT/TRIVIA leakage.
- Limit next-song selection retries and fall back to a random pick to avoid infinite loops.
- Validate <facts> block content and enforce artist/title mentions in intros.
- Log all LLM prompts and responses to output/llm_responses.log.
- Strip the repetitive "Ladies and gentlemen, welcome to the show" opener before TTS.
- Boost TTS output volume by 15 percent to better match song playback.

## 2026-01-15
- Resolve merge markers in `AGENTS.md` and consolidate style and environment notes.
