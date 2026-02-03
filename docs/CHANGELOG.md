# Changelog

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
