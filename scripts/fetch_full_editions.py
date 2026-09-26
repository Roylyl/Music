from fetch_catalog import get,base,OUT
import json
for p in sorted(OUT.glob('mb-releases-*.json')):
 rs=json.loads(p.read_text())['releases']
 if not rs: continue
 def score(r):
  return (sum(m.get('track-count',0) for m in r.get('media',[])),r.get('status')=='Official')
 r=max(rs,key=score)
 d=get(base+f'release/{r["id"]}?fmt=json&inc=recordings+artist-credits+release-groups',OUT/f'mb-release-{r["id"]}.json')
 print(d['title'],score(r),flush=True)
