import os
import asyncio
import sounddevice as sd
import websockets
import json
from datetime import datetime
from deepgram import Deepgram
import pyaudio

import voice_service as vs  # Import your custom voice service
from rag.AIVoiceAssistant import AIVoiceAssistant

# Configuration
DEEPGRAM_API_KEY = ''  # Replace with your actual Deepgram API key
RATE = 16000
CHANNELS = 1
DEFAULT_CHUNK_SIZE = 1024
CHUNK = 8000

ai_assistant = AIVoiceAssistant()
order_number = 1
order_details = {}

deepgram = Deepgram(DEEPGRAM_API_KEY)

# def print_with_timestamp(label, text):
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     print(f"[{timestamp}] {label}: {text}")

# def save_final_order_receipt(order_details, order_number):
#     date_str = datetime.now().strftime('%Y%m%d')
#     filename = f"order_{order_number}_{date_str}.txt"
#     with open(filename, 'w') as file:
#         file.write(f"Order Receipt - Order #{order_number}\n")
#         file.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
#         for key, value in order_details.items():
#             file.write(f"{key}: {value}\n")
#     print(f"Final order receipt saved as {filename}")

# async def transcribe_and_interact(ws):
#     """Handles the transcription and interaction with the AI assistant."""
#     async for message in ws:
#         response = json.loads(message)
#         if 'channel' in response and 'alternatives' in response['channel']['alternatives'][0]:
#             transcription = response['channel']['alternatives'][0]['transcript']
#             if transcription:
#                 print_with_timestamp("User", transcription)
#                 ai_response = ai_assistant.interact_with_llm(transcription)
#                 print_with_timestamp("AI", ai_response)
#                 vs.play_text_to_speech_cartesia(ai_response)

#                 # Capture relevant information based on the conversation
#                 if "name" in transcription.lower():
#                     order_details['Customer Name'] = transcription.split("name is")[-1].strip()
#                 elif "contact number" in transcription.lower():
#                     order_details['Contact Number'] = transcription.split("number is")[-1].strip()
#                 elif "order" in transcription.lower():
#                     order_details['Order Items'] = transcription.strip()

#                 # If the AI indicates the end of the conversation, save the final order receipt
#                 if any(phrase in ai_response.lower() for phrase in ["thank you", "goodbye", "have a nice day", "your order is confirmed"]):
#                     save_final_order_receipt(order_details, order_number)
#                     order_number += 1
#                     order_details.clear()  # Reset for the next order

# async def audio_stream(ws):
#     """Handles streaming audio to the WebSocket."""
#     with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16', blocksize=DEFAULT_CHUNK_SIZE) as stream:
#         while True:
#             indata = stream.read(DEFAULT_CHUNK_SIZE)[0]
#             await ws.send(indata.tobytes())

# async def main():
#     uri = "wss://api.deepgram.com/v1/listen"
#     headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

#     try:
#         async with websockets.connect(uri, extra_headers=headers) as ws:
#             print("Connected to Deepgram WebSocket API")

#             # Run both the audio stream and transcription handler concurrently
#             await asyncio.gather(
#                 audio_stream(ws),
#                 transcribe_and_interact(ws)
#             )

#     except websockets.exceptions.ConnectionClosedError as e:
#         print(f"Connection closed: {e}. Reconnecting...")
#         await reconnect_with_backoff()

#     except websockets.exceptions.ConnectionClosedOK as e:
#         print(f"Connection closed: {e}. Reconnecting...")
#         await reconnect_with_backoff()

# async def reconnect_with_backoff(attempts=5):
#     delay = 1
#     for attempt in range(attempts):
#         try:
#             await asyncio.sleep(delay)
#             await main()
#             return
#         except websockets.exceptions.ConnectionClosedError:
#             delay *= 2  # Exponential backoff
#     print("Failed to reconnect after multiple attempts.")

# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print("Terminating...")

FORMAT = pyaudio.paInt16


audio_queue = asyncio.Queue()

def callback(input_data, frame_count, time_info, status_flags):
   audio_queue.put_nowait(input_data)

   return (input_data, pyaudio.paContinue)


async def microphone(stop_event): 
   audio = pyaudio.PyAudio()
   stream = audio.open(
       format = FORMAT,
       channels = CHANNELS,
       rate = RATE,
       input = True,
       frames_per_buffer = CHUNK,
       stream_callback = callback
   )

   stream.start_stream()

   while not stop_event.is_set() and stream.is_active():
       await asyncio.sleep(0.1)


   stream.stop_stream()
   stream.close()

async def process(stop_event):
   extra_headers = {
       'Authorization': 'token ' + DEEPGRAM_API_KEY
   }

   async with websockets.connect('wss://api.deepgram.com/v1/listen?encoding=linear16&sample_rate=16000&channels=1', extra_headers = extra_headers) as ws:
       async def sender(ws): # sends audio to websocket
           try:
               while not stop_event.is_set():
                   data = await audio_queue.get()
                   await ws.send(data)
           except Exception as e:
               print('Error while sending: ' + str(e))

               raise

       async def receiver(ws): 
           async for msg in ws:
               msg = json.loads(msg)
               # Check if 'channel' exists in the message
               if 'channel' in msg and 'alternatives' in msg['channel']:
                    transcript = msg['channel']['alternatives'][0]['transcript']

               if transcript:
                    print(f'Transcript = {transcript}')
                    response = ai_assistant.interact_with_llm(transcript)
                    print("AI:", response)

                # Convert AI response text to speech and play it
                    vs.play_text_to_speech_cartesia(response)

                    # Reactivate microphone after AI response
                    stop_event.clear()
                    await asyncio.gather(microphone(stop_event), process(stop_event))
                   
               else:
                print(f"Unexpected message format: {msg}")
       await asyncio.gather(sender(ws), receiver(ws))

      




async def run():
   
            stop_event = asyncio.Event()

            while True:
         # Start microphone and processing
                 await asyncio.gather(microphone(stop_event), process(stop_event))
                 stop_event.set()  # This will stop the microphone until AI responds
    
   
if __name__ == '__main__':
   asyncio.run(run())