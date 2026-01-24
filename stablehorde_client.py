"""Stable Horde Image Generation Client - Free, Community-powered, No Auth Required"""

import logging
import base64
import httpx
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


class StableHordeClient:
    """Client for Stable Horde - Free crowdsourced image generation"""

    def __init__(self, api_key: str = "0000000000"):
        # Anonymous key works but has lowest priority
        # Users can register at https://stablehorde.net/ for higher priority
        self.api_key = api_key
        self.base_url = "https://stablehorde.net/api/v2"
        self.models = ["stable_diffusion", "SDXL 1.0"]  # Default models

    async def start(self):
        """Initialize the client"""
        logger.info("StableHordeClient initialized (free community service)")

    async def stop(self):
        """Cleanup"""
        logger.info("StableHordeClient stopped")

    async def generate_image(
        self,
        prompt: str,
        model: str = "SDXL 1.0",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
    ) -> Dict[str, Any]:
        """Generate an image using Stable Horde (free, community-powered)"""

        try:
            logger.info(
                f"🎨 StableHorde: Generating image with prompt: '{prompt[:50]}...'"
            )

            headers = {
                "apikey": self.api_key,
                "Content-Type": "application/json",
            }

            # Stable Horde generation request
            payload = {
                "prompt": prompt,
                "params": {
                    "width": min(width, 1024),  # Max 1024 for free tier
                    "height": min(height, 1024),
                    "steps": min(steps, 30),  # Limit steps for faster generation
                    "cfg_scale": 7.5,
                    "sampler_name": "k_euler_a",
                },
                "nsfw": False,
                "censor_nsfw": True,
                "models": [model],
                "r2": True,  # Use R2 for faster image delivery
            }

            async with httpx.AsyncClient() as client:
                # Step 1: Submit generation request
                logger.info("🎨 StableHorde: Submitting generation request...")
                response = await client.post(
                    f"{self.base_url}/generate/async",
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code != 202:
                    error_text = response.text
                    logger.error(
                        f"StableHorde submission failed: {response.status_code} - {error_text}"
                    )
                    return {"error": f"StableHorde error: {response.status_code}"}

                result = response.json()
                job_id = result.get("id")

                if not job_id:
                    return {"error": "StableHorde: No job ID received"}

                logger.info(f"🎨 StableHorde: Job submitted, ID: {job_id}")

                # Step 2: Poll for completion (max 3 minutes for free tier)
                max_wait = 180  # 3 minutes max
                poll_interval = 5
                elapsed = 0

                while elapsed < max_wait:
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval

                    check_response = await client.get(
                        f"{self.base_url}/generate/check/{job_id}",
                        timeout=10.0,
                    )

                    if check_response.status_code != 200:
                        continue

                    check_data = check_response.json()

                    if check_data.get("done"):
                        logger.info("🎨 StableHorde: Generation complete!")
                        break

                    wait_time = check_data.get("wait_time", 0)
                    queue_pos = check_data.get("queue_position", 0)
                    logger.info(
                        f"🎨 StableHorde: Queue position {queue_pos}, ~{wait_time}s remaining"
                    )

                # Step 3: Get the generated image
                status_response = await client.get(
                    f"{self.base_url}/generate/status/{job_id}",
                    timeout=30.0,
                )

                if status_response.status_code != 200:
                    return {
                        "error": f"StableHorde status check failed: {status_response.status_code}"
                    }

                status_data = status_response.json()
                generations = status_data.get("generations", [])

                if not generations:
                    return {"error": "StableHorde: No images generated"}

                # Get the first generated image
                gen = generations[0]
                img_url = gen.get("img")

                if not img_url:
                    return {"error": "StableHorde: No image URL in response"}

                # Download the image and convert to base64
                logger.info(f"🎨 StableHorde: Downloading image from {img_url[:50]}...")
                img_response = await client.get(img_url, timeout=60.0)

                if img_response.status_code != 200:
                    # Return URL if download fails
                    return {
                        "image_url": img_url,
                        "format": "webp",
                        "model": model,
                        "prompt": prompt,
                        "provider": "stablehorde",
                    }

                image_bytes = img_response.content
                img_b64 = base64.b64encode(image_bytes).decode("utf-8")

                logger.info(f"✅ StableHorde SUCCESS ({len(image_bytes)} bytes)")
                return {
                    "image_base64": img_b64,
                    "image_url": img_url,
                    "format": "webp",
                    "model": model,
                    "prompt": prompt,
                    "provider": "stablehorde",
                }

        except asyncio.TimeoutError:
            logger.error("StableHorde: Request timed out")
            return {"error": "StableHorde: Request timed out"}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"StableHorde error: {error_msg}")
            return {"error": f"StableHorde error: {error_msg}"}

    def get_tools(self) -> list:
        """Return tool definitions for LLM integration"""
        return [
            {
                "name": "stablehorde_image_generation",
                "description": "Generate an image using Stable Horde (FREE community service).",
                "server": "stablehorde",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Description of the image to generate",
                        },
                    },
                    "required": ["prompt"],
                },
            },
        ]
