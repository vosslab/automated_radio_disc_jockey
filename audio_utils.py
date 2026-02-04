# Standard Library
import os
import re
import random

# PIP3 modules
import mutagen
import mutagen.mp3
import mutagen.flac
import mutagen.easyid3

#============================================
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
def get_song_list(directory: str) -> list:
	"""
	Collect supported audio files from a directory tree.

	Args:
		directory (str): Path to music directory.

	Returns:
		list: Audio file paths.
	"""
	audio_extensions = [".mp3", ".wav", ".flac", ".ogg"]
	if not os.path.isdir(directory):
		raise FileNotFoundError(f"Music directory not found: {directory}")

	song_list = []
	for root, _, files in os.walk(directory):
		for filename in files:
			extension = os.path.splitext(filename)[1].lower()
			if extension in audio_extensions:
				song_list.append(os.path.join(root, filename))

	if not song_list:
		raise RuntimeError(f"No audio files found in {directory}")
	song_list.sort()
	return song_list

#============================================
def select_song(song_list: list, sample_size: int) -> str:
	"""
	Prompt user to select a song from a random sample.

	Args:
		song_list (list): All available song paths or Song objects.
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
		song_obj = song if isinstance(song, Song) else Song(song)
		print(f"{colors.OKBLUE}{index}:{colors.ENDC} {song_obj.one_line_info()}")
		index += 1

	while True:
		user_input = input("Enter number: ").strip()
		if user_input.isdigit():
			selected = int(user_input) - 1
			if 0 <= selected < sample_size:
				chosen = choices[selected]
				return chosen.path if isinstance(chosen, Song) else chosen
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
		self.year = None
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
				audio = mutagen.mp3.MP3(self.path, ID3=mutagen.easyid3.EasyID3)
				self.length_seconds = int(audio.info.length) if audio.info and audio.info.length else None
				self.title = (audio.get("title") or [self.title])[0]
				self.artist = (audio.get("artist") or [self.artist])[0]
				self.album = (audio.get("album") or [self.album])[0]
				self.is_compilation = (audio.get("TCMP") or ["0"])[0] == "1"
				self.year = self.year or _extract_year_from_candidates(
					audio.get("originaldate"),
					audio.get("date"),
					audio.get("year"),
					getattr(audio, "tags", {}).get("TDRC") if getattr(audio, "tags", None) else None,
				)
			elif lower.endswith(".flac"):
				audio = mutagen.flac.FLAC(self.path)
				self.length_seconds = int(audio.info.length) if audio.info and audio.info.length else None
				self.title = (audio.get("title") or [self.title])[0]
				self.artist = (audio.get("artist") or [self.artist])[0]
				self.album = (audio.get("album") or [self.album])[0]
				self.is_compilation = (audio.get("compilation") or ["0"])[0] == "1"
				self.year = self.year or _extract_year_from_candidates(
					audio.get("originaldate"),
					audio.get("date"),
					audio.get("year"),
				)
		except Exception as error:
			if self.debug:
				print(f"Metadata load failed for {self.path}: {error}")

	#============================================
	def one_line_info(self) -> str:
		"""
		Return a one-line summary for selection lists.
		"""
		c = self.Colors
		parts = []
		length_display = self.formatted_length()
		if length_display:
			parts.append(f"{length_display}")
		parts.append(f"{os.path.basename(self.path)}")
		parts.append(f"Artist: {c.OKGREEN}{self.artist}{c.ENDC}")
		#parts.append(f"Album: {c.OKCYAN}{self.album}{c.ENDC}")
		if self.year:
			parts.append(f"({self.year})")
		return " | ".join(parts)

	#============================================
	def multiline_info(self) -> str:
		"""
		Return a multi-line summary of key fields.
		"""
		c = self.Colors
		length_display = self.formatted_length()
		lines = [
			f"{c.BOLD}Title:{c.ENDC}  {self.title}",
			f"{c.BOLD}Artist:{c.ENDC} {self.artist}",
			f"{c.BOLD}Album:{c.ENDC}  {self.album}",
		]
		if self.year:
			lines.append(f"{c.BOLD}Year:{c.ENDC}   {self.year}")
		if length_display:
			lines.append(f"{c.BOLD}Length:{c.ENDC} {length_display}")
		lines.append(f".. Compilation: {self.is_compilation}")
		return "\n".join(lines)

	#============================================
	def formatted_length(self) -> str:
		"""
		Return length in MM:SS if available.
		"""
		if not self.length_seconds or self.length_seconds <= 0:
			return ""
		minutes, seconds = divmod(int(self.length_seconds), 60)
		return f"{minutes:02d}:{seconds:02d}"

#============================================
def _extract_year_from_candidates(*candidates) -> str | None:
	for candidate in candidates:
		year = _extract_year_value(candidate)
		if year:
			return year
	return None

#============================================
def _extract_year_value(value) -> str | None:
	if value is None:
		return None
	if isinstance(value, list):
		for entry in value:
			year = _extract_year_value(entry)
			if year:
				return year
		return None
	text = str(value).strip()
	match = re.search(r"(19|20)\d{2}", text)
	if match:
		return match.group(0)
	if text.isdigit() and len(text) == 4:
		return text
	return None
