"""Download observed public file links, without transcoding or bypassing access controls."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests,json,time,os,wave
from bs4 import BeautifulSoup
from mutagen import File
from mutagen.wave import WAVE
import argparse
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--queue',default='reports/download-queue.json');args=p.parse_args()
Q=json.loads((R/args.queue).read_text());LOG=R/'reports/download-results.jsonl'
done={}
if LOG.exists():
 for line in LOG.read_text().splitlines():
  d=json.loads(line);done[d['trackId']]=d

def run(q):
 target=R/q['localPath'];target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists() and done.get(q['trackId'],{}).get('status')=='downloaded' and done[q['trackId']].get('sourceUrl')==q['source']['url']:return None
 if target.exists():
  n=1
  while target.with_name(target.stem+f'.alternative-{n}'+target.suffix).exists():n+=1
  target.rename(target.with_name(target.stem+f'.alternative-{n}'+target.suffix))
 src=q['source'];url=('https://drive.google.com/uc?export=download&id='+src['id']) if src.get('id') else src['url']
 result={'trackId':q['trackId'],'localPath':q['localPath'],'sourceUrl':src['url'],'provider':src['provider'],'rightsStatus':'unverified-third-party','checkedAt':'2026-09-26'}
 try:
  session=requests.Session()
  r=session.get(url,stream=True,timeout=(20,45));r.raise_for_status()
  if 'text/html' in r.headers.get('Content-Type',''):
   form=BeautifulSoup(r.text,'html.parser').find('form',id='download-form')
   if not form or form.get('action')!='https://drive.usercontent.google.com/download':raise ValueError('HTML response requires login or is not the public download confirmation')
   params={x['name']:x.get('value','') for x in form.find_all('input',attrs={'name':True})}
   r=session.get(form['action'],params=params,stream=True,timeout=(20,45));r.raise_for_status()
   if 'text/html' in r.headers.get('Content-Type',''):raise ValueError('Public download confirmation did not return a file')
  tmp=target.with_name(target.name+'.part');total=0
  with tmp.open('wb') as f:
   for b in r.iter_content(1024*256):f.write(b);total+=len(b)
  expected=r.headers.get('Content-Length')
  if expected and total!=int(expected):raise ValueError('Incomplete HTTP transfer')
  if target.suffix.lower()=='.wav':
   with wave.open(str(tmp),'rb') as w:
    if total < w.getnframes()*w.getnchannels()*w.getsampwidth()+44:raise ValueError('Source WAV is truncated relative to its PCM header')
  audio=WAVE(tmp) if target.suffix.lower()==".wav" else File(tmp)
  if audio is None:raise ValueError('Downloaded file is not recognized audio')
  info=audio.info;codec=audio.__class__.__name__;props={'codec':codec,'sampleRate':getattr(info,'sample_rate',None),'bitDepth':getattr(info,'bits_per_sample',None),'channels':getattr(info,'channels',None),'duration':round(info.length,3),'fileSize':total,'bitRate':getattr(info,'bitrate',None)}
  if codec=='MP4':props['codec']=getattr(info,'codec','MP4')
  tmp.replace(target);result.update(status='downloaded',audioProperties=props,suspected_transcode=None)
 except Exception as e:result.update(status='failed',error=str(e))
 return result
with ThreadPoolExecutor(max_workers=4) as pool:
 futures=[pool.submit(run,q) for q in Q]
 for i,f in enumerate(as_completed(futures),1):
  r=f.result()
  if r:
   with LOG.open('a') as out:out.write(json.dumps(r,ensure_ascii=False)+'\n')
   print(i,r['status'],r['localPath'],r.get('error',''),flush=True)
