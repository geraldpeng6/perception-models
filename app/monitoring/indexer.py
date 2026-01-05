"""Background indexing worker for processing file events."""

import asyncio
from typing import Optional

from loguru import logger

from app.database.connection import get_db_context
from app.database.crud import FileCRUD, EmbeddingCRUD, IndexingJobCRUD
from app.core.embedding_generator import EmbeddingGenerator
from app.core.file_processor import FileProcessor, ModalityDetector
from app.database.models import File


class IndexingWorker:
    """
    Background worker that processes file events from the queue.

    Runs as an asyncio task, processes events concurrently.
    """

    def __init__(
        self,
        event_queue: asyncio.Queue,
        embedding_generator: EmbeddingGenerator,
        max_concurrent_jobs: int = 5,
    ):
        """
        Initialize indexing worker.

        Args:
            event_queue: Queue of file events to process
            embedding_generator: Embedding generator for indexing
            max_concurrent_jobs: Maximum concurrent indexing jobs
        """
        self.event_queue = event_queue
        self.embedding_generator = embedding_generator
        self.max_concurrent_jobs = max_concurrent_jobs
        self.semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start processing events from queue."""
        if self._running:
            return

        self._running = True
        logger.info("Starting indexing worker...")

        self._task = asyncio.create_task(self._process_loop())

    async def stop(self) -> None:
        """Stop processing events."""
        if not self._running:
            return

        logger.info("Stopping indexing worker...")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Indexing worker stopped")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            event = await self.event_queue.get()

            # Process event concurrently with limit
            asyncio.create_task(self._process_event(event))

    async def _process_event(self, event: dict) -> None:
        """
        Process a single file event.

        Args:
            event: Event dict with 'action', 'folder_id', 'path'
        """
        async with self.semaphore:
            action = event["action"]
            path = event["path"]

            try:
                if action in ("create", "modify"):
                    await self._index_file(path)
                elif action == "delete":
                    await self._mark_file_deleted(path)

            except Exception as e:
                logger.error(f"Error processing event {action} for {path}: {e}")

    async def _index_file(self, path: str) -> None:
        """
        Generate embedding and store in database.

        Args:
            path: File path
        """
        # Validate file
        is_valid, error_msg = FileProcessor.validate_file(path)
        if not is_valid:
            logger.warning(f"Skipping file validation: {path} - {error_msg}")
            return

        # Get file info
        file_info = FileProcessor.get_file_info(path)
        modality = file_info["modality"]

        async with get_db_context() as db:
            # Check if file already exists
            existing_file = await FileCRUD.get_by_path(db, path)

            if existing_file is None:
                # Look up folder_id from path
                # For MVP, we'll skip creating new files without folder context
                logger.debug(f"File not in database, skipping: {path}")
                return

            # Generate embedding
            embedding = await self.embedding_generator.generate_embedding_for_file(
                path, modality
            )

            if embedding is None:
                logger.warning(f"Failed to generate embedding for: {path}")
                return

            # Update or create embedding
            existing_embeddings = await EmbeddingCRUD.get_by_file(db, existing_file.id)

            if existing_embeddings:
                # Update existing
                for emb in existing_embeddings:
                    emb.vector = embedding.SerializeToString()
                await FileCRUD.update_indexed_at(db, existing_file.id)
            else:
                # Create new
                await EmbeddingCRUD.create(
                    db,
                    file_id=existing_file.id,
                    vector=embedding,
                    modality=modality,
                    embedding_type=f"{modality}_embeds",
                )

            logger.debug(f"Indexed file: {path}")

    async def _mark_file_deleted(self, path: str) -> None:
        """
        Mark file as deleted in database.

        Args:
            path: File path
        """
        async with get_db_context() as db:
            success = await FileCRUD.mark_deleted(db, path)
            if success:
                logger.info(f"Marked file as deleted: {path}")
            else:
                logger.debug(f"File not in database, skipping delete: {path}")

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
