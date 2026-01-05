"""File system event handler for Watchdog."""

import asyncio
import time
from watchdog.events import FileSystemEventHandler
from loguru import logger

from app.core.file_processor import ModalityDetector


class MultimodalEventHandler(FileSystemEventHandler):
    """
    Handles file system events and queues them for indexing.

    Runs in Watchdog's observer thread, uses asyncio for queue communication.
    """

    def __init__(
        self,
        folder_id: int,
        queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
        cooldown_seconds: float = 2.0,
    ):
        """
        Initialize event handler.

        Args:
            folder_id: Database folder ID
            queue: Async queue for events
            loop: Event loop for async operations
            cooldown_seconds: Cooldown to prevent duplicate events
        """
        self.folder_id = folder_id
        self.queue = queue
        self.loop = loop
        self.cooldown_seconds = cooldown_seconds
        self.last_event_time: dict[str, float] = {}

    def on_created(self, event) -> None:
        """Handle new file creation."""
        if event.is_directory:
            return

        if self._should_process(event.src_path):
            self._queue_event("create", event.src_path)

    def on_modified(self, event) -> None:
        """Handle file modification."""
        if event.is_directory:
            return

        if self._should_process(event.src_path):
            self._queue_event("modify", event.src_path)

    def on_deleted(self, event) -> None:
        """Handle file deletion."""
        if event.is_directory:
            return

        # For deletion, process immediately without cooldown
        self._queue_event("delete", event.src_path)

    def on_moved(self, event) -> None:
        """Handle file move/rename."""
        if event.is_directory:
            return

        # Treat as deletion of old path and creation of new path
        if self._should_process(event.src_path):
            self._queue_event("delete", event.src_path)
        if self._should_process(event.dest_path):
            self._queue_event("create", event.dest_path)

    def _should_process(self, path: str) -> bool:
        """
        Check if event should be processed (debouncing + modality check).

        Args:
            path: File path

        Returns:
            True if event should be processed
        """
        # Check if file is supported
        if not ModalityDetector.is_supported(path):
            return False

        # Check cooldown
        now = time.time()
        last_time = self.last_event_time.get(path, 0)

        if now - last_time < self.cooldown_seconds:
            return False

        self.last_event_time[path] = now
        return True

    def _queue_event(self, action: str, path: str) -> None:
        """
        Queue an event for processing.

        Args:
            action: Event action ('create', 'modify', 'delete')
            path: File path
        """
        event_data = {
            "action": action,
            "folder_id": self.folder_id,
            "path": path,
        }

        # Use asyncio to queue without blocking
        asyncio.run_coroutine_threadsafe(
            self.queue.put(event_data), self.loop
        )

        logger.debug(f"Queued {action} event for: {path}")
