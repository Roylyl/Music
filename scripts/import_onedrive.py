from pathlib import Path
import json,re,shutil
from mutagen import File
from opencc import OpenCC
R=Path(__file__).resolve().parents[1];cc=OpenCC('t2s');lib=json.loads((R/'library.json').read_text());base=Path.home()/'Library/CloudStorage/OneDrive-个人/音乐'
def norm(s):
 s=cc.convert(s).lower();s=re.sub(r'[（(].*?[）)]','',s);return re.sub(r'[\s，,、·。:：/／&＋+~～《》-]','',s)
files=list((base/'音乐工程/李志').glob('*.flac'))+list((base/'音频资源/音频').glob('*李志*.flac'))
log=R/'reports/local-import-results.jsonl';seen=set()
for p in files:
 a=File(p);tag=a.tags or {};album=(tag.get('album') or [''])[0];title=(tag.get('title') or [p.stem])[0]
 album={'李志 1701':'1701','看见  李志2015巡回演唱会':'看见','勾三搭四 CD2':'勾三搭四','In Love with Nanjing (我爱南京)':'我爱南京'}.get(album,album)
 if 'Sky City' in title:title='天空之城'
 if 'Re He Road' in title:title=title.replace('Re He Road','')
 matches=[(al,t) for al in lib['albums'] for t in al['tracks'] if norm(al['title'])==norm(album) and norm(t['title'])==norm(title)]
 if len(matches)!=1:continue
 al,t=matches[0]
 if t['id'] in seen:continue
 seen.add(t['id']);safe=re.sub(r'[/\\:*?"<>|]','_',t['title']);dest=R/al['path']/f'{t["discNumber"]:02}-{t["trackNumber"]:02} - {safe}.flac'
 shutil.copyfile(p,dest);i=a.info
 entry={'trackId':t['id'],'localPath':str(dest.relative_to(R)),'sourceUrl':'','sourceFileName':p.name,'provider':'OneDrive user library','rightsStatus':'user-provided-unverified','status':'downloaded','audioProperties':{'codec':'FLAC','sampleRate':i.sample_rate,'bitDepth':i.bits_per_sample,'channels':i.channels,'duration':round(i.length,3),'fileSize':dest.stat().st_size,'bitRate':i.bitrate},'suspected_transcode':None}
 with log.open('a') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
print('Imported',len(seen),'FLAC files')
