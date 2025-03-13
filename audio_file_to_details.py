#!/usr/bin/env python3

import os
import re
import time
import random
import argparse

import mutagen
import wikipedia
from mutagen.mp3 import MP3
from mutagen.flac import FLAC

#!/usr/bin/env python3

import time
import random
import wikipedia
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC

#============================================
class Metadata:
	"""
	Represents metadata extracted from an audio file.
	Handles Wikipedia lookups for artist, album, and song.
	"""
	#============================================
	def __init__(self, filename: str):
		"""
		Initializes metadata by extracting title, artist, album, and compilation status.
		"""
		self.filename = filename
		self.debug = True

		self.title = "Unknown Title"
		self.artist = "Unknown Artist"
		self.album = "Unknown Album"
		self.is_compilation = True

		self.artist_summary = None
		self.artist_url = None
		self.album_summary = None
		self.album_url = None
		self.song_summary = None
		self.song_url = None

		# Extract metadata when initialized
		self.extract_metadata()

	#============================================
	def __str__(self) -> str:
		"""Returns a formatted string representation of the metadata."""
		return (
			f"Title:  {self.title}\n"
			f"Artist: {self.artist}\n"
			f"Album:  {self.album}\n"
			f".. Compilation: {self.is_compilation}"
		)

	#============================================
	def extract_metadata(self):
		"""
		Extracts metadata from an MP3 or FLAC file and updates instance attributes.
		title and artist ARE required, fail without
		"""
		if self.filename.lower().endswith(".mp3"):
			audio = MP3(self.filename, ID3=mutagen.easyid3.EasyID3)
			self.title = audio.get('title')[0]
			self.artist = audio.get('artist')[0]
			self.album = audio.get('album', [self.album])[0]
			self.is_compilation = audio.get('TCMP', ['0'])[0] == '1'

		elif self.filename.lower().endswith(".flac"):
			audio = FLAC(self.filename)
			self.title = audio.get('title')[0]
			self.artist = audio.get('artist')[0]
			self.album = audio.get('album', [self.album])[0]
			self.is_compilation = audio.get('compilation', ['0'])[0] == '1'
		else:
			raise ValueError("Unsupported file format. Only MP3 and FLAC are supported.")

	#============================================
	def _clean_summary(self, summary):
		summary = summary.strip()
		paragraphs = summary.split("\n")
		summary = '* ' + '\n* '.join(paragraphs)
		return summary.strip()

	#============================================
	def _clean_title(self, title):
		"""Cleans the song title by removing unnecessary text like (feat. ...) or special characters."""
		title = re.sub(r"\(feat.*?\)", "", title, flags=re.IGNORECASE)
		title = re.sub(r"[^a-zA-Z0-9\s]", "", title)  # Remove special characters
		return title.strip()

	#============================================
	def search_wikipedia(self, query: str) -> tuple[str, str, str] | tuple[None, None, None]:
		"""
		Searches Wikipedia and returns the best match (title, URL, summary).
		"""
		if self.debug is True:
			print(f"Searching wikipedia: query='{query}'")
		time.sleep(random.random())  # Prevent overloading Wikipedia

		results = wikipedia.search(query)
		if not results:
			return None, None, None  # No results found

		time.sleep(random.random())  # Delay for API call

		page = wikipedia.page(results[0], auto_suggest=True)
		clean_summary_text = self._clean_summary(page.summary)
		if self.debug is True:
			print(f".. Summary: {clean_summary_text[:100]}")
		return page.title, page.url, clean_summary_text

	#============================================
	def fetch_wikipedia_info(self):
		"""
		Fetches Wikipedia summaries for the song, album, and artist.
		Updates the class attributes with the fetched data.
		"""
		print(f"Searching Wikipedia for:\n{self}")

		# Fetch song info
		try:
			search_title = self._clean_title(self.title)
			_, self.song_url, self.song_summary = self.search_wikipedia(f"{search_title} song by {self.artist}")
		except wikipedia.exceptions.PageError:
			print(f"Song '{self.title}' not found on Wikipedia.")

		# Modify artist search query if the name is short (3 characters or fewer)
		artist_query = f"the artist {self.artist}"
		# Try searching with "the artist" first
		try:
			_, self.artist_url, self.artist_summary = self.search_wikipedia(artist_query)
		except:
			# If that fails, try searching with just the artist's name
			try:
				_, self.artist_url, self.artist_summary = self.search_wikipedia(self.artist)
			except wikipedia.exceptions.DisambiguationError as e:
				print(f"Disambiguation error for artist '{self.artist}': {e}")
			except wikipedia.exceptions.PageError:
				print(f"Artist '{self.artist}' not found on Wikipedia.")

		# Skip album lookup if it's a compilation
		if self.is_compilation:
			print(f"Skipping Wikipedia lookup for album '{self.album}' (detected as a compilation).")
		else:
			try:
				_, self.album_url, self.album_summary = self.search_wikipedia(f"{self.album} album by {self.artist}")
			except wikipedia.exceptions.PageError:
				print(f"Album '{self.album}' not found on Wikipedia.")

	#============================================
	def get_random_chicago_suburb(self) -> str:
		"""
		Returns a random suburb of Chicago.

		Returns:
			str: Name of a Chicago suburb.
		"""
		suburbs = [
			"Naperville", "Evanston", "Schaumburg", "Oak Park", "Arlington Heights",
			"Aurora", "Skokie", "Elmhurst", "Downers Grove", "Wheaton",
			"Palatine", "Glenview", "Bolingbrook", "Orland Park", "Des Plaines"
		]
		return random.choice(suburbs)

	#============================================
	def get_opening_llm_prompt_for_dj(self) -> str:
		"""
		Generates an LLM prompt for a DJ-style introduction, ensuring only spoken content is produced.

		Returns:
			str: A formatted prompt containing structured guidance for the LLM and song details.
		"""
		suburb = self.get_random_chicago_suburb()

		dj_prompt = (
			f"You're a charismatic, knowledgeable radio DJ hosting an indie rock and alternative music show "
			f"for a small station in {suburb}, Illinois. Your intros blend deep knowledge, casual banter, "
			f"and fun trivia, making every track feel special. You introduce each song like it's a story, setting "
			f"the scene and engaging listeners.\n\n"

			"For the next song, craft an engaging introduction that:\n"
			"1. Clearly states the band and song name.\n"
			"2. Hooks the listener with an intriguing fact (e.g., how it was written, a behind-the-scenes moment).\n"
			"3. Adds depth with one or two unique details— a cool story, unexpected influences, or cultural impact.\n"
			"4. Transitions smoothly into the song, keeping energy and excitement high.\n\n"

			"Guidelines:\n"
			"- DO NOT include sound effects, stage directions, or cues in brackets [] or parentheses ().\n"
			"- Keep it fluid and natural, like you're speaking to real listeners.\n"
			"- Use shorter sentences and simple punctuation, no em-dashes.\n"
			"- Avoid over-explaining— let the storytelling feel effortless and fun.\n\n"

			"Here are the song details to work with:\n"
		)

		# Append song metadata from get_results()
		song_details = self.get_results()
		wrap_up = f"Now, craft an intro for this song using only spoken words for you audience in {suburb}."

		# Combine the DJ prompt with song metadata
		return f"{dj_prompt}\n{song_details}\n\n{wrap_up}\n"
	#============================================
	def get_results(self) -> str:
		"""
		Generates a formatted string containing Wikipedia search results.
		"""
		results = []

		if self.artist_summary:
			results.append(f"\nArtist: {self.artist}")
			results.append(f"{self.artist_url}")
			results.append(f"Summary:\n{self.artist_summary}...")

		if self.album_summary:
			results.append(f"\nAlbum: {self.album}")
			results.append(f"{self.album_url}")
			results.append(f"Summary:\n{self.album_summary}...")

		if self.song_summary:
			results.append(f"\nSong: {self.title}")
			results.append(f"{self.song_url}")
			results.append(f"Summary:\n{self.song_summary}...")

		if not results:
			results.append("No relevant Wikipedia pages found.")

		return "\n".join(results)

#============================================
def main():
	# Parse arguments
	import argparse
	parser = argparse.ArgumentParser(description="Find Wikipedia page for a given MP3 or FLAC file.")
	parser.add_argument("-i", "--input", type=str, required=True, help="Path to the MP3 or FLAC file.")
	args = parser.parse_args()

	# Create metadata object
	try:
		metadata = Metadata(args.input)
	except ValueError as e:
		print(f"Error: {e}")
		return

	# Fetch Wikipedia data
	metadata.fetch_wikipedia_info()

	# Display results
	#print(metadata.get_results())
	print("="* 70)
	print("\n\n")
	print(metadata.get_opening_llm_prompt_for_dj())

#============================================
if __name__ == "__main__":
	main()
