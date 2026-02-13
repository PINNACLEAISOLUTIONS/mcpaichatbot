import os
import logging
from dotenv import load_dotenv
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_elevenlabs_connection():
    """
    Test script to verify ElevenLabs API connection and voice availability.
    Run this after adding ELEVENLABS_API_KEY to your .env file.
    """
    load_dotenv(override=True)

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        logger.error("❌ ELEVENLABS_API_KEY not found in .env file.")
        print("\nFix: Add ELEVENLABS_API_KEY=your_key_here to your .env file.")
        return

    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=api_key)

        print("--- ElevenLabs Connection Test ---")
        print(f"Connecting with API Key: {api_key[:5]}...{api_key[-5:]}")

        # 1. Test fetching voices
        print("\n1. Fetching available voices...")
        voices_response = client.voices.get_all()
        voices = voices_response.voices

        print(f"✅ Success! Found {len(voices)} voices.")

        # 2. Check for specific voice
        target_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
        voice_found = False
        for v in voices:
            if v.voice_id == target_voice_id:
                print(f"✅ Target Voice Found: '{v.name}' (ID: {v.voice_id})")
                voice_found = True
                break

        if not voice_found:
            print(
                f"⚠️ Target Voice ID {target_voice_id} NOT found in your profile. Using default."
            )

        # 3. Test conversion (first 5 words only to save quota)
        print("\n2. Testing small text-to-speech conversion...")
        audio_generator = client.text_to_speech.convert(
            voice_id=target_voice_id,
            text="Connection test successful. Ready for Pinnacle A I.",
            model_id="eleven_multilingual_v2",
        )

        # Peek at the first chunk
        try:
            next(audio_generator)
            print("✅ TTS Stream Handshake: SUCCESS")
        except StopIteration:
            print("⚠️ Handshake produced no data (check quota).")

        print("\n--- TEST COMPLETE: EVERYTHING LOOKS GOOD ---")

    except ImportError:
        print(
            "❌ Error: 'elevenlabs' library not installed. Run 'pip install elevenlabs'"
        )
    except Exception as e:
        print(f"❌ Connection Failed: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_elevenlabs_connection())
