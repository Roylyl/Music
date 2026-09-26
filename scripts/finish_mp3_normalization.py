"""Refresh current metadata reports and verify each retained MP3 decodes."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from collections import Counter
import json
import subprocess
import imageio_ffmpeg
from mutagen.mp3 import MP3, BitrateMode

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / "reports/mp3-normalization.json").read_text())
old_meta = json.loads((ROOT / "reports/metadata-standardization.json").read_text())
lookup = {entry["path"]: entry for entry in old_meta["files"]}
files = []
baseline = {}
for result in report["files"]:
    entry = dict(lookup[result["sourcePath"]]); entry["path"] = result["localPath"]; files.append(entry)
    p = result["audioProperties"]
    baseline[result["localPath"]] = {"duration": p["duration"], "sampleRate": p["sampleRate"], "channels": p["channels"], "bits": None}
(ROOT / "reports/metadata-standardization.json").write_text(json.dumps({
    "policy": "MP3-320kbps-one-file-per-catalog-track; metadata-whitelist", "taggedFiles": len(files), "files": files,
}, ensure_ascii=False, indent=2) + "\n")
(ROOT / "reports/metadata-clean-baseline.json").write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n")

def check(entry):
    path = ROOT / entry["path"]; info = MP3(path).info
    if info.bitrate != 320000 or info.bitrate_mode != BitrateMode.CBR or info.sample_rate != 44100:
        return {"path": entry["path"], "error": "MP3 encoding parameters"}
    # Decode real samples, not just the container header. This catches files
    # whose declared duration is readable but compressed packets are broken.
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-nostdin",
                             "-ss", str(max(0, info.length * .5)), "-i", str(path), "-t", "1",
                             "-map", "0:a:0", "-threads", "1", "-f", "s16le", "-"], capture_output=True)
    if result.returncode or result.stderr or len(result.stdout) < 1000:
        return {"path": entry["path"], "error": "sample decode failed", "details": result.stderr.decode(errors="replace")[:300]}
    return None

with ThreadPoolExecutor(max_workers=3) as pool:
    errors = [error for error in pool.map(check, files) if error]
library = json.loads((ROOT / "library.json").read_text())
active = [t for a in library["albums"] for t in a["tracks"] if t["localPath"]]
if any(len(t["assets"]) != 1 for t in active): errors.append({"error": "multiple assets per track"})
physical = {str(p.relative_to(ROOT)) for base in ("artists", "live", "collections") for p in (ROOT / base).rglob("*")
            if p.suffix.lower() in (".mp3", ".flac", ".m4a", ".opus", ".wav", ".webm")}
if physical != {x["path"] for x in files}: errors.append({"error": "physical file coverage mismatch"})
result = {"valid": not errors, "mp3Files": len(files), "catalogTracks": len(active),
          "independentRecordings": report["sourceRecordings"], "sampleRate": 44100, "bitRate": 320000,
          "decodeCheck": "one second from middle of every file", "errors": errors,
          "metadataBaseline": "post-requested-320kbps-conversion"}
(ROOT / "reports/mp3-validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
if errors: raise SystemExit(1)
