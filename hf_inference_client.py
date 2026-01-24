"""HuggingFace Inference API Client - Using official library"""

import os
import logging
from typing import Dict, Any, Optional
import base64
from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)


class HFInferenceClient:
    """Client for HuggingFace Inference API - wrapper around official InferenceClient"""

    # Popular free models for different tasks
    DEFAULT_MODELS = {
        "text_generation": "mistralai/Mistral-7B-Instruct-v0.3",
        "image_generation": "stabilityai/stable-diffusion-xl-base-1.0",  # default to Stable Diffusion XL
        "text_to_speech": "facebook/mms-tts-eng",
        "speech_to_text": "openai/whisper-large-v3",
    }

    # Ordered fallback list for image generation (best to fallback)
    FALLBACK_MODELS = [
        "stabilityai/stable-diffusion-xl-base-1.0",
        "black-forest-labs/FLUX.1-schnell",
    ]

    def __init__(self):
        self.token = os.getenv("HF_TOKEN")
        self.client: Optional[InferenceClient] = None

    async def start(self):
        """Initialize the client"""
        if not self.token:
            logger.warning("HF_TOKEN not found - inference may be limited")

        # Initialize official client (handles URLs automatically)
        self.client = InferenceClient(token=self.token)
        logger.info("HFInferenceClient initialized (via huggingface_hub)")

    async def stop(self):
        """No explicit close needed for sync wrapper, but defined for interface"""
        self.client = None
        logger.info("HFInferenceClient closed")

    # ============ TEXT GENERATION ============
    async def text_generation(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_new_tokens: int = 500,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Generate text using a language model"""
        if not self.client:
            await self.start()

        model = model or self.DEFAULT_MODELS["text_generation"]

        try:
            # Using async support via run_async if available, else standard call
            # The library supports async validation? No, InferenceClient is sync by default unless AsyncInferenceClient used.
            from huggingface_hub import AsyncInferenceClient

            # Use the new router base URL for text models to prevent 404s
            async_client = AsyncInferenceClient(
                token=self.token, base_url="https://router.huggingface.co/v1"
            )

            result = await async_client.text_generation(
                prompt,
                model=model,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                return_full_text=False,
            )
            return {
                "generated_text": result,
                "model": model,
            }
        except Exception as e:
            logger.error(f"HF Inference error: {str(e)}")
            return {"error": str(e)}

    # ============ IMAGE GENERATION ============
    async def image_generation(
        self,
        prompt: str,
        model: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate an image using direct HTTP API (bypassing SDK issues)"""
        if not self.token:
            logger.warning("HF_TOKEN missing for image generation")

        # Sanitize/Map model name
        default_model = self.DEFAULT_MODELS["image_generation"]

        if model:
            model_lower = model.lower().strip()
            if "flux" in model_lower:
                model = "black-forest-labs/FLUX.1-schnell"
            elif "stable diffusion" in model_lower or "sd" in model_lower:
                model = "stabilityai/stable-diffusion-xl-base-1.0"
        else:
            model = default_model

        # Build fallback list: start with requested model (if any), then fall back through FALLBACK_MODELS
        if model:
            # Ensure the requested model is first, then add the rest of the fallback list without duplication
            models_to_try = [model] + [m for m in self.FALLBACK_MODELS if m != model]
        else:
            # No specific model requested – try the fallback list in order
            models_to_try = list(self.FALLBACK_MODELS)

        # Deduplicate
        unique_models = []
        seen = set()
        for m in models_to_try:
            if m and m not in seen:
                unique_models.append(m)
                seen.add(m)

        import httpx
        import base64

        last_error = "Unknown error"

        headers = {"Authorization": f"Bearer {self.token}"}

        for try_model in unique_models:
            try:
                logger.info(f"Trying image generation (HTTP) with model: {try_model}")
                # Updated: HuggingFace deprecated api-inference, now use router.huggingface.co
                api_url = f"https://api-inference.huggingface.co/models/{try_model}"

                payload: Dict[str, Any] = {"inputs": prompt}
                if negative_prompt:
                    payload["parameters"] = {"negative_prompt": negative_prompt}

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        api_url, headers=headers, json=payload, timeout=60.0
                    )

                    if response.status_code != 200:
                        error_detail = response.text
                        logger.warning(
                            f"Model {try_model} failed with status {response.status_code}: {error_detail}"
                        )
                        last_error = (
                            f"Status {response.status_code}: {error_detail[:200]}"
                        )
                        continue

                    # Success - Content should be image bytes
                    image_bytes = response.content
                    img_b64 = base64.b64encode(image_bytes).decode("utf-8")

                    logger.info(f"Image generated successfully with model: {try_model}")
                    return {
                        "image_base64": img_b64,
                        "format": "png",
                        "model": try_model,
                        "prompt": prompt,
                    }

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Model {try_model} failed: {last_error}")
                continue

        return {
            "error": f"Image generation failed after trying all models. Last error: {last_error}"
        }

    # ============ TEXT TO SPEECH ============
    async def text_to_speech(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert text to speech audio"""
        if not self.client:
            await self.start()

        model = model or self.DEFAULT_MODELS["text_to_speech"]

        try:
            from huggingface_hub import AsyncInferenceClient

            async_client = AsyncInferenceClient(token=self.token)

            # Returns bytes
            audio_bytes = await async_client.text_to_speech(text, model=model)

            return {
                "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
                "format": "wav",
                "model": model,
            }
        except Exception as e:
            logger.error(f"HF Inference error: {str(e)}")
            return {"error": str(e)}

    # ============ GET AVAILABLE TOOLS ============
    def get_tools(self) -> list:
        """Return tool definitions for LLM integration"""
        return [
            {
                "name": "hf_text_generation",
                "description": "Generate text using a HuggingFace language model like Mistral or Llama. Use for writing, coding, answering questions.",
                "server": "hf-inference",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "The text prompt"},
                        "model": {
                            "type": "string",
                            "description": "Optional: specific model ID",
                        },
                        "max_new_tokens": {
                            "type": "integer",
                            "description": "Max tokens to generate",
                            "default": 500,
                        },
                    },
                    "required": ["prompt"],
                },
            },
            {
                "name": "hf_image_generation",
                "description": "Generate a beautiful image from a text description.",
                "server": "hf-inference",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Description of the image to generate",
                        }
                    },
                    "required": ["prompt"],
                },
            },
            {
                "name": "hf_text_to_speech",
                "description": "Convert text to spoken audio.",
                "server": "hf-inference",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to convert to speech",
                        },
                    },
                    "required": ["text"],
                },
            },
        ]
