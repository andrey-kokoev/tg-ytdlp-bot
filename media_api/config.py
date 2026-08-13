from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaConfig:
    data_dir: Path = Path(os.getenv("MEDIA_DATA_DIR", "/app/media-runtime"))
    api_tokens: tuple[str, ...] = tuple(filter(None, os.getenv("MEDIA_API_TOKENS", "").split(",")))
    max_queue: int = int(os.getenv("MEDIA_MAX_QUEUE", "20"))
    max_artifact_bytes: int = int(os.getenv("MEDIA_MAX_ARTIFACT_BYTES", str(1024**3)))
    min_free_bytes: int = int(os.getenv("MEDIA_MIN_FREE_BYTES", str(1536 * 1024**2)))
    max_clip_seconds: int = int(os.getenv("MEDIA_MAX_CLIP_SECONDS", "1800"))
    max_runtime_seconds: int = int(os.getenv("MEDIA_MAX_RUNTIME_SECONDS", "1800"))
    artifact_ttl_seconds: int = int(os.getenv("MEDIA_ARTIFACT_TTL_SECONDS", "86400"))
    signed_url_ttl_seconds: int = int(os.getenv("MEDIA_SIGNED_URL_TTL_SECONDS", "900"))
    r2_endpoint: str = os.getenv("MEDIA_R2_ENDPOINT", "")
    r2_bucket: str = os.getenv("MEDIA_R2_BUCKET", "")
    r2_access_key: str = os.getenv("MEDIA_R2_ACCESS_KEY_ID", "")
    r2_secret_key: str = os.getenv("MEDIA_R2_SECRET_ACCESS_KEY", "")
    webhook_secret: str = os.getenv("MEDIA_WEBHOOK_SECRET", "")
    webhook_hosts: tuple[str, ...] = tuple(filter(None, os.getenv("MEDIA_WEBHOOK_HOSTS", ".ts.net").split(",")))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    @property
    def work_dir(self) -> Path:
        return self.data_dir / "work"


CONFIG = MediaConfig()
