# Automated Radio Disc Jockey 🎵🤖  

An AI-powered virtual DJ that curates and announces songs like a real radio host, using a combination of music file metadata, web-sourced song information, an LLM-generated introduction, and text-to-speech (TTS) to create a seamless listening experience.

## Features  
- **Music Curation:** Reads a folder of `.mp3`, `.flac`, `.wav`, or `.ogg` files.  
- **Smart Selection:** Randomly picks five songs and prompts the user to choose one.  
- **Song Insights:** Fetches song or artist details from Wikipedia, AllMusic, or Last.fm.  
- **AI DJ Introduction:** Uses an LLM (e.g., Ollama) to craft a dynamic radio-style intro.  
- **Text-to-Speech:** Converts the DJ intro into natural-sounding speech.  
- **Autonomous Playlist Flow:** Selects the next song based on similarity to the previous track.  

## How It Works  
1. **Scan Music Directory:** Reads all available songs from a specified folder.  
2. **User Song Selection:** Randomly chooses five songs and lets the user pick one.  
3. **Fetch Song Information:** Searches Wikipedia (or alternative sources) for relevant details.  
4. **AI-Generated DJ Intro:** Uses an LLM to create a 3-sentence radio-style introduction.  
5. **Text-to-Speech Output:** The DJ intro is read aloud using TTS before the song plays.  
6. **Play the Song:** The selected track starts playing after the introduction.  
7. **Smart Auto-Selection:** AI picks the next song from five random choices, selecting the most similar track.  
8. **Repeat the Process!**  

## Setup & Requirements  
### **Prerequisites:**  
- Python 3.10+  
- Required libraries: `pygame`, `gtts`, `wikipedia`, `argparse`, `subprocess`, `random`, `os`, `time`  
- An LLM model compatible with Ollama for text generation  

### **Installation:**  
```bash
git clone https://github.com/yourusername/Automated_Radio_Disc_Jockey.git
cd Automated_Radio_Disc_Jockey
pip install -r requirements.txt
