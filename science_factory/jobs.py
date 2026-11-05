"""Atomic job state and verified stage-resume primitives."""
from __future__ import annotations
import hashlib,json,os,tempfile
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
STAGES=("created","validated","audio","visuals","composed","technical_qa","ready")
def sha256_file(path:Path)->str:
 h=hashlib.sha256()
 with path.open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
 return h.hexdigest()
def cache_key(*parts:str)->str:
 return hashlib.sha256("\0".join(parts).encode()).hexdigest()
class JobStore:
 """Atomic JSON job ledger; completed outputs are reused only after hash verification."""
 def __init__(self,directory:Path):
  self.directory=directory; directory.mkdir(parents=True,exist_ok=True); self.path=directory/"job-state.json"
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
   if old["job_id"]!=job_id or old["input_hash"]!=input_hash or old["config"]!=config:
    raise ValueError("job ID already exists with different input or configuration")
   return old
  state={"schema_version":1,"job_id":job_id,"input_hash":input_hash,"config":config,
   "status":"running","stage":"created","completed":{},"attempt":1,
   "created_at":self._now(),"updated_at":self._now(),"error":None}
  self._write(state); return state
 def resume(self):
  state=self.load()
  if state is None: raise ValueError("job not initialized")
  if state["status"]=="ready": return state
  state["status"]="running"; state["error"]=None
  state["attempt"]=int(state.get("attempt",1))+1
  self._write(state); return state
 def rewind(self,stage:str):
  """Invalidate stage and all downstream checkpoints after a hash mismatch."""
  if stage not in STAGES: raise ValueError("unknown stage")
  state=self.load()
  if state is None: raise ValueError("job not initialized")
  idx=STAGES.index(stage); previous=STAGES[max(0,idx-1)]
  state["completed"]={k:v for k,v in state["completed"].items() if STAGES.index(k)<idx}
  state["stage"]=previous; state["status"]="running"; state["error"]=None
  self._write(state); return state
 def complete_stage(self,stage:str,outputs:dict[str,str]|None=None):
  if stage not in STAGES: raise ValueError("unknown stage")
  state=self.load()
  if state is None: raise ValueError("job not initialized")
  if STAGES.index(stage)<STAGES.index(state["stage"]): raise ValueError("stages cannot move backwards")
  state["stage"]=stage; state["completed"][stage]={"at":self._now(),"outputs":outputs or {}}
  if stage=="ready": state["status"]="ready"
  self._write(state); return state
 def fail(self,error:str):
  state=self.load()
  if state is None: raise ValueError("job not initialized")
  state["status"]="failed"; state["error"]=error[:2000]
  self._write(state); return state
 def is_complete(self,stage:str):
  state=self.load()
  if not state or STAGES.index(state.get("stage","created"))<STAGES.index(stage): return False
  record=state.get("completed",{}).get(stage)
  if not record: return False
  for name,digest in record.get("outputs",{}).items():
   path=self.directory/name
   if not path.is_file() or sha256_file(path)!=digest: return False
  return True
 def output_paths(self,stage:str)->dict[str,str]:
  state=self.load() or {}
  return dict(state.get("completed",{}).get(stage,{}).get("outputs",{}))
