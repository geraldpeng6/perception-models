"""CRUD operations for database access."""

import io
import time
from datetime import datetime
from typing import Optional

import numpy as np
from sqlalchemy import func, select, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Folder, File, Embedding, IndexingJob


# ============ Array Serialization Utilities ============


def serialize_array(array: np.ndarray) -> bytes:
    """Serialize NumPy array to bytes for BLOB storage."""
    with io.BytesIO() as buffer:
        np.save(buffer, array)
        return buffer.getvalue()


def deserialize_array(blob: bytes) -> np.ndarray:
    """Deserialize bytes back to NumPy array."""
    with io.BytesIO(blob) as buffer:
        return np.load(buffer)


# ============ Folder CRUD ============


class FolderCRUD:
    """CRUD operations for folders."""

    @staticmethod
    async def create(
        db: AsyncSession, path: str, modality: str = "all"
    ) -> Folder:
        """Create a new folder."""
        folder = Folder(path=path, modality=modality)
        db.add(folder)
        await db.commit()
        await db.refresh(folder)
        return folder

    @staticmethod
    async def get(db: AsyncSession, folder_id: int) -> Optional[Folder]:
        """Get folder by ID."""
        result = await db.execute(select(Folder).where(Folder.id == folder_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_path(db: AsyncSession, path: str) -> Optional[Folder]:
        """Get folder by path."""
        result = await db.execute(select(Folder).where(Folder.path == path))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        db: AsyncSession, active_only: bool = False
    ) -> list[Folder]:
        """List all folders."""
        query = select(Folder)
        if active_only:
            query = query.where(Folder.is_active == True)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        folder_id: int,
        is_active: Optional[bool] = None,
        modality: Optional[str] = None,
    ) -> Optional[Folder]:
        """Update folder."""
        folder = await FolderCRUD.get(db, folder_id)
        if folder is None:
            return None

        if is_active is not None:
            folder.is_active = is_active
        if modality is not None:
            folder.modality = modality

        await db.commit()
        await db.refresh(folder)
        return folder

    @staticmethod
    async def delete(db: AsyncSession, folder_id: int) -> bool:
        """Delete folder (cascades to files)."""
        folder = await FolderCRUD.get(db, folder_id)
        if folder is None:
            return False

        await db.delete(folder)
        await db.commit()
        return True

    @staticmethod
    async def update_last_indexed(
        db: AsyncSession, folder_id: int, timestamp: datetime
    ) -> None:
        """Update last_indexed_at timestamp."""
        folder = await FolderCRUD.get(db, folder_id)
        if folder:
            folder.last_indexed_at = timestamp
            await db.commit()


# ============ File CRUD ============


class FileCRUD:
    """CRUD operations for files."""

    @staticmethod
    async def create(
        db: AsyncSession,
        folder_id: int,
        path: str,
        filename: str,
        modality: str,
        file_size: Optional[int] = None,
        mime_type: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> File:
        """Create a new file record."""
        file = File(
            folder_id=folder_id,
            path=path,
            filename=filename,
            modality=modality,
            file_size=file_size,
            mime_type=mime_type,
            duration_seconds=duration_seconds,
        )
        db.add(file)
        await db.commit()
        await db.refresh(file)
        return file

    @staticmethod
    async def get(db: AsyncSession, file_id: int) -> Optional[File]:
        """Get file by ID."""
        result = await db.execute(select(File).where(File.id == file_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_path(db: AsyncSession, path: str) -> Optional[File]:
        """Get file by path."""
        result = await db.execute(select(File).where(File.path == path))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_folder(
        db: AsyncSession, folder_id: int, include_deleted: bool = False
    ) -> list[File]:
        """List files in a folder."""
        query = select(File).where(File.folder_id == folder_id)
        if not include_deleted:
            query = query.where(File.is_deleted == False)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def mark_deleted(db: AsyncSession, path: str) -> bool:
        """Mark file as deleted (soft delete)."""
        file = await FileCRUD.get_by_path(db, path)
        if file is None:
            return False

        file.is_deleted = True
        file.deletion_notified = False
        await db.commit()
        return True

    @staticmethod
    async def mark_deletion_notified(db: AsyncSession, file_id: int) -> bool:
        """Mark that deletion has been notified to user."""
        file = await FileCRUD.get(db, file_id)
        if file is None:
            return False

        file.deletion_notified = True
        await db.commit()
        return True

    @staticmethod
    async def update_indexed_at(db: AsyncSession, file_id: int) -> None:
        """Update indexed_at timestamp."""
        file = await FileCRUD.get(db, file_id)
        if file:
            file.indexed_at = datetime.utcnow()
            await db.commit()

    @staticmethod
    async def count_by_folder(db: AsyncSession, folder_id: int) -> int:
        """Count files in a folder."""
        result = await db.execute(
            select(func.count(File.id)).where(
                and_(File.folder_id == folder_id, File.is_deleted == False)
            )
        )
        return result.scalar() or 0


# ============ Embedding CRUD ============


class EmbeddingCRUD:
    """CRUD operations for embeddings."""

    @staticmethod
    async def create(
        db: AsyncSession,
        file_id: int,
        vector: np.ndarray,
        modality: str,
        embedding_type: str,
    ) -> Embedding:
        """Create an embedding with vector."""
        embedding = Embedding(
            file_id=file_id,
            modality=modality,
            embedding_type=embedding_type,
            vector=serialize_array(vector),
        )
        db.add(embedding)
        await db.commit()
        await db.refresh(embedding)
        return embedding

    @staticmethod
    async def get_by_file(db: AsyncSession, file_id: int) -> list[Embedding]:
        """Get all embeddings for a file."""
        result = await db.execute(
            select(Embedding).where(Embedding.file_id == file_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_vector(db: AsyncSession, embedding_id: int) -> Optional[np.ndarray]:
        """Get vector for an embedding."""
        result = await db.execute(
            select(Embedding).where(Embedding.id == embedding_id)
        )
        embedding = result.scalar_one_or_none()
        if embedding is None or embedding.vector is None:
            return None
        return deserialize_array(embedding.vector)

    @staticmethod
    async def search_similar(
        db: AsyncSession,
        query_vector: np.ndarray,
        modality: Optional[str] = None,
        folder_ids: Optional[list[int]] = None,
        top_k: int = 10,
        threshold: float = 0.0,
        exclude_deleted: bool = True,
    ) -> list[tuple[File, float]]:
        """
        Search for similar embeddings using dot product similarity.

        Returns list of (file, similarity) tuples.
        """
        # Build query
        query = (
            select(File, Embedding)
            .join(Embedding, File.id == Embedding.file_id)
            .where(Embedding.vector.is_not(None))
        )

        # Filter by modality
        if modality:
            query = query.where(Embedding.modality == modality)

        # Filter by folder
        if folder_ids:
            query = query.where(File.folder_id.in_(folder_ids))

        # Exclude deleted files
        if exclude_deleted:
            query = query.where(File.is_deleted == False)

        result = await db.execute(query)
        results = result.all()

        # Compute similarities in Python
        similar_files = []
        for file, embedding in results:
            if embedding.vector is None:
                continue
            stored_vector = deserialize_array(embedding.vector)
            # Dot product similarity
            similarity = float(np.dot(query_vector, stored_vector))

            if similarity >= threshold:
                similar_files.append((file, similarity))

        # Sort by similarity descending and limit
        similar_files.sort(key=lambda x: x[1], reverse=True)
        return similar_files[:top_k]

    @staticmethod
    async def delete_by_file(db: AsyncSession, file_id: int) -> int:
        """Delete all embeddings for a file."""
        result = await db.execute(
            delete(Embedding).where(Embedding.file_id == file_id)
        )
        await db.commit()
        return result.rowcount


# ============ Indexing Job CRUD ============


class IndexingJobCRUD:
    """CRUD operations for indexing jobs."""

    @staticmethod
    async def create(
        db: AsyncSession,
        job_type: str,
        folder_id: Optional[int] = None,
    ) -> IndexingJob:
        """Create a new indexing job."""
        job = IndexingJob(
            job_type=job_type,
            folder_id=folder_id,
            status="pending",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def get(db: AsyncSession, job_id: int) -> Optional[IndexingJob]:
        """Get job by ID."""
        result = await db.execute(select(IndexingJob).where(IndexingJob.id == job_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_recent(
        db: AsyncSession, limit: int = 50, status: Optional[str] = None
    ) -> list[IndexingJob]:
        """List recent jobs."""
        query = select(IndexingJob).order_by(IndexingJob.id.desc()).limit(limit)
        if status:
            query = query.where(IndexingJob.status == status)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        db: AsyncSession,
        job_id: int,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[IndexingJob]:
        """Update job status."""
        job = await IndexingJobCRUD.get(db, job_id)
        if job is None:
            return None

        job.status = status
        if error_message:
            job.error_message = error_message

        if status == "running" and job.started_at is None:
            job.started_at = datetime.utcnow()
        elif status in ("completed", "failed"):
            job.completed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def increment_progress(
        db: AsyncSession, job_id: int, processed: int = 1, failed: int = 0
    ) -> None:
        """Increment progress counters."""
        job = await IndexingJobCRUD.get(db, job_id)
        if job:
            job.processed_files += processed
            job.failed_files += failed
            await db.commit()

    @staticmethod
    async def set_total_files(db: AsyncSession, job_id: int, total: int) -> None:
        """Set total files count."""
        job = await IndexingJobCRUD.get(db, job_id)
        if job:
            job.total_files = total
            await db.commit()

    @staticmethod
    async def count_active(db: AsyncSession) -> int:
        """Count active (running/pending) jobs."""
        result = await db.execute(
            select(func.count(IndexingJob.id)).where(
                IndexingJob.status.in_(["pending", "running"])
            )
        )
        return result.scalar() or 0
