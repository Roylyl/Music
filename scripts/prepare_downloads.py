from pathlib import Path
import json,re
from opencc import OpenCC
R=Path(__file__).resolve().parents[1];cc=OpenCC('t2s')
def norm(s):
 s=cc.convert(s).lower().replace('——献给刘艺','').replace('—献给刘艺','').replace('凡高先生','梵高先生').replace('卡纳斯','喀纳斯').replace('思念的观世音','思念观世音').replace('这个世界会好吗2015','这个世界会好吗（2015版本）').replace('李志 - ','').replace('李志 – ','').replace(' - 李志','').replace('-李志','').replace('_李志','')
 for x,y in {'黒':'黑','戯':'戏','聴':'听','険':'险','郷':'乡','驼鸟':'鸵鸟','这个世界会好么':'这个世界会好吗','想起了他':'想起了她','董卓谣':'董卓瑶','春末的南方都市':'春末的南方城市','你离开了南京从此没人和我说话':'你离开了南京从此没有人和我说话','1990的春天':'1990年的春天','听妈妈讲那过去的故事':'听妈妈讲那过去的事情'}.items():s=s.replace(x,y)
 s=s.split('ボーカル：')[0]
 chinese=re.search(r'[(（]([\u4e00-\u9fff][^()（）]*)[)）]',s)
 if chinese and re.match(r'^[a-z]',s):s=chinese.group(1)
 s=re.sub(r'^\d+[.、\s]+','',s);s=re.sub(r'[（(\[].*?[）)\]]','',s);s=re.sub(r'\s*[-–]\s*\d{4}.*','',s)
 return re.sub(r'[\s，,、·。:：/／&＋+~～《》_-]','',s)
lib=json.loads((R/'library.json').read_text());drive=json.loads((R/'reports/sources/drive-catalog.json').read_text());fan=json.loads((R/'reports/sources/fan-catalog.json').read_text())
alias={'01被禁忌的游戏.wav':'被禁忌的游戏','02梵高先生.wav':'梵高先生','03这个世界会好吗.wav':'这个世界会好吗','04我爱南京.wav':'我爱南京','05你好，郑州.wav':'你好，郑州','06F':'F','[IO2014]':'i／O','108 个关键词 2012 Live':'108个关键词','动静 2015 Live':'动静','Imagine 2011 Live':'IMAGINE','北京不插电现场':'李志北京不插电现场','工体东路没有人 2009 Live':'工体东路没有人','爵士与不插电新编12首':'爵士乐与不插电新编12首','看见 2015 Live':'看见','李志 -电声与管弦乐':'李志、电声与管弦乐','李志-勾三搭四':'勾三搭四','李志、电声与管弦乐II':'李志、电声与管弦乐II','李志[1701]':'1701','北京不插电现场 2016 Live':'李志北京不插电现场','电声与管弦乐II':'李志、电声与管弦乐II','电声与管弦乐':'李志、电声与管弦乐','Imagine Live':'IMAGINE','I O':'i／O','你好 郑州':'你好，郑州','《8》':'8','《F》':'F','《1701》':'1701','这个世界会好吗2015':'这个世界会好吗（2015版本）','洗心革面 跨年音乐会':'洗心革面（歌迷站26轨版）','叁缺壹东京站':'THREE MISSING ONE JAPAN Tour 2024 in Tokyo','Best Selection Songs 2004-2018 Vol.2':'Best Selection Songs 2004-2018 Vol.2 - Ballads（叙事歌）','倒影 Best Selection Songs Vol.3':'Best Selection Songs 2004-2018 Vol.3 - 倒影'}
allc=[]
for a in drive:
 for f in a['files']:
  ext=Path(f['title']).suffix.lower()
  if ext not in ['.flac','.wav','.m4a','.mp3','.ape'] or f['title'].startswith('._') or '副本' in f['title']:continue
  allc.append({'album':alias.get(a['album'],a['album']),'title':Path(f['title']).stem,'fileName':f['title'],'url':f['url'],'provider':'Google Drive public share','id':f['id'],'extension':ext,'size':int(f['size'] or 0)})
gp=R/'reports/sources/github-mp3-tree.json'
if gp.exists():
 from urllib.parse import quote
 for f in json.loads(gp.read_text()).get('tree',[]):
  p=Path(f['path'])
  if len(p.parts)==3 and p.parts[0]=='publish' and p.suffix.lower()=='.mp3':
   allc.append({'album':p.parts[1],'title':p.stem,'fileName':p.name,'url':'https://raw.githubusercontent.com/lvboda/lizhi-mp3/main/'+quote(f['path']),'provider':'GitHub lvboda/lizhi-mp3','extension':'.mp3','size':f.get('size')})
for ts in fan:
 for f in ts:
  allc.append({'album':alias.get(f['album'],f['album']),'title':f['title'],'fileName':Path(f['hq_audio_url']).name,'url':f['hq_audio_url'],'downloadUrl':f['download_url'],'provider':'lizhinb.com','pageUrl':f['seo_url'],'extension':'.mp3'})
queue=[];unmatched=[]
for a in lib['albums']:
 for t in a['tracks']:
  candidates=[]
  for c in allc:
   if re.sub(r'[\s，,、/／《》]', '', cc.convert(c['album']).lower())!=re.sub(r'[\s，,、/／《》]', '', cc.convert(a['title']).lower()):continue
   if ('吉松浩' in c['title']) != ('吉松浩' in t['title']):continue
   if a['type']=='compilation':
    base=re.split(r'[（(]',t['title'])[0].strip()
    raw=cc.convert(c['title']);live=('live' in raw.lower() or '相信未来版' in raw or '玩偶之主' in raw)
    # The Japanese compilations have studio disc 1 and performance disc 2.
    titlematch=(norm(base)==norm(re.split(r'[（(]',raw)[0].split('feat.')[0])) if 'Vol.2' in a['title'] else (re.sub(r'[\s，,]','',base) in re.sub(r'[\s，,]','',raw))
    if titlematch and live==(t['discNumber']==2):candidates.append(c)
   elif norm(c['title'])==norm(t['title']):candidates.append(c)
  if len(candidates)>1 and a['type']=='compilation':
   candidates=[]  # Ambiguous versions require review, never choose arbitrarily.
  candidates.sort(key=lambda c:({'flac':0,'wav':1,'ape':2,'m4a':3,'mp3':4}.get(c['extension'][1:],5),c['provider']!='Google Drive public share'))
  if candidates:
   c=candidates[0];safe=re.sub(r'[/\\:*?"<>|]','_',t['title']);rel=f'{a["path"]}/{t["discNumber"]:02}-{t["trackNumber"]:02} - {safe}{c["extension"]}'
   queue.append({'trackId':t['id'],'album':a['title'],'title':t['title'],'localPath':rel,'source':c,'alternatives':candidates[1:],'rightsStatus':'unverified-third-party','status':'pending'})
  else:unmatched.append({'trackId':t['id'],'album':a['title'],'title':t['title']})
(R/'reports/download-queue.json').write_text(json.dumps(queue,ensure_ascii=False,indent=2));(R/'reports/unmatched-sources.json').write_text(json.dumps(unmatched,ensure_ascii=False,indent=2))
from collections import Counter
print('matched',len(queue),'unmatched',len(unmatched),Counter(q['source']['extension'] for q in queue))
