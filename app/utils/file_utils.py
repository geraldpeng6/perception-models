"""File utility functions."""

import os
import mimetypes
from pathlib import Path
from typing import Optional


def ensure_directory(path: str) -> Path:
    """Ensure directory exists, create if not."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    return Path(file_path).stat().st_size


def get_mime_type(file_path: str) -> Optional[str]:
    """Get MIME type for file."""
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type


def is_empty(file_path: str) -> bool:
    """Check if file is empty."""
    return get_file_size(file_path) == 0
