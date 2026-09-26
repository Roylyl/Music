"""Keep multilingual pending-search records aligned with the current catalog."""
from pathlib import Path
import json
from opencc import OpenCC
from pypinyin import lazy_pinyin
R=Path(__file__).resolve().parents[1];l=json.loads((R/'library.json').read_text());p=R/'reports/search-queue.json';old={x['trackId']:x for x in json.loads(p.read_text())} if p.exists() else {};tc=OpenCC('s2t');out=[]
for a in l['albums']:
 for t in a['tracks']:
  if t['id'] in old:out.append(old[t['id']]);continue
  variants=[('zh-Hans','李志',t['title'],a['title']),('zh-Hant','李志',tc.convert(t['title']),tc.convert(a['title'])),('romanized','Li Zhi',' '.join(lazy_pinyin(t['title'])),' '.join(lazy_pinyin(a['title'])))]
  qs=[]
  for lang,artist,title,album in variants:
   qs += [{'language':lang,'query':q,'status':'pending'} for q in [f'{artist} "{title}" official download',f'{artist} "{album}" "{title}" Bandcamp',f'{artist} "{album}" "{title}" Qobuz',f'{artist} "{album}" "{title}" lossless purchase',f'{artist} "{album}" "{title}" FLAC official',f'{artist} "{album}" "{title}" digital download']]
  out.append({'trackId':t['id'],'title':t['title'],'album':a['title'],'catalogChecks':a['sources'],'webSearchComplete':False,'queries':qs})
p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('search records',len(out))
