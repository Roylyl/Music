#!/usr/bin/env python3
"""Audit and conservatively standardize user-owned local lyrics; preserve numeric times."""
import argparse,collections,importlib.util,json,re,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/lyrics/review-20260930'
spec=importlib.util.spec_from_file_location('base',ROOT/'scripts/standardize_lyrics.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
STAMP=re.compile(r'\[(\d+):([0-5]\d)(?:[.:](\d{1,3}))?\]')
EXTRAS=['管弦乐','管弦乐编写','音乐总监','Program工程操作','Program制作','Program录音','制作协力','录音室','混音录音室','母带工作室','混音/母带工作室','和声编写','录音环境','弦乐监制','混音与母带','编程','录音助理','混音助理','童声合唱','弦乐录音','钢片琴','母带制作']
ORDER=['演唱','词','曲','编曲','制作','吉他','贝斯','键盘','鼓']+[x for x in base.HEADER_ORDER if x not in ['演唱','词','曲','编曲','制作','吉他','贝斯','键盘','鼓']]+EXTRAS
ALIASES=dict(base.KEY_ALIASES)
ALIASES.update({x.casefold():x for x in EXTRAS})
ALIASES.update({'编':'编曲','录音师':'录音','录音工程师':'录音','混音师':'混音','混音工程师':'混音','混音室':'混音录音室','低音吉他':'贝斯','后期母带处理制作人':'母带制作','母带后期工程师':'母带','后期母带处理录音师':'母带','母带后期处理录音室':'母带工作室','后期母带处理录音室':'母带工作室','配唱':'配唱制作','录音棚':'录音室'})
def conv(s):
    return s if re.search(r'[\u3040-\u30ff]',s) else base.simplified(s)
def compact(s):return re.sub(r'\s+','',conv(s)).casefold()
def split(line):
    tags=[]
    while (m:=STAMP.match(line)):
        tags.append(m.group());line=line[m.end():]
    return tags,line.strip()
def numeric(tags):
    return tuple(int((m:=STAMP.fullmatch(t))[1])*60000+int(m[2])*1000+int((m[3]or'0').ljust(3,'0')) for t in tags)
def canon(tags):return ''.join(f'[{n//60000:02d}:{n//1000%60:02d}.{n%1000:03d}]' for n in numeric(tags))
def role(s):
    if not (m:=re.match(r'^([^：:]{1,90})[：:]\s*(.*)$',s)):return None
    k=re.sub(r'\s+','',m[1]).casefold();r=ALIASES.get(k)
    if not r:
        # Existing bilingual role labels retain their credited values.
        chinese=re.match(r'^[\u4e00-\u9fff]+',k)
        if chinese:r=ALIASES.get(chinese.group())
    return (r,m[2].strip()) if r else None

def normalize(t,text):
    title=conv(t['title'])+' - '+conv(t['artist']);headers=collections.OrderedDict();body=[];removed=[];unknown=[];expected=[]
    lines=text.replace('\r\n','\n').replace('\r','\n').splitlines()
    for i,line in enumerate(lines):
        line=conv(line.strip());tags,content=split(line)
        if not line:continue
        if i==0 and compact(content)==compact(title):continue
        c=role(content)
        if c:
            r,v=c
            if not v:removed.append({'reason':'empty-credit','line':line});continue
            for part in ['词','曲'] if r=='词曲' else [r]:
                values=headers.setdefault(part,[])
                if v not in values:values.append(v)
            continue
        if re.fullmatch(r'\[(?:ti|ar|al|by|re|ve|tool|offset):[^\]]*\]',line,re.I):
            if line.lower().startswith('[offset:') and re.search(r'[1-9]',line):body.append(line);expected.append(((),line));continue
            removed.append({'reason':'metadata','line':line});continue
        duplicate=compact(content)==compact(title)
        m=re.match(r'^(.+?)\s+[-—–]\s+(.+)$',content)
        if m and compact(m[2])==compact(t['artist']):
            without_alias=re.sub(r'\s*[（(][^）)]*[）)]\s*$','',m[1])
            duplicate=duplicate or compact(without_alias)==compact(t['title'])
        if duplicate:removed.append({'reason':'duplicate-title','line':line});continue
        if re.search(r'https?://|www\.',content,re.I) and not tags:
            removed.append({'reason':'source-link','line':line});continue
        if i==0 and not tags and compact(content)==compact(t['title']):
            removed.append({'reason':'duplicate-title','line':line});continue
        if not tags and re.match(r'^.{1,50}[：:]',content):unknown.append(content)
        expected.append((numeric(tags),content));body.append(canon(tags)+content)
    assert [(numeric(split(l)[0]),split(l)[1]) for l in body]==expected
    def rank(r):
        if r=='演唱':return -1 if base.is_group_artist(t['artist']) else 1000
        return ORDER.index(r) if r in ORDER else len(ORDER)
    ordered=sorted(headers,key=rank)
    result='\n'.join([title]+[r+'：'+'、'.join(headers[r]) for r in ordered]+body)+'\n'
    times=[n for tags,content in expected if content for n in tags]
    issues=[]
    if times and max(times)/1000>t.get('duration',0)+2:issues.append({'type':'timestamp-overrun','last':max(times)/1000,'duration':t['duration']})
    # Multiple tags on one line can naturally refer to later repeated verses.
    single_times=[tags[0] for tags,content in expected if content and len(tags)==1]
    if any(b<a for a,b in zip(single_times,single_times[1:])):issues.append({'type':'nonmonotonic-single-tags'})
    for l in body:
        if l.startswith('[') and not STAMP.match(l) and not l.lower().startswith('[offset:'):issues.append({'type':'unparsed-bracket-line','line':l})
    return result,removed,unknown,issues,bool(times)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    ts=json.loads((ROOT/'tracks.json').read_text());changes=[];issues=[];missing=[];originals={};proposed={};timed=0;unknown=[];removed=[]
    for t in ts:
        rel=Path(t['src']).with_suffix('.lrc');p=ROOT/rel
        if not p.exists():missing.append(t);continue
        raw=p.read_bytes();result,deleted,unrecognized,problems,is_timed=normalize(t,raw.decode('utf-8-sig'))
        timed+=is_timed
        if result.encode()!=raw:changes.append(rel.as_posix());originals[rel.as_posix()]=raw;proposed[rel.as_posix()]=result.encode()
        if problems:issues.append({'id':t['id'],'path':rel.as_posix(),'issues':problems})
        if unrecognized:unknown.append({'path':rel.as_posix(),'lines':unrecognized})
        if deleted:removed.append({'path':rel.as_posix(),'lines':deleted})
    if args.apply:
        for rel,raw in originals.items():assert (ROOT/rel).read_bytes()==raw,('concurrent edit',rel)
        if changes:
            with zipfile.ZipFile(OUT/'originals.zip','x',zipfile.ZIP_DEFLATED) as z:
                for rel,raw in originals.items():z.writestr(rel,raw)
            for rel,data in proposed.items():(ROOT/rel).write_bytes(data)
    summary={'tracks':len(ts),'existing':len(ts)-len(missing),'missing':len(missing),'timed':timed,'plain':len(ts)-len(missing)-timed,'changed':len(changes),'applied':args.apply,'timingIssueFiles':len(issues),'changes':changes,'validation':'Numeric timestamps and retained body line order/repeats preserved; duration check uses tracks.json; no listening or externally verified transcription claim.'}
    for name,data in [('summary',summary),('missing-tracks',missing),('timing-issues',issues),('unrecognized-lines',unknown),('removed-metadata',removed)]:
        (OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='changes'},ensure_ascii=False))
if __name__=='__main__':main()
