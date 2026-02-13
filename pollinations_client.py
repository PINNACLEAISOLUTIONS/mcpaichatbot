"""Pollinations.ai Image Generation Client - Free, No API Key Required"""

import logging
import base64
import httpx  # type: ignore
import urllib.parse
import uuid
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class PollinationsImageClient:
    """Client for Pollinations.ai image generation - Free and easy to use"""

    def __init__(self):
        self.base_url = "https://pollinations.ai/p"

    async def start(self):
        """Initialize the client"""
        logger.info("PollinationsImageClient initialized")

    async def stop(self):
        """Cleanup"""
        logger.info("PollinationsImageClient stopped")

    async def generate_image(
        self,
        prompt: str,
        model: str = "flux",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate an image using Pollinations.ai with automatic model fallback"""

        # Model fallback chain - try without model first (uses default), then specific models
        model_chain = [None, "flux", "turbo", "flux-realism", "flux-anime", "flux-3d"]

        last_error = None

        for current_model in model_chain:
            try:
                model_str = current_model if current_model else "default"
                logger.info(
                    f"🎨 Pollinations: Trying model '{model_str}' for prompt: '{prompt[:50]}...'"
                )

                # Encode prompt for URL
                encoded_prompt = urllib.parse.quote(prompt)

                # Build URL with parameters - omit model param if None
                img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"
                if current_model:
                    img_url += f"&model={current_model}"
                if seed:
                    img_url += f"&seed={seed}"

                # Pollinations generates images on the fly via GET
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        img_url, timeout=60.0, follow_redirects=True
                    )

                    if response.status_code >= 500:
                        last_error = (
                            f"Model {current_model}: Status {response.status_code}"
                        )
                        continue

                    if response.status_code != 200:
                        last_error = f"Status {response.status_code}"
                        continue

                    content_type = response.headers.get("content-type", "")
                    if (
                        "text/html" in content_type
                        or "application/json" in content_type
                    ):
                        last_error = f"Model {current_model}: Non-image response"
                        continue

                    image_bytes = response.content
                    if len(image_bytes) < 100:
                        last_error = f"Model {current_model}: Invalid image data"
                        continue

                    img_b64 = base64.b64encode(image_bytes).decode("utf-8")

                    logger.info(f"✅ Pollinations SUCCESS with model '{current_model}'")
                    return {
                        "image_base64": img_b64,
                        "image_url": img_url,
                        "format": "png",
                        "model": current_model,
                        "prompt": prompt,
                        "provider": "pollinations",
                    }

            except Exception as e:
                last_error = str(e)
                continue

        return {"error": f"Pollinations: All models unavailable. {last_error}"}

    def get_tools(self) -> list:
        """Return tool definitions for LLM integration"""
        return [
            {
                "name": "pollinations_image_generation",
                "description": "Generate a beautiful image from a text description (FREE).",
                "server": "pollinations",
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
