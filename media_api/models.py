from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


Operation = Literal[
    "youtube.video.download", "youtube.audio.download", "youtube.clip",
    "youtube.transcript", "youtube.thumbnail", "x.media.download", "x.video.clip",
]


class JobRequest(BaseModel):
    operation: Operation
    url: str
    start_seconds: float | None = Field(None, ge=0)
    end_seconds: float | None = Field(None, gt=0)
    duration_seconds: float | None = Field(None, gt=0)
    quality: Literal["best", "1080p", "720p", "480p", "360p"] = "1080p"
    audio_format: Literal["m4a", "mp3", "opus", "flac"] = "m4a"
    transcript_format: Literal["txt", "json", "srt", "vtt"] = "txt"
    language: str = "en"
    media_indexes: list[int] | None = None
    callback_url: str | None = None

    @model_validator(mode="after")
    def validate_clip(self):
        if self.operation.endswith("clip"):
            if self.start_seconds is None or (self.end_seconds is None) == (self.duration_seconds is None):
                raise ValueError("clip requires start_seconds and exactly one of end_seconds or duration_seconds")
            if self.end_seconds is not None and self.end_seconds <= self.start_seconds:
                raise ValueError("clip end_seconds must be greater than start_seconds")
        return self


class InspectRequest(BaseModel):
    url: str


class Artifact(BaseModel):
    artifact_id: str
    filename: str
    media_type: str
    size: int
    sha256: str
    expires_at: str


class JobView(BaseModel):
    job_id: str
    status: str
    operation: str
    stage: str | None = None
    progress: float = 0
    created_at: str
    updated_at: str
    request: dict[str, Any]
    error: dict[str, Any] | None = None
    artifacts: list[Artifact] = []
