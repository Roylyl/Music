from pathlib import Path
import requests,json,time
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parents[1]; O=R/'reports/sources'
base='https://lizhilizhi.bandcamp.com'
s=requests.Session()
h=BeautifulSoup(s.get(base,timeout=30).text,'html.parser')
for a in h.select('#music-grid a'):
 url=base+a['href']; p=O/('bc-'+a['href'].split('/')[-1]+'.json')
 if p.exists(): continue
 soup=BeautifulSoup(s.get(url,timeout=30).text,'html.parser'); el=soup.select_one('[data-tralbum]'); d=json.loads(el['data-tralbum'])
 # Retain catalog facts only, not lyrics or preview-stream download URLs.
 out={'url':url,'title':d['current']['title'],'releaseDate':d.get('album_release_date'),'current':{k:d['current'].get(k) for k in ['minimum_price','set_price','currency','download_pref','publish_date']},'labelLinked':bool(soup.find('a',href='https://taihemusicgroup.bandcamp.com')),'tracks':[{k:t.get(k) for k in ['title','track_num','duration','title_link','track_id']} for t in d['trackinfo']],'downloadOffer':' '.join(x.get_text(' ',strip=True) for x in soup.select('.buyItem'))[:1500]}
 p.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(out['title'],len(out['tracks']),out['current'],flush=True);time.sleep(.5)
