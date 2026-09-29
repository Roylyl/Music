#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r5 本地复用导入（3份）：8窗口密集复核达标（minAbs 0.898-0.910，偏移离散<=0.46ms，
正极性）——判定为同一演唱录音的母带/响度差异版本。证据：dense-verification.json。
偏移 |off|>20ms 的重放；<=20ms 保留原时间戳。不覆盖已有文件。"""
import json, os, re
from decimal import Decimal, ROUND_HALF_UP

ROOT = '/Users/roylyl/Documents/GitHub/Music'
R5 = os.path.join(ROOT, 'reports/lyrics/supplement-20260929-r5')
TS = re.compile(r'\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]')

IMPORTS = [
    dict(target='lizhi-f441c560-c866-410a-a53e-432f3e69b809-d01-t01',
         donor='lizhi-758a394c-126c-487f-bca1-31ff28467d13-d01-t06',
         off=560.375, minabs=0.9098, spread=0.12),
    dict(target='lizhi-f441c560-c866-410a-a53e-432f3e69b809-d01-t03',
         donor='lizhi-083e1542-8767-4a92-8465-bc3fb233b8b9-d01-t05',
         off=-719.625, minabs=0.9034, spread=0.12),
    dict(target='lizhi-f441c560-c866-410a-a53e-432f3e69b809-d01-t05',
         donor='lizhi-38d58d47-5f00-4f4b-95aa-f499cdba365b-d01-t04',
         off=-15.625, minabs=0.8979, spread=0.46),
]

tracks = {t['id']: t for t in json.load(open(os.path.join(ROOT, 'tracks.json')))}

def tag_to_ms(m):
    mm, ss, ff = int(m.group(1)), int(m.group(2)), m.group(3)
    fr = 0 if ff is None else (int(ff) if len(ff) == 3 else int(ff) * 10 if len(ff) == 2 else int(ff) * 100)
    return (mm * 60 + ss) * 1000 + fr

def ms_to_tag(ms):
    s, ms2 = divmod(ms, 1000)
    mm, ss = divmod(s, 60)
    return f"[{mm:02d}:{ss:02d}.{ms2:03d}]"

report = []
for imp in IMPORTS:
    t = tracks[imp['target']]
    d = tracks[imp['donor']]
    src_lrc = os.path.splitext(os.path.join(ROOT, d['src']))[0] + '.lrc'
    tgt_lrc = os.path.splitext(os.path.join(ROOT, t['src']))[0] + '.lrc'
    assert os.path.exists(src_lrc), src_lrc
    assert not os.path.exists(tgt_lrc), 'refuse overwrite: ' + tgt_lrc
    print('PAIR:', t['title'], '<-', d['title'], '|', t['album'], '<-', d['album'])
    lines = open(src_lrc, encoding='utf-8').read().splitlines()
    print('  donor head:', lines[0][:60], '|', (lines[1][:40] if len(lines) > 1 else ''))
    keep = abs(imp['off']) <= 20.0
    off = Decimal(str(imp['off']))
    out = ["{} - {}".format(t['title'], t['artist'])]
    ordered_ms = []
    maxerr = Decimal('0')
    for ln in lines[1:]:
        if keep:
            out.append(ln)
            for m in TS.finditer(ln):
                ordered_ms.append(tag_to_ms(m))
            continue
        parts = []
        pos = 0
        for m in TS.finditer(ln):
            parts.append(ln[pos:m.start()])
            new = Decimal(tag_to_ms(m)) + off
            nm = int(new.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            err = abs(new - nm)
            if err > maxerr:
                maxerr = err
            if nm < 0:
                nm = 0
            ordered_ms.append(nm)
            parts.append(ms_to_tag(nm))
            pos = m.end()
        parts.append(ln[pos:])
        out.append(''.join(parts))
    mono = all(b >= a for a, b in zip(ordered_ms, ordered_ms[1:]))
    inb = all(0 <= v <= t['duration'] * 1000.0 for v in ordered_ms)
    assert mono, 'not monotonic'
    assert inb, 'out of bounds'
    # body timestamps only for stats
    body = []
    for ln in out[1:]:
        txt = TS.sub('', ln).strip()
        if TS.search(ln) and txt:
            for m in TS.finditer(ln):
                mm, ss, ff = int(m.group(1)), int(m.group(2)), (m.group(3) or '0')
                frac = int(ff) / (1000 if len(ff) == 3 else 100 if len(ff) == 2 else 10)
                body.append(mm * 60 + ss + frac)
    open(tgt_lrc, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    report.append(dict(
        targetTrackId=imp['target'], targetTitle=t['title'], targetAlbum=t['album'],
        target=os.path.relpath(tgt_lrc, ROOT),
        sourceTrackId=imp['donor'], source=os.path.relpath(src_lrc, ROOT),
        offsetMilliseconds=imp['off'], timestampsKept=keep,
        minAbsCorrelation=imp['minabs'], offsetSpreadMs=imp['spread'], windows=8, polarity='positive',
        tsTotal=sum(1 for ln in out if TS.search(ln)), tsBody=len(body),
        firstTs=round(min(body), 3) if body else None, lastTs=round(max(body), 3) if body else None,
        maxRoundingErrorMs=float(maxerr), monotonic=mono, withinTargetDuration=inb,
        note='8窗口密集复核通过（偏移离散<=0.46ms、恒定偏移、正极性）；判为同一演唱录音、母带/响度处理不同；时间戳已按恒定偏移校正；未逐句听辨。'))
    print('  -> wrote', os.path.relpath(tgt_lrc, ROOT), '| ts', report[-1]['tsTotal'], '| first', report[-1]['firstTs'], '| last', report[-1]['lastTs'], '| keep', keep)

json.dump({'generatedAt': '2026-09-29', 'round': 'r5',
           'evidence': 'reports/lyrics/supplement-20260929-r5/dense-verification.json (8-window)',
           'imported': len(report), 'imports': report},
          open(os.path.join(R5, 'local-reuse-imports-r5.json'), 'w'), ensure_ascii=False, indent=1)
print('saved local-reuse-imports-r5.json | files:', len(report))
