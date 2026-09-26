"""Export local playable tracks; store pages are never emitted as audio URLs."""
from pathlib import Path
from urllib.parse import quote
import json,argparse
R=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--base-url',default='');p.add_argument('--public',action='store_true',help='Only assets explicitly cleared for redistribution');p.add_argument('--output',type=Path,default=R/'tracks.json');args=p.parse_args()
if args.base_url and not args.base_url.startswith(('https://','http://','/')):raise SystemExit('base-url must be HTTP(S) or a site-relative prefix')
lib=json.loads((R/'library.json').read_text());out=[]
def url(rel):return args.base_url.rstrip('/')+'/'+quote(rel,safe='/') if args.base_url else rel
for a in lib['albums']:
 for t in a['tracks']:
  if not t['localPath'] or (args.public and not t.get('redistributionAllowed')):continue
  src=url(t['localPath']);cover=url(a['path']+'/'+a['coverWeb']) if a['coverWeb'] else ''
  out.append({'id':t['id'],'title':t['title'],'name':t['title'],'artist':t['artist'],'album':t['album'],'trackNumber':t['trackNumber'],'discNumber':t['discNumber'],'duration':t['duration'],'src':src,'url':src,'cover':cover,'format':t['format'],'sourceStatus':t['sourceStatus'],'sourceUrl':t['sourceUrl'],'rightsStatus':t.get('rightsStatus'),'redistributionAllowed':t.get('redistributionAllowed',False)})
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('Exported',len(out),'tracks')
