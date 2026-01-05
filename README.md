# Trenton - Multimodal Search System

A multimodal search system using Meta's PE-AV-Large model that enables cross-modal retrieval across text, audio, and video content.

## Features

- **Cross-modal search**: Search audio/video with text, or search across modalities
- **Automatic indexing**: Continuously monitors folders and indexes new/modified files
- **Deleted file tracking**: Soft-deletes files and warns users when matches are deleted
- **FastAPI backend**: RESTful API with async operations
- **SQLite storage**: Simple file-based database with vector embeddings

## Quick Start

### Platform-Specific Installation

**Linux + AMD GPU (Radeon 8000S/8050S/8060S):**
```bash
# See detailed guide: docs/QUICKSTART_LINUX.md
# Quick install:
uv venv
source .venv/bin/activate
uv pip install -e .

# Install ROCm PyTorch:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7

# Install decord (video decoding):
uv pip install decord

# Verify installation:
python check_install.py
```

**macOS / CPU:**
```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

### Configuration

Copy `.env.example` to `.env` and adjust settings:

```bash
cp .env.example .env
```

Key settings:
- `MODEL_NAME`: Model to use (default: `facebook/pe-av-large`)
- `DEVICE`: `cpu` or `cuda` (default: `cpu`)
- `DATABASE_URL`: SQLite database path (default: `./data/trenton.db`)

### Running the Server

```bash
python run.py
```

The API will be available at `http://localhost:8000`

API documentation (Swagger UI): `http://localhost:8000/docs`

## API Usage

### 1. Add a folder to monitor

```bash
curl -X POST "http://localhost:8000/api/v1/folders" \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/media", "modality": "all"}'
```

### 2. Trigger indexing

```bash
curl -X POST "http://localhost:8000/api/v1/index/trigger" \
  -H "Content-Type: application/json" \
  -d '{"mode": "full"}'
```

### 3. Search with text

```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "cat playing piano", "query_type": "text", "top_k": 10}'
```

### 4. Search with audio/video file

```bash
curl -X POST "http://localhost:8000/api/v1/search/file?query_type=audio&top_k=5" \
  -F "file=@/path/to/query.mp3"
```

### 5. Find similar files

```bash
curl -X GET "http://localhost:8000/api/v1/search/similar/{file_id}?top_k=10"
```

### 6. Check indexing status

```bash
curl -X GET "http://localhost:8000/api/v1/index/status"
```

### 7. Get system statistics

```bash
curl -X GET "http://localhost:8000/api/v1/stats"
```

## Project Structure

```
trenton/
├── app/
│   ├── main.py                  # FastAPI application
│   ├── config.py                # Configuration settings
│   ├── api/routes/              # API endpoints
│   ├── core/                    # ML model and embeddings
│   ├── database/                # Database models and CRUD
│   ├── services/                # High-level services
│   ├── monitoring/              # File system monitoring
│   └── utils/                   # Utility functions
├── data/                        # Database storage (gitignored)
├── pyproject.toml               # Dependencies
└── run.py                       # Development server
```

## API Endpoints

### Search
- `POST /api/v1/search` - Search with text/audio/video query
- `POST /api/v1/search/file` - Search with uploaded file
- `GET /api/v1/search/similar/{file_id}` - Find similar files

### Folders
- `POST /api/v1/folders` - Add folder to monitor
- `GET /api/v1/folders` - List folders
- `PUT /api/v1/folders/{id}` - Update folder
- `DELETE /api/v1/folders/{id}` - Remove folder

### Indexing
- `POST /api/v1/index/trigger` - Trigger indexing
- `GET /api/v1/index/status` - List jobs
- `GET /api/v1/index/status/{job_id}` - Job details

### Health
- `GET /api/v1/health` - System health
- `GET /api/v1/stats` - Statistics

## Supported File Formats

**Audio**: `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.m4a`, `.wma`, `.opus`
**Video**: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.flv`, `.wmv`, `.m4v`

## Development

```bash
# Run with auto-reload
python run.py

# Run tests (when implemented)
pytest
```

## Model Information

The PE-AV-Large model from Meta/Facebook:
- Embedding dimension: 1792
- Similarity metric: Dot product
- Supported modalities: Text, Audio, Video, Audio-Video
- Model card: https://huggingface.co/facebook/pe-av-large

### Platform-Specific Setup

- **Linux + AMD GPU**: See [docs/SETUP_LINUX_AMD.md](docs/SETUP_LINUX_AMD.md)
- **Linux + NVIDIA GPU**: Use standard `pip install torch`
- **macOS**: CPU-only mode (GPU support limited)

### Model Limitations

⚠️ **Current Issues (as of January 2026)**:
- PE-AV model was released December 2025, still being integrated into transformers
- `transformers>=5.0.0.dev0` required for `PeAudioVideoModel` classes
- For production use, consider monitoring for stable transformer releases
