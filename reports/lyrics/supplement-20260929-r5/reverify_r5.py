#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r5 dense re-verification (read-only audio probing):
(a) rebuild same-title missing->donor pairs with aggressive normalization,
    keep only never-tested ones;
(b) re-verify r1-r4 moderate candidates (offset spread <= 12 ms);
(c) manual probes.
For each pair: 8 x 8s windows (6%-90%) cross-correlation, plus a 45 s
long-segment validation. Writes dense-verification.json."""
import importlib.util, json, os, re, unicodedata

ROOT = "/Users/roylyl/Documents/GitHub/Music"
R5 = os.path.join(ROOT, "reports/lyrics/supplement-20260929-r5")
os.makedirs(R5, exist_ok=True)

spec = importlib.util.spec_from_file_location(
    "ar2", os.path.join(ROOT, "reports/lyrics/supplement-20260929-r2/align_reuse.py"))
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)

tracks = json.load(open(os.path.join(ROOT, "tracks.json")))
T = {t["id"]: t for t in tracks}

def haslrc(t):
    p = os.path.join(ROOT, os.path.splitext(t["src"])[0] + ".lrc")
    return os.path.exists(p) and os.path.getsize(p) > 0

missing = [t for t in tracks if not haslrc(t)]
donors = [t for t in tracks if haslrc(t)]
print("missing:", len(missing), "donors:", len(donors), flush=True)

VAR = str.maketrans({'黒': '黑', '戯': '戏', '郷': '乡', '聴': '听', '伝': '传',
                     '爲': '为', '斉': '齐', '瀬': '濑', '険': '险'})

def norm_title(s):
    s = unicodedata.normalize("NFKC", s)
    while True:
        s2 = re.sub(r"[\(（\[【][^()（）\[\]【】]*[\)）\]】]\s*$", "", s)
        if s2 == s or not s2:
            break
        s = s2
    s = re.sub(r"\s*(ボーカル|ヴォーカル).*$", "", s)
    s = s.replace("驼鸟", "鸵鸟").replace("么", "吗")
    s = s.translate(VAR)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[·・。，、！？!?：:；;\-—–~～\"'“”‘’《》〈〉&+＋]", "", s)
    return s

def norm_artist(a):
    a = a.lower()
    return re.split(r"[/&,，、]", a)[0].strip()

tested = set()
def addpair(mid, sid):
    if mid and sid:
        tested.add((mid, sid))
try:
    r1 = json.load(open(os.path.join(ROOT, "reports/lyrics/supplement-20260929/local-reuse-review.json")))
    for gr in r1["results"]:
        addpair(gr.get("targetTrackId"), gr.get("sourceTrackId"))
    r2 = json.load(open(os.path.join(ROOT, "reports/lyrics/supplement-20260929-r2/alignment-results.json")))
    for r in r2.get("results", []):
        for att in r.get("attempts", []) or []:
            p = att.get("pair") or {}
            addpair(p.get("missing_id"), p.get("donor_id"))
    for rnd in ("r3", "r4"):
        d = json.load(open(os.path.join(ROOT, f"reports/lyrics/supplement-20260929-{rnd}/alignment-results-{rnd}.json")))
        for r in d.get("results", []):
            p = r.get("pair") or {}
            addpair(p.get("missing_id"), p.get("donor_id"))
except Exception as e:
    print("tested-load err:", e, flush=True)
print("tested pairs loaded:", len(tested), flush=True)

by_base = {}
for d in donors:
    by_base.setdefault(norm_title(d["title"]), []).append(d)

plans = []
seen = set()
def plan(mid, did, why):
    if (mid, did) in seen:
        return
    a, b = T[mid], T[did]
    if haslrc(a):
        return
    if "梵高先生" in a["title"] or "梵高先生" in b["title"]:
        return  # protected case: never propagate
    seen.add((mid, did))
    plans.append((mid, did, why))

for m in missing:
    if any(ch in m["title"] for ch in ("+", "＋", "&")):
        continue
    bt = norm_title(m["title"])
    if not bt:
        continue
    for d in by_base.get(bt, []):
        if d["id"] == m["id"]:
            continue
        if norm_artist(d["artist"]) != norm_artist(m["artist"]):
            continue
        if (m["id"], d["id"]) in tested:
            continue
        plan(m["id"], d["id"], "untested-matrix")

mod = json.load(open(os.path.join(R5, "moderate-corr-candidates.json")))
for x in mod:
    if x.get("spread_ms", 1e9) <= 12:
        plan(x["tid"], x["sid"], "reverify-" + str(x.get("round")))

for m in missing:
    if m["title"] == "忽然 余赣宁":
        for d in donors:
            if d["title"] == "忽然":
                plan(m["id"], d["id"], "probe")

print("planned pairs:", len(plans), flush=True)
for mid, did, why in plans:
    print("  -", T[mid]["title"][:40], "->", T[did]["title"][:30], "|", T[did]["album"][:30], "|", why, flush=True)

WIN = ar.WIN
SEARCH_PAD = ar.SEARCH_PAD
SR = ar.SR
FR8 = [0.06, 0.18, 0.30, 0.42, 0.54, 0.66, 0.78, 0.90]

def analyze(mid, did):
    m, d = T[mid], T[did]
    mp = os.path.join(ROOT, m["src"])
    dp = os.path.join(ROOT, d["src"])
    shorter = min(m["duration"], d["duration"])
    ev = []
    for f in FR8:
        s_start = shorter * f - WIN / 2
        if s_start < 0:
            s_start = 0.0
        t_start = s_start - SEARCH_PAD
        if t_start < 0:
            t_start = 0.0
        try:
            sw = ar.decode(dp, s_start, WIN)
            tw = ar.decode(mp, t_start, WIN + 2 * SEARCH_PAD)
            if sw.size < SR * 2 or tw.size < sw.size:
                ev.append({"f": f, "err": "short"})
                continue
            corr, lag = ar.best_corr(sw, tw)
            off = ((t_start + lag) - s_start) * 1000.0
            ev.append({"f": f, "corr": round(corr, 6), "absCorr": round(abs(corr), 6), "offMs": round(off, 3)})
        except Exception as e:
            ev.append({"f": f, "err": str(e)[:100]})
    res = {"mid": mid, "did": did, "titleM": m["title"], "albumM": m["album"],
           "titleD": d["title"], "albumD": d["album"], "durM": m["duration"], "durD": d["duration"],
           "delta": round(abs(m["duration"] - d["duration"]), 3), "windows": ev}
    oks = [e for e in ev if "corr" in e]
    if oks:
        minabs = min(e["absCorr"] for e in oks)
        offs = [e["offMs"] for e in oks]
        spread = max(offs) - min(offs)
        med = sorted(offs)[len(offs) // 2]
        pol = "pos" if all(e["corr"] > 0 for e in oks) else ("neg" if all(e["corr"] < 0 for e in oks) else "mixed")
        res.update({"minAbs": round(minabs, 6), "spreadMs": round(spread, 3),
                    "medianOffMs": round(med, 3), "polarity": pol, "nWin": len(oks)})
        if minabs >= 0.60 and spread <= 10.0:
            lon = min(45.0, shorter * 0.5)
            f = 0.45
            s0 = shorter * f - lon / 2
            if s0 < 0:
                s0 = 0.0
            t0 = max(0.0, s0 - 2.0)
            try:
                sw = ar.decode(dp, s0, lon)
                tw = ar.decode(mp, t0, lon + 4.0)
                if sw.size >= SR * 2 and tw.size >= sw.size:
                    corr, lag = ar.best_corr(sw, tw)
                    seg_off = ((t0 + lag) - s0) * 1000.0
                    res["seg"] = {"len": round(lon, 1), "f": f, "corr": round(corr, 6),
                                  "absCorr": round(abs(corr), 6), "offMs": round(seg_off, 3),
                                  "offDeltaVsMedian": round(seg_off - med, 3)}
            except Exception as e:
                res["seg"] = {"err": str(e)[:100]}
    return res

out = []
for i, (mid, did, why) in enumerate(plans, 1):
    try:
        r = analyze(mid, did)
    except Exception as e:
        r = {"mid": mid, "did": did, "titleM": T[mid]["title"], "error": str(e)[:200]}
    r["why"] = why
    out.append(r)
    if i % 8 == 0 or i == len(plans):
        json.dump({"results": out}, open(os.path.join(R5, "dense-verification.json"), "w"),
                  ensure_ascii=False, indent=1)
    seg = (r.get("seg") or {})
    print(f"[{i}/{len(plans)}] {str(r.get('titleM'))[:34]:36s} min={r.get('minAbs')} sp={r.get('spreadMs')} "
          f"seg={seg.get('absCorr')} segd={seg.get('offDeltaVsMedian')}", flush=True)

json.dump({"results": out}, open(os.path.join(R5, "dense-verification.json"), "w"),
          ensure_ascii=False, indent=1)
print("saved", os.path.join(R5, "dense-verification.json"), len(out), flush=True)

tab = sorted([r for r in out if "minAbs" in r], key=lambda x: -x["minAbs"])
print("\n=== TABLE (sorted by minAbs desc) ===")
for r in tab:
    seg = (r.get("seg") or {})
    print(f"{r['minAbs']:.3f} sp{r['spreadMs']:7.2f} segr={seg.get('absCorr')} segd={seg.get('offDeltaVsMedian')} "
          f"| {r['titleM'][:34]:36s} -> {r['titleD'][:22]:24s} | {r['why']}")
