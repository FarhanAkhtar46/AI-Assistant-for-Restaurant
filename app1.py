import os
import wave
import pyaudio
import numpy as np
from scipy.io import wavfile
from deepgram import Deepgram
import asyncio  # Import asyncio to handle async functions

import voice_service as vs
from rag.AIVoiceAssistant import AIVoiceAssistant

DEFAULT_CHUNK_LENGTH = 10

ai_assistant = AIVoiceAssistant()

DEEPGRAM_API_KEY = ''  # Replace with your actual Deepgram API key
dg_client = Deepgram(DEEPGRAM_API_KEY)

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
        'mimetype': 'audio/wav'  # Ensure the correct MIME type for the audio file
    }, {'punctuate': True})

    transcription = response['results']['channels'][0]['alternatives'][0]['transcript']
    return transcription

def main():
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
    customer_input_transcription = ""

    try:
        while True:
            chunk_file = "temp_audio_chunk.wav"

            # Record audio chunk
            if record_audio_chunk(audio, stream):
                continue

            # Transcribe audio chunk asynchronously
            transcription = asyncio.run(transcribe_audio(chunk_file))
            print(f"Transcription: {transcription}")

            # Process the transcription with AI assistant
            response = ai_assistant.interact_with_llm(transcription)
            print(f"AI Response: {response}")

            os.remove(chunk_file)

    except KeyboardInterrupt:
        print("Terminating...")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()

if __name__ == "__main__":
    main()
