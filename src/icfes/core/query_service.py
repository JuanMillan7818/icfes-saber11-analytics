from __future__ import annotations
from enum import Enum
import duckdb
from icfes import settings


class Backend(Enum):
    LOCAL = "local"
    S3 = "s3"
    SUPABASE = "supabase"


class QueryService:
    """
    DuckDB query abstraction over Parquet files.
    Use {parquet} placeholder in SQL — replaced with read_parquet(glob) at runtime.

    Usage:
        with make_query_service() as svc:
            df = svc.query_df(
                "SELECT ano, AVG(CAST(punt_global AS DOUBLE)) FROM {parquet} GROUP BY ano"
            )
    """

    def __init__(self, parquet_glob: str, con: duckdb.DuckDBPyConnection) -> None:
        self._parquet_glob = parquet_glob
        self._con = con

    def query(self, sql: str) -> duckdb.DuckDBPyRelation:
        resolved = sql.replace("{parquet}", f"read_parquet('{self._parquet_glob}')")
        return self._con.execute(resolved)

    def query_df(self, sql: str):
        return self.query(sql).df()

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> QueryService:
        return self

    def __exit__(self, *_) -> None:
        self.close()


# ── Backend factories ─────────────────────────────────────────────────────────


def _local_service() -> QueryService:
    con = duckdb.connect()
    con.execute("LOAD parquet")
    return QueryService(f"{settings.PARQUET_PATH}/*.parquet", con)


def _s3_service() -> QueryService:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; LOAD parquet")
    con.execute(
        f"""
        SET s3_region='{settings.AWS_REGION}';
        SET s3_access_key_id='{settings.AWS_ACCESS_KEY_ID}';
        SET s3_secret_access_key='{settings.AWS_SECRET_ACCESS_KEY}';
    """
    )
    return QueryService(f"{settings.S3_PARQUET_PATH.rstrip('/')}/*.parquet", con)


def _supabase_service() -> QueryService:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; LOAD parquet")
    # Supabase Storage S3-compatible API requires path-style URLs
    con.execute(
        f"""
        SET s3_endpoint='{settings.SUPABASE_S3_ENDPOINT}';
        SET s3_region='auto';
        SET s3_access_key_id='{settings.SUPABASE_ACCESS_KEY}';
        SET s3_secret_access_key='{settings.SUPABASE_SECRET_KEY}';
        SET s3_url_style='path';
    """
    )
    return QueryService(f"{settings.SUPABASE_PARQUET_PATH.rstrip('/')}/*.parquet", con)


_FACTORIES = {
    Backend.LOCAL: _local_service,
    Backend.S3: _s3_service,
    Backend.SUPABASE: _supabase_service,
}


def make_query_service() -> QueryService:
    backend = Backend(settings.STORAGE_BACKEND)
    return _FACTORIES[backend]()
