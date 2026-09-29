#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r5 phase1 —— 网络歌词源批量计划与抓取（只写审计信息；暂存文件放 /tmp，不写仓库歌词）。
来源A：lizhinb.com 全站配套 .lrc 索引（st.nj1701.com，与库内李志音频同源发行体系）。
来源B：lrclib.net 开放数据库（r3 探测结果 + 本轮新查询）。
产出：reports/lyrics/supplement-20260929-r5/{plan-r5.json,audit-lrclib.json}
"""
import json, os, re, time, difflib, subprocess, urllib.request, urllib.parse
from urllib.error import HTTPError

ROOT = '/Users/roylyl/Documents/GitHub/Music'
R3 = os.path.join(ROOT, 'reports/lyrics/supplement-20260929-r3')
R5 = os.path.join(ROOT, 'reports/lyrics/supplement-20260929-r5')
STAGE = '/tmp/r5_stage'
os.makedirs(STAGE, exist_ok=True)
os.makedirs(R5, exist_ok=True)

UAV = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36'
HDRS = {'User-Agent': UAV, 'Referer': 'https://www.lizhinb.com/gequ/'}

def safe_url(u):
    if all(ord(c) < 128 for c in u):
        return u
    return urllib.parse.quote(u, safe=":/?&=+,;@!~*()%-'")

def http_get(url, tries=3):
    last = ''
    req_url = safe_url(url)
    for i in range(tries):
        try:
            req = urllib.request.Request(req_url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read(), 200
        except HTTPError as e:
            if e.code == 404:
                return None, 404
            last = str(e)
        except Exception as e:
            last = str(e)
        time.sleep(0.9 + 0.8 * i)
    try:
        p = '/tmp/r5_curl.out'
        r = subprocess.run(['curl', '-sL', '--max-time', '30', '-A', UAV,
                            '-e', 'https://www.lizhinb.com/', '-w', '%{http_code}', '-o', p, req_url],
                           capture_output=True, text=True)
        code = (r.stdout.strip().split() or ['000'])[-1]
        if code == '200' and os.path.exists(p):
            b = open(p, 'rb').read()
            os.remove(p)
            return b, 200
        return None, code
    except Exception as e:
        return None, str(e)

# ---------- 归一化 ----------
VARIANT = str.maketrans({'黒': '黑', '戯': '戏', '郷': '乡', '聴': '听', '伝': '传', '爲': '为',
                         '斉': '齐', '瀬': '濑', '険': '险', '驼': '鸵', '說': '说'})
def norm_t(s):
    s = str(s).strip()
    s = s.replace('（', '(').replace('）', ')').replace('，', ',').replace('、', ',').replace('：', ':').replace('；', ';')
    s = re.sub(r'[\s\u3000]+', '', s)
    s = s.strip('《》「」')
    s = re.sub(r'(ボーカル|ヴォーカル).*$', '', s)
    while True:
        s2 = re.sub(r'\([^()]*\)$', '', s)
        if s2 == s or not s2:
            break
        s = s2
    s = re.sub(r'-\d{1,4}.*$', '', s)
    s = s.translate(VARIANT)
    if s == '关于郑州的回忆':
        s = '关于郑州的记忆'
    return s

def site_id_for(t):
    a = t['album']; s = t['src']
    def H(x):
        return x in a or x in s
    if '我们也爱南京' in a:
        return None
    if '2015版本' in a or '2015版本' in t['title']:
        return 57
    if H('Ballads') or 'Vol.2' in a:
        return 68
    if 'Vol.3' in a or '倒影' in a:
        return 70
    if 'Best Selection' in a:
        return 67
    if '洗心革面' in a:
        return 69
    if 'JAPAN' in a or 'Tokyo' in s or 'Tokyo' in a:
        return 71
    if '吉隆坡' in a or '吉隆坡' in s:
        return 72
    if '义乌' in s:
        return 40
    if '工体东路' in s:
        return 41
    if '十月十六日事件' in a:
        return 43
    if '108个关键词' in a:
        return 50
    if '勾三搭四' in s or '勾三搭四' in a:
        return 52
    if '挺 不插电' in a or '挺不插电' in a or '郑州站' in a:
        return 49
    if 'i／O' in a or 'i/O' in a:
        return 54
    if '酒球会' in s:
        return 55
    if '北京不插电' in s:
        return 60
    if '动静' in s:
        return 59
    if '看见' in s:
        return 56
    if '爵士乐与不插电' in s:
        return 65
    if '管弦乐II' in s:
        return 64
    if '管弦乐' in s:
        return 63
    if '应天大街' in s:
        return 61
    if '金城兰州' in a:
        return 66
    if '被禁忌的游戏' in s:
        return 37
    if '这个世界会好吗' in s:
        return 38
    if '梵高先生' in s:
        return 39
    if '我爱南京' in s:
        return 42
    if '郑州' in s:
        return 44
    if re.search(r'2011[ /-]+F|/F/|/\s*F\s*/', s):
        return 45
    if '1701' in s:
        return 53
    if 'IMAGINE' in s:
        return 46
    return None

# ---------- 载入 ----------
tracks = json.load(open(os.path.join(ROOT, 'tracks.json')))
def has_lrc(t):
    p = os.path.splitext(t['src'])[0] + '.lrc'
    return os.path.exists(p) and os.path.getsize(p) > 0
missing = [t for t in tracks if not has_lrc(t)]
print('missing baseline:', len(missing), flush=True)

index = json.load(open(os.path.join(R3, 'lizhinb-lyrics-index.json')))
byalc = {}
for e in index:
    byalc.setdefault(e['album_id'], []).append(e)
join = {r['trackId']: r for r in json.load(open(os.path.join(R3, 'retrieval-join-r3.json')))['tracks']}
probe = {r['trackId']: r for r in json.load(open(os.path.join(R3, 'lrclib-probe.json')))['results']}

EXCLUDE = set()
for t in missing:
    if 'Ballads' in t['album'] and t['title'].startswith('梵高先生'):
        EXCLUDE.add(t['id'])
print('excluded (Ballads 梵高先生，既定结论不复制传播):', sorted(EXCLUDE), flush=True)

# ---------- 来源A：lizhinb 配套 lrc ----------
TS = re.compile(r'\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]')
OFFTAG = re.compile(r'^\s*\[offset:\s*([+-]?\d+)\s*\]\s*$', re.I)
META = re.compile(r'^\[(ti|ar|al|by|re|ve|au|length):', re.I)
DROP = re.compile(r'https?://|www\.|\.com|\.cn|\.net|\.org|歌词制作|LRC制作|lrc制作|歌词整理|收集整理|搜集整理|编辑整理|更多歌词|歌词下载|下载歌词|QQ群|微信|微博|头条|快手|抖音|酷狗|酷我|QQ音乐|网易云|虾米|百度|搜狐|新浪|关于李志的记忆|李志歌迷站|版权所有|禁止转载|扫描二维码', re.I)
CREDW = r'(?:演唱|唱|词|曲|作词|作曲|词曲|编曲|改编|制作人|制作|监制|录音师|录音|混音师|混音|母带工程师|母带|后期|吉他|木吉他|电吉他|贝斯|贝司|低音吉他|鼓手|鼓|键盘手|键盘|钢琴|电子琴|合成器|打击乐手|打击乐|打击|和声编写|和声|合唱|旁白|口白|念白|配唱|小号|长号|萨克斯|口琴|手风琴|小提琴|大提琴|中提琴|弦乐|管乐|programming|program|编程|编写|人声|女声|男声|童声|朗诵|助理|统筹|企划|出品人|出品|发行人|发行|录音棚|录音室|乐器)'
CRED = re.compile(r'^\s*' + CREDW + r'\s*[:：]')

def tag_ms(m):
    mm, ss, ff = int(m.group(1)), int(m.group(2)), m.group(3)
    fr = 0 if ff is None else (int(ff) if len(ff) == 3 else int(ff) * 10 if len(ff) == 2 else int(ff) * 100)
    return (mm * 60 + ss) * 1000 + fr

def clean_lz(raw_text, local_title, title_line):
    lines = raw_text.splitlines()
    out = []
    stats = {'drop': 0, 'detag': 0, 'empty': 0, 'duptitle': 0}
    nonzero_off = False
    ordered = []
    for ln in lines:
        s = ln.rstrip()
        if not s.strip():
            continue
        mo = OFFTAG.match(s)
        if mo:
            if int(mo.group(1)) != 0:
                nonzero_off = True
            continue
        if META.match(s):
            stats['drop'] += 1
            continue
        body = TS.sub('', s).strip()
        tags = list(TS.finditer(s))
        t0 = min(tag_ms(m) for m in tags) if tags else None
        if DROP.search(body):
            stats['drop'] += 1
            continue
        if not body:
            stats['empty'] += 1
            continue
        nt = norm_t(body)
        if nt == norm_t(local_title) and (t0 is None or t0 <= 600):
            stats['duptitle'] += 1
            continue
        if t0 is not None and t0 <= 1200 and (CRED.match(body) or (t0 <= 300 and ('：' in body or ':' in body) and len(body) <= 40)):
            out.append(body)
            stats['detag'] += 1
            continue
        if t0 is None and CRED.match(body):
            out.append(body)
            continue
        out.append(s)
        for m in tags:
            ordered.append(tag_ms(m))
    first_ts = min(ordered) if ordered else None
    last_ts = max(ordered) if ordered else None
    mono = all(b >= a for a, b in zip(ordered, ordered[1:]))
    return [title_line] + out, dict(ts_count=len(ordered), first_ts=first_ms(first_ts), last_ts=first_ms(last_ts),
                                    monotonic=mono, nonzero_offset=nonzero_off, **stats)

def first_ms(v):
    return None if v is None else round(v / 1000.0, 3)

lz_rows = []
for t in missing:
    if t['artist'] != '李志':
        continue
    aid = site_id_for(t)
    entry = None
    match = None
    alt = []
    if aid is not None:
        for e in byalc.get(aid, []):
            ne = norm_t(e['title']); nt = norm_t(t['title'])
            if ne == nt:
                entry = e; match = 'strict'
                break
        if entry is None:
            for e in byalc.get(aid, []):
                ne = norm_t(e['title']); nt = norm_t(t['title'])
                if (ne and (ne in nt or nt in ne)):
                    entry = e; match = 'loose'
                    break
        if entry is None:
            best = None
            for e in byalc.get(aid, []):
                r = difflib.SequenceMatcher(None, norm_t(e['title']), norm_t(t['title'])).ratio()
                if r >= 0.75 and (best is None or r > best[0]):
                    best = (r, e)
            if best:
                entry = best[1]; match = 'fuzzy'
                alt.append(round(best[0], 3))
    row = dict(trackId=t['id'], title=t['title'], album=t['album'], artist=t['artist'],
               dur=round(t['duration'], 3), src=t['src'], siteId=aid,
               siteTitle=entry['title'] if entry else None,
               siteUrl=entry['lyricsUrl'] if entry else None,
               match=match, fetch=None, http=None, bytes=None,
               ts_count=None, first_ts=None, last_ts=None, monotonic=None,
               overshoot=None, nonzero_offset=None, checks_ok=False, clean_stats=None,
               note='')
    if entry is None:
        j = join.get(t['id'], {})
        if 'lizhinb' in j:
            row['note'] = '仅旧映射命中（未随当前专辑规则）；不自动导入'
            row['match'] = 'join-fallback'
            row['siteId'] = j['lizhinb'].get('albumId')
            row['siteTitle'] = j['lizhinb'].get('title')
            row['siteUrl'] = j['lizhinb'].get('lyricsUrl')
    lz_rows.append(row)
    if not entry:
        continue
    # fetch
    raw, code = http_get(entry['lyricsUrl'])
    row['http'] = code
    if raw is None:
        row['fetch'] = 'fail'
        row['note'] = 'HTTP ' + str(code)
        continue
    row['fetch'] = 'ok'
    row['bytes'] = len(raw)
    try:
        txt = raw.decode('utf-8-sig')
    except Exception:
        try:
            txt = raw.decode('gbk')
        except Exception:
            txt = raw.decode('utf-8', errors='replace')
    title_line = "{} - {}".format(t['title'], t['artist'])
    try:
        cleaned, chk = clean_lz(txt, t['title'], title_line)
    except Exception as e:
        row['fetch'] = 'cleanerr'
        row['note'] = str(e)
        continue
    row.update({k: chk[k] for k in ('ts_count', 'first_ts', 'last_ts', 'monotonic', 'nonzero_offset')})
    row['clean_stats'] = {k: chk[k] for k in ('drop', 'detag', 'empty', 'duptitle')}
    if row['last_ts'] is not None:
        row['overshoot'] = round(row['last_ts'] - t['duration'], 3)
    ok = (row['ts_count'] is not None and row['ts_count'] >= 3 and row['monotonic']
          and not row['nonzero_offset'] and row['last_ts'] is not None
          and row['last_ts'] <= t['duration'] + 1.0
          and row['trackId'] not in EXCLUDE)
    row['checks_ok'] = bool(ok)
    if not ok and not row['note']:
        reasons = []
        if row['ts_count'] is None or row['ts_count'] < 3:
            reasons.append('时间戳过少')
        if row['monotonic'] is False:
            reasons.append('时间戳乱序')
        if row['nonzero_offset']:
            reasons.append('offset标签非零')
        if row['last_ts'] is not None and row['last_ts'] > t['duration'] + 1.0:
            reasons.append(f"末时间戳超音轨 {row['overshoot']}s")
        if row['trackId'] in EXCLUDE:
            reasons.append('既定排除')
        row['note'] = ';'.join(reasons)
    if row['fetch'] == 'ok':
        open(os.path.join(STAGE, t['id'] + '.clean.lrc'), 'w', encoding='utf-8', newline='\n').write('\n'.join(cleaned) + '\n')
        open(os.path.join(STAGE, t['id'] + '.raw.lrc'), 'wb').write(raw)

auto = [r['trackId'] for r in lz_rows if r['match'] == 'strict' and r['checks_ok']]
review = [r for r in lz_rows if r['match'] in ('loose', 'fuzzy', 'join-fallback') or (r['match'] == 'strict' and not r['checks_ok'])]
fails = [r for r in lz_rows if r['fetch'] and r['fetch'] != 'ok']
print('\n===== 来源A（lizhinb 配套 lrc）=====', flush=True)
print('rows:', len(lz_rows), '| strict auto-ok:', len(auto), '| review:', len(review), '| fetch/check fail:', len(fails))
print('no-entry（本专辑规则下网站无对应条目）:', sum(1 for r in lz_rows if r['match'] is None))
from collections import Counter
print('by album:', dict(Counter(r['album'][:18] for r in lz_rows if r['match'])))
print('\n-- review 明细 --')
for r in review:
    print(f"  [{r['match']}] {r['album'][:26]:28s} | {r['title'][:30]:32s} -> {str(r['siteTitle'])[:34]:36s} | http={r['http']} ts={r['ts_count']} last={r['last_ts']} over={r['overshoot']} note={r['note'][:40]}")
print('\n-- fetch/check fail 明细 --')
for r in fails:
    print(f"  [{r['match']}] {r['title'][:34]:36s} | {r['note'][:60]}")

# ---------- 来源B：lrclib ----------
def artist_ok(local, entry):
    a = re.sub(r'\s+', '', (local or '').lower())
    b = re.sub(r'\s+', '', (entry or '').lower())
    if not b:
        return False
    return a == b or a in b or b in a

lc_candidates = []
lz_auto_set = set(auto)
for t in missing:
    p = probe.get(t['id'])
    if not p or p.get('status') != 'found':
        continue
    diff = p.get('bestDurationDiff')
    if diff is None:
        continue
    if diff <= 2.0:
        cands = p.get('candidates') or []
        best = cands[0] if cands else {}
        lc_candidates.append(dict(
            trackId=t['id'], localTitle=t['title'], localAlbum=t['album'], localArtist=t['artist'],
            localDur=round(t['duration'], 3), localSrc=t['src'],
            coveredByLz=t['id'] in lz_auto_set,
            entryId=best.get('id'), entryTrack=best.get('trackName'), entryArtist=best.get('artistName'),
            entryAlbum=best.get('albumName'), entryDur=best.get('duration'), diff=round(diff, 3),
            synced=bool(best.get('hasSyncedLyrics')), plain=bool(best.get('hasPlainLyrics')),
            instrumental=bool(best.get('instrumental')), source='r3-probe'))

# 新查询：未覆盖且 probe 非 close 的曲目（含查无结果的）
req_targets = []
for t in missing:
    if t['id'] in lz_auto_set:
        continue
    if '+' in t['title'] or '＋' in t['title']:
        continue
    p = probe.get(t['id'])
    if p and p.get('status') == 'found' and (p.get('bestDurationDiff') or 99) <= 2.0:
        continue
    req_targets.append(t)
req_targets = req_targets[:220]
print('\n===== 来源B（lrclib）=====', flush=True)
print('r3候选(close):', len(lc_candidates), '| 新查询目标:', len(req_targets), flush=True)

def lrclib_search(track, artist):
    url = 'https://lrclib.net/api/search?' + urllib.parse.urlencode({'track_name': track, 'artist_name': artist})
    raw, code = http_get(url)
    if raw is None:
        return None, code
    try:
        return json.loads(raw.decode('utf-8')), code
    except Exception:
        return None, 'parse'

seen_ids = set()
for x in lc_candidates:
    if x.get('entryId'):
        seen_ids.add(x['entryId'])

new_cands = []
for i, t in enumerate(req_targets, 1):
    tried = 0
    for qt in (t['title'], norm_t(t['title'])):
        if not qt or tried >= 2:
            continue
        tried += 1
        data, code = lrclib_search(qt, t['artist'])
        time.sleep(0.3)
        if not isinstance(data, list):
            continue
        for r in data:
            if not isinstance(r, dict):
                continue
            rid = r.get('id')
            if rid in seen_ids:
                continue
            if not artist_ok(t['artist'], r.get('artistName')):
                continue
            diff = abs((r.get('duration') or 0) - t['duration'])
            if diff > 2.5:
                continue
            seen_ids.add(rid)
            new_cands.append(dict(
                trackId=t['id'], localTitle=t['title'], localAlbum=t['album'], localArtist=t['artist'],
                localDur=round(t['duration'], 3), localSrc=t['src'], coveredByLz=False,
                entryId=rid, entryTrack=r.get('trackName'), entryArtist=r.get('artistName'),
                entryAlbum=r.get('albumName'), entryDur=r.get('duration'), diff=round(diff, 3),
                synced=bool(r.get('syncedLyrics')), plain=bool(r.get('plainLyrics')),
                instrumental=bool(r.get('instrumental')), source='r5-requery', query=qt))
        break
    if i % 40 == 0:
        print(f'  requery {i}/{len(req_targets)} ... 新候选 {len(new_cands)}', flush=True)

print('新查询新增候选:', len(new_cands))

json.dump({'generatedAt': '2026-09-29', 'round': 'r5-phase1',
           'missingBaseline': len(missing),
           'lz_rows': lz_rows, 'lz_auto': auto, 'excludeIds': sorted(EXCLUDE),
           'note': 'lz_rows: 来源A逐条抓取与文本检查（原文暂存 /tmp/r5_stage，仓库未写入歌词）；strict+checks_ok 进入自动导入候审。'},
          open(os.path.join(R5, 'plan-r5.json'), 'w'), ensure_ascii=False, indent=1)
json.dump({'generatedAt': '2026-09-29', 'round': 'r5-phase1',
           'r3CloseCandidates': lc_candidates, 'newCandidates': new_cands,
           'note': 'lrclib候选（已按歌手匹配+时长差<=2.0/2.5s过滤）；是否导入待逐条审核（版本、平台标注）。'},
          open(os.path.join(R5, 'audit-lrclib.json'), 'w'), ensure_ascii=False, indent=1)
print('PHASE1 DONE  | auto:', len(auto), '| review:', len(review), '| lrclib cand:', len(lc_candidates) + len(new_cands), flush=True)
