import os
import logging
from dotenv import load_dotenv  # type: ignore
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

    print("--- ElevenLabs Connection Test ---")
    if not api_key:
        print("❌ STATUS: ELEVENLABS_API_KEY is MISSING from environment/ .env")
        print("Fix: Ensure the key is set in Render's Environment Variables.")
        return

    api_key = api_key.strip()
    print(f"✅ STATUS: Key found (starts with: {api_key[:5]}...)")

    try:
        from elevenlabs.client import ElevenLabs  # type: ignore

        client = ElevenLabs(api_key=api_key)

        # 1. Test fetching voices
        print("\n1. Fetching available voices...")
        # Note: .voices.get_all() is the correct SDK v1.x pattern
        voices_response = client.voices.get_all()
        voices = voices_response.voices

        print(f"✅ Success! Found {len(voices)} voices.")

        # 2. Check for specific voice
        target_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
        voice_found = False
        voice_name = "Unknown"
        for v in voices:
            if v.voice_id == target_voice_id:
                print(f"✅ Target Voice Found: '{v.name}' (ID: {v.voice_id})")
                voice_found = True
                voice_name = v.name
                break

        if not voice_found:
            print(f"⚠️ Target Voice ID {target_voice_id} NOT found in your profile.")
            if voices:
                target_voice_id = voices[0].voice_id
                voice_name = voices[0].name
                print(
                    f"👉 Using first available instead: '{voice_name}' (ID: {target_voice_id})"
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
            # For the generator, we use next() to get the first chunk of bytes
            chunk = next(audio_generator)
            if chunk:
                print("✅ TTS Stream Handshake: SUCCESS")
            else:
                print("⚠️ Handshake produced empty data.")
        except StopIteration:
            print("⚠️ Handshake produced no data (check quota).")

        print("\n--- TEST COMPLETE: EVERYTHING LOOKS GOOD ---")

    except ImportError:
        print("❌ Error: 'elevenlabs' library not installed correctly.")
    except Exception as e:
        print(f"❌ Connection Failed: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_elevenlabs_connection())
