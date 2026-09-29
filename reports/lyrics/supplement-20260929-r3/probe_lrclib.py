#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 3 web retrieval: probe lrclib.net (open lyrics DB) per missing track.
Records ONLY metadata (found? synced? duration match?) — never saves lyric text.
"""
import json, os, re, time, urllib.parse, urllib.request

ROOT = "/Users/roylyl/Documents/GitHub/Music"
OUT = os.path.join(ROOT, "reports/lyrics/supplement-20260929-r3/lrclib-probe.json")
UA = {"User-Agent": "WorkBuddyMusicLibrary/1.0 (personal lyric source audit; contact: local)"}

def clean_title(t):
    s = t.replace('（', '(').replace('）', ')')
    s = re.sub(r'\[[^\]]*\]', '', s)
    while True:
        s2 = re.sub(r'\s*\([^()]*\)\s*$', '', s)
        if s2 == s or not s2: break
        s = s2
    s = re.sub(r'\s*(ボーカル|ヴォーカル).*$', '', s)
    s = re.sub(r'(19|20)\d{2}年?版?$', '', s).strip(' -')
    return s.strip() or t

def clean_artist(a):
    a = re.split(r'[/&,，、]', a)[0].strip()
    return a

def query(track, artist, tries=2):
    url = "https://lrclib.net/api/search?" + urllib.parse.urlencode({"track_name": track, "artist_name": artist})
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1: return {"error": str(e)}
            time.sleep(1.5)
    return {"error": "unreachable"}

tracks = json.load(open(os.path.join(ROOT, "tracks.json")))
missing = [t for t in tracks if not (os.path.exists(os.path.splitext(t['src'])[0]+'.lrc') and os.path.getsize(os.path.splitext(t['src'])[0]+'.lrc')>0)]
print("missing to probe:", len(missing), flush=True)

out = []
for i, t in enumerate(missing, 1):
    ct, ca = clean_title(t['title']), clean_artist(t['artist'])
    data = query(ct, ca)
    entry = {"trackId": t['id'], "title": t['title'], "artist": t['artist'], "album": t['album'],
             "localDuration": round(t['duration'], 3), "queryTitle": ct, "queryArtist": ca}
    if isinstance(data, dict) and "error" in data:
        entry.update({"status": "query-error", "error": data["error"]})
    else:
        cands = []
        for r in (data or []):
            if not isinstance(r, dict): continue
            cands.append({
                "id": r.get("id"), "trackName": r.get("trackName"), "artistName": r.get("artistName"),
                "albumName": r.get("albumName"), "duration": r.get("duration"),
                "instrumental": r.get("instrumental"),
                "hasSyncedLyrics": bool(r.get("syncedLyrics")),
                "hasPlainLyrics": bool(r.get("plainLyrics")),
            })
        # best: artist-accent match, then closest duration
        def score(c):
            art_ok = any(part and part in (c['artistName'] or '') for part in ca.split())
            dd = abs((c['duration'] or 0) - t['duration']) if c['duration'] else 9999
            return (0 if art_ok else 1, dd)
        cands.sort(key=score)
        best = cands[0] if cands else None
        entry["resultCount"] = len(cands)
        if best:
            entry["bestDurationDiff"] = round(abs((best['duration'] or 0) - t['duration']), 3)
            entry["bestHasSyncedLyrics"] = best['hasSyncedLyrics']
            entry["bestHasPlainLyrics"] = best['hasPlainLyrics']
            entry["bestInstrumental"] = best['instrumental']
            entry["bestUrl"] = f"https://lrclib.net/{best['id']}" if best.get('id') else None
            entry["bestAlbum"] = best['albumName']
        entry["status"] = "found" if best else "not-found"
        entry["candidates"] = cands[:5]
    out.append(entry)
    if i % 25 == 0 or i == len(missing):
        print(f"[{i}/{len(missing)}] ...", flush=True)
    time.sleep(0.35)

with open(OUT, "w") as f:
    json.dump({"generatedAt": "2026-09-29", "source": "lrclib.net public search API (metadata only; no lyric text stored)",
               "probed": len(out),
               "found": sum(1 for e in out if e.get("status") == "found"),
               "foundSynced": sum(1 for e in out if e.get("bestHasSyncedLyrics")),
               "foundPlainOnly": sum(1 for e in out if e.get("status") == "found" and e.get("bestHasPlainLyrics") and not e.get("bestHasSyncedLyrics")),
               "results": out}, f, ensure_ascii=False, indent=1)
print("saved", OUT)
