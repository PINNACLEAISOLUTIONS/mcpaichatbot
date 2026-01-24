"""Replicate Image Generation Client - Using Replicate API for image generation"""

import os
import logging
import base64
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ReplicateImageClient:
    """Client for Replicate image generation API"""

    # Best models for image generation on Replicate (in order of quality)
    MODELS = [
        "black-forest-labs/flux-schnell",  # Fast, good quality, cheap
        "black-forest-labs/flux-dev",  # Higher quality, slower
        "stability-ai/sdxl",  # Stable Diffusion XL
    ]

    def __init__(self):
        self.api_token = os.getenv("REPLICATE_API_TOKEN")
        self.base_url = "https://api.replicate.com/v1"

    async def start(self):
        """Initialize the client"""
        if not self.api_token:
            logger.warning("REPLICATE_API_TOKEN not found - image generation will fail")
        else:
            logger.info("ReplicateImageClient initialized")

    async def stop(self):
        """Cleanup"""
        logger.info("ReplicateImageClient stopped")

    async def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate an image using Replicate API"""

        if not self.api_token:
            return {"error": "Replicate API token not configured"}

        # Use specified model or default to first in list
        models_to_try = (
            [model] if model else self.MODELS[:1]
        )  # Only try one model to save credits

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        last_error = "Unknown error"

        for try_model in models_to_try:
            try:
                logger.info(f"🎨 Replicate: Generating image with model: {try_model}")
                logger.info(f"🎨 Replicate: Prompt: '{prompt}'")

                # Create prediction
                async with httpx.AsyncClient() as client:
                    # Start the prediction
                    create_response = await client.post(
                        f"{self.base_url}/models/{try_model}/predictions",
                        headers=headers,
                        json={
                            "input": {
                                "prompt": prompt,
                                "num_outputs": 1,
                            }
                        },
                        timeout=30.0,
                    )

                    if create_response.status_code != 201:
                        error_text = create_response.text
                        logger.warning(
                            f"Replicate create failed: {create_response.status_code} - {error_text}"
                        )
                        last_error = (
                            f"Status {create_response.status_code}: {error_text[:200]}"
                        )
                        continue

                    prediction = create_response.json()
                    prediction_id = prediction.get("id")

                    logger.info(f"Replicate prediction started: {prediction_id}")

                    # Poll for completion (max 60 seconds)
                    import asyncio

                    for _ in range(30):  # 30 attempts * 2 seconds = 60 seconds max
                        await asyncio.sleep(2)

                        status_response = await client.get(
                            f"{self.base_url}/predictions/{prediction_id}",
                            headers=headers,
                            timeout=10.0,
                        )

                        if status_response.status_code != 200:
                            continue

                        status_data = status_response.json()
                        status = status_data.get("status")

                        if status == "succeeded":
                            output = status_data.get("output")
                            if output and len(output) > 0:
                                image_url = (
                                    output[0] if isinstance(output, list) else output
                                )
                                logger.info(
                                    f"✅ Replicate image generated: {image_url[:50]}..."
                                )

                                # Download the image and convert to base64
                                img_response = await client.get(image_url, timeout=30.0)
                                if img_response.status_code == 200:
                                    img_b64 = base64.b64encode(
                                        img_response.content
                                    ).decode("utf-8")
                                    return {
                                        "image_base64": img_b64,
                                        "image_url": image_url,
                                        "format": "png",
                                        "model": try_model,
                                        "prompt": prompt,
                                    }
                                else:
                                    # Return URL if download fails
                                    return {
                                        "image_url": image_url,
                                        "format": "png",
                                        "model": try_model,
                                        "prompt": prompt,
                                    }

                        elif status == "failed":
                            error = status_data.get("error", "Unknown error")
                            logger.warning(f"Replicate prediction failed: {error}")
                            last_error = str(error)
                            break

                        elif status in ["starting", "processing"]:
                            continue

                    else:
                        last_error = "Timeout waiting for image generation"

            except Exception as e:
                last_error = str(e)
                logger.error(f"Replicate error: {last_error}")
                continue

        return {"error": f"Image generation failed: {last_error}"}

    def get_tools(self) -> list:
        """Return tool definitions for LLM integration"""
        return [
            {
                "name": "replicate_image_generation",
                "description": "Generate an image from a text description.",
                "server": "replicate",
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
