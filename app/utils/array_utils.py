"""NumPy array serialization utilities."""

import io
from typing import Optional

import numpy as np


def serialize_array(array: np.ndarray) -> bytes:
    """
    Serialize NumPy array to bytes for BLOB storage.

    Args:
        array: NumPy array to serialize

    Returns:
        Serialized bytes
    """
    with io.BytesIO() as buffer:
        np.save(buffer, array)
        return buffer.getvalue()


def deserialize_array(blob: bytes) -> Optional[np.ndarray]:
    """
    Deserialize bytes back to NumPy array.

    Args:
        blob: Serialized bytes

    Returns:
        NumPy array or None if invalid
    """
    try:
        with io.BytesIO(blob) as buffer:
            return np.load(buffer)
    except Exception:
        return None


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    """
    L2-normalize vector for cosine similarity.

    Note: PE-AV-Large uses dot product, so normalization
    converts dot product to cosine similarity.

    Args:
        vector: Input vector

    Returns:
        Normalized vector
    """
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm
