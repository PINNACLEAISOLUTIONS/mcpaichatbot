"""FAL.ai Image Generation Client - Free tier without billing required"""

import os
import logging
import base64
import httpx
from typing import Dict, Any

logger = logging.getLogger(__name__)


class FalImageClient:
    """Client for FAL.ai image generation API - $50 free credits for new users"""

    def __init__(self):
        self.api_key = os.getenv("FAL_KEY")
        self.base_url = "https://fal.run"

    async def start(self):
        """Initialize the client"""
        if not self.api_key:
            logger.warning("FAL_KEY not found - FAL.ai image generation disabled")
        else:
            logger.info("FalImageClient initialized with API key")

    async def stop(self):
        """Cleanup"""
        logger.info("FalImageClient stopped")

    async def generate_image(
        self,
        prompt: str,
        model: str = "fal-ai/flux/schnell",
    ) -> Dict[str, Any]:
        """Generate an image using FAL.ai API"""

        if not self.api_key:
            return {"error": "FAL_KEY not configured"}

        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            logger.info(f"🎨 FAL.ai: Generating image with model: {model}")
            logger.info(f"🎨 FAL.ai: Prompt: '{prompt}'")

            async with httpx.AsyncClient() as client:
                # FAL.ai uses a simple endpoint structure
                response = await client.post(
                    f"{self.base_url}/{model}",
                    headers=headers,
                    json={
                        "prompt": prompt,
                        "num_images": 1,
                        "enable_safety_checker": True,
                    },
                    timeout=120.0,  # Image generation can take time
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.warning(
                        f"FAL.ai failed: {response.status_code} - {error_text[:200]}"
                    )
                    return {"error": f"FAL.ai error: {error_text[:200]}"}

                result = response.json()

                # FAL.ai returns images in the "images" array
                images = result.get("images", [])
                if not images:
                    return {"error": "No images returned from FAL.ai"}

                image_url = images[0].get("url")
                if not image_url:
                    return {"error": "No image URL in FAL.ai response"}

                logger.info(f"✅ FAL.ai image generated: {image_url[:50]}...")

                # Download the image and convert to base64
                img_response = await client.get(image_url, timeout=30.0)
                if img_response.status_code == 200:
                    img_b64 = base64.b64encode(img_response.content).decode("utf-8")
                    return {
                        "image_base64": img_b64,
                        "image_url": image_url,
                        "format": "png",
                        "model": model,
                        "prompt": prompt,
                    }
                else:
                    # Return URL if download fails
                    return {
                        "image_url": image_url,
                        "format": "png",
                        "model": model,
                        "prompt": prompt,
                    }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"FAL.ai error: {error_msg}")
            return {"error": f"FAL.ai error: {error_msg}"}

    def get_tools(self) -> list:
        """Return tool definitions for LLM integration"""
        return [
            {
                "name": "fal_image_generation",
                "description": "Generate an image from a text description.",
                "server": "fal",
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
