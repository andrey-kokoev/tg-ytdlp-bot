import json,shutil,time
from media_api.config import CONFIG
from media_api.engine import R2,execute
from media_api.store import JobStore
def run():
    CONFIG.work_dir.mkdir(parents=True,exist_ok=True); store=JobStore(CONFIG.db_path)
    while True:
        row=store.claim()
        if not row: time.sleep(1); continue
        job=row["job_id"]; work=CONFIG.work_dir/job
        try:
            if shutil.disk_usage(CONFIG.work_dir).free<CONFIG.min_free_bytes: raise RuntimeError("insufficient_disk_space")
            store.update(job,stage="acquiring",progress=.1); files=execute(json.loads(row["request_json"]),work); r2=R2(); store.update(job,stage="publishing",progress=.8)
            for p in files:
                if p.stat().st_size>CONFIG.max_artifact_bytes: raise RuntimeError("artifact_too_large")
                store.add_artifact(job,r2.upload(job,p))
            store.update(job,status="succeeded",stage="complete",progress=1)
        except Exception as e: store.update(job,status="failed",stage="failed",error={"code":str(e),"message":str(e),"retryable":False})
        finally: shutil.rmtree(work,ignore_errors=True)
if __name__=="__main__": run()
