import os
import wave
import pyaudio
import numpy as np
from scipy.io import wavfile
from openai import OpenAI
import voice_service as vs
from rag.AIVoiceAssistant import AIVoiceAssistant
from concurrent.futures import ThreadPoolExecutor
import time

ai_assistant = AIVoiceAssistant()
executor = ThreadPoolExecutor(max_workers=1)  # Ensure only one thread for audio processing

client = OpenAI(api_key='')

DEFAULT_CHUNK_LENGTH = 10

last_transcription = None
last_transcription_time = 0
debounce_interval = 2  # in seconds, increased to prevent quick duplicate processing

def is_silence(data, max_amplitude_threshold=3000):
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

    return temp_file_path

def transcribe_audio(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        return transcription.text
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""

def process_audio_chunk(audio, stream):
    global last_transcription, last_transcription_time
    
    chunk_file = record_audio_chunk(audio, stream)
    try:
        samplerate, data = wavfile.read(chunk_file)
        if not is_silence(data):
            transcription = transcribe_audio(chunk_file)
            
            current_time = time.time()
            if transcription == last_transcription and (current_time - last_transcription_time) < debounce_interval:
                return

            last_transcription = transcription
            last_transcription_time = current_time

            print("Customer: {}".format(transcription))

            output = ai_assistant.interact_with_llm(transcription)
            if output:
                output = output.lstrip()
                vs.play_text_to_speech(output)
                print("AI Assistant: {}".format(output))
    except Exception as e:
        print(f"Error while reading audio file: {e}")
    finally:
        if os.path.exists(chunk_file):
            os.remove(chunk_file)

def main():
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)

    try:
        while True:
            executor.submit(process_audio_chunk, audio, stream)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()

if __name__ == "__main__":
    main()
