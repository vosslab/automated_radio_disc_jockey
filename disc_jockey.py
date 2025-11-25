#!/usr/bin/env python3

# Standard Library
import os
import time
import argparse
import threading

# PIP3 modules

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
		self.queued_intro = ""
		self.previous_song: audio_utils.Song | None = None
		self.history = HistoryLogger()
		self.model_name = llm_wrapper.select_ollama_model()

	#============================================
	def log_intro(self, song: audio_utils.Song, intro: str) -> None:
		self.history.log(song.path, intro)

	#============================================
	def choose_next(self, last_song: audio_utils.Song) -> audio_utils.Song | None:
		next_song = next_song_selector.choose_next_song(
			last_song,
			self.song_paths,
			self.args.sample_size,
			self.model_name,
		)
		if isinstance(next_song, audio_utils.Song):
			return next_song
		#recursive
		print("FAILED to find a new song, trying again.")
		time.sleep(1)
		return self.choose_next(last_song)

	#============================================
	def prepare_next_async(self, last_song: audio_utils.Song) -> None:
		next_song = self.choose_next(last_song)
		print(f"{Colors.OKBLUE}Preparing next song: {os.path.basename(next_song.path)}{Colors.ENDC}")
		self.queued_intro = song_details_to_dj_intro.prepare_intro_text(
			next_song,
			prev_song=last_song,
			model_name=self.model_name,
		)
		self.next_song = next_song

	#============================================
	def prepare_and_speak_intro(self, song: audio_utils.Song, use_queue: bool) -> None:
		if use_queue and self.queued_intro:
			intro_text = self.queued_intro
			self.queued_intro = ""
			print(f"{Colors.OKCYAN}Using queued intro for current track.{Colors.ENDC}")
		else:
			intro_text = song_details_to_dj_intro.prepare_intro_text(
				song,
				prev_song=self.previous_song,
				model_name=self.model_name,
			)
		if intro_text and len(intro_text.strip()) > 5:
			print(f"{Colors.BOLD}{Colors.OKMAGENTA}DJ Introduction:{Colors.ENDC}")
			print(f"{Colors.OKCYAN}{intro_text}{Colors.ENDC}")
			tts_helpers.speak_dj_intro(intro_text, self.args.tts_speed)
			self.log_intro(song, intro_text)
		else:
			print(f"{Colors.WARNING}No usable intro text; skipping TTS.{Colors.ENDC}")

	#============================================
	def queue_next_intro(self, next_song: audio_utils.Song | None) -> None:
		if not next_song:
			print(f"{Colors.WARNING}No next song available to prepare.{Colors.ENDC}")
			return
		print(f"{Colors.OKBLUE}Preparing next song: {os.path.basename(next_song.path)}{Colors.ENDC}")
		self.queued_intro = song_details_to_dj_intro.prepare_intro_text(
				next_song,
				prev_song=self.current_song,
				model_name=self.model_name,
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
			self.queued_intro = ""
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
def main() -> None:
	args = parse_args()
	dj = DiscJockey(args)
	dj.run()

#============================================
if __name__ == "__main__":
	main()
