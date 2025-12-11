TODO

LLM behavior
- ~~Add a retry system: request a second and third LLM answer when the first looks wrong.~~ (two selector passes + intro retries in `disc_jockey.py`)
- ~~Add a referee model to choose the best of three next track predictions.~~ (dual selectors + referee comparison in `disc_jockey.py`)
- Improve failure detection by checking for genre violations and impossible scores.

Song list handling
- Build a shared utility for formatting and validating candidate song lists.
- ~~Add safeguards to prevent misparsed entries.~~ (handled via new candidate normalization in `next_song_selector.py`)

Playback features
- Better playback TUI window with a real progress bar.
- Add skip control and optional auto skip.
- Use track duration as a factor in next song selection.
- Support queueing multiple songs ahead.

Future enhancements
- Track history for analytics and feedback into the LLM.
- Save past LLM predictions for debugging bad choices.
- ~~Allow a second model to critique DJ intros for quality control.~~ (intro duel with referee in `disc_jockey.py`)
