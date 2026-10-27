import asyncio, json, logging, os, shutil, subprocess, tempfile, time, uuid, threading
from pathlib import Path
from typing import Optional
import librosa, numpy as np, soundfile as sf
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=os.getenv('LOG_LEVEL','INFO'), format='%(asctime)s %(levelname)s %(message)s')
log=logging.getLogger('studio')
ROOT=Path(__file__).resolve().parent
DATA=Path(os.getenv('AUDIO_DATA_DIR',ROOT/'data')); DATA.mkdir(parents=True,exist_ok=True)
MAX=int(os.getenv('MAX_UPLOAD_MB','250'))*1024*1024
MODEL=os.getenv('DEMUCS_MODEL','htdemucs_ft'); ALLOWED={'.mp3','.wav','.flac','.m4a','.aac','.ogg','.webm'}
app=FastAPI(title='Sonder Audio API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173,http://localhost:8000').split(','),allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
jobs={}; lock=threading.Semaphore(max(1,int(os.getenv('JOB_WORKERS','1'))))

def fb():
    bucket=os.getenv('FIREBASE_STORAGE_BUCKET')
    if not bucket: return None,None
    import firebase_admin
    from firebase_admin import firestore,storage
    if not firebase_admin._apps: firebase_admin.initialize_app(options={'storageBucket':bucket})
    return firestore.client(),storage.bucket()

def persist(jid,fields):
    jobs.setdefault(jid,{}).update(fields)
    try:
        db,_=fb()
        if db: db.collection('jobs').document(jid).set({**fields,'updatedAt':time.time()},merge=True)
    except Exception: log.exception('Firestore status write failed')

def run(args,timeout=3600):
    log.info('RUN %s',' '.join(map(str,args)))
    proc=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=timeout)
    if proc.returncode: raise RuntimeError((proc.stderr or proc.stdout or 'Process failed')[-4000:])
    return proc.stdout

def analyze(path):
    y,sr=librosa.load(str(path),sr=22050,mono=True,duration=600)
    tempo,frames=librosa.beat.beat_track(y=y,sr=sr,units='frames')
    bpm=float(np.asarray(tempo).reshape(-1)[0]); beats=librosa.frames_to_time(frames,sr=sr)
    onset=librosa.onset.onset_detect(y=y,sr=sr,units='frames'); ons=librosa.frames_to_time(onset,sr=sr)
    return {'bpm':round(bpm,2) if bpm else None,'beatCount':len(beats),'durationSeconds':round(len(y)/sr,2),'firstBeatSeconds':float(beats[0]) if len(beats) else 0,'firstOnsetSeconds':float(ons[0]) if len(ons) else 0}

def device():
    import torch
    forced=os.getenv('DEMUCS_DEVICE','auto')
    return ('cuda' if torch.cuda.is_available() else 'cpu') if forced=='auto' else forced

def process(jid,owner,src,kind,vocal_src):
    folder=DATA/jid; folder.mkdir(parents=True,exist_ok=True)
    try:
      with lock:
        persist(jid,{'status':'processing','progress':8,'stage':'Validating audio','error':None})
        input_wav=folder/'source.wav'
        run(['ffmpeg','-nostdin','-y','-i',src,'-map','0:a:0','-vn','-ac','2','-ar','44100','-c:a','pcm_s24le',input_wav],600)
        duration=json.loads(run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',input_wav])).get('format',{}).get('duration')
        if not duration or float(duration)>1800: raise ValueError('Audio must be valid and no longer than 30 minutes')
        stems={}; analysis={}
        original_ref=None
        db,bucket=fb()
        if bucket:
          original_blob=bucket.blob(f'users/{owner}/jobs/{jid}/original{Path(src).suffix.lower()}'); original_blob.upload_from_filename(src); original_ref=original_blob.name
        if db:
          db.collection('users').document(owner).set({'uid':owner,'lastSeenAt':time.time()},merge=True)
        persist(jid,{'originalRef':original_ref,'owner':owner,'filename':Path(src).name})
        if kind in ('separate','separate-and-mix'):
          persist(jid,{'status':'separating','progress':15,'stage':'Separating with '+MODEL})
          output=folder/'stems'; run([os.sys.executable,'-m','demucs','-n',MODEL,'--device',device(),'--shifts','2','--overlap','0.5','-o',output,input_wav],21600)
          stem_dir=output/MODEL/'source';
          for name in ('vocals','drums','bass','other'):
            p=stem_dir/(name+'.wav')
            if not p.is_file() or p.stat().st_size<1000: raise RuntimeError('Demucs did not produce a valid '+name+' stem')
            saved=folder/(name+'.wav'); shutil.copy2(p,saved); stems[name]=saved
          inst=folder/'instrumental.wav'
          import torchaudio
          waves=[torchaudio.load(str(stems[n])) for n in ('drums','bass','other')]
          total=min(w.shape[1] for w,s in waves); mix=sum(w[:,:total] for w,s in waves); peak=float(mix.abs().max())
          if peak>0.98: mix*=0.98/peak
          torchaudio.save(str(inst),mix,waves[0][1],encoding='PCM_S',bits_per_sample=24); stems['instrumental']=inst
          analysis=analyze(input_wav)
          persist(jid,{'progress':66,'stage':'Validating stems and analyzing beat','analysis':analysis})
        if kind in ('mix','separate-and-mix'):
          persist(jid,{'status':'mixing','progress':73,'stage':'Aligning vocal and mixing'})
          vocal=Path(vocal_src) if vocal_src else stems.get('vocals')
          instrumental=stems.get('instrumental') or Path(src)
          if not vocal or not Path(vocal).is_file(): raise ValueError('A vocal recording is required for mixing')
          vocal_pcm=folder/'mix-vocal.wav'; instrumental_pcm=folder/'mix-instrumental.wav'
          run(['ffmpeg','-nostdin','-y','-i',vocal,'-map','0:a:0','-vn','-ac','2','-ar','44100','-c:a','pcm_s24le',vocal_pcm],600)
          run(['ffmpeg','-nostdin','-y','-i',instrumental,'-map','0:a:0','-vn','-ac','2','-ar','44100','-c:a','pcm_s24le',instrumental_pcm],600)
          va,ia=analyze(vocal_pcm),analyze(instrumental_pcm); v,sr=librosa.load(str(vocal_pcm),sr=44100,mono=False)
          if va['bpm'] and ia['bpm'] and .8<=ia['bpm']/va['bpm']<=1.25: v=librosa.effects.time_stretch(v,rate=ia['bpm']/va['bpm'])
          v=v.T if v.ndim==2 else np.column_stack((v,v)); inst,sri=sf.read(str(instrumental),dtype='float32',always_2d=True)
          if sr!=sri: v=librosa.resample(v.T,orig_sr=sr,target_sr=sri).T
          offset=max(0,int((ia['firstBeatSeconds']-va['firstOnsetSeconds'])*sri)); out=np.zeros((max(len(inst),offset+len(v)),2),np.float32)
          out[:len(inst)]+=inst*.78; out[offset:offset+len(v)]+=v*.72; peak=float(np.max(np.abs(out)))
          if peak: out*=min(1,.98/peak)
          wav=folder/'final.wav'; mp3=folder/'final.mp3'; sf.write(wav,out,sri,subtype='PCM_24')
          run(['ffmpeg','-nostdin','-y','-i',wav,'-codec:a','libmp3lame','-b:a','320k',mp3],600)
          run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',mp3],60)
          analysis={'vocal':va,'instrumental':ia,'tempoRatio':round(ia['bpm']/va['bpm'],3) if va['bpm'] and ia['bpm'] else None,'alignment':'Pitch-preserving tempo stretch and onset-to-first-beat offset'}
          stems['final-wav']=wav; stems['final-mp3']=mp3
        persist(jid,{'progress':85,'stage':'Uploading verified outputs','analysis':analysis})
        refs={}
        try:
          db,bucket=fb()
          if bucket:
            for name,path in stems.items():
              blob=bucket.blob(f'users/{owner}/jobs/{jid}/{name}{path.suffix}'); blob.upload_from_filename(str(path)); refs[name]=blob.name
          else: refs={name:f'/api/jobs/{jid}/files/{name}' for name in stems}
        except Exception: raise
        # Expose local files only when Firebase is not configured.
        persist(jid,{'status':'completed','progress':100,'stage':'Ready','files':refs,'completedAt':time.time(),'analysis':analysis,'downloadable':True})
        log.info('Job %s completed with files=%s',jid,list(refs))
    except Exception as exc:
      log.exception('Job %s failed',jid); persist(jid,{'status':'failed','progress':0,'stage':'Failed','error':str(exc)[:2000],'failedAt':time.time()})
    finally:
      # Keep outputs for local playback. Temporary intermediate conversion and Demucs files are discarded after success.
      if jobs.get(jid,{}).get('status')=='completed':
        shutil.rmtree(folder/'stems',ignore_errors=True); (folder/'source.wav').unlink(missing_ok=True); (folder/('upload'+Path(src).suffix.lower())).unlink(missing_ok=True); (folder/'vocal'+Path(vocal_src).suffix.lower()).unlink(missing_ok=True) if vocal_src else None; (folder/'mix-vocal.wav').unlink(missing_ok=True); (folder/'mix-instrumental.wav').unlink(missing_ok=True)
        if os.getenv('FIREBASE_STORAGE_BUCKET'):
          for artifact in Path(folder).glob('*.wav'): artifact.unlink(missing_ok=True)
          (folder/'final.mp3').unlink(missing_ok=True)

@app.get('/api/health')
def health(): return {'ok':True,'model':MODEL,'firebaseConfigured':bool(os.getenv('FIREBASE_STORAGE_BUCKET'))}

@app.post('/api/jobs')
async def create_job(background:BackgroundTasks, audio:UploadFile=File(...), vocal:Optional[UploadFile]=File(None), kind:str=Form('separate'), authorization:Optional[str]=Header(None)):
    owner='local'
    if os.getenv('FIREBASE_STORAGE_BUCKET'):
      try:
        from firebase_admin import auth
        token=(authorization or '').replace('Bearer ',''); owner=auth.verify_id_token(token)['uid']
      except Exception: raise HTTPException(401,'Sign in with Firebase before uploading')
    ext=Path(audio.filename or '').suffix.lower()
    if ext not in ALLOWED: raise HTTPException(415,'Use MP3, WAV, FLAC, M4A, AAC or OGG audio')
    if kind not in ('separate','mix','separate-and-mix'): raise HTTPException(400,'Unsupported job type')
    jid=uuid.uuid4().hex; folder=DATA/jid; folder.mkdir(parents=True,exist_ok=True)
    source=folder/('upload'+ext); size=0
    try:
      with source.open('wb') as out:
        while chunk:=await audio.read(1024*1024):
          size+=len(chunk)
          if size>MAX: raise HTTPException(413,f'Upload exceeds {MAX//1048576} MB')
          out.write(chunk)
      if size<1024: raise HTTPException(400,'File is empty or too small to be audio')
      vocal_path=None
      if vocal:
        if Path(vocal.filename or '').suffix.lower() not in ALLOWED: raise HTTPException(415,'Unsupported vocal file type')
        vocal_path=folder/('vocal'+Path(vocal.filename).suffix.lower()); vsize=0
        with vocal_path.open('wb') as out:
          while chunk:=await vocal.read(1024*1024):
            vsize+=len(chunk)
            if vsize>MAX: raise HTTPException(413,'Vocal file exceeds upload size limit')
            out.write(chunk)
      if kind=='mix' and not vocal_path: raise HTTPException(400,'Upload a vocal recording to mix')
      jobs[jid]={'id':jid,'owner':owner,'status':'queued','progress':0,'stage':'Queued','createdAt':time.time(),'filename':audio.filename,'files':{}}
      persist(jid,jobs[jid]); background.add_task(process,jid,owner,str(source),kind,str(vocal_path) if vocal_path else None)
      return {'id':jid,'status':'queued'}
    except Exception:
      shutil.rmtree(folder,ignore_errors=True); raise

@app.get('/api/jobs/{jid}')
def status(jid:str,authorization:Optional[str]=Header(None)):
    job=jobs.get(jid)
    if not job:
      try:
        db,_=fb(); doc=db.collection('jobs').document(jid).get() if db else None; job=doc.to_dict() if doc and doc.exists else None
      except Exception: job=None
    if not job: raise HTTPException(404,'Job not found or expired')
    if os.getenv('FIREBASE_STORAGE_BUCKET'):
      try:
        from firebase_admin import auth
        if auth.verify_id_token((authorization or '').replace('Bearer ',''))['uid']!=job['owner']: raise HTTPException(403,'Forbidden')
      except HTTPException: raise
      except Exception: raise HTTPException(401,'Authentication required')
    return job

@app.get('/api/jobs/{jid}/files/{name}')
def download(jid:str,name:str,authorization:Optional[str]=Header(None)):
    job=jobs.get(jid)
    if not job:
      try:
        db,_=fb(); doc=db.collection('jobs').document(jid).get() if db else None; job=doc.to_dict() if doc and doc.exists else {}
      except Exception: job={}
    if job.get('status')!='completed': raise HTTPException(409,'Output is not ready')
    if os.getenv('FIREBASE_STORAGE_BUCKET'):
      try:
        from firebase_admin import auth
        if auth.verify_id_token((authorization or '').replace('Bearer ',''))['uid']!=job['owner']: raise HTTPException(403,'Forbidden')
      except HTTPException: raise
      except Exception: raise HTTPException(401,'Authentication required')
    path=DATA/jid/name
    if not path.is_file():
      # Map named artifact directly; reject path traversal.
      mapping={'vocals':'vocals.wav','drums':'drums.wav','bass':'bass.wav','other':'other.wav','instrumental':'instrumental.wav','final-wav':'final.wav','final-mp3':'final.mp3'}
      artifact=mapping.get(name)
      if not artifact: raise HTTPException(404,'File not found')
      candidate=DATA/jid/artifact
      if candidate.is_file(): path=candidate
      else:
        _,bucket=fb(); ref=job.get('files',{}).get(name)
        if bucket and ref:
          url=bucket.blob(ref).generate_signed_url(version='v4',expiration=3600,method='GET')
          from fastapi.responses import RedirectResponse
          return RedirectResponse(url)
        raise HTTPException(404,'File not found')
    return FileResponse(path,filename=path.name,media_type='audio/wav' if path.suffix=='.wav' else 'audio/mpeg')
