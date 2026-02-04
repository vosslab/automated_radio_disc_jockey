# Standard Library
import array
import os
import tempfile
import wave

# PIP3 modules
import pygame
from rich import print
from rich.markup import escape

# Local repo modules
from cli_colors import Colors

#============================================
DEFAULT_PLAYBACK_RATE = 44100
DEFAULT_TRANSCRIBE_RATE = 16000

#============================================
def _sample_format_from_size(size: int) -> tuple[int, bool]:
	width = abs(size) // 8
	if width in (1, 2, 4):
		return width, size < 0
	return 2, True

#============================================
def ensure_mixer_initialized(frequency: int, size: int, channels: int) -> None:
	if pygame.mixer.get_init():
		return
	pygame.mixer.init(frequency=frequency, size=size, channels=channels)

#============================================
def _write_wav(path: str, raw: bytes, channels: int, sample_width: int, rate: int) -> None:
	with wave.open(path, "wb") as wav_file:
		wav_file.setnchannels(channels)
		wav_file.setsampwidth(sample_width)
		wav_file.setframerate(rate)
		wav_file.writeframes(raw)

#============================================
def _sample_typecode(sample_width: int, signed: bool) -> str | None:
	if sample_width == 1:
		return "b" if signed else "B"
	if sample_width == 2:
		return "h"
	if sample_width == 4:
		return "i"
	return None

#============================================
def _convert_channels(
	raw: bytes,
	sample_width: int,
	signed: bool,
	src_channels: int,
	dst_channels: int,
) -> tuple[bytes, int]:
	if src_channels == dst_channels:
		return raw, src_channels
	if src_channels not in (1, 2) or dst_channels not in (1, 2):
		return raw, src_channels
	typecode = _sample_typecode(sample_width, signed)
	if not typecode:
		return raw, src_channels

	samples = array.array(typecode)
	samples.frombytes(raw)

	if src_channels == 2 and dst_channels == 1:
		mono = array.array(typecode)
		for index in range(0, len(samples), 2):
			left = samples[index]
			right = samples[index + 1] if index + 1 < len(samples) else left
			if typecode == "B":
				mono.append((left + right) // 2)
			else:
				mono.append(int((left + right) / 2))
		return mono.tobytes(), 1

	if src_channels == 1 and dst_channels == 2:
		stereo = array.array(typecode)
		for sample in samples:
			stereo.append(sample)
			stereo.append(sample)
		return stereo.tobytes(), 2
	return raw, src_channels

#============================================
def create_temp_wav(
	audio_path: str,
	rate: int,
	channels: int,
	size: int = -16,
) -> str | None:
	"""
	Decode an audio file with pygame and write a temporary WAV file.
	"""
	if not audio_path:
		return None
	if not os.path.isfile(audio_path):
		print(f"{Colors.WARNING}Audio file not found: {escape(audio_path)}{Colors.ENDC}")
		return None

	ensure_mixer_initialized(rate, size, channels)
	init = pygame.mixer.get_init()
	if not init:
		print(f"{Colors.WARNING}pygame mixer not initialized; skipping WAV.{Colors.ENDC}")
		return None

	frequency, init_size, init_channels = init
	sample_width, signed = _sample_format_from_size(init_size)

	try:
		sound = pygame.mixer.Sound(audio_path)
		raw = sound.get_raw()
	except Exception as error:
		print(f"{Colors.WARNING}Failed to decode audio with pygame: {escape(str(error))}{Colors.ENDC}")
		return None

	raw, out_channels = _convert_channels(raw, sample_width, signed, init_channels, channels)
	if frequency != rate:
		print(f"{Colors.WARNING}pygame mixer rate {frequency} != requested {rate}; using {frequency}.{Colors.ENDC}")
		rate = frequency

	with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as handle:
		temp_path = handle.name

	try:
		_write_wav(temp_path, raw, out_channels, sample_width, rate)
	except Exception as error:
		print(f"{Colors.WARNING}Failed to write WAV: {escape(str(error))}{Colors.ENDC}")
		try:
			os.unlink(temp_path)
		except OSError:
			pass
		return None
	return temp_path

#============================================
def create_playback_wav(audio_path: str) -> str | None:
	return create_temp_wav(audio_path, DEFAULT_PLAYBACK_RATE, channels=2, size=-16)

#============================================
def create_transcription_wav(audio_path: str) -> str | None:
	return create_temp_wav(audio_path, DEFAULT_TRANSCRIBE_RATE, channels=1, size=-16)
