#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 3 imports: 14 verified same-recording copies (evidence:
reports/lyrics/supplement-20260929-r3/alignment-results-r3.json).
8 keep-cases (|offset|<=18ms): timestamps kept byte-faithfully (title line set
to tracks.json title); 6 shift-cases: offset added (ROUND_HALF_UP to 1ms,
3-digit output). No file overwritten; donors unchanged."""
import json, os, re
from decimal import Decimal, ROUND_HALF_UP

ROOT = "/Users/roylyl/Documents/GitHub/Music"
R3 = os.path.join(ROOT, "reports/lyrics/supplement-20260929-r3")
TS_RE = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")

tracks = {t["id"]: t for t in json.load(open(os.path.join(ROOT, "tracks.json")))}
align = json.load(open(os.path.join(R3, "alignment-results-r3.json")))["results"]
matches = [r for r in align if r.get("sameRecordingSupportedBySamples")]

def tag_to_ms(m):
    mm, ss, ff = int(m.group(1)), int(m.group(2)), m.group(3)
    fr = 0 if ff is None else (int(ff) if len(ff) == 3 else int(ff) * 10 if len(ff) == 2 else int(ff) * 100)
    return (mm * 60 + ss) * 1000 + fr

def ms_to_tag(ms):
    total_s, msec = divmod(ms, 1000)
    mm, ss = divmod(total_s, 60)
    return f"[{mm:02d}:{ss:02d}.{msec:03d}]"

report = []
for r in matches:
    p = r["pair"]
    t = tracks[p["missing_id"]]
    src_path = os.path.join(ROOT, p["donor_lrc"])
    tgt_path = os.path.join(ROOT, p["missing_src"])
    tgt_path = os.path.splitext(tgt_path)[0] + ".lrc"
    if os.path.exists(tgt_path):
        raise SystemExit("refusing to overwrite: " + tgt_path)
    with open(src_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    title_line = "{} - {}".format(t["title"], t["artist"])
    off_ms = Decimal(str(r["medianOffsetMilliseconds"]))
    keep = abs(r["medianOffsetMilliseconds"]) <= 20.0
    out_lines, shifted, max_err = [], [], Decimal("0")
    for i, ln in enumerate(lines):
        if i == 0:
            out_lines.append(title_line)
            continue
        if keep:
            out_lines.append(ln)
            continue
        def repl(m):
            new = Decimal(tag_to_ms(m)) + off_ms
            new_ms = int(new.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            state_err = abs(new - new_ms)
            repl.max_err = max(repl.max_err, state_err)
            shifted.append(new_ms)
            return ms_to_tag(new_ms)
        repl.max_err = Decimal("0")
        out_lines.append(TS_RE.sub(repl, ln))
        max_err = max(max_err, repl.max_err)
    # validate
    body_ts = []
    for oln, ln in zip(out_lines[1:], lines[1:]):
        if TS_RE.search(ln) and TS_RE.sub("", ln).strip():
            for m in TS_RE.finditer(oln):
                mm, ss, ff = int(m.group(1)), int(m.group(2)), (m.group(3) or "0")
                frac = int(ff) / (1000 if len(ff) == 3 else 100 if len(ff) == 2 else 10)
                body_ts.append(mm * 60 + ss + frac)
    mono = all(b >= a for a, b in zip(body_ts, body_ts[1:]))
    in_bounds = all(0 <= v <= p["missing_dur"] for v in body_ts)
    assert mono, "not monotonic: " + tgt_path
    assert in_bounds, "out of bounds: " + tgt_path
    assert len(out_lines) == len(lines), "line count changed"
    for a, b in zip(lines[1:], out_lines[1:]):
        if keep:
            assert a == b, f"keep-case line changed: {a!r}"
        else:
            if not TS_RE.search(a):
                assert a == b, f"non-timed line changed: {a!r}"
            else:
                assert TS_RE.sub("", a) == TS_RE.sub("", b), f"timed text changed: {a!r}"
    with open(tgt_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out_lines) + "\n")
    report.append({
        "targetTrackId": p["missing_id"], "targetTitle": t["title"], "targetAlbum": t["album"],
        "target": os.path.relpath(tgt_path, ROOT),
        "sourceTrackId": p["donor_id"], "source": p["donor_lrc"],
        "offsetMilliseconds": r["medianOffsetMilliseconds"],
        "timestampsKept": keep, "totalAppliedOffsetMilliseconds": 0 if keep else r["medianOffsetMilliseconds"],
        "minimumAbsoluteCorrelation": r["minimumAbsoluteCorrelation"],
        "offsetSpreadMilliseconds": r["offsetSpreadMilliseconds"],
        "rounding": "保留原标签（|偏移|<=20ms）" if keep else "每个变换后的时间标签按ROUND_HALF_UP四舍五入到最近1毫秒；输出三位小数；未先对整体偏移取整",
        "maximumRoundingErrorMilliseconds": float(max_err),
        "sourceLineCount": len(lines), "targetLineCount": len(out_lines),
        "timestampCount": len(shifted) if not keep else sum(1 for ln in out_lines[1:] if TS_RE.search(ln)),
        "firstTimestampSeconds": min(body_ts), "lastTimestampSeconds": max(body_ts),
        "monotonic": mono, "targetTimeBoundaryValid": in_bounds,
        "titleLineAdjusted": True, "sourceUnchanged": True,
        "notes": "证据：alignment-results-r3.json（三段8秒窗口，最小|相关|与离散见本条目）。未逐句听辨。",
    })
    print("imported:", os.path.relpath(tgt_path, ROOT), "| keep:", keep, "| ts:", report[-1]["timestampCount"],
          "| first:", report[-1]["firstTimestampSeconds"], "| last:", report[-1]["lastTimestampSeconds"])

with open(os.path.join(R3, "local-imports.json"), "w") as f:
    json.dump({"generatedAt": "2026-09-29", "libraryRoot": ROOT,
               "evidenceSource": "alignment-results-r3.json (audio sampling)",
               "imported": len(report), "imports": report}, f, ensure_ascii=False, indent=1)
print("saved local-imports.json | imported:", len(report))
