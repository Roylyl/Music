"""Build a source-grounded catalog. Unknown facts remain null; never transcode audio."""
from pathlib import Path
import json,re,shutil,argparse
from collections import Counter
from opencc import OpenCC
from pypinyin import lazy_pinyin
from PIL import Image,ImageOps
R=Path(__file__).resolve().parents[1]; S=R/'reports/sources'; cc=OpenCC('t2s'); tc=OpenCC('s2t')
def read(p): return json.loads(p.read_text())
def write(p,d): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def norm(s):
 s=cc.convert(s).lower().replace('李志lizhi - ','')
 s=re.sub(r'[（(].*?[）)]','',s);s=re.sub(r'\s*[-–]\s*\d{4}.*','',s)
 return re.sub(r'[\s，,、·。:：/／&＋+~～-]','',s)
# Explicit edition selection prevents automatic merging of unrelated MB groups.
rows=[
('被禁忌的游戏','2004','studio','758a394c-126c-487f-bca1-31ff28467d13','-'),
('梵高先生','2005-12-25','studio','211ffdd9-238e-4c6d-858d-a38f725e0493','--2'),
('这个世界会好吗','2006-11-20','studio','083e1542-8767-4a92-8465-bc3fb233b8b9','--3'),
('工体东路没有人','2009-01-22','live','200dad30-e066-4956-bc59-88f98524563d','--4'),
('我爱南京','2009-10-16','studio','355106ea-2263-4983-b24a-42d225d222ad','--5'),
('你好，郑州','2010-09-01','studio','38d58d47-5f00-4f4b-95aa-f499cdba365b','--6'),
('二零零九年十月十六日事件','2010-01-30','live','4970c47f-8920-416b-94e5-485ca1be5396',None),
('F','2011-09-28','studio','3a52b24e-1c71-4e2d-91b2-b90e13b91617','f'),
('IMAGINE','2012','live','f7f7a172-a4cb-4342-af4d-eca0b8371c05',None),
('108个关键词','2013','live','46c5e5b4-84a7-40d5-bed9-7383ae6202ca','108'),
('勾三搭四','2014-04-01','live','1442643e-a76d-4bcf-b2f5-9fbddc1b05c6','--7'),
('1701','2014-11-13','studio','bfe30cec-4119-41e4-9961-338356921a3c','1701'),
('看见','2015-06-27','live',None,'--8'),
('动静','2016-03-14','live','860b6bbc-fd99-42a9-94bb-0b08af0958f7','--10'),
('李志北京不插电现场','2016-08-11','live','dfca4787-fa3a-442c-9fd7-877145bc471a','--13'),
('8','2016-10-18','studio','ccf142c6-ad89-4115-aa0c-30d8f587b0fe','--9'),
('在每一条伤心的应天大街上','2016-11-20','studio','dde3284d-3c53-4d81-b139-ac11bc831e73','--11'),
('李志、电声与管弦乐','2017-05-16','live','a2df0227-b7ae-4408-95c8-79baf1099f39','--12'),
('爵士乐与不插电新编12首','2018-04-16','live','8b283e60-70fa-46ea-a564-675db0444a8b','12'),
('李志、电声与管弦乐II','2018-05-16','live','6a798753-fe04-4301-b727-3b0b9be33fa1','ii'),
('Best Selection Songs 2004-2018','2019-04-01','compilation','7c2d7ddb-9446-4c59-a9ac-42582d4ea6bc',None),
('Best Selection Songs 2004-2018 Vol.2 - Ballads（叙事歌）','2020-05-27','compilation','30817cce-0960-44cd-b570-d39bcd8c8de5',None),
('Best Selection Songs 2004-2018 Vol.3 - 倒影','2021-11-12','compilation','f441c560-c866-410a-a53e-432f3e69b809',None),
('i／O - 完整版录音','2015','concert','8d7610e1-9ecd-417f-a261-66cf2a0d615a',None),
('洗心革面 - 演唱会录音',None,'concert','2faf828e-04f3-4410-9a84-e88c547ffdda',None),
]
manual=[
('将进酒','2007-11-11','concert','将进酒|黑色信封|来了|喀纳斯|被禁忌的游戏|梵高先生|斜|阿兰|想起了她|春末的南方城市|董卓瑶|人民不需要自由|翁庆年的六英镑|和你在一起|这个世界会好吗|Wish You Were Here','https://www.shopmsdn.com/detail-%E6%9D%8E%E5%BF%97%3A%E5%B0%86%E8%BF%9B%E9%85%92%28%E6%BC%94%E5%94%B1%E4%BC%9ALIVE%29%282DVD%29-504.html'),
('我们也爱南京','2011-09-18','concert','','https://music.douban.com/subject/6853203/'),
('i／O','2015-01-21','live','杭州|墙上的向日葵|铅笔|来了|下雨+董卓瑶+忽然|这个世界会好吗|妈妈|定西|方式|鸵鸟+天空之城+我们不能失去信仰|山阴路的夏天','https://music.douban.com/subject/26310288/'),
('这个世界会好吗（2015版本）','2015-04-13','single','这个世界会好吗（2015版本）','https://www.joox.com/th/single/J0_GQeVazVUSIlD4O_PqLA%3D%3D'),
('THREE MISSING ONE JAPAN Tour 2024 in Tokyo','2025-06-13','live','关于郑州的记忆+董卓瑶+春末的南方城市|苍井空|倒影|黑色信封|和你在一起|天空之城|鸵鸟+墙上的向日葵+鼠说|这个世界会好吗|梵高先生|被禁忌的游戏+定西+一个夜晚|大象+门+来了+热河|寻找+忽然|山阴路的夏天|你离开了南京，从此没有人和我说话','https://wwr.com.tw/artists/li-zhi')]
WIKI='https://zh.wikipedia.org/wiki/李志'
coveraliases={'8':'捌','i／O - 完整版录音':'i／O'}
conflicts={
'被禁忌的游戏':'自发行常记为2004；MusicBrainz记录2004-11-30，豆瓣记2004-12，维基表记2005-12-01，摇滚数据库另列2006再版。仅采用年，具体日期待核。',
'梵高先生':'MusicBrainz数字版记2005-12-01，实体版记2005-12-25；再版另有2007日期。',
'1701':'百度人物资料记2014-11-13，维基表记2014-05-22，摇滚数据库记2014-12；暂采用2014-11-13，待首发公告确认。',
'二零零九年十月十六日事件':'本次MusicBrainz版本27轨，维基表为26轨，含开场/分轨差异，未删轨凑数。',
'108个关键词':'MusicBrainz数字版17轨，维基实体版16轨，Bandcamp现售版8轨。保留所选版本，不混合曲序。',
'看见':'原版10轨；Bandcamp现售版8轨。原版曲序来自Mulanci和Jums；未匹配的时长留空。',
'Best Selection Songs 2004-2018 Vol.2 - Ballads（叙事歌）':'采用CD版2020-05-27；资料另列黑胶2020-05-18。',
'Best Selection Songs 2004-2018 Vol.3 - 倒影':'最早黑胶发行采用厂牌微博2021-11-12；本曲单取CD版，CD发行2021-12-24；MusicBrainz写2021-09存在冲突。',
'将进酒':'主DVD16轨已录入；赠碟的迷笛演出与采访分轨待核。第三方商品页有曲名笔误，已保留说明。',
'我们也爱南京':'确认4CD+4DVD套装，含多位表演者；完整40轨及各曲表演者尚待可靠内页，不把所有歌曲归为李志。',
'洗心革面 - 演唱会录音':'演出于2018-12-31至2019-01-01；尚未确认全场录音正式发行，releaseDate为空。',
'i／O - 完整版录音':'MusicBrainz标为Bootleg；与2015年正式11轨现场专辑分开。日期是收录数据库的流通年份，非已证实正式发行日期。'}
parser=argparse.ArgumentParser();parser.add_argument('--covers',type=Path);args=parser.parse_args()
coverfiles=list(args.covers.rglob('*')) if args.covers else []
for folder in ['artists/李志','live/李志','collections','covers','stream','reports','scripts']: (R/folder).mkdir(parents=True,exist_ok=True)
albums=[]
for title,date,kind,rid,bc in rows+[(x[0],x[1],x[2],None,'i-o' if x[0]=='i／O' else None) for x in manual]:
 aid='lizhi-'+(rid if rid else {'看见':'seen-2015','将进酒':'jiangjinjiu','我们也爱南京':'we-love-nanjing','i／O':'io-2015','这个世界会好吗（2015版本）':'has-man-a-future-2015','THREE MISSING ONE JAPAN Tour 2024 in Tokyo':'tokyo-2024'}[title])
 year=int(date[:4]) if date else None
 folder=('collections/李志' if kind=='compilation' else 'live/李志' if kind in ('live','concert') else 'artists/李志')+'/'+f'{year or "未知发行年"} - {title.replace("/","／")}'
 a={'id':aid,'artist':'李志','title':title,'releaseDate':date,'releaseDatePrecision':{4:'year',7:'month',10:'day'}.get(len(date or ''),'unknown'),'year':year,'type':kind,'path':folder,'cover':'','coverWeb':'','tracks':[],'sources':[WIKI],'notes':[conflicts[title]] if title in conflicts else [],'metadataStatus':'provisional','editions':[]}
 ts=[]
 if rid:
  d=read(S/f'mb-release-{rid}.json');u='https://musicbrainz.org/release/'+rid;a['sources'].append(u);a['selectedEdition']={'id':rid,'title':d['title'],'date':d.get('date'),'status':d.get('status')}
  for m in d['media']:
   for t in m.get('tracks',[]): ts.append((cc.convert(t['title']),m['position'],t['position'],round(t['length']/1000,3) if t.get('length') else None,u))
  a['releaseDateClaims']=[{'date':d.get('date'),'source':u},{'date':date,'source':WIKI}]
 if title=='看见': ts=[(t,1,i,None,'https://www.mulanci.org/lyric/s4127/') for i,t in enumerate('看见|黑色信封|苍井空|春末的南方城市|你离开了南京，从此没有人和我说话|下雨|热河|董卓瑶|离婚|梵高先生'.split('|'),1)]
 for x in manual:
  if x[0]==title:
   a['sources'].append(x[4]);ts=[(t,2 if title.startswith('THREE') and i>8 else 1,i-8 if title.startswith('THREE') and i>8 else i,None,x[4]) for i,t in enumerate(x[3].split('|'),1) if t]
 if title=='i／O - 完整版录音': a['releaseDate']=None;a['releaseDatePrecision']='unknown';a['officialReleaseConfirmed']=False
 if kind=='concert': a['officialReleaseConfirmed']=title in ['将进酒','我们也爱南京']
 if bc:
  b=read(S/f'bc-{bc}.json');a['sources'].append(b['url']);a['editions'].append({'provider':'Bandcamp','url':b['url'],'title':b['title'],'releaseDate':b['releaseDate'],'trackCount':len(b['tracks']),'tracks':b['tracks'],'offer':b['downloadOffer'],'note':'平台上架日期，不替代原始发行日期。'})
 for ti,(name,disc,num,duration,src) in enumerate(ts,1):
  t={'id':f'{aid}-d{disc:02}-t{num:02}','artist':'李志','album':title,'title':name,'discNumber':disc,'trackNumber':num,'sequenceNumber':ti,'duration':duration,'durationSource':src if duration else '', 'sourceStatus':'missing','sourceUrl':'','format':'','localPath':'','sources':[],'suspected_transcode':None,'audioProperties':None,'searchStatus':'catalog-checked','versionMatch':'unconfirmed'}
  if bc:
   hits=[x for x in b['tracks'] if norm(x['title'])==norm(name)]
   if len(hits)==1:
    h=hits[0];url='https://lizhilizhi.bandcamp.com'+h['title_link'];offer={'provider':'Bandcamp','url':url,'albumUrl':b['url'],'status':'purchasable','formats':['FLAC','ALAC','WAV','AAC','MP3'],'advertisedSampleRate':44100 if '44.1kHz' in b['downloadOffer'] else None,'advertisedBitDepth':16 if '16-bit' in b['downloadOffer'] else None,'qualityVerifiedFromFile':False,'checkedAt':'2026-09-26','sourceTrackNumber':h['track_num'],'duration':h['duration'],'matchBasis':'同专辑曲名规范化唯一匹配；未比对音频母带'}
    t.update(sourceStatus='purchasable',sourceUrl=url,versionMatch='same-album-title-match');t['sources'].append(offer)
    if duration is None: t['duration']=h['duration'];t['durationSource']=url
  if title=='这个世界会好吗（2015版本）':t.update(sourceStatus='streaming-only',sourceUrl=src);t['sources'].append({'provider':'JOOX','url':src,'status':'streaming-only','checkedAt':'2026-09-26'})
  a['tracks'].append(t)
 # Preserve acquisitions on rebuild.
 old=R/folder/'album.json'
 if old.exists():
  oldtracks={t['id']:t for t in read(old)['tracks']}
  for t in a['tracks']:
   ot=oldtracks.get(t['id'],{})
   if ot.get('localPath'):
    for key in ['sourceStatus','sourceUrl','format','localPath','audioProperties','suspected_transcode']:t[key]=ot.get(key)
 cname=coveraliases.get(title,title)
 matches=[f for f in coverfiles if f.is_file() and f.suffix.lower() in ['.jpg','.png','.webp'] and norm(f.stem.split(' - 李志 - ')[-1])==norm(cname)]
 if matches:
  f=matches[0];dest=R/folder;dest.mkdir(parents=True,exist_ok=True)
  with Image.open(f) as im:
   im=ImageOps.exif_transpose(im).convert('RGB');w,h=im.size
   if f.suffix.lower()=='.jpg':shutil.copyfile(f,dest/'cover.jpg')
   else:im.save(dest/'cover.jpg',quality=96,subsampling=0)
   im.thumbnail((1000,1000));im.save(dest/'cover.webp',quality=88,method=6)
  original=R/'covers/originals'/f.name;original.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,original)
  a.update(cover='cover.jpg',coverWeb='cover.webp',coverSource={'provider':'OneDrive','sourceFileName':f.name,'width':w,'height':h,'lowResolution':min(w,h)<500,'originalPath':str(original.relative_to(R))})
 elif old.exists():
  oa=read(old)
  for key in ['cover','coverWeb','coverSource']:
   if key in oa:a[key]=oa[key]
 a['trackCount']=len(a['tracks']);a['tracklistStatus']='partial' if title in ['将进酒','我们也爱南京'] else 'edition-listed'
 write(R/folder/'album.json',a);albums.append(a)
albums.sort(key=lambda a:(a['releaseDate'] or '9999',a['title']))
tracks=[t for a in albums for t in a['tracks']]
lib={'schemaVersion':1,'updatedAt':'2026-09-26','pathBase':'repository-root','artist':'李志','catalogStatus':'in-progress','completenessClaim':False,'types':['studio','ep','single','live','concert','compilation','special'],'statusDefinitions':{'available':'已验证可授权免费下载或已合法取得本地文件','purchasable':'已找到对应曲目的数字购买入口，尚未购买','streaming-only':'已找到合法在线播放入口，未确认可下载','missing':'本次已核来源中未确认合法数字来源，并非证明全网不存在'},'albums':albums,'summary':{'albums':len(albums),'tracks':len(tracks),'status':dict(Counter(t['sourceStatus'] for t in tracks)),'types':dict(Counter(a['type'] for a in albums))}}
write(R/'library.json',lib)
queries=[]
for a in albums:
 for t in a['tracks']:
  variants=[('zh-Hans','李志',t['title'],a['title']),('zh-Hant','李志',tc.convert(t['title']),tc.convert(a['title'])),('romanized','Li Zhi',' '.join(lazy_pinyin(t['title'])),' '.join(lazy_pinyin(a['title'])))]
  qs=[]
  for lang,artist,title,album in variants:
   qs += [{'language':lang,'query':q,'status':'pending'} for q in [f'{artist} "{title}" official download',f'{artist} "{album}" "{title}" Bandcamp',f'{artist} "{album}" "{title}" Qobuz',f'{artist} "{album}" "{title}" lossless purchase',f'{artist} "{album}" "{title}" FLAC official',f'{artist} "{album}" "{title}" digital download']]
  queries.append({'trackId':t['id'],'title':t['title'],'album':a['title'],'catalogChecks':[x['url'] for x in a['editions']],'webSearchComplete':False,'queries':qs})
write(R/'reports/search-queue.json',queries)
write(R/'stream/links.json',[{'id':t['id'],'title':t['title'],'album':t['album'],'status':t['sourceStatus'],'url':t['sourceUrl']} for t in tracks if t['sourceUrl']])
write(R/'reports/missing.json',[{'id':t['id'],'album':t['album'],'title':t['title'],'reason':'尚未确认此版本的合法数字来源'} for t in tracks if t['sourceStatus']=='missing'])
print(json.dumps(lib['summary'],ensure_ascii=False))
