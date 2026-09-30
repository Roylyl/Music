import json,re,urllib.request,urllib.parse,concurrent.futures,pathlib,collections
from opencc import OpenCC
root=pathlib.Path(__file__).resolve().parents[3];out=root/'reports/lyrics/review-20260930';ts=json.loads((out/'missing-tracks.json').read_text());cc=OpenCC('t2s');norm=lambda s:re.sub(r'[^\w\u4e00-\u9fff]','',cc.convert(str(s)).casefold())
groups=collections.defaultdict(list)
for t in ts:groups[t['artist']].append(t)
# One metadata-only iTunes search per artist, no lyric bodies or music downloads.
def search(pair):
 artist,tracks=pair;url='https://itunes.apple.com/search?'+urllib.parse.urlencode({'term':artist,'entity':'song','country':'HK','limit':200})
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'RoylylMusicMetadataReview/1.0'}),timeout=12) as response:entries=json.load(response).get('results',[])
  rows=[]
  for t in tracks:
   matches=[]
   for e in entries:
    if norm(e.get('trackName'))!=norm(t['title']):continue
    if not any(norm(a) in norm(e.get('artistName')) for a in re.split(r'\s*&\s*|\s*/\s*',artist)):continue
    matches.append({k:e.get(k) for k in ['trackId','trackName','artistName','collectionName','trackTimeMillis','releaseDate','trackViewUrl','collectionViewUrl']})
   for e in matches:e['durationDifferenceSeconds']=round(abs((e.get('trackTimeMillis')or 0)/1000-t['duration']),3);e['albumMatches']=norm(e['collectionName'])==norm(t['album'])
   matches.sort(key=lambda e:(not e['albumMatches'],e['durationDifferenceSeconds']))
   rows.append({'trackId':t['id'],'title':t['title'],'artist':artist,'album':t['album'],'source':'iTunes Search','queryUrl':url,'candidates':matches[:5],'status':'metadata-candidate' if matches else 'no-exact-title-match'})
  return rows
 except Exception as e:return [{'trackId':t['id'],'title':t['title'],'artist':artist,'queryUrl':url,'status':'request-error','error':str(e),'candidates':[]} for t in tracks]
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
 for rows in executor.map(search,groups.items()):
  results+=rows
  print(rows[0]['artist'],len(rows),'tracks',sum(bool(r['candidates']) for r in rows),'metadata matches',flush=True)
(out/'itunes-hk-metadata.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print('DONE',len(results),sum(bool(r['candidates']) for r in results),'matches',flush=True)
