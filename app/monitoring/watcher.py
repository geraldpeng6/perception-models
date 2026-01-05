"""File system watcher using Watchdog."""

import asyncio
from typing import Optional

from watchdog.observers import Observer
from loguru import logger

from app.database.connection import get_db_context
from app.database.crud import FolderCRUD
from app.monitoring.event_handler import MultimodalEventHandler


class FileWatcher:
    """
    Manages Watchdog observers for file system monitoring.

    Runs in a background thread with async queue for event processing.
    """

    def __init__(self, event_loop: Optional[asyncio.AbstractEventLoop] = None):
        self.observers: list[Observer] = []
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.event_loop = event_loop or asyncio.get_event_loop()
        self._running = False

    async def start(self) -> None:
        """Start monitoring all active folders from database."""
        if self._running:
            return

        self._running = True
        logger.info("Starting file watcher...")

        async with get_db_context() as db:
            folders = await FolderCRUD.list_all(db, active_only=True)

            for folder in folders:
                await self.add_folder(folder.path, folder.id, db)

        logger.info(f"File watcher started, monitoring {len(self.observers)} folder(s)")

    async def stop(self) -> None:
        """Stop all observers gracefully."""
        if not self._running:
            return

        logger.info("Stopping file watcher...")
        self._running = False

        for observer in self.observers:
            observer.stop()
            observer.join()

        self.observers.clear()
        logger.info("File watcher stopped")

    async def add_folder(
        self, folder_path: str, folder_id: int, db
    ) -> bool:
        """
        Add a new folder to monitoring.

        Args:
            folder_path: Path to folder
            folder_id: Database folder ID
            db: Database session

        Returns:
            True if folder was added successfully
        """
        from pathlib import Path

        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            logger.warning(f"Folder not found: {folder_path}")
            return False

        # Create event handler
        event_handler = MultimodalEventHandler(
            folder_id=folder_id,
            queue=self.event_queue,
            loop=self.event_loop,
        )

        # Create and start observer
        observer = Observer()
        observer.schedule(event_handler, str(path), recursive=True)
        observer.start()

        self.observers.append(observer)
        logger.info(f"Added folder to monitoring: {folder_path}")

        return True

    async def remove_folder(self, folder_path: str) -> bool:
        """
        Remove a folder from monitoring.

        Args:
            folder_path: Path to folder

        Returns:
            True if folder was removed
        """
        from pathlib import Path

        target_path = str(Path(folder_path).absolute())

        # Find and remove observer for this path
        for i, observer in enumerate(self.observers):
            # Check if any watch path matches
            for watch in observer.emitters:
                if watch.watch.path == target_path:
                    observer.stop()
                    observer.join()
                    self.observers.pop(i)
                    logger.info(f"Removed folder from monitoring: {folder_path}")
                    return True

        return False

    async def get_next_event(self, timeout: float = 1.0) -> Optional[dict]:
        """
        Get next event from queue.

        Args:
            timeout: Queue timeout in seconds

        Returns:
            Event dict or None if timeout
        """
        try:
            return await asyncio.wait_for(self.event_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running
