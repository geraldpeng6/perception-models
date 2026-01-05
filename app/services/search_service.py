"""Search service - orchestrates search operations."""

import time
from typing import Optional, Union, List

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.similarity_calculator import SimilarityCalculator
from app.core.embedding_generator import EmbeddingGenerator
from app.database.crud import EmbeddingCRUD, FileCRUD
from app.database.schemas import SearchRequest, SearchResponse, SearchResult, FileMetadata
from app.services.deletion_tracker import DeletionTracker


class SearchService:
    """
    High-level search orchestration.

    Coordinates embedding generation and similarity search.
    """

    def __init__(
        self,
        similarity_calculator: SimilarityCalculator,
        embedding_generator: EmbeddingGenerator,
        deletion_tracker: Optional[DeletionTracker] = None,
    ):
        self.similarity_calculator = similarity_calculator
        self.embedding_generator = embedding_generator
        self.deletion_tracker = deletion_tracker

    async def search(
        self,
        db: AsyncSession,
        request: SearchRequest,
    ) -> SearchResponse:
        """
        Execute search query.

        Args:
            db: Database session
            request: Search request

        Returns:
            Search response with results
        """
        start_time = time.time()

        # Determine target modalities
        target_modalities = request.modalities or ["audio", "video", "audio_video"]

        # Generate query embedding(s)
        query_embeddings = await self.similarity_calculator.compute_query_embedding(
            query=request.query,
            query_type=request.query_type,
            target_modalities=target_modalities,
        )

        if not query_embeddings:
            logger.warning("No query embeddings generated")
            return SearchResponse(
                results=[],
                total=0,
                query_time_ms=(time.time() - start_time) * 1000,
            )

        # Perform search for each modality
        all_results = []

        for modality, query_emb in query_embeddings.items():
            results = await EmbeddingCRUD.search_similar(
                db,
                query_vector=query_emb,
                modality=modality,
                folder_ids=request.folder_ids,
                top_k=request.top_k,
                threshold=request.threshold,
                exclude_deleted=True,
            )

            for file, similarity in results:
                all_results.append((file, similarity, modality))

        # Sort by similarity and limit
        all_results.sort(key=lambda x: x[1], reverse=True)
        all_results = all_results[: request.top_k]

        # Build response
        search_results = []
        warnings = []

        for file, similarity, modality in all_results:
            # Check for deleted file warning
            if self.deletion_tracker and file.is_deleted:
                warning = await self.deletion_tracker.notify_if_deleted(db, file.id)
                if warning:
                    warnings.append(warning)

            search_results.append(
                SearchResult(
                    file_id=file.id,
                    path=file.path,
                    filename=file.filename,
                    modality=file.modality,
                    similarity=similarity,
                    metadata=FileMetadata(
                        id=file.id,
                        path=file.path,
                        filename=file.filename,
                        modality=file.modality,
                        file_size=file.file_size,
                        mime_type=file.mime_type,
                        duration_seconds=file.duration_seconds,
                        is_deleted=file.is_deleted,
                        indexed_at=file.indexed_at,
                    ),
                    is_deleted=file.is_deleted,
                )
            )

        query_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Search completed: {len(search_results)} results in {query_time_ms:.2f}ms"
        )

        return SearchResponse(
            results=search_results,
            total=len(search_results),
            query_time_ms=query_time_ms,
            warnings=warnings if warnings else None,
        )

    async def find_similar_files(
        self,
        db: AsyncSession,
        file_id: int,
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> SearchResponse:
        """
        Find files similar to a specific indexed file.

        Args:
            db: Database session
            file_id: ID of file to find similar files for
            top_k: Maximum number of results
            threshold: Similarity threshold

        Returns:
            Search response with similar files
        """
        start_time = time.time()

        # Get file and its embedding
        file = await FileCRUD.get(db, file_id)
        if file is None:
            return SearchResponse(
                results=[],
                total=0,
                query_time_ms=(time.time() - start_time) * 1000,
            )

        embeddings = await EmbeddingCRUD.get_by_file(db, file_id)
        if not embeddings:
            return SearchResponse(
                results=[],
                total=0,
                query_time_ms=(time.time() - start_time) * 1000,
            )

        # Use first embedding
        from app.database.crud import deserialize_array

        query_vector = deserialize_array(embeddings[0].vector)

        # Search for similar files (exclude the original file)
        results = await EmbeddingCRUD.search_similar(
            db,
            query_vector=query_vector,
            modality=file.modality,
            top_k=top_k + 1,  # +1 to account for the original file
            threshold=threshold,
            exclude_deleted=True,
        )

        # Filter out the original file and limit
        search_results = []
        for similar_file, similarity in results:
            if similar_file.id != file_id:
                search_results.append(
                    SearchResult(
                        file_id=similar_file.id,
                        path=similar_file.path,
                        filename=similar_file.filename,
                        modality=similar_file.modality,
                        similarity=similarity,
                        metadata=FileMetadata(
                            id=similar_file.id,
                            path=similar_file.path,
                            filename=similar_file.filename,
                            modality=similar_file.modality,
                            file_size=similar_file.file_size,
                            mime_type=similar_file.mime_type,
                            duration_seconds=similar_file.duration_seconds,
                            is_deleted=similar_file.is_deleted,
                            indexed_at=similar_file.indexed_at,
                        ),
                        is_deleted=similar_file.is_deleted,
                    )
                )

            if len(search_results) >= top_k:
                break

        query_time_ms = (time.time() - start_time) * 1000

        return SearchResponse(
            results=search_results[:top_k],
            total=len(search_results[:top_k]),
            query_time_ms=query_time_ms,
        )
