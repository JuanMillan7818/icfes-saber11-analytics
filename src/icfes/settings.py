from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (works regardless of cwd)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ── Storage ───────────────────────────────────────────────────────────────────
# local | s3 | supabase
STORAGE_BACKEND: str = os.environ.get("STORAGE_BACKEND", "local")

# ── ETL ───────────────────────────────────────────────────────────────────────
DATA_PATH_TEXT: str = os.environ.get("DATA_PATH_TEXT", "../Bases nacionales 2015-2026")
PARQUET_PATH: str = os.environ.get("PARQUET_PATH", "files/parquet")

# ── Supabase Storage (Fase 2) ─────────────────────────────────────────────────
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")
SUPABASE_BUCKET: str = os.environ.get("SUPABASE_BUCKET", "icfes-parquet")
# S3-compatible endpoint: <project-ref>.supabase.co/storage/v1/s3
SUPABASE_S3_ENDPOINT: str = os.environ.get("SUPABASE_S3_ENDPOINT", "")
SUPABASE_ACCESS_KEY: str = os.environ.get("SUPABASE_ACCESS_KEY", "")
SUPABASE_SECRET_KEY: str = os.environ.get("SUPABASE_SECRET_KEY", "")
SUPABASE_PARQUET_PATH: str = os.environ.get("SUPABASE_PARQUET_PATH", "")

# ── AWS S3 ────────────────────────────────────────────────────────────────────
AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID: str = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY: str = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
S3_PARQUET_PATH: str = os.environ.get("S3_PARQUET_PATH", "")

# ── API (Fase 2) ──────────────────────────────────────────────────────────────
API_HOST: str = os.environ.get("API_HOST", "0.0.0.0")
API_PORT: int = int(os.environ.get("API_PORT", "8000"))
