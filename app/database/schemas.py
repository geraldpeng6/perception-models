"""Pydantic schemas for API requests/responses."""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, field_validator


# ============ Folder Schemas ============


class FolderCreate(BaseModel):
    """Schema for creating a folder."""

    path: str = Field(..., description="Absolute path to folder")
    modality: Literal["audio", "video", "audio_video", "all"] = Field(
        default="all", description="Modality type to index"
    )


class FolderResponse(BaseModel):
    """Schema for folder response."""

    id: int
    path: str
    modality: str
    is_active: bool
    created_at: datetime
    last_indexed_at: Optional[datetime] = None
    file_count: Optional[int] = None

    model_config = {"from_attributes": True}


class FolderUpdate(BaseModel):
    """Schema for updating a folder."""

    is_active: Optional[bool] = None
    modality: Optional[Literal["audio", "video", "audio_video", "all"]] = None


# ============ Search Schemas ============


class SearchRequest(BaseModel):
    """Schema for search request."""

    query: str = Field(..., description="Text query or file path")
    query_type: Literal["text", "audio", "video"] = Field(
        default="text", description="Type of query"
    )
    modalities: Optional[list[Literal["audio", "video", "audio_video"]]] = Field(
        default=None, description="Filter by modalities"
    )
    folder_ids: Optional[list[int]] = Field(
        default=None, description="Filter by folder IDs"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    threshold: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Similarity threshold"
    )

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        """Validate top_k is within bounds."""
        from app.config import settings

        return min(v, settings.max_top_k)


class FileMetadata(BaseModel):
    """Schema for file metadata."""

    id: int
    path: str
    filename: str
    modality: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    duration_seconds: Optional[float] = None
    is_deleted: bool
    indexed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SearchResult(BaseModel):
    """Schema for a single search result."""

    file_id: int
    path: str
    filename: str
    modality: str
    similarity: float
    metadata: FileMetadata
    is_deleted: bool


class SearchResponse(BaseModel):
    """Schema for search response."""

    results: list[SearchResult]
    total: int
    query_time_ms: float
    warnings: Optional[list[str]] = None


# ============ Indexing Schemas ============


class IndexTriggerRequest(BaseModel):
    """Schema for triggering indexing."""

    folder_id: Optional[int] = Field(
        default=None, description="Folder ID (omit for all folders)"
    )
    mode: Literal["full", "incremental"] = Field(
        default="incremental", description="Indexing mode"
    )


class IndexingJobResponse(BaseModel):
    """Schema for indexing job response."""

    id: int
    job_type: str
    folder_id: Optional[int] = None
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class IndexStatusListResponse(BaseModel):
    """Schema for listing indexing jobs."""

    jobs: list[IndexingJobResponse]


# ============ Health & Stats Schemas ============


class HealthResponse(BaseModel):
    """Schema for health check response."""

    status: Literal["healthy", "degraded", "unhealthy"]
    database: str
    model_loaded: bool
    watcher_running: bool


class StatsResponse(BaseModel):
    """Schema for system statistics."""

    total_folders: int
    total_files: int
    total_embeddings: int
    files_by_modality: dict[str, int]
    deleted_files: int
    active_indexing_jobs: int
