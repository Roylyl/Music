"""Keep one MP3 320 kbps / 44.1 kHz file per catalog track and source recording."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import json
import shutil
import subprocess
import imageio_ffmpeg
from mutagen import File
from mutagen.mp3 import MP3, BitrateMode
from mutagen.id3 import TIT2, TPE1, TPE2, TALB, TRCK, TPOS, TDRC, APIC
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".mp3-conversion"
STAGE.mkdir(exist_ok=True)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
lib = json.loads((ROOT / "library.json").read_text())
metadata = {x["path"]: x for x in json.loads((ROOT / "reports/metadata-standardization.json").read_text())["files"]}
physical = {str(p.relative_to(ROOT)): p.stat().st_size for base in ("artists", "live", "collections")
            for p in (ROOT / base).rglob("*") if p.suffix.lower() in (".mp3", ".flac", ".m4a", ".opus", ".wav", ".webm")}
jobs = []
covers = {}
for album in lib["albums"]:
    with Image.open(ROOT / album["path"] / "cover.jpg") as im:
        im = im.convert("RGB"); im.thumbnail((900, 900))
        buf = BytesIO(); im.save(buf, format="JPEG", quality=86, optimize=True)
        covers[album["path"]] = buf.getvalue()
    for track in album["tracks"]:
        if track["localPath"]:
            jobs.append({"old": track["localPath"], "new": str(Path(track["localPath"]).with_suffix(".mp3")),
                         "album": album, "track": track})
    for path in (ROOT / album["path"]).iterdir():
        if path.name in ("full-concert.opus", "full-concert.mp3", "01-09 - 这个世界会好吗.full-source.flac", "01-09 - 这个世界会好吗.full-source.mp3"):
            rel = str(path.relative_to(ROOT))
            jobs.append({"old": rel, "new": str(Path(rel).with_suffix(".mp3")), "album": album, "track": None})
targets = [job["new"] for job in jobs]
if len(set(targets)) != len(targets):
    raise ValueError("Duplicate destination paths")

def properties(path):
    a = File(path); i = a.info
    return {"codec": "MP3" if isinstance(a, MP3) else getattr(i, "codec", type(a).__name__),
            "sampleRate": getattr(i, "sample_rate", 48000), "channels": i.channels,
            "bitDepth": getattr(i, "bits_per_sample", None), "duration": round(i.length, 3),
            "fileSize": path.stat().st_size, "bitRate": getattr(i, "bitrate", None)}

def convert(job):
    src = ROOT / job["old"]; dest = STAGE / job["new"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = File(src); before = properties(src)
    passthrough = isinstance(source, MP3) and source.info.bitrate == 320000 and source.info.bitrate_mode == BitrateMode.CBR and source.info.sample_rate == 44100
    chapter = job["track"].get("segment") if job["track"] and src.suffix.lower() == ".opus" else None
    input_args = ["-i", str(src)]
    selection = None
    if chapter:
        full = ROOT / job["album"]["path"] / "full-concert.opus"
        if not full.exists(): raise FileNotFoundError(full)
        input_args = ["-ss", str(chapter["start"]), "-i", str(full), "-t", str(chapter["end"] - chapter["start"])]
        selection = {"recording": str(full.relative_to(ROOT)), "start": chapter["start"], "end": chapter["end"],
                     "reason": "rebuild chapter from full recording to avoid malformed Ogg granule timestamps"}
    expected_duration = before["duration"]
    decoded_duration = None
    if dest.exists() and not chapter:
        try:
            if abs(MP3(dest).info.length - expected_duration) > .15:
                probe = subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-i", str(src),
                                        "-map", "0:a:0", "-f", "null", "-", "-progress", "pipe:1"],
                                       capture_output=True, text=True)
                times = [int(line.split("=", 1)[1]) / 1000000 for line in probe.stdout.splitlines() if line.startswith("out_time_us=")]
                if probe.returncode or probe.stderr or not times:
                    raise RuntimeError("Source decode failed: " + job["old"] + probe.stderr[-300:])
                decoded_duration = times[-1]
                expected_duration = decoded_duration
        except (ValueError, OSError):
            pass
    prepared = False
    if dest.exists():
        try:
            ready = MP3(dest).info
            prepared = not chapter and ready.bitrate == 320000 and ready.bitrate_mode == BitrateMode.CBR and ready.sample_rate == 44100 and abs(ready.length-expected_duration) <= .15
        except Exception:
            pass
    if passthrough and not prepared:
        shutil.copyfile(src, dest)
    elif not prepared:
        result = subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-y", *input_args,
                                 "-map", "0:a:0", "-map_metadata", "-1", "-map_chapters", "-1",
                                 "-c:a", "libmp3lame", "-b:a", "320k", "-ar", "44100", "-threads", "1", str(dest)],
                                capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(job["old"] + ": " + result.stderr[-500:])
    m = metadata[job["old"]]
    audio = MP3(dest)
    if audio.tags is None: audio.add_tags()
    audio.tags.clear()
    for cls, value in ((TIT2, m["title"]), (TPE1, m["artist"]), (TPE2, m["albumArtist"]),
                       (TALB, m["album"]), (TRCK, m["trackNumber"]), (TPOS, m["discNumber"]), (TDRC, m["date"])):
        if value is not None and str(value): audio.tags.add(cls(encoding=3, text=str(value)))
    audio.tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Front cover", data=covers[job["album"]["path"]]))
    audio.save(v2_version=3, v1=0)
    audio = MP3(dest); after = properties(dest)
    if abs(after["duration"] - expected_duration) > .15 or after["channels"] != before["channels"]:
        raise ValueError("Duration/channel mismatch: " + job["old"])
    if audio.info.bitrate != 320000 or audio.info.bitrate_mode != BitrateMode.CBR or audio.info.sample_rate != 44100:
        raise ValueError("Encoding mismatch: " + job["new"])
    if str(audio.tags["TIT2"]) != m["title"] or audio.tags.getall("APIC")[0].data != covers[job["album"]["path"]]:
        raise ValueError("Metadata mismatch: " + job["new"])
    return {"sourcePath": job["old"], "localPath": job["new"], "sourceAudioProperties": before,
            "audioProperties": after, "action": "kept-existing-320" if passthrough else "encoded-mp3-320",
            "decodedSourceDuration": decoded_duration, "lossySource": src.suffix.lower() in (".mp3", ".m4a", ".opus", ".webm"), "sourceSelection": selection}

results = {}
failures = []
with ThreadPoolExecutor(max_workers=3) as pool:
    futures = {pool.submit(convert, job): job for job in jobs}
    for future in as_completed(futures):
        try:
            result = future.result(); results[result["sourcePath"]] = result
        except Exception as exc:
            failures.append(str(exc)); print("FAILED: " + str(exc), flush=True); continue
        if len(results) % 25 == 0 or len(results) == len(jobs): print(f"Prepared {len(results)}/{len(jobs)}", flush=True)
if failures:
    raise RuntimeError("Sources retained; conversion failures: " + repr(failures))

# No source file is removed before every output has passed the targeted checks.
for job in jobs:
    (STAGE / job["new"]).replace(ROOT / job["new"])
changes = {job["old"]: job["new"] for job in jobs}
events = []
for job in jobs:
    result = results[job["old"]]; track = job["track"]
    if track is None: continue
    old_assets = deepcopy(track.get("assets", []))
    selected = next(x for x in old_assets if x["localPath"] == job["old"])
    track["sourceAudioProperties"] = result["sourceAudioProperties"]
    track["sourceAssetHistory"] = old_assets
    track["conversion"] = {"target": "MP3 CBR 320kbps 44.1kHz", "action": result["action"],
                           "lossySource": result["lossySource"], "sourceQualityImproved": False,
                           "sourceSelection": result["sourceSelection"]}
    selected.update(localPath=job["new"], audioProperties=result["audioProperties"],
                    sourceAudioProperties=result["sourceAudioProperties"], conversion=track["conversion"],
                    qualityAudit="encoding-and-metadata-verified", status="downloaded")
    track.update(localPath=job["new"], format="MP3", audioProperties=result["audioProperties"],
                 duration=result["audioProperties"]["duration"], assets=[selected])
    events.append(selected)

def rewrite(value):
    if isinstance(value, list): return [rewrite(x) for x in value]
    if isinstance(value, dict): return {k:rewrite(x) for k,x in value.items()}
    return changes.get(value, value) if isinstance(value, str) else value

for album in lib["albums"]:
    recording_file = ROOT / album["path"] / "recording.json"
    if recording_file.is_file():
        old = json.loads(recording_file.read_text()); source = old["localFiles"][0]
        if source in results:
            result = results[source]; record = rewrite(old)
            record["sourceAudioProperties"] = result["sourceAudioProperties"]
            record["audioProperties"] = result["audioProperties"]
            record["acodec"] = "mp3"; record["asr"] = 44100; record["abr"] = 320; record["lossless"] = False
            recording_file.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
            album["fullRecordings"] = [record]
    extended = ROOT / album["path"] / "extended-source.json"
    if extended.exists():
        d = rewrite(json.loads(extended.read_text()))
        d["conversionNote"] = "按用户要求仅保留MP3 320kbps版本；早期切分说明描述源文件处理历史。"
        extended.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    (ROOT / album["path"] / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=2) + "\n")

all_tracks = [t for a in lib["albums"] for t in a["tracks"]]
lib["playbackPolicy"] = {"format": "MP3", "bitRate": 320000, "sampleRate": 44100, "oneAssetPerCatalogTrack": True}
lib["summary"].update(localFormats=dict(Counter(t["format"] for t in all_tracks if t["localPath"])),
                      assetBytes=sum(x["audioProperties"]["fileSize"] for t in all_tracks for x in t.get("assets", [])))
(ROOT / "library.json").write_text(json.dumps(lib, ensure_ascii=False, indent=2) + "\n")
(ROOT / "reports/mp3-normalization-results.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in events) + "\n")
removed = sorted(set(physical) - set(targets))
for old in removed: (ROOT / old).unlink()
shutil.rmtree(STAGE)
report = {"format": "MP3 CBR 320kbps 44.1kHz", "tracks": len(events), "sourceRecordings": len(jobs)-len(events),
          "files": list(results.values()), "removedPaths": removed,
          "removedAlternativeCount": len(physical)-len(jobs), "beforeBytes": sum(physical.values()),
          "afterBytes": sum((ROOT / x).stat().st_size for x in targets)}
(ROOT / "reports/mp3-normalization.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k:v for k,v in report.items() if k not in ("files", "removedPaths")}, ensure_ascii=False), flush=True)
