"""Add documented collaborations and clearly identified unofficial concert editions."""
from pathlib import Path
import json,copy
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
l=read(R/'library.json');fan=read(R/'reports/sources/fan-catalog.json')
for title,aid,date,year,kind,credit,note,source in [
 ('金城兰州','lizhi-jincheng-lanzhou','2018-08',2018,'single','老狼 / 李志 / 张玮玮','2018年8月已发布；第三方目录另称2018-08-06，具体日尚待原始公告。','https://gansu.gscn.com.cn/system/2018/08/31/012007272.shtml'),
 ('叁缺壹吉隆坡站','lizhi-kuala-lumpur-2025',None,2025,'concert','李志','歌迷站30轨演出录音；2025年11月演出，具体场次和公开流通日期待核，不作为正式发行专辑。','https://www.lizhinb.com/gequ/?oa_album=72')]:
 if any(a['id']==aid for a in l['albums']):continue
 fs=next(a for a in fan if a and a[0]['album']==title)
 folder=('artists' if kind=='single' else 'live')+f'/李志/{year} - {title}'
 a={'id':aid,'artist':credit,'albumArtist':'李志','title':title,'releaseDate':date,'releaseDatePrecision':'month' if date else 'unknown','year':year,'type':kind,'path':folder,'cover':'','coverWeb':'','tracks':[],'sources':[source,fs[0]['seo_url']],'notes':[note],'metadataStatus':'provisional','editions':[],'officialReleaseConfirmed':kind=='single','tracklistStatus':'third-party-listed'}
 for i,f in enumerate(fs,1):a['tracks'].append({'id':f'{aid}-d01-t{i:02}','artist':credit,'album':'金城兰州' if kind=='single' else title,'title':f['title'],'discNumber':1,'trackNumber':i,'sequenceNumber':i,'duration':None,'durationSource':'','sourceStatus':'streaming-only','sourceUrl':f['seo_url'],'format':'','localPath':'','sources':[{'provider':'lizhinb.com','url':f['seo_url'],'status':'streaming-only','checkedAt':'2026-09-26'}],'suspected_transcode':None,'audioProperties':None,'searchStatus':'catalog-checked','versionMatch':'unconfirmed'})
 a['trackCount']=len(a['tracks']);write(R/folder/'album.json',a);l['albums'].append(a)
for a in l['albums']:
 if a['title']=='1701':
  u='https://music.douban.com/review/7191243/'
  if u not in a['sources']:a['sources'].append(u)
 if a['title']=='我们也爱南京':a['expectedTrackCount']=40;a['missingTracklistCount']=40
 if a['title']=='洗心革面 - 演唱会录音':
  fs=next(x for x in fan if x and x[0]['album']=='洗心革面 跨年音乐会')
  e={'provider':'lizhinb.com','url':fs[0]['seo_url'],'trackCount':len(fs),'tracks':[{'trackNumber':i,'title':t['title']} for i,t in enumerate(fs,1)],'note':'歌迷站26轨，与当前MusicBrainz22轨版本不完全相同，保留独立曲序。'}
  a['editions']=[x for x in a['editions'] if x.get('provider')!='lizhinb.com']+[e]
 write(R/a['path']/'album.json',a)
l['albums'].sort(key=lambda a:(a['releaseDate'] or '9999',a['title']))
from collections import Counter
l['summary'].update(albums=len(l['albums']),tracks=sum(len(a['tracks']) for a in l['albums']),types=dict(Counter(a['type'] for a in l['albums'])))
write(R/'library.json',l)
write(R/'reports/catalog-leads.json',[
 {'title':'我们也爱南京','status':'partial','issue':'4CD+4DVD的完整40轨曲序、表演者与内页尚缺；已取得31分钟视频音轨，不能代表整套发行。','source':'https://music.douban.com/subject/6853203/'},
 {'title':'影秋','status':'needs-research','issue':'资料称李志以陈小二参与2003年南京大学校园民谣合辑，曲目与原始内页待核。','source':'https://zh.wikipedia.org/wiki/李志'},
 {'title':'宁园曲 / 風吹麥浪 / 逃离北方计划 / 日出了','status':'identity-unconfirmed','issue':'商店同名艺人串页风险；未确认属于南京音乐人李志，不自动加入。','sources':['https://music.amazon.co.jp/artists/B00JH1NC44','https://www.qobuz.com/lu-fr/interpreter/-11550046/7682637','https://music.91q.com/artist/A12304080']},
 {'title':'单专辑下载（无损）23项','status':'login-required','issue':'下载按钮要求登录；未取得公开直链，不绕过登录。','source':'https://www.lizhi334.com/xiazai/'}])
print(l['summary']['albums'],l['summary']['tracks'])
