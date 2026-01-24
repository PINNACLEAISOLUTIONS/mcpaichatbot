"""Gemini 2.0 Flash Image Generation Client - FREE tier only, no paid fallbacks"""

import os
import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta

from google import genai  # type: ignore
from google.genai import types  # type: ignore

logger = logging.getLogger(__name__)


class GeminiImageClient:
    """
    Image generation using Gemini 2.0 Flash (FREE tier).

    Features:
    - Server-side queue (one image at a time)
    - Rate limiting per user
    - Retries with exponential backoff for 429/503 errors
    - 24-hour caching based on prompt+aspect_ratio hash
    - No fallback to paid providers
    """

    PRIMARY_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-fast-generate-001")
    SECONDARY_MODEL = "imagen-3.0-generate-001"

    def __init__(
        self, api_key: Optional[str] = None, static_dir: str = "static/generated"
    ):
        raw_key = api_key or os.getenv("GEMINI_API_KEY")
        self.api_key = raw_key.strip() if raw_key else None
        self.static_dir = Path(static_dir)
        self.static_dir.mkdir(parents=True, exist_ok=True)

        # Queue for sequential processing
        self._queue_lock = asyncio.Lock()

        # Rate limiting: max requests per user per hour
        self._user_requests: Dict[str, list] = defaultdict(list)
        self._rate_limit_per_hour = 15  # Conservative for free tier

        # Cache: hash -> (filepath, timestamp)
        self._cache: Dict[str, tuple] = {}
        self._cache_duration = timedelta(hours=24)

        # Configure the SDK
        self.client: Optional[genai.Client] = None
        self.enabled = False

        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self.enabled = True
                logger.info(
                    f"GeminiImageClient initialized (Primary: {self.PRIMARY_MODEL})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.enabled = False
        else:
            logger.warning(
                "GeminiImageClient: No GEMINI_API_KEY found - image generation disabled"
            )

    async def start(self):
        """Initialize the client"""
        logger.info(f"GeminiImageClient started (enabled: {self.enabled})")

    async def stop(self):
        """Cleanup"""
        logger.info("GeminiImageClient stopped")

    def _get_cache_key(self, prompt: str, aspect_ratio: str) -> str:
        """Generate a cache key from prompt and aspect ratio"""
        content = f"{prompt}|{aspect_ratio}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _check_cache(self, cache_key: str) -> Optional[str]:
        """Check if a cached image exists and is still valid"""
        if cache_key not in self._cache:
            return None

        filepath, timestamp = self._cache[cache_key]

        # Check if cache has expired
        if datetime.now() - timestamp > self._cache_duration:
            del self._cache[cache_key]
            return None

        # Check if file still exists
        if not Path(filepath).exists():
            del self._cache[cache_key]
            return None

        return filepath

    def _add_to_cache(self, cache_key: str, filepath: str):
        """Add an image to the cache"""
        self._cache[cache_key] = (filepath, datetime.now())

    def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user has exceeded rate limit. Returns True if allowed."""
        now = time.time()
        hour_ago = now - 3600

        # Clean old entries
        self._user_requests[user_id] = [
            t for t in self._user_requests[user_id] if t > hour_ago
        ]

        # Check if under limit (allow UP TO the limit, not just up to limit-1)
        if len(self._user_requests[user_id]) > self._rate_limit_per_hour:
            return False

        # Record this request
        self._user_requests[user_id].append(now)
        return True

    async def _generate_with_retry(
        self, prompt: str, max_retries: int = 3
    ) -> Dict[str, Any]:
        """Generate image with exponential backoff for temporary errors"""

        if not self.client:
            return {
                "success": False,
                "error": "Gemini client not initialized",
                "retry": False,
            }

        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"🎨 Gemini: Attempt {attempt + 1}/{max_retries} for prompt: '{prompt[:50]}...'"
                )

                # Try Primary Model first
                try:
                    response = await asyncio.to_thread(
                        self.client.models.generate_images,
                        model=self.PRIMARY_MODEL,
                        prompt=prompt,
                        config=types.GenerateImagesConfig(
                            number_of_images=1,
                            include_rai_reason=True,
                        ),
                    )
                except Exception as primary_err:
                    logger.warning(f"Primary Gemini model failed: {primary_err}")
                    # Try Secondary Model
                    logger.info(
                        f"🔄 Falling back to secondary model: {self.SECONDARY_MODEL}"
                    )
                    response = await asyncio.to_thread(
                        self.client.models.generate_images,
                        model=self.SECONDARY_MODEL,
                        prompt=prompt,
                        config=types.GenerateImagesConfig(
                            number_of_images=1,
                            include_rai_reason=True,
                        ),
                    )

                # Extract image from generate_image response
                if response and response.generated_images:
                    image_obj = response.generated_images[0]
                    if image_obj.image:
                        image_data = image_obj.image.image_bytes
                        mime_type = image_obj.image.mime_type or "image/png"

                        if image_data:
                            logger.info(
                                f"✅ Gemini: Image generated successfully ({len(image_data)} bytes)"
                            )
                            return {
                                "success": True,
                                "image_bytes": image_data,
                                "mime_type": mime_type,
                            }

                # Handling case with no images (e.g., safety filters)
                error_msg = "Gemini did not return an image."
                # GenerateImagesResponse might have RAI reasons or safety info
                if response and hasattr(response, "rai_media_filter_responses"):
                    error_msg += " (Possible safety filter trigger)"

                return {
                    "success": False,
                    "error": error_msg,
                    "retry": False,
                }

            except Exception as e:
                error_str = str(e)
                last_error = error_str

                is_rate_limit = (
                    "429" in error_str
                    or "quota" in error_str.lower()
                    or "resource_exhausted" in error_str.lower()
                )
                is_modality_error = (
                    "modality" in error_str.lower() or "modalities" in error_str.lower()
                )
                is_temporary = (
                    "503" in error_str
                    or "500" in error_str
                    or "timeout" in error_str.lower()
                )

                if is_rate_limit or is_modality_error:
                    logger.warning(f"Gemini immediate fallback required: {error_str}")
                    return {
                        "success": False,
                        "error": "FORCE_FALLBACK",
                        "error_detail": error_str,
                        "retry": False,
                    }

                if is_temporary and attempt < max_retries - 1:
                    # Exponential backoff: 2, 4, 8 seconds
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(
                        f"Gemini temporary error, retrying in {wait_time}s: {error_str}"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                logger.error(f"Gemini error (attempt {attempt + 1}): {error_str}")

        return {
            "success": False,
            "error": f"Image generation failed after {max_retries} attempts. Last error: {last_error}",
            "retry": True,
        }

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        size: Optional[str] = None,
        user_id: str = "anonymous",
    ) -> Dict[str, Any]:
        """
        Generate an image using Gemini 2.0 Flash.

        Args:
            prompt: Text description of the image
            aspect_ratio: Aspect ratio (e.g., "1:1", "16:9", "9:16")
            size: Optional size hint
            user_id: User identifier for rate limiting

        Returns:
            Dict with either:
            - success: True, image_url, cached (bool)
            - success: False, error message
        """

        if not self.enabled:
            return {
                "success": False,
                "error": "Image generation is disabled. GEMINI_API_KEY not configured.",
            }

        # Check rate limit
        if not self._check_rate_limit(user_id):
            return {
                "success": False,
                "error": f"You've reached the hourly rate limit of {self._rate_limit_per_hour} images. Please try again in an hour.",
            }

        # Check cache
        cache_key = self._get_cache_key(prompt, aspect_ratio)
        cached_path = self._check_cache(cache_key)

        if cached_path:
            logger.info(f"🎨 Gemini: Returning cached image for key {cache_key}")
            image_url = f"/static/generated/{Path(cached_path).name}"

            # Read bytes for base64 return
            import base64

            with open(cached_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            return {
                "success": True,
                "image_url": image_url,
                "image_base64": img_b64,
                "cached": True,
                "prompt": prompt,
                "provider": "gemini",
                "mime_type": "image/png",
            }

        # Acquire queue lock (one image at a time)
        async with self._queue_lock:
            logger.info("🎨 Gemini: Processing image request (queue acquired)")

            # Enhance prompt with aspect ratio hint
            enhanced_prompt = f"Generate an image: {prompt}"
            if aspect_ratio != "1:1":
                enhanced_prompt += f" (aspect ratio: {aspect_ratio})"

            # Generate the image
            result = await self._generate_with_retry(enhanced_prompt)

            if not result["success"]:
                return {
                    "success": False,
                    "error": result["error"],
                    "retry_suggested": result.get("retry", False),
                }

            # Save the image
            try:
                image_bytes = result["image_bytes"]
                mime_type = result.get("mime_type", "image/png")

                # Determine extension from mime type
                ext = "png"
                if "jpeg" in mime_type or "jpg" in mime_type:
                    ext = "jpg"
                elif "webp" in mime_type:
                    ext = "webp"

                # Generate filename
                filename = f"{cache_key}_{int(time.time())}.{ext}"
                filepath = self.static_dir / filename

                # Write the file
                with open(filepath, "wb") as f:
                    f.write(image_bytes)

                logger.info(f"✅ Gemini: Image saved to {filepath}")

                # Add to cache
                self._add_to_cache(cache_key, str(filepath))

                # Generate URL
                image_url = f"/static/generated/{filename}"

                import base64

                img_b64 = base64.b64encode(image_bytes).decode("utf-8")

                return {
                    "success": True,
                    "image_url": image_url,
                    "image_base64": img_b64,
                    "cached": False,
                    "prompt": prompt,
                    "provider": "gemini",
                    "mime_type": mime_type,
                }

            except Exception as e:
                logger.error(f"Failed to save image: {e}")
                return {
                    "success": False,
                    "error": f"Failed to save generated image: {e}",
                }

    def get_health_status(self) -> Dict[str, Any]:
        """Return health status for the /health endpoint"""
        return {
            "image_generation_enabled": self.enabled,
            "model": self.PRIMARY_MODEL if self.enabled else None,
            "cache_size": len(self._cache),
            "rate_limit_per_hour": self._rate_limit_per_hour,
        }

    def get_tools(self) -> list:
        """Return tool definitions for LLM integration"""
        return [
            {
                "name": "generate_image",
                "description": "Generate an image from a text description using Gemini 2.0 Flash (FREE).",
                "server": "gemini",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Detailed description of the image to generate",
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "description": "Aspect ratio (e.g., '1:1', '16:9', '9:16')",
                            "default": "1:1",
                        },
                        "size": {
                            "type": "string",
                            "description": "Optional size hint (e.g., 'small', 'medium', 'large')",
                        },
                    },
                    "required": ["prompt"],
                },
            },
        ]
