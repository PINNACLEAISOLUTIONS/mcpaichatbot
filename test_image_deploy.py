import httpx
import asyncio
import os
import sys


async def verify_image_fix():
    print("🔍 Starting Image Fix Verification...")

    # Use PUBLIC_BASE_URL if set, else localhost
    base_url = os.getenv("EXTERNAL_TEST_URL") or "http://localhost:8001"
    debug_endpoint = f"{base_url}/api/debug/image-test"

    print(f"📡 Triggering image test at: {debug_endpoint}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 1. Trigger the debug generation
            resp = await client.get(debug_endpoint)
            if resp.status_code != 200:
                print(f"❌ Error: Debug endpoint returned {resp.status_code}")
                print(resp.text)
                return False

            data = resp.json()
            if not data.get("success"):
                print(f"❌ Error: Debug generation failed: {data.get('error')}")
                return False

            abs_url = data.get("absolute_url")
            print("✅ Image generated successfully.")
            print(f"🔗 Absolute URL to test: {abs_url}")

            # 2. Verify accessibility
            print("📡 Testing image accessibility...")
            img_resp = await client.get(abs_url)

            if img_resp.status_code == 200:
                print("🎉 SUCCESS! Image is reachable and returned HTTP 200.")
                print(f"📊 Content-Type: {img_resp.headers.get('Content-Type')}")
                print(f"📊 Size: {len(img_resp.content)} bytes")
                return True
            else:
                print(f"❌ FAILURE! Image returned HTTP {img_resp.status_code}")
                print(
                    "Hint: Check if the server is serving /static correctly and if PUBLIC_BASE_URL is correct."
                )
                return False

        except Exception as e:
            print(f"❌ Unexpected error during verification: {e}")
            return False


if __name__ == "__main__":
    success = asyncio.run(verify_image_fix())
    if not success:
        sys.exit(1)
    else:
        sys.exit(0)
