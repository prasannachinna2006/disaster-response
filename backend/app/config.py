import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
load_dotenv(BACKEND_DIR / ".env")
DATABASE_URL = os.getenv(
    "RESQMESH_DATABASE_URL",
    f"sqlite:///{(DATA_DIR / 'resqmesh.db').as_posix()}",
)
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "RESQMESH_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
SYNC_SHARED_SECRET = os.getenv("RESQMESH_SYNC_SHARED_SECRET", "")
