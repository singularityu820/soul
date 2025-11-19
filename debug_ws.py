import asyncio
import websockets
import sys

async def test_connection():
    uri = "ws://localhost:8000/ws/pipeline"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            msg = await websocket.recv()
            print(f"Received: {msg}")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(test_connection())
    except KeyboardInterrupt:
        pass
