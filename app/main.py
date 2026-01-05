"""Main FastAPI application for Trenton."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.config import settings
from app.database.connection import init_db, close_db
from app.database.migrations import run_migrations
from app.core.model_loader import ModelLoader
from app.core.embedding_generator import EmbeddingGenerator
from app.core.similarity_calculator import SimilarityCalculator
from app.services.search_service import SearchService
from app.services.indexing_service import IndexingService
from app.services.deletion_tracker import DeletionTracker
from app.monitoring.watcher import FileWatcher
from app.monitoring.indexer import IndexingWorker
from app.api.routes import search, folders, index, health

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    level=settings.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
)

# Global singletons
_model_loader = None
_embedding_generator = None
_similarity_calculator = None
_search_service = None
_indexing_service = None
_deletion_tracker = None
_watcher = None
_indexing_worker = None


def get_model_loader():
    """Get global model loader instance."""
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader


def get_search_service():
    """Get global search service instance."""
    global _search_service
    return _search_service


def get_indexing_service():
    """Get global indexing service instance."""
    global _indexing_service
    return _indexing_service


def get_watcher():
    """Get global file watcher instance."""
    global _watcher
    return _watcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _model_loader
    global _embedding_generator
    global _similarity_calculator
    global _search_service
    global _indexing_service
    global _deletion_tracker
    global _watcher
    global _indexing_worker

    logger.info("Starting Trenton...")

    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    await run_migrations()
    logger.info("Database initialized")

    # Initialize ML components (lazy loading - model loads on first use)
    logger.info("Initializing ML components (model will load on first request)...")
    _model_loader = get_model_loader()
    _embedding_generator = EmbeddingGenerator(_model_loader)
    _similarity_calculator = SimilarityCalculator(_embedding_generator)
    logger.info("ML components ready (model will lazy-load)")

    # Initialize services
    _deletion_tracker = DeletionTracker()
    _search_service = SearchService(
        _similarity_calculator, _embedding_generator, _deletion_tracker
    )
    _indexing_service = IndexingService(_embedding_generator)
    logger.info("Services initialized")

    # Initialize file monitoring
    logger.info("Starting file watcher...")
    event_loop = asyncio.get_event_loop()
    _watcher = FileWatcher(event_loop=event_loop)
    await _watcher.start()

    _indexing_worker = IndexingWorker(
        _watcher.event_queue, _embedding_generator
    )
    await _indexing_worker.start()
    logger.info("File watcher started")

    yield

    # Shutdown
    logger.info("Shutting down Trenton...")

    if _indexing_worker:
        await _indexing_worker.stop()

    if _watcher:
        await _watcher.stop()

    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router)
app.include_router(folders.router)
app.include_router(index.router)
app.include_router(health.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
