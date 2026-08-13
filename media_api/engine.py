from __future__ import annotations
import hashlib, json, mimetypes, os, re, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
import boto3, yt_dlp
from CONFIG.config import Config
from media_api.config import CONFIG

YOUTUBE={"youtube.com","www.youtube.com","m.youtube.com","youtu.be"}; X={"x.com","www.x.com","twitter.com","www.twitter.com"}
def validate_url(url:str,platform:str|None=None)->str:
    p=urlparse(url); allowed=YOUTUBE if platform=="youtube" else X if platform=="x" else YOUTUBE|X
    if p.scheme!="https" or p.username or p.password or (p.hostname or "").lower() not in allowed: raise ValueError("unsupported_url")
    return url
def options(url:str)->dict:
    out={"quiet":True,"no_warnings":True,"noplaylist":True,"restrictfilenames":True}
    cookie=getattr(Config,"COOKIE_FILE_PATH",None)
    if cookie and os.path.exists(cookie): out["cookiefile"]=cookie
    try:
        from HELPERS.proxy_helper import add_proxy_to_ytdl_opts
        out=add_proxy_to_ytdl_opts(out,url)
    except Exception: pass
    return out
def inspect(url:str,platform:str)->dict:
    validate_url(url,platform)
    with yt_dlp.YoutubeDL(options(url)|{"skip_download":True}) as y: info=y.extract_info(url,download=False)
    formats=[{k:f.get(k) for k in ("format_id","ext","height","width","vcodec","acodec","filesize","tbr")} for f in info.get("formats",[])[-100:]]
    entries=info.get("entries") or []
    return {k:info.get(k) for k in ("id","title","description","duration","uploader","uploader_id","timestamp","webpage_url","thumbnail")}|{"platform":platform,"formats":formats,"subtitle_languages":sorted(set((info.get("subtitles") or {})|(info.get("automatic_captions") or {}))),"media":[{"index":i,"id":e.get("id"),"ext":e.get("ext")} for i,e in enumerate(entries)]}
def quality(q:str)->str:
    if q=="best": return "bv*+ba/b"
    h=int(q.removesuffix("p")); return f"bv*[height<={h}]+ba/b[height<={h}]"
def plain(path:Path)->Path:
    lines=[]
    for raw in path.read_text(encoding="utf-8",errors="replace").splitlines():
        s=raw.strip()
        if not s or s.isdigit() or s=="WEBVTT" or "-->" in s or s.startswith(("Kind:","Language:","NOTE")): continue
        s=re.sub(r"<[^>]+>","",s)
        if s and (not lines or lines[-1]!=s): lines.append(s)
    target=path.with_suffix(".txt"); target.write_text("\n".join(lines)+"\n",encoding="utf-8"); return target
def execute(req:dict,work:Path)->list[Path]:
    op,url=req["operation"],req["url"]; validate_url(url,"youtube" if op.startswith("youtube") else "x"); work.mkdir(parents=True,exist_ok=True)
    opts=options(url)|{"outtmpl":str(work/"%(title).120B-%(id)s.%(ext)s"),"noplaylist":True}
    if op.endswith("transcript"):
        fmt=req.get("transcript_format","txt"); opts|={"skip_download":True,"writesubtitles":True,"writeautomaticsub":True,"subtitleslangs":[req.get("language","en")],"subtitlesformat":"srt" if fmt in ("txt","json","srt") else "vtt"}
    elif op.endswith("thumbnail"): opts|={"skip_download":True,"writethumbnail":True}
    elif ".audio." in op:
        af=req.get("audio_format","m4a"); opts|={"format":"ba/b","postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":af}]}
    else:
        opts|={"format":quality(req.get("quality","1080p")),"merge_output_format":"mp4"}
        if op.endswith("clip"):
            start=float(req["start_seconds"]); end=req.get("end_seconds") or start+float(req["duration_seconds"])
            opts["download_ranges"]=yt_dlp.utils.download_range_func(None,[(start,float(end))]); opts["force_keyframes_at_cuts"]=True
    with yt_dlp.YoutubeDL(opts) as y: y.download([url])
    files=[p for p in work.iterdir() if p.is_file() and not p.name.endswith((".part",".ytdl"))]
    if op.endswith("transcript"):
        subs=[p for p in files if p.suffix in (".srt",".vtt")]
        if not subs: raise RuntimeError("captions_unavailable")
        if req.get("transcript_format")=="txt": files=[plain(subs[0])]
        elif req.get("transcript_format")=="json":
            txt=plain(subs[0]); target=txt.with_suffix(".json"); target.write_text(json.dumps({"text":txt.read_text(encoding="utf-8")}),encoding="utf-8"); files=[target]
        else: files=[subs[0]]
    if not files: raise RuntimeError("no_artifact_produced")
    return files
class R2:
    def __init__(self):
        if not all((CONFIG.r2_endpoint,CONFIG.r2_bucket,CONFIG.r2_access_key,CONFIG.r2_secret_key)): raise RuntimeError("r2_not_configured")
        self.c=boto3.client("s3",endpoint_url=CONFIG.r2_endpoint,aws_access_key_id=CONFIG.r2_access_key,aws_secret_access_key=CONFIG.r2_secret_key,region_name="auto")
    def upload(self,job:str,path:Path)->dict:
        digest=hashlib.sha256(path.read_bytes()).hexdigest(); aid=str(uuid.uuid4()); key=f"media/{job}/{aid}/{path.name}"; media=mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.c.upload_file(str(path),CONFIG.r2_bucket,key,ExtraArgs={"ContentType":media}); expires=datetime.now(timezone.utc)+timedelta(seconds=CONFIG.artifact_ttl_seconds)
        return {"artifact_id":aid,"filename":path.name,"media_type":media,"size":path.stat().st_size,"sha256":digest,"object_key":key,"expires_at":expires.isoformat()}
    def url(self,key:str)->str: return self.c.generate_presigned_url("get_object",Params={"Bucket":CONFIG.r2_bucket,"Key":key},ExpiresIn=CONFIG.signed_url_ttl_seconds)
