#!/usr/bin/env python3

# Standard Library
import os
import random
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC

#============================================
def get_song_list(directory: str) -> list:
	"""
	Collect supported audio files from a directory.

	Args:
		directory (str): Path to music directory.

	Returns:
		list: Audio file paths.
	"""
	audio_extensions = [".mp3", ".wav", ".flac", ".ogg"]
	if not os.path.isdir(directory):
		raise FileNotFoundError(f"Music directory not found: {directory}")

	song_list = []
	for entry in os.listdir(directory):
		path = os.path.join(directory, entry)
		if os.path.isfile(path) and os.path.splitext(entry)[1].lower() in audio_extensions:
			song_list.append(path)

	if not song_list:
		raise RuntimeError(f"No audio files found in {directory}")
	return song_list

#============================================
def select_song(song_list: list, sample_size: int) -> str:
	"""
	Prompt user to select a song from a random sample.

	Args:
		song_list (list): All available song paths.
		sample_size (int): Sample size for selection.

	Returns:
		str: Path to chosen song.
	"""
	colors = Song.Colors
	sample_size = max(1, min(sample_size, len(song_list)))
	choices = random.sample(song_list, sample_size)
	print(f"Please select a song (1-{sample_size}):")
	index = 1
	for song in choices:
		song_obj = Song(song)
		print(f"{colors.OKBLUE}{index}:{colors.ENDC} {song_obj.one_line_info()}")
		index += 1

	while True:
		user_input = input("Enter number: ").strip()
		if user_input.isdigit():
			selected = int(user_input) - 1
			if 0 <= selected < sample_size:
				return choices[selected]
		print(f"Please enter a number between 1 and {sample_size}.")

#============================================
def select_song_list(song_list: list, sample_size: int) -> list:
	"""
	Return a random list of songs (no prompt), useful for non-interactive flows.

	Args:
		song_list (list): All available song paths.
		sample_size (int): Sample size for selection.

	Returns:
		list: Randomly sampled song paths.
	"""
	sample_size = max(1, min(sample_size, len(song_list)))
	return random.sample(song_list, sample_size)

#============================================
class Song:
	"""
	Represents a song file with cached metadata and info helpers.
	"""
	class Colors:
		OKBLUE = "\033[94m"
		OKGREEN = "\033[92m"
		OKCYAN = "\033[96m"
		ENDC = "\033[0m"
		BOLD = "\033[1m"

	#============================================
	def __init__(self, path: str, debug: bool = False):
		"""
		Initialize song metadata from file tags where possible.

		Args:
			path (str): Path to the audio file.
			debug (bool): Enable verbose logging.
		"""
		self.path = path
		self.debug = debug
		self.title = os.path.splitext(os.path.basename(path))[0]
		self.artist = "Unknown Artist"
		self.album = "Unknown Album"
		self.is_compilation = False
		self.length_seconds = None
		self.size_bytes = None
		self._load_file_info()

	#============================================
	def _load_file_info(self) -> None:
		"""
		Load size and length plus tags for mp3/flac files.
		"""
		if os.path.exists(self.path):
			self.size_bytes = os.path.getsize(self.path)
		lower = self.path.lower()
		try:
			if lower.endswith(".mp3"):
				audio = MP3(self.path, ID3=mutagen.easyid3.EasyID3)
				self.length_seconds = int(audio.info.length) if audio.info and audio.info.length else None
				self.title = (audio.get("title") or [self.title])[0]
				self.artist = (audio.get("artist") or [self.artist])[0]
				self.album = (audio.get("album") or [self.album])[0]
				self.is_compilation = (audio.get("TCMP") or ["0"])[0] == "1"
			elif lower.endswith(".flac"):
				audio = FLAC(self.path)
				self.length_seconds = int(audio.info.length) if audio.info and audio.info.length else None
				self.title = (audio.get("title") or [self.title])[0]
				self.artist = (audio.get("artist") or [self.artist])[0]
				self.album = (audio.get("album") or [self.album])[0]
				self.is_compilation = (audio.get("compilation") or ["0"])[0] == "1"
		except Exception as error:
			if self.debug:
				print(f"Metadata load failed for {self.path}: {error}")

	#============================================
	def one_line_info(self) -> str:
		"""
		Return a one-line summary for selection lists.
		"""
		c = self.Colors
		return (
			f"- {os.path.basename(self.path)} | "
			f"Artist: {c.OKGREEN}{self.artist}{c.ENDC} | "
			f"Album: {c.OKCYAN}{self.album}{c.ENDC}"
		)

	#============================================
	def multiline_info(self) -> str:
		"""
		Return a multi-line summary of key fields.
		"""
		c = self.Colors
		return (
			f"{c.BOLD}Title:{c.ENDC}  {self.title}\n"
			f"{c.BOLD}Artist:{c.ENDC} {self.artist}\n"
			f"{c.BOLD}Album:{c.ENDC}  {self.album}\n"
			f".. Compilation: {self.is_compilation}"
		)
