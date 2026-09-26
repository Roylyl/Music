"""Add three separately documented concert recordings from the public fan catalog."""
from pathlib import Path
from collections import Counter
import json
R=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
lib=load(R/'library.json');fan=load(R/'reports/sources/fan-catalog.json')
entries=[
 ('义乌隔壁酒吧','2009-12-31',2009,'https://ent.sina.com.cn/y/2009-09-24/09372711414.shtml','2009年12月31日义乌隔壁酒吧演出。'),
 ('挺 不插电巡演 郑州站',None,2014,'https://audiomack.com/hasmanafuture/album/ting-bu-cha-dian-xun-yan-zheng-zhou-zhan','2014年《挺》巡演郑州站；具体演出日尚待核对。'),
 ('杭州酒球会一身酒气','2015-08-07',2015,'https://www.youtube.com/watch?v=2QA5TbRMjx4','2015年8月7日杭州酒球会“一身酒气”演出；8月8日亦有演出，歌迷站分轨属于哪场尚待核。')]
for name,event_date,year,event_source,note in entries:
 fs=next(group for group in fan if group and group[0]['album']==name)
 aid={'义乌隔壁酒吧':'lizhi-yiwu-2009','挺 不插电巡演 郑州站':'lizhi-ting-zhengzhou-2014','杭州酒球会一身酒气':'lizhi-hangzhou-2015'}[name]
 if any(a['id']==aid for a in lib['albums']):continue
 path=f'live/李志/{year} - {name}'
 album={'id':aid,'artist':'李志','title':name,'releaseDate':None,'releaseDatePrecision':'unknown','year':year,'eventDate':event_date,'type':'concert','path':path,'cover':'','coverWeb':'','tracks':[],'sources':[fs[0]['seo_url'],event_source],'notes':[note,'歌迷站整理的独立分轨录音；正式发行未确认。'],'metadataStatus':'provisional','editions':[],'officialReleaseConfirmed':False,'tracklistStatus':'third-party-listed'}
 for i,f in enumerate(fs,1):
  album['tracks'].append({'id':f'{aid}-d01-t{i:02}','artist':'李志','album':name,'title':f['title'],'discNumber':1,'trackNumber':i,'sequenceNumber':i,'duration':None,'durationSource':'','sourceStatus':'streaming-only','sourceUrl':f['seo_url'],'format':'','localPath':'','sources':[{'provider':'lizhinb.com','url':f['seo_url'],'status':'streaming-only','checkedAt':'2026-09-27'}],'suspected_transcode':None,'audioProperties':None,'searchStatus':'catalog-checked','versionMatch':'same-fan-catalog-title'})
 album['trackCount']=len(album['tracks']);save(R/path/'album.json',album);lib['albums'].append(album)
lib['albums'].sort(key=lambda a:(a['releaseDate'] or a.get('eventDate') or '9999',a['title']))
lib['summary'].update(albums=len(lib['albums']),tracks=sum(len(a['tracks']) for a in lib['albums']),types=dict(Counter(a['type'] for a in lib['albums'])))
save(R/'library.json',lib);print(lib['summary']['albums'],lib['summary']['tracks'])
