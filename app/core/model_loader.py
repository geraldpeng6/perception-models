"""PE-AV-Large model loading and management."""

import asyncio
import os
from typing import Optional

import torch
from transformers import PeAudioVideoModel, PeAudioVideoProcessor
from loguru import logger

from app.config import settings


class ModelLoader:
    """Manages loading and caching of PE-AV-Large model."""

    def __init__(self):
        self._model: Optional[PeAudioVideoModel] = None
        self._processor: Optional[PeAudioVideoProcessor] = None
        self._loading_lock = asyncio.Lock()
        self._device = torch.device(settings.device)

    async def load(self) -> tuple[PeAudioVideoModel, PeAudioVideoProcessor]:
        """
        Load model and processor (lazy loading with caching).

        Returns:
            Tuple of (model, processor)
        """
        if self._model is not None and self._processor is not None:
            return self._model, self._processor

        async with self._loading_lock:
            # Check again in case another coroutine loaded it
            if self._model is not None and self._processor is not None:
                return self._model, self._processor

            logger.info(f"Loading PE-AV-Large model from {settings.model_name}...")

            # Run loading in thread pool to avoid blocking
            model, processor = await self._load_model_sync()

            self._model = model
            self._processor = processor

            logger.info("Model loaded successfully")
            return self._model, self._processor

    async def _load_model_sync(
        self,
    ) -> tuple[PeAudioVideoModel, PeAudioVideoProcessor]:
        """Load model synchronously in thread pool."""
        loop = asyncio.get_event_loop()

        def load():
            # Set Hugging Face mirror endpoint if configured
            if settings.hf_endpoint:
                os.environ["HF_ENDPOINT"] = settings.hf_endpoint
                logger.info(f"Using Hugging Face mirror: {settings.hf_endpoint}")
            
            processor = PeAudioVideoProcessor.from_pretrained(settings.model_name)
            model = PeAudioVideoModel.from_pretrained(
                settings.model_name,
                torch_dtype=torch.float32,
            )
            model = model.to(self._device)
            model.eval()  # Set to evaluation mode
            return model, processor

        return await loop.run_in_executor(None, load)

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None and self._processor is not None

    @property
    def device(self) -> torch.device:
        """Get the device the model is on."""
        return self._device


# Global singleton instance
_model_loader: Optional[ModelLoader] = None


def get_model_loader() -> ModelLoader:
    """Get global model loader instance."""
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader
