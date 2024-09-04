import os
import time
import pygame
import subprocess
from deepgram import DeepgramClient, SpeakOptions
from dotenv import load_dotenv

load_dotenv()

deep_api_key = os.getenv('DEEPGRAM_API_KEY')  # Replace with your Deepgram API key
filename = "temp_audio.mp3"


def play_text_to_speech_deepgram(text):
    
        # STEP 1: Create a Deepgram client.
        deepgram = DeepgramClient(api_key=deep_api_key)

        # STEP 2: Configure the options (such as model choice, audio configuration, etc.)
        options = SpeakOptions(
            model="aura-asteria-en",
        )

        # STEP 3: Call the save method on the speak property
        SPEAK_OPTIONS = {"text": text}
        response = deepgram.speak.rest.v("1").save(filename, SPEAK_OPTIONS, options)

        

        
            # Initialize pygame mixer and play the .wav file
        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)


        pygame.mixer.music.stop()
        pygame.mixer.quit()

        time.sleep(1)
        
        # Clean up temporary files
        # os.remove(temp_raw_file)
        os.remove(filename)
    

# Example usage
# response_text = "Hello, how can I help you today?"
# play_text_to_speech_deepgram(response_text)

