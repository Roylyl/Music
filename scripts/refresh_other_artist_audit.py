"""Apply cached audio-audit findings to user-imported tracks."""
from collections import Counter
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
library_file = ROOT / "library.json"
library = json.loads(library_file.read_text())
audit = {item["localPath"]: item for item in json.loads((ROOT / "reports/audio-audit.json").read_text())}
source_names = {
    "六月飛霜": "01. 六月飞霜.flac", "勞斯.萊斯": "15. 劳斯.莱斯.flac",
    "愛你": "陈芳语 - 爱你.flac", "一块红布": "崔健 – 一块红布.flac",
    "皇后大道東": "皇后大道东.MP3", "年少無知": "黄贯中 - 年少无知.wav",
    "長城": "Beyond - 长城.flac", "抗戰二十年": "Beyond - 抗战二十年.flac",
    "歲月無聲": "Beyond - 岁月无声.flac",
}

for album in library["albums"]:
    if not album["id"].startswith("other-"):
        continue
    for track in album["tracks"]:
        finding = audit[track["localPath"]]
        track["suspected_transcode"] = finding.get("suspected_transcode")
        track["qualityAudit"] = finding.get("analysisStatus")
        track["sourceFileName"] = source_names[track["title"]]
        for asset in track["assets"]:
            asset["suspected_transcode"] = finding.get("suspected_transcode")
            asset["qualityAudit"] = finding.get("analysisStatus")
            asset["sourceFileName"] = track["sourceFileName"]
    (ROOT / album["path"] / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=2) + "\n")

tracks = [track for album in library["albums"] for track in album["tracks"]]
library["summary"].update({
    "albums": len(library["albums"]), "tracks": len(tracks),
    "types": dict(Counter(album["type"] for album in library["albums"])),
    "status": dict(Counter(track["sourceStatus"] for track in tracks)),
    "localTracks": sum(bool(track["localPath"]) for track in tracks),
    "localFormats": dict(Counter(track["format"] for track in tracks if track["localPath"])),
    "assetBytes": sum(asset["audioProperties"]["fileSize"] for track in tracks for asset in track.get("assets", [])),
    "suspectedTranscodes": sum(track.get("suspected_transcode") is True for track in tracks),
})
library_file.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n")
