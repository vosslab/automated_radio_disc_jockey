#!/usr/bin/env python3

import argparse
from gtts import gTTS
import pygame
import time

def speak_text(text):
    # Initialize pygame mixer
    pygame.mixer.init()
    
    # Generate speech and save to an audio file
    tts = gTTS(text=text, lang='en')
    audio_file = "output.mp3"
    tts.save(audio_file)
    
    # Load and play the audio file
    pygame.mixer.music.load(audio_file)
    pygame.mixer.music.play()
    
    # Wait until the audio is done playing
    while pygame.mixer.music.get_busy():
        time.sleep(1)  # Sleep to wait for the audio to finish

def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Convert text to speech using gTTS.")
    parser.add_argument("--text", type=str, required=True, help="Text to speak.")
    args = parser.parse_args()

    # Speak the provided text
    speak_text(args.text)

if __name__ == "__main__":
    main()
