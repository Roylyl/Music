"""Normalize only the 155 r5 imports, offline; retain originals in a ZIP."""
import importlib.util,json,re,zipfile
from pathlib import Path
from collections import OrderedDict
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
R5=ROOT/'reports/lyrics/supplement-20260929-r5'
spec=importlib.util.spec_from_file_location('existing',ROOT/'scripts/standardize_lyrics.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
tracks={t['id']:t for t in json.loads((ROOT/'tracks.json').read_text())}
rows=[]
for name in ['lizhinb-imports-r5.json','lrclib-imports-r5.json','local-reuse-imports-r5.json']:
    rows+=json.loads((R5/name).read_text())['imports']
for row in json.loads((R5/'recovery-r5.json').read_text())['items']:
    rows.append(dict(row,target=str(Path(tracks[row['trackId']]['src']).with_suffix('.lrc'))))
assert len(rows)==len({r['target'] for r in rows})==155
aliases=dict(base.KEY_ALIASES)
aliases.update({'录音师':'录音','混音师':'混音','母带工程师':'母带','伴唱':'和声'})
extras=['管弦乐编写','音乐总监','管弦乐','Program工程操作','Program制作','Program录音','混音/母带工作室']
aliases.update({r.casefold():r for r in extras})
order=['词','曲','编曲','制作','吉他','贝斯','键盘','鼓']+[x for x in base.HEADER_ORDER if x not in ['词','曲','编曲','制作','吉他','贝斯','键盘','鼓']]+extras
stamp=re.compile(r'\[(\d+):([0-5]\d)(?:[.:](\d{1,3}))?\]')
def convert(s):
    # Keep Japanese text intact; English and other non-Han text are unchanged.
    return s if re.search(r'[\u3040-\u30ff]',s) else base.simplified(s)
def split_line(line):
    tags=[]
    while (m:=stamp.match(line)):
        tags.append(m.group());line=line[m.end():]
    return tags,line.strip()
def key(s):return re.sub(r'\s+','',convert(s)).casefold()
def title_duplicate(body,t):
    return key(body)==key(t['title']+' - '+t['artist'])
def credit(body):
    m=re.match(r'^([^：:]{1,32})[：:]\s*(.*)$',body)
    if not m:return None
    role=aliases.get(m[1].strip().casefold());value=m[2].strip()
    return (role,value) if role else None
def canonical_tag(tag):
    m=stamp.fullmatch(tag);return f'[{int(m[1]):02d}:{int(m[2]):02d}.{(m[3]or"0").ljust(3,"0")}]'
changes=[];originals={};proposed={};references=[];counts={'traditionalFiles':0,'creditLinesExtracted':0,'duplicateHeadersRemoved':0,'removedSourceLines':0}
for row in rows:
    rel=row['target'];p=ROOT/rel;t=tracks[row.get('trackId')or row['targetTrackId']]
    raw=p.read_bytes();originals[rel]=raw;text=raw.decode('utf-8-sig');lines=text.splitlines()
    assert title_duplicate(lines[0],t),(rel,'unexpected first line')
    if 'so mi re mi re do' in text and '等了好久才发现是纯音乐' in text:
        references.append(rel);continue
    if convert(text)!=text:counts['traditionalFiles']+=1
    headers=OrderedDict();body=[];expected=[]
    for rawline in lines[1:]:
        line=convert(rawline.strip());tags,content=split_line(line)
        if not line:continue
        if re.fullmatch(r'\[(?:ti|ar|al|by|re|ve|tool|offset):[^\]]*\]',line,re.I):
            if line.lower().startswith('[offset:') and re.search(r'[1-9]',line):raise ValueError('nonzero offset '+rel)
            continue
        if title_duplicate(content,t):counts['duplicateHeadersRemoved']+=1;continue
        if re.search(r'https?://|www\.',content,re.I):counts['removedSourceLines']+=1;continue
        c=credit(content)
        if c:
            role,value=c
            if not value:continue
            for part in (['词','曲'] if role=='词曲' else [role]):
                if value not in headers.setdefault(part,[]):headers[part].append(value)
            counts['creditLinesExtracted']+=bool(tags)
            continue
        expected.append((tuple(canonical_tag(tag) for tag in tags),content))
        body.append(''.join(canonical_tag(tag) for tag in tags)+content)
    # Preserve exact original time points and every retained body line, including repeats.
    actual=[(tuple(canonical_tag(tag) for tag in split_line(line)[0]),split_line(line)[1]) for line in body]
    assert actual==expected
    title=convert(t['title'])+' - '+convert(t['artist'])
    roles=sorted(headers,key=lambda x:(-1 if base.is_group_artist(t['artist']) and x=='演唱' else order.index(x) if x in order else 999))
    result='\n'.join([title]+[r+'：'+'、'.join(headers[r]) for r in roles]+body)+'\n'
    proposed[rel]=result.encode('utf-8')
    if proposed[rel]!=raw:changes.append(rel)
assert len(references)==2
# Check for concurrent edits before writing any file; never overwrite a prior backup.
for rel,raw in originals.items():assert (ROOT/rel).read_bytes()==raw,('concurrent edit',rel)
backup=OUT/'originals.zip'
with zipfile.ZipFile(backup,'x',zipfile.ZIP_DEFLATED) as z:
    for rel in changes+references:z.writestr(rel,originals[rel])
for rel in changes:(ROOT/rel).write_bytes(proposed[rel])
for rel in references:
    dest=OUT/'reference-notes'/Path(rel).with_suffix('.txt');dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(originals[rel]);(ROOT/rel).unlink()
summary={'scope':155,'normalizedFiles':len(changes),'retainedLyrics':153,'timedLyrics':sum(bool(stamp.search(x.decode())) for x in proposed.values()),'plainLyrics':sum(not bool(stamp.search(x.decode())) for x in proposed.values()),'referenceOnly':references,'changes':changes,**counts,'validation':'Body order, repeated lines and numeric timestamps preserved; no audio alignment claim.'}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['changes','referenceOnly']},ensure_ascii=False))
