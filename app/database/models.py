"""SQLAlchemy database models."""

from datetime import datetime
from typing import Literal

from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Folder(Base):
    """Monitored folder configuration."""

    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    modality: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )  # 'audio', 'video', 'audio_video', 'all'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    files: Mapped[list["File"]] = relationship(
        "File", back_populates="folder", cascade="all, delete-orphan"
    )
    indexing_jobs: Mapped[list["IndexingJob"]] = relationship(
        "IndexingJob", back_populates="folder"
    )


class File(Base):
    """File metadata and tracking."""

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    folder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    modality: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )  # 'audio', 'video', 'text'
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deletion_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    modified_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    folder: Mapped["Folder"] = relationship("Folder", back_populates="files")
    embeddings: Mapped[list["Embedding"]] = relationship(
        "Embedding", back_populates="file", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_files_folder_modality", "folder_id", "modality"),
        Index("ix_files_folder_deleted", "folder_id", "is_deleted"),
    )


class Embedding(Base):
    """Embedding metadata (vector stored separately)."""

    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modality: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )  # 'audio', 'video', 'audio_video', 'text'
    embedding_type: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )  # Specific type from model
    vector: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    file: Mapped["File"] = relationship("File", back_populates="embeddings")

    __table_args__ = (
        Index("ix_embeddings_file_type", "file_id", "embedding_type"),
    )


class IndexingJob(Base):
    """Background indexing job tracking."""

    __tablename__ = "indexing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # 'full_scan', 'incremental', 'single_file'
    folder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String, default="pending", index=True
    )  # 'pending', 'running', 'completed', 'failed'
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    folder: Mapped["Folder"] = relationship("Folder", back_populates="indexing_jobs")
