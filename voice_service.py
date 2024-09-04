import os
import time
import pygame
import requests
import subprocess
from dotenv import load_dotenv

load_dotenv()

def play_text_to_speech_cartesia(text):
    url = "https://api.cartesia.ai/tts/bytes"
    
    headers = {
        "Cartesia-Version": "2024-06-10",
        # "X-API-Key": "ed1a5450-7043-4546-b79c-4d27bf8dd363",  # Replace with your actual API key
        
        "X-API-Key": os.getenv("Cartesia-API-Key"),
        "Content-Type": "application/json"
    }
    
    payload = {
        "transcript": text,
        "model_id": "sonic-english",  # Adjust the model ID as needed
        "voice": {
            "mode": "id",
            "id": "248be419-c632-4f23-adf1-5324ed7dbf1d"  # Replace with the appropriate voice ID
        },
        "output_format": {
            "container": "wav",  # Requesting WAV format directly
            "encoding": "pcm_s16le",  # Standard encoding for WAV
            "sample_rate": 44100
        }
    }
    
    # Send the POST request
    response = requests.post(url, headers=headers, json=payload, stream=True)
    
    if response.status_code == 200:
        # temp_raw_file = "temp_audio.raw"
        temp_wav_file = "temp_audio.wav"
        
        # Write the raw audio data to a temporary file
        with open(temp_wav_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Convert the raw audio to a .wav file using ffmpeg
        # subprocess.run([
        #     r'C:\Users\farhan.akhtar\Downloads\ffmpeg-master-latest-win64-gpl\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe', '-f', 'f32le', '-i', temp_raw_file, temp_wav_file
        # ])
        
        # Initialize pygame mixer and play the .wav file
        pygame.mixer.init()
        pygame.mixer.music.load(temp_wav_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        pygame.mixer.music.stop()
        pygame.mixer.quit()

        time.sleep(1)
        
        # Clean up temporary files
        # os.remove(temp_raw_file)
        os.remove(temp_wav_file)
    else:
        print(f"Error: {response.status_code}, {response.text}")

# Example usage
# response_text = "Welcome to Cartesia Sonic!"
# play_text_to_speech_cartesia(response_text)
