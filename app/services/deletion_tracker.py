"""Deletion tracker - manages deleted file notifications."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.crud import FileCRUD


class DeletionTracker:
    """
    Tracks deleted files and manages user notifications.
    """

    async def mark_file_deleted(self, db: AsyncSession, file_path: str) -> bool:
        """
        Mark file as deleted in database.

        Args:
            db: Database session
            file_path: Path to file

        Returns:
            True if file was found and marked
        """
        success = await FileCRUD.mark_deleted(db, file_path)
        if success:
            logger.info(f"Marked file as deleted: {file_path}")
        return success

    async def check_file_exists(self, db: AsyncSession, file_path: str) -> bool:
        """
        Check if file still exists on disk.

        Args:
            db: Database session
            file_path: Path to file

        Returns:
            True if file exists
        """
        from pathlib import Path

        return Path(file_path).exists()

    async def notify_if_deleted(
        self, db: AsyncSession, file_id: int
    ) -> Optional[str]:
        """
        Check if file is deleted and return warning message.

        Marks as notified to avoid repeated warnings.

        Args:
            db: Database session
            file_id: File ID

        Returns:
            Warning message or None
        """
        file = await FileCRUD.get(db, file_id)

        if file is None:
            return None

        if file.is_deleted and not file.deletion_notified:
            # Mark as notified
            await FileCRUD.mark_deletion_notified(db, file_id)

            return (
                f"Warning: Matching file '{file.filename}' has been deleted from source. "
                f"The file was originally located at: {file.path}"
            )

        return None

    async def scan_for_deleted_files(self, db: AsyncSession, folder_id: int) -> int:
        """
        Scan folder for deleted files and update database.

        Args:
            db: Database session
            folder_id: Folder ID to scan

        Returns:
            Number of files marked as deleted
        """
        from app.database.crud import FolderCRUD
        from pathlib import Path

        folder = await FolderCRUD.get(db, folder_id)
        if folder is None:
            return 0

        files = await FileCRUD.list_by_folder(db, folder_id, include_deleted=False)
        deleted_count = 0

        for file in files:
            if not Path(file.path).exists():
                await self.mark_file_deleted(db, file.path)
                deleted_count += 1

        if deleted_count > 0:
            logger.info(f"Marked {deleted_count} files as deleted in folder {folder_id}")

        return deleted_count
