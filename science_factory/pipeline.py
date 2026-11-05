"""Resumable storyboard -> local TTS -> render -> technical QA pipeline."""
from __future__ import annotations
import hashlib,importlib.metadata,json,platform,re,subprocess,uuid
from datetime import datetime,timezone
from pathlib import Path
from .audio import trim_wav_edges
from .jobs import JobStore,sha256_file
from .media import extract_scene_stills,inspect_mp4,mux_video,render_manim,require_tools,scan_media_quality
from .quality import QualityReport
from .schema import Storyboard
from .timeline import make_timeline,save_captions
from .voice import VoiceCue,generate_voice,wav_duration

class BuildError(RuntimeError): pass
def _write_json(path:Path,data:dict)->None:
 path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
def _version(package:str)->str:
 try:return importlib.metadata.version(package)
 except importlib.metadata.PackageNotFoundError:return "unknown"
def _tool_version(name:str)->str:
 try:
  result=subprocess.run([name,"-version"],capture_output=True,text=True,timeout=10,check=False)
  return result.stdout.splitlines()[0][:200] if result.stdout else "unknown"
 except Exception:return "unknown"

def build(storyboard_file:Path,*,output_root:Path,voice:str="kokoro",quality:str="preview",job_id:str|None=None)->Path:
 storyboard=Storyboard.from_file(storyboard_file)
 if quality not in ("preview","full"):raise BuildError("quality must be preview or full")
 if voice not in ("kokoro","tone"):raise BuildError("voice must be kokoro or tone")
 require_tools("ffmpeg","ffprobe")
 try:import manim
 except ImportError as exc:raise BuildError('Manim is missing; install with: pip install -e ".[render]"') from exc
 run_id=job_id or (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8])
 if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}",run_id):raise BuildError("job_id must be 1-80 safe filename characters")
 directory=output_root.resolve()/run_id
 directory.mkdir(parents=True,exist_ok=True)
 source_bytes=storyboard_file.read_bytes(); input_hash=hashlib.sha256(source_bytes).hexdigest()
 config={"voice":voice,"quality":quality,"language":storyboard.language,
  "python":platform.python_version(),"manim":getattr(manim,"__version__","unknown"),
  "kokoro":_version("kokoro"),"numpy":_version("numpy"),"ffmpeg":_tool_version("ffmpeg")}
 jobs=JobStore(directory); existing=jobs.load()
 jobs.create(run_id,input_hash,config)
 if existing and existing.get("status")!="ready":jobs.resume()
 if jobs.is_complete("ready") and (directory/"final.mp4").is_file():return directory/"final.mp4"
 asset_provenance=json.loads((Path(__file__).resolve().parent/"assets"/"provenance.json").read_text(encoding="utf-8"))
 manifest={"schema_version":2,"run_id":run_id,"status":"RUNNING","voice_backend":voice,
  "language":storyboard.language,"quality":quality,"storyboard_sha256":input_hash,"configuration":config,
  "source_urls":list(storyboard.sources),"visual_asset_credits":{name:{"source":item["source"],
  "credit":item["credit"],"sha256":item["generated_sha256"]} for name,item in asset_provenance.items()},
  "started_at":datetime.now(timezone.utc).isoformat(),"attempt":(jobs.load() or {}).get("attempt",1)}
 manifest_file=directory/"manifest.json";_write_json(manifest_file,manifest)
 storyboard_path=directory/"storyboard.json";_write_json(storyboard_path,storyboard.to_dict())
 try:
  if not jobs.is_complete("validated"):
   if (jobs.load() or {}).get("stage")!="created":jobs.rewind("validated")
   jobs.complete_stage("validated",{"storyboard.json":sha256_file(storyboard_path)})
  wavs=[];audio_durations=[];chunk_cues=[];timing_evidence=[]
  cues_path=directory/"voice-cues.json"
  if jobs.is_complete("audio"):
   cue_data=json.loads(cues_path.read_text(encoding="utf-8"))
   for i in range(len(storyboard.scenes)):
    file=directory/f"voice_{i:02}.wav";wavs.append(file);audio_durations.append(wav_duration(file))
    chunk_cues.append([VoiceCue(**cue) for cue in cue_data[i]])
    timing_evidence.append({"scene":i,"trimmed_voice_seconds":round(audio_durations[-1],3),
      "tts_chunks":len(chunk_cues[-1]),"resumed_from_cache":True})
  else:
   if (jobs.load() or {}).get("stage") in ("audio","visuals","composed","technical_qa","ready"):jobs.rewind("audio")
   for index,scene in enumerate(storyboard.scenes):
    file=directory/f"voice_{index:02}.wav";cues=[]
    raw_duration=generate_voice(scene.narration,file,backend=voice,language=storyboard.language,cues_out=cues)
    trim_result=trim_wav_edges(file);duration=trim_result.duration
    aligned=[VoiceCue(cue.text,max(0.0,cue.start-trim_result.removed_start),
      min(duration,cue.end-trim_result.removed_start)) for cue in cues
      if cue.end>trim_result.removed_start and cue.start<trim_result.removed_start+duration]
    wavs.append(file);audio_durations.append(duration);chunk_cues.append(aligned)
    timing_evidence.append({"scene":index,"raw_voice_seconds":round(raw_duration,3),
      "trimmed_voice_seconds":round(duration,3),"trim_start_seconds":round(trim_result.removed_start,3),
      "trim_end_seconds":round(trim_result.removed_end,3),"tts_chunks":len(aligned),"resumed_from_cache":False})
   _write_json(cues_path,[[{"text":c.text,"start":c.start,"end":c.end} for c in group] for group in chunk_cues])
   jobs.complete_stage("audio",{p.name:sha256_file(p) for p in wavs}|{cues_path.name:sha256_file(cues_path)})
  timeline=make_timeline(storyboard,audio_durations);total_duration=timeline[-1].start+timeline[-1].duration
  plan=directory/"render-plan.json"
  _write_json(plan,{"schema_version":1,"target_seconds":storyboard.target_seconds,
    "actual_seconds":round(total_duration,3),"scenes":[scene.to_dict() for scene in timeline]})
  subtitles=directory/"captions.srt";save_captions(timeline,subtitles,cues_by_scene=chunk_cues)
  if jobs.is_complete("visuals"):
   saved=jobs.output_paths("visuals");relative=next(iter(saved),None)
   silent=directory/relative if relative else None
   if silent is None or not silent.is_file():
    jobs.rewind("visuals");silent=render_manim(plan,directory,quality=quality)
    jobs.complete_stage("visuals",{str(silent.relative_to(directory)):sha256_file(silent)})
  else:
   if (jobs.load() or {}).get("stage") in ("visuals","composed","technical_qa","ready"):jobs.rewind("visuals")
   silent=render_manim(plan,directory,quality=quality)
   jobs.complete_stage("visuals",{str(silent.relative_to(directory)):sha256_file(silent)})
  finished=directory/"final.mp4"
  if jobs.is_complete("composed"):
   if not finished.is_file():
    jobs.rewind("composed");mux_video(silent,wavs,timeline,subtitles,finished)
    jobs.complete_stage("composed",{"final.mp4":sha256_file(finished)})
  else:
   if (jobs.load() or {}).get("stage") in ("composed","technical_qa","ready"):jobs.rewind("composed")
   mux_video(silent,wavs,timeline,subtitles,finished)
   jobs.complete_stage("composed",{"final.mp4":sha256_file(finished)})
  width,height=(360,640) if quality=="preview" else (1080,1920)
  checks=inspect_mp4(finished,expected_width=width,expected_height=height,target_duration=total_duration)
  checks.update(scan_media_quality(finished));stills=extract_scene_stills(finished,timeline,directory)
  jobs.complete_stage("technical_qa",{"final.mp4":sha256_file(finished)})
  report=QualityReport(technical_passed=True)
  final_status="TECHNICALLY_READY" if voice=="kokoro" else "PREVIEW_ONLY"
  manifest.update({"status":final_status,"checks":checks,"quality_report":report.to_dict(),
   "voice_timing":timing_evidence,"review_frames":stills,"duration_seconds":round(total_duration,3),
   "output_sha256":sha256_file(finished),"finished_at":datetime.now(timezone.utc).isoformat()})
  _write_json(manifest_file,manifest)
  if voice=="kokoro":jobs.complete_stage("ready",{"final.mp4":sha256_file(finished)})
  return finished
 except Exception as exc:
  jobs.fail(str(exc));manifest.update({"status":"FAILED","error":str(exc),
   "finished_at":datetime.now(timezone.utc).isoformat()});_write_json(manifest_file,manifest);raise
