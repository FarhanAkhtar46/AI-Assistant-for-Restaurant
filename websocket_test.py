import asyncio
import websockets

async def test_connection():
    uri = "ws://localhost:8000/stt"  # Replace with your actual URI
    try:
        # Connect to the WebSocket server
        websocket = await websockets.connect(uri)
        try:
            await websocket.send("Hello Server!")
            response = await websocket.recv()
            print(f"Received: {response}")
        finally:
            # Close the WebSocket connection
            await websocket.close()
    except ConnectionRefusedError:
        print("Connection refused. Ensure the WebSocket server is running and accessible.")
    except Exception as e:
        print(f"An error occurred: {e}")

# Run the test
asyncio.run(test_connection())
