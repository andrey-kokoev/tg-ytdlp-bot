from __future__ import annotations
import hashlib,json
from fastapi import Depends,FastAPI,Header,HTTPException,Query
from media_api.config import CONFIG
from media_api.engine import R2,inspect,validate_url
from media_api.models import InspectRequest,JobRequest
from media_api.store import JobStore
app=FastAPI(title="Narada Media Operations API",version="1.0.0"); store=JobStore(CONFIG.db_path)
def auth(authorization:str=Header("")):
    token=authorization.removeprefix("Bearer ")
    if not token or token not in CONFIG.api_tokens: raise HTTPException(401,detail={"code":"unauthorized"})
    return hashlib.sha256(token.encode()).hexdigest()[:16]
def view(row):
    r={k:row.get(k) for k in ("job_id","status","operation","stage","progress","created_at","updated_at")}; r["request"]=json.loads(row["request_json"]); r["error"]=json.loads(row["error_json"]) if row.get("error_json") else None
    r["artifacts"]=[{k:a[k] for k in ("artifact_id","filename","media_type","size","sha256","expires_at")} for a in store.artifacts(row["job_id"])]; return r
@app.get("/v1/health/live")
def live(): return {"status":"ok"}
@app.get("/v1/health/ready")
def ready(_:str=Depends(auth)): return {"status":"ready","queue_depth":store.queue_depth(),"r2_configured":bool(CONFIG.r2_bucket)}
@app.get("/v1/capabilities")
def capabilities(_:str=Depends(auth)): return {"operations":["youtube.video.download","youtube.audio.download","youtube.clip","youtube.transcript","youtube.thumbnail","x.media.download","x.video.clip"],"limits":{"queue":CONFIG.max_queue,"clip_seconds":CONFIG.max_clip_seconds,"artifact_bytes":CONFIG.max_artifact_bytes}}
@app.post("/v1/youtube/inspect")
def yi(req:InspectRequest,_:str=Depends(auth)): return inspect(req.url,"youtube")
@app.post("/v1/x/inspect")
def xi(req:InspectRequest,_:str=Depends(auth)): return inspect(req.url,"x")
@app.post("/v1/jobs",status_code=202)
def submit(req:JobRequest,token:str=Depends(auth),idempotency_key:str|None=Header(None)):
    if store.queue_depth()>=CONFIG.max_queue: raise HTTPException(429,detail={"code":"queue_full"})
    if req.operation.endswith("clip"):
        duration = req.duration_seconds if req.duration_seconds is not None else req.end_seconds - req.start_seconds
        if duration > CONFIG.max_clip_seconds: raise HTTPException(422,detail={"code":"clip_too_long"})
    try: validate_url(req.url,"youtube" if req.operation.startswith("youtube") else "x"); row,created=store.submit(token,req.model_dump(),idempotency_key)
    except ValueError as e: raise HTTPException(409 if str(e)=="idempotency_key_conflict" else 422,detail={"code":str(e)})
    return view(row)|{"created":created,"status_url":f"/v1/jobs/{row['job_id']}"}
@app.get("/v1/jobs")
def jobs(limit:int=Query(50,ge=1,le=200),_:str=Depends(auth)): return [view(x) for x in store.list(limit)]
@app.get("/v1/jobs/{job_id}")
def job(job_id:str,_:str=Depends(auth)):
    row=store.get(job_id)
    if not row: raise HTTPException(404,detail={"code":"job_not_found"})
    return view(row)
@app.get("/v1/jobs/{job_id}/events")
def events(job_id:str,_:str=Depends(auth)): return [{**x,"payload":json.loads(x["payload_json"])} for x in store.events(job_id)]
@app.post("/v1/jobs/{job_id}/cancel",status_code=202)
def cancel(job_id:str,_:str=Depends(auth)): store.cancel(job_id); return {"job_id":job_id,"status":"cancel_requested"}
@app.post("/v1/jobs/{job_id}/artifacts/{artifact_id}/url")
def url(job_id:str,artifact_id:str,_:str=Depends(auth)):
    a=next((x for x in store.artifacts(job_id) if x["artifact_id"]==artifact_id),None)
    if not a: raise HTTPException(404,detail={"code":"artifact_not_found"})
    return {"url":R2().url(a["object_key"]),"filename":a["filename"],"media_type":a["media_type"],"expires_in":CONFIG.signed_url_ttl_seconds}
