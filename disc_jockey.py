#!/usr/bin/env python3.10

import os
import random
import subprocess
import pygame
import time
from gtts import gTTS
import wikipedia
import argparse

# Step 1: Get a listing of songs from a directory
def get_song_list(directory):
    audio_extensions = ['.mp3', '.wav', '.flac', '.ogg']
    song_list = [
        os.path.join(directory, file)
        for file in os.listdir(directory)
        if os.path.splitext(file)[1].lower() in audio_extensions
    ]
    return song_list

# Step 2: Randomly select five songs and prompt the user to select one
def select_song(song_list):
    selected_songs = random.sample(song_list, 5)
    print("Please select a song:")
    for i, song in enumerate(selected_songs):
        print(f"{i + 1}: {os.path.basename(song)}")
    
    choice = int(input("Enter the number of your choice: ")) - 1
    return selected_songs[choice]

# Step 3: Fetch content about the song from Wikipedia
def fetch_song_info(song_title):
    try:
        summary = wikipedia.summary(song_title, sentences=2)
    except wikipedia.exceptions.DisambiguationError as e:
        summary = wikipedia.summary(e.options[0], sentences=2)
    return summary

# Step 4: Pipe content about the song to the Ollama model
def query_ollama_model(prompt):
    command = ["ollama", "run", "model_name", prompt]  # Replace with your model name
    result = subprocess.run(command, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error:", result.stderr)
        return None
    
    return result.stdout.strip()

# Step 5: Use pygame to read aloud the DJ introduction
def speak_dj_intro(prompt):
    pygame.mixer.init()
    tts = gTTS(text=prompt, lang='en')
    audio_file = "dj_intro.mp3"
    tts.save(audio_file)
    pygame.mixer.music.load(audio_file)
    pygame.mixer.music.play()
    
    while pygame.mixer.music.get_busy():
        time.sleep(1)  # Wait for the audio to finish

# Step 6: Play the selected song
def play_song(song_path):
    pygame.mixer.init()
    pygame.mixer.music.load(song_path)
    pygame.mixer.music.play()
    
    while pygame.mixer.music.get_busy():
        time.sleep(1)  # Wait for the song to finish

# Main loop
def main(directory):
    song_list = get_song_list(directory)
    
    while True:
        chosen_song = select_song(song_list)
        song_name = os.path.basename(chosen_song)
        
        # Fetch song info and query the Ollama model
        song_info = fetch_song_info(song_name)
        prompt = (
            f"Imagine you’re a radio disc jockey introducing the next song on the playlist. "
            f"Start by stating the band and song name: '{song_name}'. "
            f"Here are some fun facts: {song_info}. "
            f"Now, repeat the band and song name: '{song_name}'."
        )
        
        # Generate the DJ introduction using the Ollama model
        dj_intro = query_ollama_model(prompt)
        print("DJ Introduction:", dj_intro)
        
        # Use TTS to read the DJ intro and play the song
        speak_dj_intro(dj_intro)
        play_song(chosen_song)

        # Optionally find and play a similar song
        similar_song = random.choice(song_list)  # Placeholder for finding a similar song
        print(f"Next up: {os.path.basename(similar_song)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Radio AI Disc Jockey")
    parser.add_argument(
        "directory",
        type=str,
        help="Path to the directory containing music files."
    )
    args = parser.parse_args()
    
    main(args.directory)
