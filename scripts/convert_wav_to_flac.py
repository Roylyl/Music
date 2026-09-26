"""Convert repository WAV audio to 44.1 kHz FLAC and update local references."""
from collections import Counter
from pathlib import Path
import json
import subprocess

import imageio_ffmpeg
from mutagen import File


ROOT = Path(__file__).resolve().parents[1]
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
sources = sorted(p for base in ("artists", "live", "collections") for p in (ROOT / base).rglob("*")
                 if p.is_file() and p.suffix.lower() == ".wav")
if not sources:
    raise SystemExit("没有待转换的WAV；现有转换记录保持不变。")
converted = {}

for src in sources:
    target = src.with_suffix(".flac")
    if target.exists():
        target = src.with_name(src.stem + ".from-wav.flac")
    temporary = target.with_name(target.name + ".part")
    original = File(src).info
    bits = 16 if original.bits_per_sample <= 16 else 24
    codec_format = "s16" if bits == 16 else "s32"
    command = [FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(src),
               "-map", "0:a:0", "-vn", "-ar", "44100", "-sample_fmt", codec_format,
               "-c:a", "flac", "-compression_level", "8"]
    if bits == 24:
        command += ["-bits_per_raw_sample", "24"]
    command += ["-f", "flac", str(temporary)]
    if not temporary.exists():
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"转换失败：{src}\n{result.stderr[-800:]}")
    info = File(temporary).info
    if info.sample_rate != 44100 or info.bits_per_sample != bits or info.channels != original.channels:
        raise ValueError(f"音频参数不符：{temporary}")
    if abs(info.length - original.length) > 0.05:
        raise ValueError(f"时长不符：{temporary}")
    temporary.replace(target)
    old = str(src.relative_to(ROOT))
    new = str(target.relative_to(ROOT))
    converted[old] = {"new": new, "sourceSampleRate": original.sample_rate,
                      "sourceBitDepth": original.bits_per_sample,
                      "audioProperties": {"codec": "FLAC", "sampleRate": info.sample_rate,
                                          "bitDepth": info.bits_per_sample, "channels": info.channels,
                                          "duration": round(info.length, 3), "fileSize": target.stat().st_size,
                                          "bitRate": getattr(info, "bitrate", None)}}
    print(f"{len(converted)}/{len(sources)} {old} -> {target.name}", flush=True)


def update(value):
    if isinstance(value, list):
        return [update(item) for item in value]
    if not isinstance(value, dict):
        return converted[value]["new"] if isinstance(value, str) and value in converted else value
    old_path = value.get("localPath") or value.get("selectedTrackPath") or value.get("originalPath")
    result = {key: update(item) for key, item in value.items()}
    if old_path in converted and value.get("localPath") == old_path:
        result["audioProperties"] = converted[old_path]["audioProperties"]
        if result.get("format") == "WAV":
            result["format"] = "FLAC"
        if result.get("codec") == "WAV":
            result["codec"] = "FLAC"
        result["duration"] = converted[old_path]["audioProperties"]["duration"]
        result["conversion"] = {"from": "WAV", "to": "FLAC", "sampleRate": 44100,
                                "sourceSampleRate": converted[old_path]["sourceSampleRate"],
                                "sourceBitDepth": converted[old_path]["sourceBitDepth"]}
    return result


library_file = ROOT / "library.json"
library = update(json.loads(library_file.read_text()))
tracks = [track for album in library["albums"] for track in album["tracks"]]
library["summary"]["localFormats"] = dict(Counter(track["format"] for track in tracks if track["localPath"]))
library["summary"]["assetBytes"] = sum(asset["audioProperties"]["fileSize"] for track in tracks for asset in track.get("assets", []))
library_file.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n")
for album in library["albums"]:
    (ROOT / album["path"] / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=2) + "\n")

for path in (ROOT / "artists").rglob("extended-source.json"):
    contents = update(json.loads(path.read_text()))
    contents["conversionNote"] = "WAV文件已转换为44.1kHz FLAC；路径指向保存的转换版本。"
    path.write_text(json.dumps(contents, ensure_ascii=False, indent=2) + "\n")

for name in ("download-results.jsonl", "local-import-results.jsonl", "youtube-import-results.jsonl"):
    path = ROOT / "reports" / name
    if not path.exists():
        continue
    lines = []
    for line in path.read_text().splitlines():
        record = json.loads(line)
        lines.append(json.dumps(update(record) if record.get("status") == "downloaded" else record,
                                ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n")

(ROOT / "reports" / "wav-conversions.json").write_text(json.dumps(converted, ensure_ascii=False, indent=2) + "\n")
for old in converted:
    (ROOT / old).unlink()
print(f"转换并替换{len(converted)}个WAV；原文件已在核对后移除。")
