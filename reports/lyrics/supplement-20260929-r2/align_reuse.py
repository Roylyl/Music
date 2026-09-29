#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reuse-review round 2: verify whether a missing-lyric track is the same
recording as an in-repo donor track that already has an LRC.

Method replicated from reports/lyrics/supplement-20260929/local-reuse-review.json:
- read-only ffmpeg accurate seeks, 8s source windows centered at 20/50/80%
  of the shorter duration, 8kHz mono PCM via stdout;
- target search window: source window start - 4s, length 16s;
- mean-removed, amplitude-normalized cross-correlation, 1-sample resolution
  (0.125 ms at 8kHz);
- acceptance: min |corr| >= 0.92 on all windows, offset spread <= 15 ms,
  same correlation polarity on all windows.
Positive offset means: target audio holds the same sample LATER than source;
source lyric timestamps would need that offset ADDED for the target file.
"""
import json, os, re, subprocess, sys
from fractions import Fraction

import numpy as np
import imageio_ffmpeg

ROOT = "/Users/roylyl/Documents/GitHub/Music"
R2 = os.path.join(ROOT, "reports/lyrics/supplement-20260929-r2")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SR = 8000
WIN = 8.0
SEARCH_PAD = 4.0
MIN_CORR = 0.92
MAX_SPREAD_MS = 15.0
KEEP_TS_MAX_OFFSET_MS = 20.0
MAX_DONORS_PER_TRACK = 5

def decode(path, start, dur):
    cmd = [FFMPEG, "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
           "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {path}: {p.stderr.decode(errors='replace')[:200]}")
    a = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float64) / 32768.0
    return a

def best_corr(src_win, tgt_seg):
    """Normalized cross-correlation of src_win inside tgt_seg. Returns (corr, lag_seconds)."""
    s = src_win - src_win.mean()
    ns = int(s.size)
    nt = int(tgt_seg.size)
    nlags = nt - ns + 1
    if nlags <= 0:
        return 0.0, 0.0
    # cross-correlation via FFT
    nfft = 1 << (nt + ns - 1).bit_length()
    S = np.fft.rfft(s, nfft)
    T = np.fft.rfft(tgt_seg, nfft)
    xc = np.fft.irfft(T * np.conj(S), nfft)[:nlags]  # sum s[i]*t[lag+i]
    # per-lag normalization
    s_energy = np.sqrt(np.sum(s * s))
    t2 = tgt_seg * tgt_seg
    csum = np.concatenate(([0.0], np.cumsum(t2)))
    t_energy = np.sqrt(csum[ns:] - csum[:-ns])
    t_mean_sum = np.concatenate(([0.0], np.cumsum(tgt_seg)))
    t_sum = t_mean_sum[ns:] - t_mean_sum[:-ns]
    t_mean = t_sum / ns
    # mean-removed correlation numerator: sum((s-s̄)(t-t̄)) = xc - s̄... s already mean-removed,
    # so sum(s*(t-t̄_lag)) = sum(s*t) - t̄_lag*sum(s) = xc (since sum(s)==0)
    denom = s_energy * t_energy
    denom[denom == 0] = 1e-12
    corr = xc / denom
    i = int(np.argmax(np.abs(corr)))
    return float(corr[i]), float(i) / SR

def lrc_parse(path):
    """Return (lines, offset_tag_ms, ts_count, body_ts_list_seconds, has_karaoke)."""
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    lines = raw.splitlines()
    offset_ms = 0
    ts_re = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
    body_ts = []
    has_karaoke = bool(re.search(r"<\d{1,2}:\d{2}", raw))
    for ln in lines:
        m = re.match(r"^\s*\[offset:\s*([+-]?\d+)\s*\]", ln, re.I)
        if m:
            offset_ms = int(m.group(1))
            continue
        tags = ts_re.findall(ln)
        text = ts_re.sub("", ln).strip()
        if tags and text:
            for mm, ss, ff in tags:
                frac = 0.0
                if ff:
                    frac = int(ff) / (1000 if len(ff) == 3 else 100 if len(ff) == 2 else 10)
                body_ts.append(int(mm) * 60 + int(ss) + frac)
    return lines, offset_ms, len(body_ts), body_ts, has_karaoke

def audio_duration(path):
    cmd = [FFMPEG, "-v", "error", "-i", path, "-f", "null", "-"]
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    m = re.findall(rb"time=(\d+):(\d+):([\d.]+)", p.stderr)
    if m:
        h, mm, ss = m[-1]
        return int(h) * 3600 + int(mm) * 60 + float(ss)
    return None

def test_pair(miss, donor):
    """Run 3-window correlation. miss/donor: dicts with src (repo-relative) and duration."""
    mp = os.path.join(ROOT, miss["src"])
    dp = os.path.join(ROOT, donor["src"])
    shorter = min(miss["duration"], donor["duration"])
    evidence = []
    for frac in (0.2, 0.5, 0.8):
        s_start = shorter * frac - WIN / 2
        if s_start < 0:
            s_start = 0.0
        t_start = s_start - SEARCH_PAD
        if t_start < 0:
            t_start = 0.0
        try:
            sw = decode(dp, s_start, WIN)
            tw = decode(mp, t_start, WIN + 2 * SEARCH_PAD)
        except Exception as e:
            return {"error": str(e)}
        if sw.size < SR * 2 or tw.size < sw.size:
            return {"error": "decode too short"}
        corr, lag = best_corr(sw, tw)
        offset_ms = ((t_start + lag) - s_start) * 1000.0
        # zero-offset reference correlation
        z_lag = int(round((s_start - t_start) * SR))
        z = 0.0
        if 0 <= z_lag <= tw.size - sw.size:
            seg = tw[z_lag:z_lag + sw.size]
            s0 = sw - sw.mean(); t0 = seg - seg.mean()
            d = np.sqrt(np.sum(s0 * s0) * np.sum(t0 * t0))
            z = float(np.sum(s0 * t0) / d) if d else 0.0
        evidence.append({
            "sourceStartSeconds": round(s_start, 3), "sourceWindowSeconds": WIN,
            "targetSearchStartSeconds": round(t_start, 3), "targetSearchSeconds": WIN + 2 * SEARCH_PAD,
            "correlation": round(corr, 6), "absoluteCorrelation": round(abs(corr), 6),
            "offsetMilliseconds": round(offset_ms, 3), "zeroOffsetCorrelation": round(z, 6),
        })
    corrs = [e["correlation"] for e in evidence]
    offs = [e["offsetMilliseconds"] for e in evidence]
    min_abs = min(abs(c) for c in corrs)
    same_pol = all(c > 0 for c in corrs) or all(c < 0 for c in corrs)
    spread = max(offs) - min(offs)
    same_rec = min_abs >= MIN_CORR and spread <= MAX_SPREAD_MS and same_pol
    med = sorted(offs)[1]
    return {
        "evidence": evidence,
        "sameRecordingSupportedBySamples": bool(same_rec),
        "minimumAbsoluteCorrelation": round(min_abs, 6),
        "medianOffsetMilliseconds": round(med, 3),
        "offsetSpreadMilliseconds": round(spread, 3),
        "maximumAbsoluteOffsetMilliseconds": round(max(abs(o) for o in offs), 3),
        "sameCorrelationPolarity": bool(same_pol),
        "polarity": "positive" if all(c > 0 for c in corrs) else ("negative" if all(c < 0 for c in corrs) else "mixed"),
        "canKeepOriginalTimestamps": bool(same_rec and max(abs(o) for o in offs) <= KEEP_TS_MAX_OFFSET_MS),
    }

def main():
    with open(os.path.join(R2, "reuse-candidates.json")) as f:
        pairs = json.load(f)["pairs"]
    with open(os.path.join(ROOT, "tracks.json")) as f:
        tracks = {t["id"]: t for t in json.load(f)}

    # previously tested conclusively: skip re-test, reuse prior verdict
    prev = {}
    prev_path = os.path.join(ROOT, "reports/lyrics/supplement-20260929/local-reuse-review.json")
    with open(prev_path) as f:
        for r in json.load(f)["results"]:
            prev[(r["targetTrackId"], r["sourceTrackId"])] = r

    by_missing = {}
    for p in pairs:
        if not p["same_artist"]:
            continue
        by_missing.setdefault(p["missing_id"], []).append(p)

    results = []
    tested = 0
    for mid, cands in by_missing.items():
        cands.sort(key=lambda x: x["dur_diff"])
        best = None
        attempts = []
        for p in cands[:MAX_DONORS_PER_TRACK]:
            key = (p["missing_id"], p["donor_id"])
            if key in prev:
                r = prev[key]
                verdict = {
                    "pair": p, "previouslyTested": True,
                    "sameRecordingSupportedBySamples": r["sameRecordingSupportedBySamples"],
                    "medianOffsetMilliseconds": r["medianOffsetMilliseconds"],
                    "minimumAbsoluteCorrelation": r["minimumAbsoluteCorrelation"],
                    "decision": r["decision"],
                }
                attempts.append(verdict)
                if r["sameRecordingSupportedBySamples"] and r["decision"] != "source-timeline-invalid":
                    best = verdict
                    break
                continue
            miss_t = tracks[p["missing_id"]]
            donor_t = {"src": p["donor_src"], "duration": p["donor_dur"]}
            miss_d = {"src": p["missing_src"], "duration": p["missing_dur"]}
            res = test_pair(miss_d, donor_t)
            tested += 1
            res["pair"] = p
            res["previouslyTested"] = False
            attempts.append(res)
            if res.get("sameRecordingSupportedBySamples"):
                best = res
                break
        results.append({"missing_id": mid, "best": best, "attempts": attempts})
        print(f"[{len(results)}/{len(by_missing)}] {cands[0]['title']} | attempts={len(attempts)} | "
              f"{'MATCH ' + str(best['medianOffsetMilliseconds']) + 'ms' if best else 'no match'}", flush=True)

    out = os.path.join(R2, "alignment-results.json")
    with open(out, "w") as f:
        json.dump({"method": "see header docstring; replicated from supplement-20260929",
                   "newPairsTested": tested, "results": results}, f, ensure_ascii=False, indent=1)
    print("saved", out, "new pairs tested:", tested)

if __name__ == "__main__":
    main()
