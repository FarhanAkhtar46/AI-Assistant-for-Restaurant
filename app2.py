import os
import wave
import pyaudio
import numpy as np
from scipy.io import wavfile
from deepgram import Deepgram
import asyncio
from datetime import datetime

import voice_service as vs  # Import your custom voice service
from rag.AIVoiceAssistant import AIVoiceAssistant

DEFAULT_CHUNK_LENGTH = 5  # Adjusted for faster processing

ai_assistant = AIVoiceAssistant()

DEEPGRAM_API_KEY = ''  # Replace with your actual Deepgram API key
dg_client = Deepgram(DEEPGRAM_API_KEY)

order_number = 1  # Starting order number
order_details = {}  # Dictionary to store the order details

def is_silence(data, max_amplitude_threshold=3000):
    """Check if audio data contains silence."""
    max_amplitude = np.max(np.abs(data))
    return max_amplitude <= max_amplitude_threshold

def record_audio_chunk(audio, stream, chunk_length=DEFAULT_CHUNK_LENGTH):
    frames = []
    for _ in range(0, int(16000 / 1024 * chunk_length)):
        data = stream.read(1024)
        frames.append(data)

    temp_file_path = 'temp_audio_chunk.wav'
    with wave.open(temp_file_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b''.join(frames))

    # Check if the recorded chunk contains silence
    try:
        samplerate, data = wavfile.read(temp_file_path)
        if is_silence(data):
            os.remove(temp_file_path)
            return True
        else:
            return False
    except Exception as e:
        print(f"Error while reading audio file: {e}")
        return False

async def transcribe_audio(file_path):
    with open(file_path, 'rb') as audio_file:
        audio_data = audio_file.read()

    response = await dg_client.transcription.prerecorded({
        'buffer': audio_data,
        'mimetype': 'audio/wav'
    }, {'punctuate': True})

    transcription = response['results']['channels'][0]['alternatives'][0]['transcript']
    return transcription

def print_with_timestamp(label, text):
    """Prints the text with a timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {label}: {text}")

def save_final_order_receipt(order_details, order_number):
    """Save the final order details to a receipt file."""
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f"order_{order_number}_{date_str}.txt"
    with open(filename, 'w') as file:
        file.write(f"Order Receipt - Order #{order_number}\n")
        file.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        file.write("\n")
        for key, value in order_details.items():
            file.write(f"{key}: {value}\n")
    print(f"Final order receipt saved as {filename}")

def main():
    global order_number
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)

    try:
        while True:
            chunk_file = "temp_audio_chunk.wav"

            # Record audio chunk
            if record_audio_chunk(audio, stream):
                continue

            # Transcribe audio chunk asynchronously
            transcription = asyncio.run(transcribe_audio(chunk_file))
            print_with_timestamp("User", transcription)

            # Process the transcription with AI assistant
            response = ai_assistant.interact_with_llm(transcription)
            print_with_timestamp("AI", response)

            # Convert AI response text to speech and play it
            vs.play_text_to_speech_cartesia(response)

            # Capture relevant information based on the conversation
            if "name" in transcription.lower():
                order_details['Customer Name'] = transcription.split("name is")[-1].strip()
            elif "contact number" in transcription.lower():
                order_details['Contact Number'] = transcription.split("number is")[-1].strip()
            elif "order" in transcription.lower():
                order_details['Order Items'] = transcription.strip()

            # If the AI indicates the end of the conversation, save the final order receipt
            if any(phrase in response.lower() for phrase in ["thank you", "goodbye", "have a nice day", "your order is confirmed"]):
                save_final_order_receipt(order_details, order_number)
                order_number += 1
                order_details.clear()  # Reset for the next order

            os.remove(chunk_file)

    except KeyboardInterrupt:
        print("Terminating...")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()

if __name__ == "__main__":
    main()
