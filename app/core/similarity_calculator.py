"""Similarity calculation using dot product."""

from typing import Dict, List, Union

import numpy as np

from app.core.embedding_generator import EmbeddingGenerator


class SimilarityCalculator:
    """Computes similarity between query embedding and database embeddings."""

    def __init__(self, embedding_generator: EmbeddingGenerator):
        self.embedding_generator = embedding_generator

    async def compute_query_embedding(
        self,
        query: Union[str, bytes],
        query_type: str,
        target_modalities: List[str],
    ) -> Dict[str, np.ndarray]:
        """
        Generate query embeddings for each target modality.

        Args:
            query: Query text or file data
            query_type: Type of query ('text', 'audio', 'video')
            target_modalities: List of modalities to search

        Returns:
            Dict mapping modality to query embedding
        """
        embeddings = {}

        if query_type == "text":
            # For text queries, generate embeddings for each target modality
            # using the appropriate text embedding type
            for modality in target_modalities:
                # Map target modality to text embedding type
                if modality == "audio":
                    emb = await self.embedding_generator.generate_text_embedding(
                        query, target_modality="audio"
                    )
                elif modality == "video":
                    emb = await self.embedding_generator.generate_text_embedding(
                        query, target_modality="video"
                    )
                else:  # audio_video
                    emb = await self.embedding_generator.generate_text_embedding(
                        query, target_modality="audio_video"
                    )
                # Only add if embedding was successfully generated
                if emb is not None:
                    embeddings[modality] = emb

        elif query_type == "audio":
            # Audio query can search against audio or audio-video
            embedding = await self.embedding_generator.generate_audio_embedding(query)
            if embedding is not None:
                for modality in target_modalities:
                    if modality in ("audio", "audio_video"):
                        embeddings[modality] = embedding

        elif query_type == "video":
            # Video query can search against video or audio-video
            embedding = await self.embedding_generator.generate_video_embedding(query)
            if embedding is not None:
                for modality in target_modalities:
                    if modality in ("video", "audio_video"):
                        embeddings[modality] = embedding

        return embeddings

    def compute_similarity(
        self, query_embedding: np.ndarray, database_embedding: np.ndarray
    ) -> float:
        """
        Compute dot product similarity.

        Args:
            query_embedding: Query embedding vector
            database_embedding: Database embedding vector

        Returns:
            Similarity score (higher = more similar)
        """
        return float(np.dot(query_embedding, database_embedding))

    def compute_similarities(
        self, query_embedding: np.ndarray, database_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute similarities between query and multiple database embeddings.

        Args:
            query_embedding: Query embedding vector (1792,)
            database_embeddings: Database embeddings (N, 1792)

        Returns:
            Similarity scores array (N,)
        """
        return np.dot(database_embeddings, query_embedding)

    def rank_results(
        self,
        similarities: np.ndarray,
        threshold: float = 0.0,
        top_k: int = 10,
    ) -> np.ndarray:
        """
        Rank results by similarity and apply threshold/top_k.

        Args:
            similarities: Array of similarity scores
            threshold: Minimum similarity threshold
            top_k: Maximum number of results

        Returns:
            Indices of top-k results above threshold, sorted by similarity
        """
        # Filter by threshold
        above_threshold = np.where(similarities >= threshold)[0]

        # Sort by similarity descending
        sorted_indices = above_threshold[
            np.argsort(similarities[above_threshold])[::-1]
        ]

        # Limit to top_k
        return sorted_indices[:top_k]
