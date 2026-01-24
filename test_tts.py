import asyncio
import os
from dotenv import load_dotenv
from elevenlabs.client import AsyncElevenLabs
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_tts():
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ No ELEVENLABS_API_KEY found")
        return

    print(f"Using API Key: {api_key[:5]}...")
    client = AsyncElevenLabs(api_key=api_key)

    try:
        print("Attempting to get audio stream WITHOUT await on convert...")
        # Try without await first since the error suggested convert() returns the generator directly
        audio_stream = client.text_to_speech.convert(
            text="Hello, this is a test of the ElevenLabs voice system.",
            voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        print(f"Type of audio_stream: {type(audio_stream)}")

        print("Consuming chunks...")
        audio_data = b""
        async for chunk in audio_stream:
            audio_data += chunk

        print(f"✅ Success! Received {len(audio_data)} bytes of audio data.")

        with open("test_output.mp3", "wb") as f:
            f.write(audio_data)
        print("Saved to test_output.mp3")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_tts())
