#!/usr/bin/env python3

# Standard Library
import os
import time
import argparse
import threading
import re
import random

# PIP3 modules
from rich.console import Console

# Local repo modules
import audio_utils
import llm_wrapper
import next_song_selector
import song_details_to_dj_intro
import playback_helpers
import tts_helpers

#============================================
# Simple ANSI color helpers
class Colors:
	HEADER = "\033[95m"
	OKBLUE = "\033[94m"
	OKCYAN = "\033[96m"
	OKGREEN = "\033[92m"
	OKMAGENTA = "\033[95m"
	WARNING = "\033[93m"
	FAIL = "\033[91m"
	ENDC = "\033[0m"
	BOLD = "\033[1m"
	UNDERLINE = "\033[4m"

#============================================
MAX_NEXT_SONG_ATTEMPTS = 5
RICH_CONSOLE = Console()

#============================================
class HistoryLogger:
	"""
	Append played songs and DJ intros to a history file.
	"""
	def __init__(self, path: str = "history.log"):
		self.path = path

	def log(self, song_path: str, intro_text: str) -> None:
		line_song = f"SONG: {os.path.basename(song_path)}\n"
		line_intro = f"INTRO: {intro_text}\n"
		with open(self.path, "a", encoding="utf-8") as f:
			f.write(line_song)
			f.write(line_intro)
			f.write("-" * 40 + "\n")

#============================================
def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="AI disc jockey for local music files.")
	parser.add_argument("-d", "--directory", dest="directory", required=True, help="Path to music directory.")
	parser.add_argument("-n", "--sample-size", dest="sample_size", type=int, default=10, help="How many random songs to sample for initial choice and next suggestion.")
	parser.add_argument("-r", "--tts-speed", dest="tts_speed", type=float, default=1.2, help="Playback speed multiplier for the DJ intro.")
	parser.add_argument("--tts-engine", choices=["say", "gtts", "pyttsx3"], default="say", help="TTS engine to use for DJ intros (default: macOS say).")
	parser.add_argument("-t", "--testing", dest="testing", action="store_true", help="Testing mode: play only the first 20 seconds of each song.")
	return parser.parse_args()

#============================================
#============================================
class DiscJockey:
	def __init__(self, args: argparse.Namespace):
		self.args = args
		self.song_paths = audio_utils.get_song_list(args.directory)
		first_path = audio_utils.select_song(self.song_paths, args.sample_size)
		self.current_song = audio_utils.Song(first_path)
		self.next_song: audio_utils.Song | None = None
		self.queued_intro: str | None = None
		self.previous_song: audio_utils.Song | None = None
		self.history = HistoryLogger()
		self.model_name = llm_wrapper.get_default_model_name()
		tts_helpers.DEFAULT_ENGINE = args.tts_engine

	#============================================
	def log_intro(self, song: audio_utils.Song, intro: str) -> None:
		self.history.log(song.path, intro)

	#============================================
	def choose_next(self, last_song: audio_utils.Song) -> audio_utils.Song | None:
		last_candidates = []
		for attempt in range(MAX_NEXT_SONG_ATTEMPTS):
			candidates = next_song_selector.build_candidate_songs(
				last_song,
				self.song_paths,
				self.args.sample_size,
			)
			if not candidates:
				print(
					f"{Colors.WARNING}No candidate songs available "
					f"(attempt {attempt + 1}/{MAX_NEXT_SONG_ATTEMPTS}); retrying selection.{Colors.ENDC}"
				)
				time.sleep(1)
				continue

			last_candidates = candidates
			self._print_candidate_pool(candidates)
			first_result = next_song_selector.choose_next_song(
				last_song,
				self.song_paths,
				self.args.sample_size,
				self.model_name,
				candidates=candidates,
				show_candidates=False,
			)
			second_result = next_song_selector.choose_next_song(
				last_song,
				self.song_paths,
				self.args.sample_size,
				self.model_name,
				candidates=candidates,
				show_candidates=False,
			)

			first_song = first_result.song
			second_song = second_result.song

			if first_song and second_song:
				if first_song.path == second_song.path:
					print(f"{Colors.OKGREEN}Both selectors picked {os.path.basename(first_song.path)}; accepting unanimous choice.{Colors.ENDC}")
					return first_song

				best_result = self._run_referee(last_song, candidates, [("A", first_result), ("B", second_result)])
				if best_result and best_result.song:
					return best_result.song

				print(
					f"{Colors.WARNING}Referee could not pick a winner "
					f"(attempt {attempt + 1}/{MAX_NEXT_SONG_ATTEMPTS}); retrying selection.{Colors.ENDC}"
				)
				time.sleep(1)
				continue

			if first_song or second_song:
				chosen = first_song or second_song
				source = "first" if first_song else "second"
				print(f"{Colors.OKGREEN}Only {source} selector produced a song; using {os.path.basename(chosen.path)}.{Colors.ENDC}")
				return chosen

			print(
				f"{Colors.WARNING}Neither selector produced a song "
				f"(attempt {attempt + 1}/{MAX_NEXT_SONG_ATTEMPTS}); retrying selection.{Colors.ENDC}"
			)
			time.sleep(1)

		return self._fallback_next_song(last_song, last_candidates)

	#============================================
	def _fallback_next_song(
		self,
		last_song: audio_utils.Song,
		candidates: list[audio_utils.Song],
	) -> audio_utils.Song | None:
		"""
		Fallback selection to avoid infinite LLM retry loops.
		"""
		if candidates:
			chosen = random.choice(candidates)
			print(f"{Colors.WARNING}Falling back to random candidate: {os.path.basename(chosen.path)}{Colors.ENDC}")
			return chosen

		other_paths = [path for path in self.song_paths if path != last_song.path]
		if not other_paths:
			print(f"{Colors.FAIL}No fallback songs available; ending session.{Colors.ENDC}")
			return None

		chosen_path = random.choice(other_paths)
		chosen = audio_utils.Song(chosen_path)
		print(f"{Colors.WARNING}Falling back to random library pick: {os.path.basename(chosen.path)}{Colors.ENDC}")
		return chosen

	#============================================
	def prepare_next_async(self, last_song: audio_utils.Song) -> None:
		next_song = self.choose_next(last_song)
		if not next_song:
			print(f"{Colors.FAIL}No next song available after retries; ending session.{Colors.ENDC}")
			self.next_song = None
			self.queued_intro = None
			return
		print(f"{Colors.OKBLUE}Preparing next song: {os.path.basename(next_song.path)}{Colors.ENDC}")
		self.queued_intro = self._generate_intro(
			next_song,
			prev_song=last_song,
			use_referee=True,
		)
		self.next_song = next_song

	#============================================
	def prepare_and_speak_intro(self, song: audio_utils.Song, use_queue: bool) -> None:
		max_attempts = 2
		intro_text: str | None = None
		for attempt in range(max_attempts):
			using_queue = attempt == 0 and use_queue and self.queued_intro
			if using_queue:
				intro_text = self.queued_intro
				self.queued_intro = None
				print(f"{Colors.OKCYAN}Using queued intro for current track.{Colors.ENDC}")
			else:
				if attempt > 0:
					print(f"{Colors.WARNING}Retrying intro generation via LLM (attempt {attempt + 1}).{Colors.ENDC}")
				intro_text = self._generate_intro(
					song,
					prev_song=self.previous_song,
					use_referee=False,
				)

			if intro_text and len(intro_text.strip()) > 5:
				print(f"{Colors.OKGREEN}Intro text ready (len={len(intro_text.strip())}).{Colors.ENDC}")
				break
			else:
				if intro_text is None:
					print(f"{Colors.WARNING}Intro generation rejected by validation; retrying...{Colors.ENDC}")
				else:
					print(
						f"{Colors.WARNING}Intro text candidate too short "
						f"(len={len(intro_text.strip()) if intro_text else 0}); retrying...{Colors.ENDC}"
					)

			intro_text = None
			if using_queue:
				print(f"{Colors.WARNING}Queued intro was invalid; requesting a fresh one.{Colors.ENDC}")
			else:
				print(f"{Colors.WARNING}Intro generation failed; will retry if attempts remain.{Colors.ENDC}")

		if intro_text:
			border = "=" * 14
			display_text = tts_helpers.format_intro_for_tts(intro_text) or intro_text
			RICH_CONSOLE.print("DJ Introduction:", style="bold magenta")
			RICH_CONSOLE.print(border, style="magenta")
			for line in display_text.splitlines() or [""]:
				RICH_CONSOLE.print(f"   {line}", style="cyan")
			RICH_CONSOLE.print(border, style="magenta")
			try:
				tts_helpers.speak_dj_intro(intro_text, self.args.tts_speed, engine=self.args.tts_engine)
			except Exception as error:
				print(f"{Colors.FAIL}TTS playback failed: {error}{Colors.ENDC}")
			self.log_intro(song, intro_text)
		else:
			print(f"{Colors.FAIL}No usable intro text after retries; skipping TTS.{Colors.ENDC}")

	#============================================
	def queue_next_intro(self, next_song: audio_utils.Song | None) -> None:
		if not next_song:
			print(f"{Colors.WARNING}No next song available to prepare.{Colors.ENDC}")
			return
		print(f"{Colors.OKBLUE}Preparing next song: {os.path.basename(next_song.path)}{Colors.ENDC}")
		self.queued_intro = self._generate_intro(
			next_song,
			prev_song=self.current_song,
			use_referee=True,
		)

	#============================================
	def run(self) -> None:
		print(f"{Colors.WARNING}Found {len(self.song_paths)} audio files in {self.args.directory}.{Colors.ENDC}")
		print(f"{Colors.OKGREEN}Starting with user-selected song: {os.path.basename(self.current_song.path)}{Colors.ENDC}")

		while True:
			self.prepare_and_speak_intro(self.current_song, use_queue=True)
			playback_helpers.play_song(self.current_song)

			# Prepare next song and intro concurrently while current is playing
			self.next_song = None
			self.queued_intro = None
			next_thread = threading.Thread(target=self.prepare_next_async, args=(self.current_song,))
			next_thread.start()

			playback_helpers.wait_for_song_end(self.args.testing)
			next_thread.join()

			if not self.next_song:
				print(f"{Colors.FAIL}No next song available. Ending session.{Colors.ENDC}")
				break

			if self.queued_intro and len(self.queued_intro.strip()) > 5:
				print(f"{Colors.OKGREEN}Queued intro ready for next track.{Colors.ENDC}")
			else:
				print(f"{Colors.WARNING}Next intro missing or too short; will skip TTS for next track.{Colors.ENDC}")

			# Handoff to the next track
			self.previous_song = self.current_song
			self.current_song = self.next_song
			self.next_song = None

	#============================================
	def _generate_intro(self, song: audio_utils.Song, prev_song: audio_utils.Song | None, use_referee: bool) -> str | None:
		if use_referee:
			return self._generate_intro_with_referee(song, prev_song)
		return song_details_to_dj_intro.prepare_intro_text(
			song,
			prev_song=prev_song,
			model_name=self.model_name,
		)

	#============================================
	def _generate_intro_with_referee(self, song: audio_utils.Song, prev_song: audio_utils.Song | None) -> str | None:
		try:
			details_text = song_details_to_dj_intro.fetch_song_details(song)
		except Exception as error:
			print(f"{Colors.WARNING}Failed to fetch song details for intro referee: {error}{Colors.ENDC}")
			return None

		def _estimate_sentence_count(text: str) -> int:
			parts = re.split(r"[.!?]+", text)
			sentences = 0
			for part in parts:
				words = part.strip().split()
				if len(words) >= 3:
					sentences += 1
			return sentences

		def _is_intro_usable(intro: str, relaxed: bool = False) -> tuple[bool, str]:
			if not intro:
				return (False, "empty intro")
			text = intro.strip()
			lowered = text.lower()
			if "<response" in lowered or "</response" in lowered:
				return (False, "contains XML tags")
			if "fact:" in lowered or "trivia:" in lowered:
				return (False, "contains FACT/TRIVIA lines")
			sentence_count = _estimate_sentence_count(text)
			if relaxed:
				if len(text.split()) < 12:
					return (False, "too short (<12 words)")
				if sentence_count < 2:
					return (False, "not enough sentences (<2)")
			else:
				if len(text) < 200:
					return (False, "too short (<200 chars)")
				if len(text.split()) < 35:
					return (False, "too short (<35 words)")
				if sentence_count < 3:
					return (False, "not enough sentences (<3)")

			return (True, "")

		candidates: list[tuple[str, str]] = []
		relaxed_candidates: list[tuple[str, str]] = []
		for label in ("A", "B"):
			print(f"{Colors.OKBLUE}Generating DJ intro option {label}...{Colors.ENDC}")
			max_intro_attempts = 2
			intro = ""
			accepted_relaxed = False
			for attempt in range(max_intro_attempts):
				intro = song_details_to_dj_intro.prepare_intro_text(
					song,
					prev_song=prev_song,
					model_name=self.model_name,
					details_text=details_text,
					strict_reminder=(attempt > 0),
				)
				if not intro:
					print(f"{Colors.WARNING}Intro option {label} attempt {attempt + 1} rejected: empty intro{Colors.ENDC}")
					intro = ""
					continue
				intro = intro.strip()
				ok, reason = _is_intro_usable(intro, relaxed=False)
				if ok:
					accepted_relaxed = False
					break
				ok_relaxed, _ = _is_intro_usable(intro, relaxed=True)
				if ok_relaxed:
					accepted_relaxed = True
					print(
						f"{Colors.WARNING}Intro option {label} attempt {attempt + 1} "
						f"accepted with relaxed validation: {reason}{Colors.ENDC}"
					)
					break
				print(f"{Colors.WARNING}Intro option {label} attempt {attempt + 1} rejected: {reason}{Colors.ENDC}")
				intro = ""

			if intro:
				print(f"{Colors.OKMAGENTA}Intro Option {label}:{Colors.ENDC}\n{intro}\n{'-'*60}")
				if accepted_relaxed:
					relaxed_candidates.append((label, intro))
				else:
					candidates.append((label, intro))
			else:
				print(f"{Colors.WARNING}Intro option {label} failed validation; skipping it.{Colors.ENDC}")

		if not candidates and relaxed_candidates:
			best_relaxed = max(relaxed_candidates, key=lambda item: len(item[1]))
			print(f"{Colors.WARNING}Using relaxed intro fallback; strict validation produced no candidates.{Colors.ENDC}")
			return best_relaxed[1]

		if not candidates:
			print(f"{Colors.FAIL}All DJ intro attempts failed; no intro will be queued.{Colors.ENDC}")
			return None

		if len(candidates) == 1:
			print(f"{Colors.WARNING}Only option {candidates[0][0]} produced text; using it by default.{Colors.ENDC}")
			return candidates[0][1]

		best_intro = self._run_intro_referee(song, prev_song, candidates, details_text)
		if best_intro:
			return best_intro

		print(f"{Colors.WARNING}Intro referee could not decide; using option {candidates[0][0]} as fallback.{Colors.ENDC}")
		return candidates[0][1]

	#============================================
	def _run_intro_referee(
		self,
		song: audio_utils.Song,
		prev_song: audio_utils.Song | None,
		candidates: list[tuple[str, str]],
		details_text: str,
	) -> str:
		prompt = ""
		prompt += "You are judging two DJ introductions for the same song.\n"
		prompt += "Pick the intro that sounds natural, uses concrete facts from the song details, "
		prompt += "and creates a smooth handoff from the previous track.\n"
		prompt += "\nDisqualifying rules: if an option includes 'FACT:' or 'TRIVIA:' in the intro text, "
		prompt += "or is fewer than 3 sentences, it must lose.\n"
		prompt += "Prefer options that mention the song title when it fits naturally.\n"
		prompt += "Choose based on quality and naturalness, with brevity as a secondary factor.\n"
		prompt += "(***) Current song summary:\n"
		prompt += song.one_line_info() + "\n"
		if prev_song:
			prompt += "(***) Previous song summary:\n"
			prompt += prev_song.one_line_info() + "\n"
		prompt += "(***) Authoritative song info:\n"
		prompt += details_text + "\n"

		for label, text in candidates:
			prompt += f"\nOption {label} intro:\n{text}\n"

		prompt += (
			"\nRespond ONLY with these XML tags on a single line. "
			"The <winner> tag must contain only the letter A or B (no extra words). "
			"The <reason> must be 1-2 sentences (max 40 words). "
			"<winner>A or B</winner><reason>Explain why that intro is better.</reason>\n"
		)

		raw = llm_wrapper.run_llm(prompt, model_name=self.model_name)
		winner_text = llm_wrapper.extract_xml_tag(raw, "winner")
		ref_reason = llm_wrapper.extract_xml_tag(raw, "reason")

		if ref_reason:
			print(f"{Colors.OKGREEN}Intro referee reason: {ref_reason}{Colors.ENDC}")

		label = self._resolve_intro_referee_winner(winner_text, candidates)
		if label:
			for candidate_label, candidate_text in candidates:
				if candidate_label == label:
					print(f"{Colors.OKCYAN}Intro referee selected option {label}.{Colors.ENDC}")
					return candidate_text

		print(f"{Colors.WARNING}Intro referee response was unusable (winner: {winner_text}).{Colors.ENDC}")
		return ""

	#============================================
	def _resolve_intro_referee_winner(self, winner_text: str, candidates: list[tuple[str, str]]) -> str:
		if not winner_text:
			return ""
		text = winner_text.strip().lower()
		for label, _ in candidates:
			if text in (label.lower(), f"option {label.lower()}"):
				return label
		return ""

	#============================================
	def _print_candidate_pool(self, candidates: list[audio_utils.Song]) -> None:
		print(f"{Colors.OKMAGENTA}Candidates for next song:{Colors.ENDC}")
		lines = []
		for song in candidates:
			lines.append(song.one_line_info())
		lines.sort()
		print('\n'.join(lines))

	#============================================
	def _run_referee(
		self,
		current_song: audio_utils.Song,
		candidates: list[audio_utils.Song],
		results: list[tuple[str, next_song_selector.SelectionResult]],
	) -> next_song_selector.SelectionResult | None:
		valid = [(label, result) for (label, result) in results if result.song]
		if not valid:
			return None
		if len(valid) == 1:
			label, _ = valid[0]
			print(f"{Colors.WARNING}Only option {label} yielded a song; rerunning the duel.{Colors.ENDC}")
			return None

		candidate_lines = []
		for song in candidates:
			candidate_lines.append(
				f"- {os.path.basename(song.path)} | Artist: {song.artist} | Album: {song.album} | Title: {song.title}"
			)

		max_attempts = 2
		for attempt in range(max_attempts):
			prompt = self._build_referee_prompt(current_song, candidate_lines, results, attempt > 0)
			raw = llm_wrapper.run_llm(prompt, model_name=self.model_name)
			raw_output = raw.strip() if raw else ""
			winner_text = llm_wrapper.extract_xml_tag(raw, "winner")
			ref_reason = llm_wrapper.extract_xml_tag(raw, "reason")

			resolved = self._resolve_referee_winner(winner_text, valid)
			if resolved and resolved.song:
				file_name = os.path.basename(resolved.song.path)
				print(f"{Colors.OKCYAN}Referee selected: {file_name}{Colors.ENDC}")
				if ref_reason:
					print(f"{Colors.OKGREEN}Referee reason: {ref_reason}{Colors.ENDC}")
				return resolved

			self._log_referee_failure(winner_text, ref_reason, raw_output)
			if attempt < max_attempts - 1:
				print(f"{Colors.WARNING}Referee format issue; requesting a corrected XML reply...{Colors.ENDC}")

		print(f"{Colors.WARNING}Referee could not pick a valid winner after retries; retrying selection.{Colors.ENDC}")
		return None

	#============================================
	def _build_referee_prompt(
		self,
		current_song: audio_utils.Song,
		candidate_lines: list[str],
		results: list[tuple[str, next_song_selector.SelectionResult]],
		strict_reminder: bool,
	) -> str:
		prompt = "You are a DJ referee choosing the better follow-up track for a radio show.\n"
		prompt += (
			f"Current song: {os.path.basename(current_song.path)} | "
			f"Artist: {current_song.artist} | Album: {current_song.album} | Title: {current_song.title}\n"
		)
		prompt += "The next song must be chosen from this candidate pool:\n"
		prompt += "\n".join(candidate_lines)
		prompt += "\n\nTwo selectors reviewed the same pool and provided their picks.\n"
		for label, result in results:
			if not result.song:
				prompt += f"\nOption {label}: No selection returned.\n"
				continue
			target = result.song
			reason_text = result.reason.strip() if result.reason else "No reasoning provided."
			prompt += (
				f"\nOption {label}: {os.path.basename(target.path)} | Artist: {target.artist} | Album: {target.album}\n"
				f"Selector rationale:\n{reason_text}\n"
			)

		prompt += (
			"\nPick the option that delivers the smoother transition and honors the reasoning quality. "
			"Respond only with these tags. "
			"The <winner> tag must contain exactly one file name as shown in the candidate list "
			"(example: Spoon-I_Summon_You.mp3), and the file name alone belongs inside <winner>.\n"
			"<winner>ExactFileName.mp3</winner>"
			"<reason>Why this option beats the other</reason>\n"
		)
		if strict_reminder:
			prompt += (
				"\nReminder: Include both <winner> and <reason> tags and keep the reply to those tags.\n"
			)
		return prompt

	#============================================
	def _log_referee_failure(self, winner_text: str, ref_reason: str, raw_output: str) -> None:
		if winner_text:
			print(
				f"{Colors.WARNING}Referee response could not be matched to a candidate (winner tag: '{winner_text.strip()}').{Colors.ENDC}"
			)
		else:
			print(f"{Colors.WARNING}Referee reply was missing a <winner> tag.{Colors.ENDC}")
		if ref_reason:
			print(f"{Colors.WARNING}Referee <reason> text (unparsed): {ref_reason}{Colors.ENDC}")
		if raw_output:
			snippet = raw_output.splitlines()
			display = "\n".join(snippet[:6])
			print(f"{Colors.WARNING}Referee raw output preview:\n{display}{Colors.ENDC}")

	#============================================
	def _resolve_referee_winner(
		self,
		winner_text: str,
		valid_results: list[tuple[str, next_song_selector.SelectionResult]],
	) -> next_song_selector.SelectionResult | None:
		if not winner_text:
			return None
		text = winner_text.strip()
		normalized = text.lower()
		for label, result in valid_results:
			if normalized in (label.lower(), f"option {label.lower()}"):
				return result

		cleaned = next_song_selector.clean_llm_choice(text).lower()
		for _, result in valid_results:
			if not result.song:
				continue
			file_name = os.path.basename(result.song.path)
			if cleaned and cleaned == result.choice_text.lower():
				return result
			if cleaned and cleaned == file_name.lower():
				return result
		return None

#============================================
def main() -> None:
	args = parse_args()
	dj = DiscJockey(args)
	dj.run()

#============================================
if __name__ == "__main__":
	main()
