#!/usr/bin/env python3

import argparse
import os
import random
import re
import time
import urllib.parse
import urllib.request
import html
import warnings
from bs4 import GuessedAtParserWarning
from typing import Optional, Tuple

import mutagen
import wikipedia
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

#============================================
class Colors:
	OKBLUE = "\033[94m"
	OKGREEN = "\033[92m"
	BOLD = "\033[1m"
	ENDC = "\033[0m"

#============================================
class Metadata:
	"""
	Represents metadata extracted from an audio file.
	Handles Wikipedia lookups for artist, album, and song.
	"""
	#============================================
	def __init__(self, filename: str, debug: bool = False):
		"""
		Initializes metadata by extracting title, artist, album, and compilation status.
		"""
		self.filename = filename
		self.debug = debug

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
			f"{Colors.BOLD}Title:{Colors.ENDC}  {self.title}\n"
			f"{Colors.BOLD}Artist:{Colors.ENDC} {self.artist}\n"
			f"{Colors.BOLD}Album:{Colors.ENDC}  {self.album}\n"
			f".. Compilation: {self.is_compilation}"
		)

	#============================================
	def extract_metadata(self):
		"""
		Extracts metadata from an MP3 or FLAC file and updates instance attributes.
		Tries to be resilient to missing tags.
		"""
		if self.filename.lower().endswith(".mp3"):
			audio = MP3(self.filename, ID3=mutagen.easyid3.EasyID3)
			self.title = (audio.get('title') or [self.title])[0]
			self.artist = (audio.get('artist') or [self.artist])[0]
			self.album = (audio.get('album') or [self.album])[0]
			self.is_compilation = (audio.get('TCMP') or ['0'])[0] == '1'

		elif self.filename.lower().endswith(".flac"):
			audio = FLAC(self.filename)
			self.title = (audio.get('title') or [self.title])[0]
			self.artist = (audio.get('artist') or [self.artist])[0]
			self.album = (audio.get('album') or [self.album])[0]
			self.is_compilation = (audio.get('compilation') or ['0'])[0] == '1'
		else:
			raise ValueError("Unsupported file format. Only MP3 and FLAC are supported.")

	#============================================
	def _clean_summary(self, summary):
		summary = summary.strip()
		paragraphs = summary.split("\n")
		summary = '* ' + '\n* '.join(paragraphs)
		return summary.strip()

	#============================================
	def _fetch_lastfm_wiki(self, artist: str, title: str, kind: str) -> Tuple[Optional[str], Optional[str]]:
		"""
		Attempts to fetch a short description from Last.fm wiki pages.
		kind is one of: song, album, artist
		"""
		try:
			artist_slug = urllib.parse.quote(artist)
			title_slug = urllib.parse.quote(title)

			if kind == "song":
				url = f"https://www.last.fm/music/{artist_slug}/{title_slug}/+wiki"
			elif kind == "album":
				url = f"https://www.last.fm/music/{artist_slug}/{title_slug}/+wiki"
			else:  # artist
				url = f"https://www.last.fm/music/{artist_slug}/+wiki"

			with urllib.request.urlopen(url, timeout=5) as resp:
				if resp.status != 200:
					return None, None
				html_text = resp.read().decode("utf-8", errors="ignore")

			# Grab the OpenGraph description if present
			match = re.search(r'<meta property="og:description" content="(.*?)"', html_text, flags=re.IGNORECASE)
			if match:
				desc = html.unescape(match.group(1)).strip()
				desc = desc.replace("\n", " ")
				if desc:
					return url, desc
		except Exception as exc:
			if self.debug:
				print(f"Last.fm lookup failed ({kind}): {exc}")
		return None, None

	#============================================
	def _fetch_allmusic_description(self, query: str, kind: str) -> Tuple[Optional[str], Optional[str]]:
		"""
		Attempts to fetch a description from AllMusic search results.
		kind is one of: song, album, artist.
		Returns (url, description) if found.
		"""
		try:
			search_url = self._fallback_allmusic_link(query)
			req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
			with urllib.request.urlopen(req, timeout=5) as resp:
				if resp.status != 200:
					return None, None
				html_text = resp.read().decode("utf-8", errors="ignore")
			pattern = r'href="(https://www.allmusic.com/(song|album|artist)/[^"]+)"'
			for match in re.finditer(pattern, html_text, flags=re.IGNORECASE):
				url = match.group(1)
				if kind == "song" and "/song/" not in url:
					continue
				if kind == "album" and "/album/" not in url:
					continue
				if kind == "artist" and "/artist/" not in url:
					continue
				# fetch the first matching detail page
				req_detail = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
				with urllib.request.urlopen(req_detail, timeout=5) as resp_detail:
					if resp_detail.status != 200:
						break
					detail_html = resp_detail.read().decode("utf-8", errors="ignore")
				meta_match = re.search(r'<meta name="description" content="(.*?)"', detail_html, flags=re.IGNORECASE)
				if not meta_match:
					meta_match = re.search(r'<meta property="og:description" content="(.*?)"', detail_html, flags=re.IGNORECASE)
				if meta_match:
					desc = html.unescape(meta_match.group(1)).strip()
					desc = desc.replace("\n", " ")
					return url, desc
				break
		except Exception as exc:
			if self.debug:
				print(f"AllMusic lookup failed ({kind}): {exc}")
		return None, None

	#============================================
	def _fallback_allmusic_link(self, query: str) -> str:
		"""
		Provides a search URL for AllMusic as a loose fallback.
		"""
		safe_query = urllib.parse.quote(query)
		return f"https://www.allmusic.com/search/all/{safe_query}"

	#============================================
	def _clean_title(self, title):
		"""Cleans the song title by removing unnecessary text like (feat. ...) or special characters."""
		title = re.sub(r"\(feat.*?\)", "", title, flags=re.IGNORECASE)
		title = re.sub(r"[^a-zA-Z0-9\s]", "", title)  # Remove special characters
		return title.strip()

	#============================================
	def search_wikipedia(self, query: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
		"""
		Searches Wikipedia and returns the best match (title, URL, summary).
		"""
		if self.debug is True:
			print(f"Searching wikipedia: query='{query}'")
		time.sleep(random.random())  # Prevent overloading Wikipedia
		with warnings.catch_warnings():
			warnings.simplefilter("ignore", GuessedAtParserWarning)
			results = wikipedia.search(query)
		if not results:
			return None, None, None  # No results found

		options = results[:3]  # Try a few options to avoid disambiguation pitfalls
		for candidate in options:
			time.sleep(random.random())  # Delay for API call
			try:
				with warnings.catch_warnings():
					warnings.simplefilter("ignore", GuessedAtParserWarning)
					page = wikipedia.page(candidate, auto_suggest=True)
				clean_summary_text = self._clean_summary(page.summary)
				if self.debug is True:
					print(f".. Summary for {candidate}: {clean_summary_text[:100]}")
				return page.title, page.url, clean_summary_text
			except wikipedia.exceptions.DisambiguationError as e:
				if self.debug:
					print(f"Disambiguation for '{candidate}': options={e.options[:3]}")
				# try first disambiguation option
				try:
					with warnings.catch_warnings():
						warnings.simplefilter("ignore", GuessedAtParserWarning)
						page = wikipedia.page(e.options[0], auto_suggest=True)
					return page.title, page.url, self._clean_summary(page.summary)
				except Exception as inner_error:
					if self.debug:
						print(f".. Disambiguation follow-up failed: {inner_error}")
			except wikipedia.exceptions.PageError as page_error:
				if self.debug:
					print(f".. PageError: {page_error}")
			except Exception as error:
				if self.debug:
					print(f".. Wikipedia lookup error for {candidate}: {error}")
		return None, None, None

	#============================================
	def fetch_wikipedia_info(self):
		"""
		Fetches Wikipedia summaries for the song, album, and artist.
		Updates the class attributes with the fetched data.
		"""
		print(f"{Colors.OKBLUE}Searching Wikipedia for:{Colors.ENDC}\n{self}")

		# Fetch song info
		search_title = self._clean_title(self.title)
		print(f"{Colors.OKBLUE}Searching song page for '{search_title}'...{Colors.ENDC}")
		_, self.song_url, self.song_summary = self.search_wikipedia(f"{search_title} song by {self.artist}")
		if self.song_summary:
			print(f"{Colors.OKGREEN}Received song summary ({len(self.song_summary)} chars).{Colors.ENDC}")
		if not self.song_summary:
			lfm_url, lfm_desc = self._fetch_lastfm_wiki(self.artist, search_title, kind="song")
			if lfm_desc:
				self.song_url = lfm_url
				self.song_summary = self._clean_summary(lfm_desc)
			else:
				am_url, am_desc = self._fetch_allmusic_description(f"{self.artist} {search_title}", kind="song")
				if am_desc:
					self.song_url = am_url
					self.song_summary = self._clean_summary(am_desc)
			if not self.song_summary:
				self.song_url = self.song_url or self._fallback_allmusic_link(f"{self.artist} {self.title} song")
				self.song_summary = self.song_summary or "No Wikipedia, Last.fm, or AllMusic summary available."

		# Modify artist search query if the name is short (3 characters or fewer)
		artist_query = f"the artist {self.artist}"
		# Try searching with "the artist" first
		print(f"{Colors.OKBLUE}Searching artist page for '{self.artist}'...{Colors.ENDC}")
		_, self.artist_url, self.artist_summary = self.search_wikipedia(artist_query)
		if self.artist_summary:
			print(f"{Colors.OKGREEN}Received artist summary ({len(self.artist_summary)} chars).{Colors.ENDC}")
		if not self.artist_summary:
			_, self.artist_url, self.artist_summary = self.search_wikipedia(self.artist)

		if not self.artist_summary:
			lfm_url, lfm_desc = self._fetch_lastfm_wiki(self.artist, self.artist, kind="artist")
			if lfm_desc:
				self.artist_url = lfm_url
				self.artist_summary = self._clean_summary(lfm_desc)
			else:
				am_url, am_desc = self._fetch_allmusic_description(self.artist, kind="artist")
				if am_desc:
					self.artist_url = am_url
					self.artist_summary = self._clean_summary(am_desc)
			if not self.artist_summary:
				self.artist_url = self.artist_url or self._fallback_allmusic_link(self.artist)
				self.artist_summary = self.artist_summary or "No Wikipedia, Last.fm, or AllMusic summary available."

		# Skip album lookup if it's a compilation
		if self.is_compilation:
			print(f"Skipping Wikipedia lookup for album '{self.album}' (detected as a compilation).")
		else:
			print(f"{Colors.OKBLUE}Searching album page for '{self.album}'...{Colors.ENDC}")
			_, self.album_url, self.album_summary = self.search_wikipedia(f"{self.album} album by {self.artist}")
			if self.album_summary:
				print(f"{Colors.OKGREEN}Received album summary ({len(self.album_summary)} chars).{Colors.ENDC}")
			if not self.album_summary:
				lfm_url, lfm_desc = self._fetch_lastfm_wiki(self.artist, self.album, kind="album")
				if lfm_desc:
					self.album_url = lfm_url
					self.album_summary = self._clean_summary(lfm_desc)
				else:
					am_url, am_desc = self._fetch_allmusic_description(f"{self.artist} {self.album}", kind="album")
					if am_desc:
						self.album_url = am_url
						self.album_summary = self._clean_summary(am_desc)
				if not self.album_summary:
					self.album_url = self.album_url or self._fallback_allmusic_link(f"{self.artist} {self.album} album")
					self.album_summary = self.album_summary or "No Wikipedia, Last.fm, or AllMusic summary available."

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
	parser = argparse.ArgumentParser(description="Extract metadata and build DJ prompt for an MP3 or FLAC file.")
	parser.add_argument("-i", "--input", type=str, required=True, help="Path to the MP3 or FLAC file.")
	parser.add_argument("-d", "--debug", action="store_true", help="Enable verbose logging.")
	parser.add_argument("-p", "--prompt-only", action="store_true", help="Print only the LLM prompt (suppress metadata block).")
	args = parser.parse_args()

	# Create metadata object
	try:
		metadata = Metadata(args.input, debug=args.debug)
	except ValueError as e:
		print(f"Error: {e}")
		return

	# Fetch Wikipedia data
	metadata.fetch_wikipedia_info()

	# Display results only
	print("=" * 70)
	print(metadata.get_results())
	print("=" * 70)

#============================================
if __name__ == "__main__":
	main()
