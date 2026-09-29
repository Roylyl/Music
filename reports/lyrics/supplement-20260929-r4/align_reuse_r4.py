#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 4: same method as r2/r3 (functions imported from r2 script). Tests only r4 pairs."""
import importlib.util, json, os

ROOT = "/Users/roylyl/Documents/GitHub/Music"
spec = importlib.util.spec_from_file_location(
    "align_reuse_r2", os.path.join(ROOT, "reports/lyrics/supplement-20260929-r2/align_reuse.py"))
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)

pairs = json.load(open(os.path.join(ROOT, "reports/lyrics/supplement-20260929-r4/test-pairs-r4.json")))["pairs"]
results = []
for i, p in enumerate(pairs, 1):
    try:
        res = ar.test_pair({"src": p["missing_src"], "duration": p["missing_dur"]},
                           {"src": p["donor_src"], "duration": p["donor_dur"]})
    except Exception as e:
        res = {"error": str(e)}
    res["pair"] = {k: p.get(k) for k in ("missing_id","title","album","missing_dur","missing_src",
                    "donor_id","donor_album","donor_dur","donor_lrc","delta","class")}
    results.append(res)
    v = "ERROR" if "error" in res else ("MATCH %+.3fms corr %.3f" % (res["medianOffsetMilliseconds"], res["minimumAbsoluteCorrelation"]) if res.get("sameRecordingSupportedBySamples") else "no (%s)" % res.get("minimumAbsoluteCorrelation", "?"))
    print(f"[{i}/{len(pairs)}] {p['title'][:34]:36s} <- {p['donor_album'][:30]:32s} | {v}", flush=True)
out = os.path.join(ROOT, "reports/lyrics/supplement-20260929-r4/alignment-results-r4.json")
json.dump({"method": "identical to r2/r3 (imported functions); acceptance min|corr|>=0.92, spread<=15ms, same polarity",
           "pairsTested": len(results),
           "matches": sum(1 for r in results if r.get("sameRecordingSupportedBySamples")),
           "results": results}, open(out, "w"), ensure_ascii=False, indent=1)
print("saved", out)
