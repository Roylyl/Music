from pathlib import Path
import json
from mutagen.wave import WAVE
R=Path(__file__).resolve().parents[1];log=R/'reports/download-results.jsonl';last={}
for line in log.read_text().splitlines():
 d=json.loads(line);last[d['trackId']]=d
n=0
for d in last.values():
 if d.get('error')!='Downloaded file is not recognized audio' or not d['localPath'].endswith('.wav'):continue
 p=R/(d['localPath']+'.part')
 if not p.exists():continue
 a=WAVE(p);i=a.info
 # Check PCM byte count: a truncated transfer must not be promoted.
 import wave
 with wave.open(str(p),'rb') as w:expected=w.getnframes()*w.getnchannels()*w.getsampwidth()
 if p.stat().st_size<expected+44:continue
 dest=R/d['localPath'];p.replace(dest);d.pop('error',None);d.update(status='downloaded',suspected_transcode=None,audioProperties={'codec':'WAV','sampleRate':i.sample_rate,'bitDepth':i.bits_per_sample,'channels':i.channels,'duration':round(i.length,3),'fileSize':dest.stat().st_size,'bitRate':i.bitrate})
 with log.open('a') as f:f.write(json.dumps(d,ensure_ascii=False)+'\n')
 n+=1
print('Recovered without re-downloading:',n)
