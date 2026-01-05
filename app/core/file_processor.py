"""File processing utilities."""

import os
from pathlib import Path
from typing import Literal, Optional


class ModalityDetector:
    """Detect file modality from extension."""

    AUDIO_EXTENSIONS = {
        ".mp3",
        ".wav",
        ".flac",
        ".aac",
        ".ogg",
        ".m4a",
        ".wma",
        ".opus",
    }

    VIDEO_EXTENSIONS = {
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",
        ".flv",
        ".wmv",
        ".m4v",
    }

    @classmethod
    def detect(cls, file_path: str) -> Optional[Literal["audio", "video"]]:
        """
        Detect file modality from extension.

        Args:
            file_path: Path to file

        Returns:
            'audio', 'video', or None if unsupported
        """
        ext = Path(file_path).suffix.lower()

        if ext in cls.AUDIO_EXTENSIONS:
            return "audio"
        elif ext in cls.VIDEO_EXTENSIONS:
            return "video"

        return None

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """Check if file is supported."""
        return cls.detect(file_path) is not None


class FileProcessor:
    """File validation and processing utilities."""

    @staticmethod
    def validate_file(file_path: str) -> tuple[bool, Optional[str]]:
        """
        Validate file before processing.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(file_path)

        # Check file exists
        if not path.exists():
            return False, f"File not found: {file_path}"

        # Check it's a file (not directory)
        if not path.is_file():
            return False, f"Path is not a file: {file_path}"

        # Check file is readable
        if not os.access(file_path, os.R_OK):
            return False, f"File not readable: {file_path}"

        # Check file is not empty
        if path.stat().st_size == 0:
            return False, f"File is empty: {file_path}"

        # Check format is supported
        if not ModalityDetector.is_supported(file_path):
            return False, f"Unsupported file format: {file_path}"

        return True, None

    @staticmethod
    def get_file_info(file_path: str) -> dict:
        """
        Get file metadata.

        Args:
            file_path: Path to file

        Returns:
            Dict with file metadata
        """
        path = Path(file_path)

        return {
            "path": str(path.absolute()),
            "filename": path.name,
            "file_size": path.stat().st_size,
            "modality": ModalityDetector.detect(file_path),
        }

    @staticmethod
    def get_mime_type(file_path: str) -> Optional[str]:
        """
        Get MIME type for file.

        Args:
            file_path: Path to file

        Returns:
            MIME type string or None
        """
        import mimetypes

        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type


class EmptyFileError(Exception):
    """Raised when file is empty."""

    pass


class UnsupportedFormatError(Exception):
    """Raised when file format is not supported."""

    pass


class FileNotFoundError_(Exception):
    """Raised when file is not found."""

    pass
