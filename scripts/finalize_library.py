from pathlib import Path
from collections import Counter,defaultdict
import json
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
lib=read(R/'library.json');acq=defaultdict(dict)
for name in ['download-results.jsonl','local-import-results.jsonl','youtube-import-results.jsonl','mp3-normalization-results.jsonl']:
 p=R/'reports'/name
 if not p.exists():continue
 for l in p.read_text().splitlines():
  d=json.loads(l)
  if d['status']=='downloaded' and (R/d['localPath']).exists():acq[d['trackId']][d['localPath']]=d
quality={x['localPath']:x for x in read(R/'reports/audio-audit.json')} if (R/'reports/audio-audit.json').exists() else {}
for a in lib['albums']:
 for t in a['tracks']:
  assets=list(acq[t['id']].values())
  for x in assets:
   if x['localPath'] in quality:
    q=quality[x['localPath']];x['audioProperties']={k:q.get(k) for k in ['codec','sampleRate','bitDepth','channels','duration','fileSize','bitRate']};x['suspected_transcode']=q['suspected_transcode'];x['qualityAudit']=q.get('analysisStatus')
   x['redistributionAllowed']=False
  def rank(x):
   p=x['audioProperties'];lossless=(p.get('codec') or '').lower() in ['flac','wave','wav','alac','pcm_s16le','pcm_s24le'];return (lossless,x.get('suspected_transcode') is not True,p.get('bitDepth') or 0,p.get('sampleRate') or 0,p.get('bitRate') or 0)
  assets.sort(key=rank,reverse=True);t['assets']=assets
  if assets:
   x=assets[0];t.update(sourceStatus='available',sourceUrl=x['sourceUrl'],format=x['audioProperties']['codec'],localPath=x['localPath'],audioProperties=x['audioProperties'],suspected_transcode=x.get('suspected_transcode'),rightsStatus=x['rightsStatus'],redistributionAllowed=False)
   t['versionReviewRequired']=False
   if x.get('segment'):t['segment']=x['segment'];t['versionReviewRequired']=True;t['versionReviewReason']='分段时间来自视频上传者章节，尚未逐首试听核对边界。'
   t['catalogDuration']=t.get('catalogDuration',t['duration']);t['duration']=x['audioProperties']['duration'];t['durationSource']='local-file'
   ref=t['catalogDuration']
   if ref and abs(ref-t['duration'])>max(5,ref*.03):t['versionReviewRequired']=True;t['versionReviewReason']='本地文件与所选版本曲目时长差异超过5秒或3%，需试听核对。'
  elif t.get('localPath'):
   offers=[o for o in t.get('sources',[]) if o.get('status') in ['purchasable','streaming-only']]
   offer=next((o for o in offers if o['status']=='purchasable'),offers[0] if offers else {})
   t.update(localPath='',format='',audioProperties=None,sourceStatus=offer.get('status','missing'),sourceUrl=offer.get('url',''),duration=t.get('catalogDuration',t['duration']),versionReviewRequired=False)
  # Guest performers are not silently credited to Li Zhi.
  if 'ボーカル：' in t['title']:t['performerCredit']=t['title'].split('ボーカル：')[1];t['albumArtist']='李志';t['artist']=t['performerCredit'].replace('・',' / ')
 rp=R/a['path']/'recording.json'
 if rp.exists():a['fullRecordings']=[read(rp)]
 write(R/a['path']/'album.json',a)
tracks=[t for a in lib['albums'] for t in a['tracks']]
lib['statusDefinitions']['missing']='已核来源中尚无可确认的对应数字音轨；不代表全网不存在。'
lib['statusDefinitions']['streaming-only']='找到对应播放入口，尚未取得独立本地音轨。'
lib['statusDefinitions']['available']='已取得可读取的本地文件，授权状态见rightsStatus；不等同于允许公开再分发。'
lib['summary'].update(status=dict(Counter(t['sourceStatus'] for t in tracks)),localTracks=sum(bool(t['localPath']) for t in tracks),localFormats=dict(Counter(t['format'] for t in tracks if t['localPath'])),assetBytes=sum(x['audioProperties']['fileSize'] for t in tracks for x in t.get('assets',[])),suspectedTranscodes=sum(t.get('suspected_transcode') is True for t in tracks))
write(R/'stream/links.json',[{'id':t['id'],'album':t['album'],'title':t['title'],'status':src['status'],'url':src['url']} for t in tracks for src in t.get('sources',[]) if src.get('status') in ['purchasable','streaming-only'] and src.get('url')]);
write(R/'library.json',lib);write(R/'reports/missing.json',[{'id':t['id'],'album':t['album'],'title':t['title'],'sourceStatus':t['sourceStatus'],'sourceUrl':t['sourceUrl']} for t in tracks if not t['localPath']]);write(R/'reports/version-review.json',[{'id':t['id'],'album':t['album'],'title':t['title'],'catalogDuration':t['catalogDuration'],'fileDuration':t['duration'],'path':t['localPath']} for t in tracks if t.get('versionReviewRequired')]);print(json.dumps(lib['summary'],ensure_ascii=False))
