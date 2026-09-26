from pathlib import Path
import requests,json,time
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'reports/sources'; OUT.mkdir(parents=True,exist_ok=True)
s=requests.Session(); s.headers['User-Agent']='RoylylMusicCatalog/1.0 (personal discography research)'
def get(url,path):
 if path.exists(): return json.loads(path.read_text())
 r=s.get(url,timeout=40);r.raise_for_status();d=r.json();path.write_text(json.dumps(d,ensure_ascii=False,indent=2));time.sleep(1.1);return d
base='https://musicbrainz.org/ws/2/'
if __name__ == "__main__":
 g=get(base+'release-group?artist=e54bc357-19aa-4e1f-9795-3346e486d5db&fmt=json&limit=100',OUT/'mb-groups.json')
 for group in g['release-groups']:
  gid=group['id']; releases=get(base+f'release?release-group={gid}&fmt=json&limit=100&inc=media',OUT/f'mb-releases-{gid}.json')['releases']
  # Earliest official issue with a populated tracklist; preserve all edition metadata separately.
  if not releases:
   print(group['title'],'no releases',flush=True);continue
  ranked=sorted(releases,key=lambda r:(r.get('status')!='Official',not r.get('date'),r.get('date','9999')))
  for r in ranked:
   d=get(base+f'release/{r["id"]}?fmt=json&inc=recordings+artist-credits+release-groups',OUT/f'mb-release-{r["id"]}.json')
   if any(m.get('tracks') for m in d.get('media',[])): break
  print(group['title'],r.get('date'),sum(len(m.get('tracks',[])) for m in d.get('media',[])),flush=True)
