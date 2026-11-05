"""Atomic job state and content-addressed cache primitives."""
from __future__ import annotations
import hashlib, json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STAGES=("created","validated","audio","visuals","composed","technical_qa","ready")

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def cache_key(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()

class JobStore:
    """Filesystem-backed atomic state store; replaceable by a remote queue."""
    def __init__(self,directory:Path):
        self.directory=directory
        directory.mkdir(parents=True,exist_ok=True)
        self.path=directory/"job-state.json"
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
    def load(self):
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else None
    def _write(self,state):
        state["updated_at"]=self._now()
        fd,name=tempfile.mkstemp(prefix=".job-state-",suffix=".tmp",dir=self.directory)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f:
                json.dump(state,f,ensure_ascii=False,indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name): os.unlink(name)
    def create(self,job_id:str,input_hash:str,config:dict[str,Any]):
        old=self.load()
        if old:
            if old["job_id"]!=job_id or old["input_hash"]!=input_hash:
                raise ValueError("job directory belongs to a different input")
            return old
        state={"schema_version":1,"job_id":job_id,"input_hash":input_hash,"config":config,
               "status":"running","stage":"created","completed":{},"attempt":1,
               "created_at":self._now(),"updated_at":self._now(),"error":None}
        self._write(state); return state
    def complete_stage(self,stage:str,outputs:dict[str,str]|None=None):
        if stage not in STAGES: raise ValueError("unknown stage")
        state=self.load()
        if state is None: raise ValueError("job not initialized")
        if STAGES.index(stage)<STAGES.index(state["stage"]): raise ValueError("stages cannot move backwards")
        state["stage"]=stage
        state["completed"][stage]={"at":self._now(),"outputs":outputs or {}}
        if stage=="ready": state["status"]="ready"
        self._write(state); return state
    def fail(self,error:str):
        state=self.load()
        if state is None: raise ValueError("job not initialized")
        state["status"]="failed"; state["error"]=error[:2000]
        state["attempt"]=int(state.get("attempt",1))+1
        self._write(state); return state
    def is_complete(self,stage:str,expected_outputs:dict[str,str]|None=None):
        state=self.load()
        if not state or STAGES.index(state.get("stage","created"))<STAGES.index(stage):
            return False
        record=state.get("completed",{}).get(stage)
        if not record: return False
        outputs=record.get("outputs",{})
        for name,recorded_hash in outputs.items():
            expected=(expected_outputs or {}).get(name,recorded_hash)
            path=self.directory/name
            if expected!=recorded_hash or not path.is_file() or sha256_file(path)!=recorded_hash:
                return False
        return True
