"""Copy original compressed packets at uploader-provided chapter boundaries."""
from pathlib import Path
import json,re,subprocess
from mutagen import File
import imageio_ffmpeg
R=Path(__file__).resolve().parents[1];lib=json.loads((R/'library.json').read_text());log=R/'reports/youtube-import-results.jsonl'
def norm(t):return re.sub(r'[\s，,、+&／/_-]','',t.replace('想起了他','想起了她').replace('董卓谣','董卓瑶'))
n=0
for a in lib['albums']:
 p=R/a['path']/'recording.json'
 if not p.exists():continue
 info=json.loads(p.read_text());files=info.get('localFiles',[])
 if not files:continue
 for ch in info.get('chapters') or []:
  matches=[t for t in a['tracks'] if norm(t['title'])==norm(ch['title'])]
  if len(matches)!=1:continue
  t=matches[0];suffix='.opus' if info['acodec']=='opus' else '.m4a' if info['acodec'].startswith('mp4a') else None
  if not suffix:continue
  safe=re.sub(r'[/\\:*?"<>|]','_',t['title']);out=R/a['path']/f'{t["discNumber"]:02}-{t["trackNumber"]:02} - {safe}{suffix}'
  if out.exists():continue
  subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-ss',str(ch['start_time']),'-i',str(R/files[0]),'-t',str(ch['end_time']-ch['start_time']),'-map','0:a:0','-c:a','copy',str(out)],check=True)
  f=File(out);i=f.info
  entry={'trackId':t['id'],'localPath':str(out.relative_to(R)),'sourceUrl':info['webpage_url'],'provider':'YouTube','status':'downloaded','rightsStatus':'unverified-third-party','suspected_transcode':None,'segment':{'start':ch['start_time'],'end':ch['end_time'],'boundarySource':'video uploader chapters','boundaryVerifiedByListening':False},'audioProperties':{'codec':info['acodec'],'sampleRate':info.get('asr'),'bitDepth':None,'channels':getattr(i,'channels',None),'duration':round(i.length,3),'fileSize':out.stat().st_size,'bitRate':round(info['abr']*1000) if info.get('abr') else None}}
  with log.open('a') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
  n+=1
print('Split without re-encoding:',n)
