"""Database migrations and initialization."""

from aiosqlite import connect
from pathlib import Path

from app.config import settings


async def run_migrations() -> None:
    """Run database migrations."""
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with connect(db_path) as db:
        # Enable extension loading
        await db.enable_load_extension(True)

        # Try to load sqlite-vec extension
        try:
            await db.load_extension("vec0")
            # Create vec0 virtual table if it doesn't exist
            await db.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS embeddings_vec USING vec0(
                    embedding_id INTEGER PRIMARY KEY,
                    embedding_type TEXT,
                    vector FLOAT(1792)
                )
            """
            )
        except Exception as e:
            # sqlite-vec not available, will use BLOB storage
            print(f"sqlite-vec extension not available: {e}")
            print("Using BLOB storage for embeddings (slower)")

        await db.enable_load_extension(False)
        await db.commit()


async def create_indexes() -> None:
    """Create additional indexes for performance."""
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")

    async with connect(db_path) as db:
        # Indexes for common queries
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_files_folder_modality ON files(folder_id, modality)",
            "CREATE INDEX IF NOT EXISTS ix_files_folder_deleted ON files(folder_id, is_deleted)",
            "CREATE INDEX IF NOT EXISTS ix_embeddings_file_type ON embeddings(file_id, embedding_type)",
        ]

        for idx in indexes:
            await db.execute(idx)

        await db.commit()
