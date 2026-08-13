from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.initialize()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def initialize(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY, token_id TEXT NOT NULL,
              idempotency_key TEXT, fingerprint TEXT, operation TEXT NOT NULL, request_json TEXT NOT NULL,
              status TEXT NOT NULL, stage TEXT, progress REAL NOT NULL DEFAULT 0, error_json TEXT,
              retry_count INTEGER NOT NULL DEFAULT 0, cancel_requested INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS jobs_idem ON jobs(token_id,idempotency_key) WHERE idempotency_key IS NOT NULL;
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
              kind TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts(artifact_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
              filename TEXT NOT NULL, media_type TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL,
              object_key TEXT NOT NULL, expires_at TEXT NOT NULL);
            """)

    def submit(self, token_id: str, request: dict[str, Any], idempotency_key: str | None):
        encoded = json.dumps(request, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
        with self.connect() as db:
            if idempotency_key:
                old = db.execute("SELECT * FROM jobs WHERE token_id=? AND idempotency_key=?", (token_id,idempotency_key)).fetchone()
                if old:
                    if old["fingerprint"] != fingerprint:
                        raise ValueError("idempotency_key_conflict")
                    return dict(old), False
            job_id, stamp = str(uuid.uuid4()), now()
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (job_id,token_id,idempotency_key,fingerprint,request["operation"],encoded,"queued","queued",0,None,0,0,stamp,stamp))
            self.event(db, job_id, "queued", {})
            return dict(db.execute("SELECT * FROM jobs WHERE job_id=?",(job_id,)).fetchone()), True

    def event(self, db, job_id: str, kind: str, payload: dict[str, Any]):
        db.execute("INSERT INTO events(job_id,kind,payload_json,created_at) VALUES(?,?,?,?)",(job_id,kind,json.dumps(payload),now()))

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                db.execute("COMMIT"); return None
            stamp=now(); db.execute("UPDATE jobs SET status='running',stage='starting',updated_at=? WHERE job_id=?",(stamp,row["job_id"]))
            self.event(db,row["job_id"],"running",{}); db.execute("COMMIT")
            return dict(db.execute("SELECT * FROM jobs WHERE job_id=?",(row["job_id"],)).fetchone())

    def update(self, job_id: str, *, status=None, stage=None, progress=None, error=None):
        fields, values = ["updated_at=?"], [now()]
        for name,value in (("status",status),("stage",stage),("progress",progress)):
            if value is not None: fields.append(f"{name}=?"); values.append(value)
        if error is not None: fields.append("error_json=?"); values.append(json.dumps(error))
        values.append(job_id)
        with self.connect() as db:
            db.execute(f"UPDATE jobs SET {','.join(fields)} WHERE job_id=?",values)
            self.event(db,job_id,status or stage or "progress",{"progress":progress,"error":error})

    def get(self, job_id: str):
        with self.connect() as db:
            row=db.execute("SELECT * FROM jobs WHERE job_id=?",(job_id,)).fetchone()
            return dict(row) if row else None

    def list(self, limit=50):
        with self.connect() as db: return [dict(x) for x in db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",(limit,))]

    def events(self, job_id: str):
        with self.connect() as db: return [dict(x) for x in db.execute("SELECT * FROM events WHERE job_id=? ORDER BY id",(job_id,))]

    def cancel(self, job_id: str):
        with self.connect() as db:
            db.execute("UPDATE jobs SET cancel_requested=1,status=CASE WHEN status='queued' THEN 'canceled' ELSE status END,updated_at=? WHERE job_id=?",(now(),job_id))

    def add_artifact(self, job_id: str, data: dict[str, Any]):
        with self.connect() as db:
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?)",(data["artifact_id"],job_id,data["filename"],data["media_type"],data["size"],data["sha256"],data["object_key"],data["expires_at"]))

    def artifacts(self, job_id: str):
        with self.connect() as db: return [dict(x) for x in db.execute("SELECT * FROM artifacts WHERE job_id=?",(job_id,))]

    def queue_depth(self):
        with self.connect() as db: return db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
