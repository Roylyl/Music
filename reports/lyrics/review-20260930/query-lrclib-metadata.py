import json,pathlib,urllib.request,urllib.parse,concurrent.futures,collections
root=pathlib.Path(__file__).resolve().parents[3];out=root/'reports/lyrics/review-20260930';missing=json.loads((out/'missing-tracks.json').read_text());itunes={x['trackId']:x for x in json.loads((out/'itunes-hk-metadata.json').read_text())};old={x['trackId']:x for x in json.loads((root/'reports/lyrics/supplement-20260929-r3/lrclib-probe.json').read_text())['results']};tasks=[];rows=[]
for t in missing:
 if (root/pathlib.Path(t['src']).with_suffix('.lrc')).exists():continue
 candidates=[x for x in itunes[t['id']]['candidates'] if x['albumMatches'] and x['durationDifferenceSeconds']<=2]
 record={'trackId':t['id'],'title':t['title'],'artist':t['artist'],'album':t['album'],'previousProbe':old.get(t['id']),'copyPermission':'not-established','imported':False}
 if candidates:tasks.append((t,candidates[0],record))
 else:record['status']='previous-evidence-retained';rows.append(record)
def probe(task):
 t,c,record=task;url='https://lrclib.net/api/get?'+urllib.parse.urlencode({'track_name':c['trackName'],'artist_name':c['artistName'],'album_name':c['collectionName'],'duration':round(t['duration'])});record['queryUrl']=url
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'RoylylMusicSourceReview/1.0'}),timeout=10) as response:d=json.load(response)
  record['entry']={k:d.get(k) for k in ['id','trackName','artistName','albumName','duration','instrumental']};record['entry']['hasSyncedLyrics']=bool(d.get('syncedLyrics'));record['entry']['hasPlainLyrics']=bool(d.get('plainLyrics'));record['entry']['url']='https://lrclib.net/'+str(d.get('id'));record['status']='exact-api-candidate'
 except Exception as e:record['status']='exact-api-unavailable';record['error']=str(e)
 return record
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
 for index,record in enumerate(executor.map(probe,tasks),1):
  rows.append(record)
  if index%10==0:print('LRCLIB metadata',index,'/',len(tasks),flush=True)
(out/'lyric-source-worklist.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print('DONE',collections.Counter(r['status'] for r in rows),flush=True)
