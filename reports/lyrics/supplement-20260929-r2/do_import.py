#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write the two verified same-recording LRC copies for Ballads d02-t09/d02-t10.
Timestamps shifted by the measured offsets from supplement-20260929/local-reuse-review.json;
each tag rounded ROUND_HALF_UP to 1ms; non-timed lines preserved verbatim."""
import json, os, re
from decimal import Decimal, ROUND_HALF_UP

ROOT = "/Users/roylyl/Documents/GitHub/Music"
OUT = os.path.join(ROOT, "reports/lyrics/supplement-20260929-r2/local-imports.json")

IMPORTS = [
    {
        "sourceTrackId": "lizhi-8b283e60-70fa-46ea-a564-675db0444a8b-d01-t01",
        "targetTrackId": "lizhi-30817cce-0960-44cd-b570-d39bcd8c8de5-d02-t09",
        "source": "live/李志/2018 - 爵士乐与不插电新编12首/01-01 - 看见.lrc",
        "target": "collections/李志/2020 - Best Selection Songs 2004-2018 Vol.2 - Ballads（叙事歌）/02-09 - 看见.lrc",
        "offsetMilliseconds": 82.125,
        "targetDurationSeconds": 235.093,
        "minimumSampleCorrelation": 0.984479,
        "sampleOffsetSpreadMilliseconds": 0.0,
    },
    {
        "sourceTrackId": "lizhi-8b283e60-70fa-46ea-a564-675db0444a8b-d01-t06",
        "targetTrackId": "lizhi-30817cce-0960-44cd-b570-d39bcd8c8de5-d02-t10",
        "source": "live/李志/2018 - 爵士乐与不插电新编12首/01-06 - 热河.lrc",
        "target": "collections/李志/2020 - Best Selection Songs 2004-2018 Vol.2 - Ballads（叙事歌）/02-10 - 热河.lrc",
        "offsetMilliseconds": 34.125,
        "targetDurationSeconds": 478.32,
        "minimumSampleCorrelation": 0.985574,
        "sampleOffsetSpreadMilliseconds": 0.0,
    },
]

TS_RE = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")


def tag_to_ms(m):
    mm, ss, ff = int(m.group(1)), int(m.group(2)), m.group(3)
    if ff is None:
        frac = 0
    elif len(ff) == 3:
        frac = int(ff)
    elif len(ff) == 2:
        frac = int(ff) * 10
    else:
        frac = int(ff) * 100
    return (mm * 60 + ss) * 1000 + frac


def ms_to_tag(ms):
    total_s, msec = divmod(ms, 1000)
    mm, ss = divmod(total_s, 60)
    return f"[{mm:02d}:{ss:02d}.{msec:03d}]"


def shift_line(line, off):
    state = {"err": Decimal("0"), "shifted": []}

    def repl(m):
        new = Decimal(tag_to_ms(m)) + off
        new_ms = int(new.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        state["err"] = max(state["err"], abs(new - new_ms))
        state["shifted"].append(new_ms)
        return ms_to_tag(new_ms)

    return TS_RE.sub(repl, line), state


def main():
    report = []
    for imp in IMPORTS:
        src_path = os.path.join(ROOT, imp["source"])
        tgt_path = os.path.join(ROOT, imp["target"])
        if os.path.exists(tgt_path):
            raise SystemExit(f"refusing to overwrite existing file: {tgt_path}")
        with open(src_path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        off = Decimal(str(imp["offsetMilliseconds"]))
        out_lines, shifted, max_err = [], [], Decimal("0")
        for ln in lines:
            oln, state = shift_line(ln, off)
            out_lines.append(oln)
            shifted.extend(state["shifted"])
            max_err = max(max_err, state["err"])
        # validation: body timestamps monotonic and within target duration
        body_ts = []
        for oln, ln in zip(out_lines, lines):
            if TS_RE.search(ln) and TS_RE.sub("", ln).strip():
                for m in TS_RE.finditer(oln):
                    body_ts.append(int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3) or 0) / 1000.0)
        mono = all(b >= a for a, b in zip(body_ts, body_ts[1:]))
        in_bounds = all(0 <= t <= imp["targetDurationSeconds"] for t in body_ts)
        if not mono:
            raise SystemExit("timestamps not monotonic: " + imp["target"])
        if not in_bounds:
            raise SystemExit("timestamp out of target duration: " + imp["target"])
        if len(out_lines) != len(lines):
            raise SystemExit("line count changed")
        for a, b in zip(lines, out_lines):
            if not TS_RE.search(a):
                if a != b:
                    raise SystemExit(f"non-timed line changed: {a!r}")
            elif TS_RE.sub("", a) != TS_RE.sub("", b):
                raise SystemExit(f"timed text changed: {a!r}")
        with open(tgt_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out_lines) + "\n")
        entry = dict(imp)
        entry.update({
            "status": "imported",
            "sourceOffsetTagMilliseconds": 0,
            "totalAppliedOffsetMilliseconds": imp["offsetMilliseconds"],
            "rounding": "每个变换后的时间标签按ROUND_HALF_UP四舍五入到最接近的1毫秒，输出三位小数；未先对整体偏移取整。",
            "maximumRoundingErrorMilliseconds": float(max_err),
            "sourceLineCount": len(lines),
            "targetLineCount": len(out_lines),
            "timestampCount": len(shifted),
            "firstTimestampSeconds": min(body_ts) if body_ts else None,
            "lastTimestampSeconds": max(body_ts) if body_ts else None,
            "monotonic": mono,
            "targetTimeBoundaryValid": in_bounds,
            "bodyAndCreditsPreserved": True,
            "sourceUnchanged": True,
            "notes": "复用上一轮supplement-20260929/local-reuse-review.json的音频抽样证据（三段8秒窗口最小相关性0.984/0.986，偏移离散0毫秒），本轮未重复抽样。未逐句听辨。",
        })
        report.append(entry)
        print("imported:", imp["target"], "| lines:", len(out_lines), "| ts:", len(shifted),
              "| first:", min(body_ts), "| last:", max(body_ts))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"generatedAt": "2026-09-29", "libraryRoot": ROOT,
                   "evidenceSource": "supplement-20260929/local-reuse-review.json (audio sampling, reused)",
                   "imported": len(report), "imports": report}, f, ensure_ascii=False, indent=1)
    print("saved", OUT)


if __name__ == "__main__":
    main()
