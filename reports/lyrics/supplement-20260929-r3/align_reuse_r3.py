#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 3: same method as r2 (function reuse via import). Tests only pairs in
test-pairs.json (never tested in r1/r2). Read-only audio probing."""
import importlib.util, json, os, sys

ROOT = "/Users/roylyl/Documents/GitHub/Music"
spec = importlib.util.spec_from_file_location(
    "align_reuse_r2", os.path.join(ROOT, "reports/lyrics/supplement-20260929-r2/align_reuse.py"))
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)

pairs = json.load(open(os.path.join(ROOT, "reports/lyrics/supplement-20260929-r3/test-pairs.json")))["pairs"]
results = []
count = 0
for p in pairs:
    miss_d = {"src": p["missing_src"], "duration": p["missing_dur"]}
    donor_t = {"src": p["donor_src"], "duration": p["donor_dur"]}
    try:
        res = ar.test_pair(miss_d, donor_t)
    except Exception as e:
        res = {"error": str(e)}
    res["pair"] = {k: p.get(k) for k in ("missing_id","title","album","missing_dur","missing_src",
                    "donor_id","donor_album","donor_dur","donor_lrc","delta","class")}
    results.append(res)
    count += 1
    verdict = "ERROR" if "error" in res else ("MATCH %+.3fms corr%.3f" % (res["medianOffsetMilliseconds"], res["minimumAbsoluteCorrelation"]) if res.get("sameRecordingSupportedBySamples") else ("near corr%.3f" % res.get("minimumAbsoluteCorrelation",0) if res.get("minimumAbsoluteCorrelation") else "low"))
    print(f"[{count}/{len(pairs)}] {p['title'][:30]:32s} <- {p['donor_album'][:30]:32s} | {verdict}", flush=True)

out = os.path.join(ROOT, "reports/lyrics/supplement-20260929-r3/alignment-results-r3.json")
with open(out, "w") as f:
    json.dump({"method": "identical to supplement-20260929-r2/align_reuse.py (imported); acceptance: min|corr|>=0.92, spread<=15ms, same polarity",
               "pairsTested": len(results),
               "matches": sum(1 for r in results if r.get("sameRecordingSupportedBySamples")),
               "results": results}, f, ensure_ascii=False, indent=1)
print("saved", out)
