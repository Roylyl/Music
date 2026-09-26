"""Remove eight confirmed same-recording OneDrive copies from the repository."""
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
library_file = ROOT / "library.json"
library = json.loads(library_file.read_text())
removed = []

for album in library["albums"]:
    for track in album["tracks"]:
        duplicates = [item for item in track.get("assets", [])
                      if item["localPath"].endswith(" [OneDrive].flac")]
        for item in duplicates:
            path = ROOT / item["localPath"]
            if not path.is_file() or not (ROOT / track["localPath"]).is_file():
                raise FileNotFoundError(path)
            removed.append({"artist": album["artist"], "album": album["title"],
                            "title": track["title"], "removedPath": item["localPath"],
                            "retainedPath": track["localPath"], "removedBytes": path.stat().st_size,
                            "reason": "同一录音的重复来源；抽样音频高度一致，时长差异为编码边界或近乎静音的尾段。",
                            "cloudOriginalUnchanged": True})
            track["assets"].remove(item)

if len(removed) != 8:
    raise ValueError(f"预期移除8份，实际发现{len(removed)}份；停止修改。")

for item in removed:
    (ROOT / item["removedPath"]).unlink()
for album in library["albums"]:
    (ROOT / album["path"] / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=2) + "\n")
library["summary"]["assetBytes"] = sum(item["audioProperties"]["fileSize"]
                                         for album in library["albums"] for track in album["tracks"]
                                         for item in track.get("assets", []))
library_file.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n")

log_file = ROOT / "reports" / "local-import-results.jsonl"
if log_file.is_file():
    removed_paths = {item["removedPath"] for item in removed}
    logs = []
    for line in log_file.read_text().splitlines():
        record = json.loads(line)
        if record.get("localPath") in removed_paths:
            record["status"] = "duplicate-removed"
            record["formerLocalPath"] = record.pop("localPath")
            record["reason"] = "同录音重复副本已移除；OneDrive原始文件未改动。"
        logs.append(json.dumps(record, ensure_ascii=False))
    log_file.write_text("\n".join(logs) + "\n")

(ROOT / "reports" / "duplicate-onedrive-review.json").write_text(
    json.dumps(removed, ensure_ascii=False, indent=2) + "\n")
print("已移除", len(removed), "份重复副本，节省", round(sum(x["removedBytes"] for x in removed) / 1024**2, 1), "MiB")
