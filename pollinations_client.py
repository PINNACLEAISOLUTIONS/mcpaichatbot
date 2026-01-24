"""Pollinations.ai Image Generation Client - Free, No API Key Required"""

import logging
import base64
import httpx  # type: ignore
import urllib.parse
from typing import Dict, Any, Optional

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
        # None = no model param (lets Pollinations choose the best available)
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
                    logger.info(f"🎨 Pollinations: Fetching from {img_url[:80]}...")
                    response = await client.get(
                        img_url, timeout=180.0, follow_redirects=True
                    )

                    # Check for server errors - try next model
                    if response.status_code >= 500:
                        logger.warning(
                            f"Pollinations model '{current_model}' returned {response.status_code}, trying next..."
                        )
                        last_error = (
                            f"Model {current_model}: Status {response.status_code}"
                        )
                        continue

                    if response.status_code != 200:
                        logger.warning(
                            f"Pollinations failed with status {response.status_code}"
                        )
                        last_error = f"Status {response.status_code}"
                        continue

                    # Validate that we got actual image data, not HTML/JSON error page
                    content_type = response.headers.get("content-type", "")
                    if (
                        "text/html" in content_type
                        or "application/json" in content_type
                    ):
                        logger.warning(
                            f"Pollinations model '{current_model}' returned non-image: {content_type}, trying next..."
                        )
                        last_error = f"Model {current_model}: Non-image response"
                        continue

                    # Check if content looks like valid image data
                    image_bytes = response.content
                    if len(image_bytes) < 100:
                        logger.warning(
                            f"Pollinations model '{current_model}' returned too little data: {len(image_bytes)} bytes"
                        )
                        last_error = f"Model {current_model}: Invalid image data"
                        continue

                    img_b64 = base64.b64encode(image_bytes).decode("utf-8")

                    logger.info(
                        f"✅ Pollinations SUCCESS with model '{current_model}' ({len(image_bytes)} bytes)"
                    )
                    return {
                        "image_base64": img_b64,
                        "image_url": img_url,
                        "format": "png",
                        "model": current_model,
                        "prompt": prompt,
                        "provider": "pollinations",
                    }

            except httpx.TimeoutException:
                logger.warning(
                    f"Pollinations model '{current_model}' timed out, trying next..."
                )
                last_error = f"Model {current_model}: Timeout"
                continue
            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    f"Pollinations model '{current_model}' error: {error_msg}, trying next..."
                )
                last_error = f"Model {current_model}: {error_msg}"
                continue

        # All models failed
        logger.error(f"All Pollinations models failed. Last error: {last_error}")
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
