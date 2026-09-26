"""Keep the fan site's 26-track Washing edition distinct from the 22-track index."""
from pathlib import Path
from collections import Counter
import json
R=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
lib=load(R/'library.json');fs=next(g for g in load(R/'reports/sources/fan-catalog.json') if g and g[0]['album']=='洗心革面 跨年音乐会');aid='lizhi-washing-2019-fan-26'
if not any(a['id']==aid for a in lib['albums']):
 title='洗心革面（歌迷站26轨版）';path='live/李志/2019 - 洗心革面（歌迷站26轨版）'
 a={'id':aid,'artist':'李志','title':title,'releaseDate':None,'releaseDatePrecision':'unknown','year':2019,'eventDate':'2018-12-31','type':'special','path':path,'cover':'','coverWeb':'','tracks':[],'sources':[fs[0]['seo_url'],'https://www.lizhinb.com/xixingemian-lizhi2019kuanianyinlehui/'],'notes':['网站26轨分段与另一个22轨目录不同，独立保存曲序与串烧，不互相冒充。','正式发行日期及权利状态未确认。'],'metadataStatus':'provisional','editions':[],'officialReleaseConfirmed':False,'tracklistStatus':'third-party-listed','relatedReleaseId':'lizhi-2faf828e-04f3-4410-9a84-e88c547ffdda'}
 for i,f in enumerate(fs,1):
  a['tracks'].append({'id':f'{aid}-d01-t{i:02}','artist':'李志','album':title,'title':f['title'],'discNumber':1,'trackNumber':i,'sequenceNumber':i,'duration':None,'durationSource':'','sourceStatus':'streaming-only','sourceUrl':f['seo_url'],'format':'','localPath':'','sources':[{'provider':'lizhinb.com','url':f['seo_url'],'status':'streaming-only','checkedAt':'2026-09-27'}],'suspected_transcode':None,'audioProperties':None,'searchStatus':'catalog-checked','versionMatch':'same-fan-edition-track'})
 a['trackCount']=len(a['tracks']);save(R/path/'album.json',a);lib['albums'].append(a)
lib['albums'].sort(key=lambda a:(a['releaseDate'] or a.get('eventDate') or '9999',a['title']))
lib['summary'].update(albums=len(lib['albums']),tracks=sum(len(a['tracks']) for a in lib['albums']),types=dict(Counter(a['type'] for a in lib['albums'])))
save(R/'library.json',lib);print(lib['summary']['albums'],lib['summary']['tracks'])
