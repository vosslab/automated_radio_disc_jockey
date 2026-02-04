# Standard Library
import os
import time
import warnings

# PIP3 modules
warnings.filterwarnings("ignore", category=UserWarning, module="pkg_resources")
import pygame

# Local repo modules
import audio_utils

#============================================
def ensure_mixer_initialized() -> None:
	if not pygame.mixer.get_init():
		pygame.mixer.init()

#============================================
def play_song(song: audio_utils.Song) -> None:
	ensure_mixer_initialized()
	print(f"{audio_utils.Colors.OKGREEN}Playing song: {os.path.basename(song.path)}{audio_utils.Colors.ENDC}")
	pygame.mixer.music.load(song.path)
	pygame.mixer.music.play()

#============================================
def wait_for_song_end(testing: bool, poll_seconds: float = 1.0, preview_seconds: int = 20) -> None:
	start_time = time.time()
	while pygame.mixer.music.get_busy():
		if testing and (time.time() - start_time) >= preview_seconds:
			print(f"Testing mode: stopping playback after {preview_seconds} seconds.")
			pygame.mixer.music.stop()
			break
		time.sleep(poll_seconds)
	print(f"{audio_utils.Colors.OKBLUE}Song finished playing.{audio_utils.Colors.ENDC}")
