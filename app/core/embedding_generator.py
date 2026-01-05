"""Embedding generation for all modalities."""

import asyncio
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from loguru import logger

from app.core.model_loader import ModelLoader


class EmbeddingGenerator:
    """Generate embeddings for text, audio, and video inputs."""

    def __init__(self, model_loader: ModelLoader):
        self.model_loader = model_loader

    async def generate_text_embedding(
        self,
        text: str,
        target_modality: str = "audio_video",
    ) -> np.ndarray:
        """
        Generate text embedding aligned to target modality.

        Args:
            text: Input text
            target_modality: Target modality for alignment ('audio', 'video', 'audio_video')

        Returns:
            Embedding vector of shape (1792,)
        """
        model, processor = await self.model_loader.load()
        device = self.model_loader.device

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        def process():
            inputs = processor(text=text, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = model(**inputs)

            # Select appropriate text embedding based on target modality
            # Use the correct attribute names from PE-AV model outputs
            if target_modality == "audio":
                embedding = outputs.text_audio_embeds
            elif target_modality == "video":
                embedding = outputs.text_video_embeds
            else:  # audio_video
                embedding = outputs.audio_video_text_embeds

            # Check if embedding is None (model may not support this combination)
            if embedding is None:
                logger.warning(f"Text embedding for modality '{target_modality}' returned None")
                return None

            # Get first item from batch
            embedding = embedding[0].cpu().numpy()
            return embedding

        return await loop.run_in_executor(None, process)

    async def generate_audio_embedding(
        self, audio_path: str
    ) -> Optional[np.ndarray]:
        """
        Generate audio embedding.

        Args:
            audio_path: Path to audio file

        Returns:
            Embedding vector of shape (1792,) or None if failed
        """
        if not Path(audio_path).exists():
            logger.warning(f"Audio file not found: {audio_path}")
            return None

        model, processor = await self.model_loader.load()
        device = self.model_loader.device

        loop = asyncio.get_event_loop()

        def process():
            try:
                inputs = processor(audio=audio_path, return_tensors="pt")
                inputs = {k: v.to(device) for k, v in inputs.items()}

                with torch.no_grad():
                    outputs = model(**inputs)

                embedding = outputs.audio_embeds[0].cpu().numpy()
                return embedding
            except Exception as e:
                logger.error(f"Failed to process audio {audio_path}: {e}")
                return None

        return await loop.run_in_executor(None, process)

    async def generate_video_embedding(
        self, video_path: str
    ) -> Optional[np.ndarray]:
        """
        Generate video embedding.

        Args:
            video_path: Path to video file

        Returns:
            Embedding vector of shape (1792,) or None if failed
        """
        if not Path(video_path).exists():
            logger.warning(f"Video file not found: {video_path}")
            return None

        model, processor = await self.model_loader.load()
        device = self.model_loader.device

        loop = asyncio.get_event_loop()

        def process():
            try:
                inputs = processor(videos=video_path, return_tensors="pt")
                inputs = {k: v.to(device) for k, v in inputs.items()}

                with torch.no_grad():
                    outputs = model(**inputs)

                embedding = outputs.video_embeds[0].cpu().numpy()
                return embedding
            except Exception as e:
                logger.error(f"Failed to process video {video_path}: {e}")
                return None

        return await loop.run_in_executor(None, process)

    async def generate_audio_video_embedding(
        self, audio_path: str, video_path: str
    ) -> Optional[np.ndarray]:
        """
        Generate combined audio-video embedding.

        Args:
            audio_path: Path to audio file
            video_path: Path to video file

        Returns:
            Embedding vector of shape (1792,) or None if failed
        """
        model, processor = await self.model_loader.load()
        device = self.model_loader.device

        loop = asyncio.get_event_loop()

        def process():
            try:
                inputs = processor(
                    audio=audio_path, videos=video_path, return_tensors="pt"
                )
                inputs = {k: v.to(device) for k, v in inputs.items()}

                with torch.no_grad():
                    outputs = model(**inputs)

                embedding = outputs.audio_video_embeds[0].cpu().numpy()
                return embedding
            except Exception as e:
                logger.error(f"Failed to process audio-video: {e}")
                return None

        return await loop.run_in_executor(None, process)

    async def generate_embedding_for_file(
        self, file_path: str, modality: str
    ) -> Optional[np.ndarray]:
        """
        Generate embedding for a file based on its modality.

        Args:
            file_path: Path to file
            modality: File modality ('audio', 'video', 'audio_video')

        Returns:
            Embedding vector or None if failed
        """
        if modality == "audio":
            return await self.generate_audio_embedding(file_path)
        elif modality == "video":
            return await self.generate_video_embedding(file_path)
        elif modality == "audio_video":
            # For audio_video, we need both audio and video from same file
            # The model handles this internally
            return await self.generate_video_embedding(
                file_path
            )  # video includes audio
        else:
            logger.error(f"Unknown modality: {modality}")
            return None
