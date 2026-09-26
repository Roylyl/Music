"""Inspect codec and sample spectra. Flags are clues, never proof of provenance."""
from pathlib import Path
import json,numpy as np,soundfile as sf
from mutagen import File
from mutagen.wave import WAVE
R=Path(__file__).resolve().parents[1];OUT=R/'reports/audio-audit.json'
old={x['localPath']:x for x in json.loads(OUT.read_text())} if OUT.exists() else {}
results=[]
for base in ['artists','live','collections']:
 for p in (R/base).rglob('*'):
  if p.suffix.lower() not in ['.flac','.wav','.m4a','.mp3','.opus','.ogg']:continue
  rel=str(p.relative_to(R));size=p.stat().st_size
  if rel in old and old[rel].get('fileSize')==size:results.append(old[rel]);continue
  try:
   a=WAVE(p) if p.suffix.lower()=='.wav' else File(p)
   if a is None:continue
   i=a.info;codec='WAV' if isinstance(a,WAVE) else a.__class__.__name__
   if codec=='MP4':codec=getattr(i,'codec','MP4')
   if codec=='OggOpus':codec='opus'
   d={'localPath':rel,'codec':codec,'sampleRate':getattr(i,'sample_rate',48000 if codec=='opus' else None),'bitDepth':getattr(i,'bits_per_sample',None),'channels':getattr(i,'channels',None),'duration':round(i.length,3),'fileSize':size,'bitRate':getattr(i,'bitrate',None),'suspected_transcode':None,'analysisStatus':'not-applicable-lossy','evidence':[]}
   if p.suffix.lower() in ['.flac','.wav'] or codec=='alac':
    d['analysisStatus']='sampled-spectrum';ratios=[]
    try:
     with sf.SoundFile(p) as f:
      sr=f.samplerate
      if sr>=40000:
       for frac in [.25,.5,.75]:
        f.seek(min(int(len(f)*frac),max(0,len(f)-sr*12)));x=f.read(sr*12,dtype='float32',always_2d=True).mean(axis=1)
        n=4096;frames=len(x)//n
        if frames<1:continue
        spec=np.mean(abs(np.fft.rfft(x[:frames*n].reshape(frames,n)*np.hanning(n),axis=1))**2,axis=0);freq=np.fft.rfftfreq(n,1/sr)
        for cutoff in [16000,18000,20000]:
         if cutoff+1500>=sr/2:continue
         low=np.mean(spec[(freq>cutoff-1500)&(freq<cutoff-300)]);high=np.mean(spec[(freq>cutoff+300)&(freq<cutoff+1500)])
         db=float(10*np.log10((high+1e-30)/(low+1e-30)));ratios.append({'position':frac,'cutoffHz':cutoff,'dropDb':round(db,1)})
       flagged=[c for c in [16000,18000,20000] if sum(z['cutoffHz']==c and z['dropDb'] < -45 for z in ratios)>=2]
       d['suspected_transcode']=bool(flagged);d['evidence']=[{'possibleLowpassHz':c,'note':'多个抽样片段存在明显低通，可能源于有损转码，也可能源于原始录音或母带处理。'} for c in flagged];d['spectralSamples']=ratios
      else:d['analysisStatus']='sample-rate-too-low-for-heuristic'
    except Exception as e:d['analysisStatus']='analysis-unavailable';d['evidence']=[str(e)]
   results.append(d)
  except Exception as e:results.append({'localPath':rel,'fileSize':size,'error':str(e),'suspected_transcode':None})
OUT.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');print('Audited',len(results),'flagged',sum(x.get('suspected_transcode') is True for x in results))
