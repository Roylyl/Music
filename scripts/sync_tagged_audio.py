"""Sync audio properties after metadata tags and embedded artwork change file size."""
from collections import Counter
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
library_path = ROOT / "library.json"
library = json.loads(library_path.read_text())
audit = {item["localPath"]: item for item in json.loads((ROOT / "reports" / "audio-audit.json").read_text())}

for album in library["albums"]:
    for track in album["tracks"]:
        for asset in track.get("assets", []):
            path = asset["localPath"]
            record = audit[path]
            asset["audioProperties"] = {key: record.get(key) for key in
                                        ("codec", "sampleRate", "bitDepth", "channels", "duration", "fileSize", "bitRate")}
            asset["qualityAudit"] = record.get("analysisStatus")
            if record.get("suspected_transcode") is True:
                asset["suspected_transcode"] = True
        primary = track.get("localPath")
        if primary:
            selected = next(asset for asset in track["assets"] if asset["localPath"] == primary)
            track["audioProperties"] = selected["audioProperties"]
            track["format"] = selected["audioProperties"]["codec"]
            track["qualityAudit"] = selected.get("qualityAudit")
            if selected.get("suspected_transcode") is True:
                track["suspected_transcode"] = True
    (ROOT / album["path"] / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=2) + "\n")

tracks = [track for album in library["albums"] for track in album["tracks"]]
library["summary"].update({
    "localFormats": dict(Counter(track["format"] for track in tracks if track["localPath"])),
    "assetBytes": sum(asset["audioProperties"]["fileSize"] for track in tracks for asset in track.get("assets", [])),
    "suspectedTranscodes": sum(track.get("suspected_transcode") is True for track in tracks),
})
library_path.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n")
print("已同步音频参数：", len(audit), "个文件")
