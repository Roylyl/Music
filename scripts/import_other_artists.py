"""Import the nine user-selected OneDrive tracks as partial album entries."""
from argparse import ArgumentParser
from collections import Counter
from io import BytesIO
from pathlib import Path
import json
import shutil
import urllib.request

from mutagen import File
from PIL import Image
from windows_paths import safe_component


ROOT = Path(__file__).resolve().parents[1]
parser = ArgumentParser()
parser.add_argument("--source-dir", type=Path, required=True)
args = parser.parse_args()
source_dir = args.source_dir.expanduser()

# Release dates refer to the original album where established. These are
# partial albums: only the files explicitly supplied by the user are included.
entries = [
    ("陳奕迅", "Stranger Under My Skin", "2011-02-22", "ep", 1, "六月飛霜", "01. 六月飞霜.flac", "https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/f3/c8/cb/f3c8cb79-da10-eed6-4c9e-03bb8e5f40fc/00602488996495.rgb.jpg/1200x1200bb.jpg", "https://musicbrainz.org/release/b0463f37-c2de-4ea5-8244-152e0a346b9f/cover-art", None),
    ("何韻詩", "Goomusic Collection 2004-2008", "2008-04-02", "compilation", 15, "勞斯.萊斯", "15. 劳斯.莱斯.flac", "https://is1-ssl.mzstatic.com/image/thumb/Music114/v4/36/23/02/362302e8-8977-e813-b3aa-1007c9f1df97/825646270798.jpg/1200x1200bb.jpg", "https://music.apple.com/hk/search?term=Goomusic%20Collection%202004-2008", None),
    ("Beyond", "真的見証", "1989", "studio", 1, "歲月無聲", "Beyond - 岁月无声.flac", "https://is1-ssl.mzstatic.com/image/thumb/Music118/v4/f1/6e/ab/f16eabbb-55aa-25a1-a2fb-8b934948ef23/00602517137325.rgb.jpg/1200x1200bb.jpg", "https://musicbrainz.org/release/8fab0f9c-2b59-463a-9e96-f69759445fd2", None),
    ("崔健", "解决", "1991-02", "studio", 3, "一块红布", "崔健 – 一块红布.flac", "https://artrockstore.com/cdn/shop/files/R-5335236-1390835475-8858_1024x1024.jpg?v=1696137493", "https://www.bmcritic.com/album/u26sk8", "本地音频约281秒，所查《解决》曲目资料约371秒；版本未确认。"),
    ("羅大佑 & 蔣志光", "皇后大道東", "1991-01-23", "compilation", 1, "皇后大道東", "皇后大道东.MP3", "https://is1-ssl.mzstatic.com/image/thumb/Music211/v4/1a/ee/2b/1aee2b13-b9af-ee0a-a75d-f485d46f8390/cover.jpg/1200x1200bb.jpg", "https://musicbrainz.org/release/12fa7029-5b41-4381-876d-e6c02fa59fe3", None),
    ("Beyond", "繼續革命", "1992-08", "studio", 1, "長城", "Beyond - 长城.flac", "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/21/a9/c8/21a9c8f3-eecf-9829-bdbc-d5ab20f514e5/mzi.zjalonbm.jpg/1200x1200bb.jpg", "https://musicbrainz.org/release/835b1079-2856-4e53-804a-6dae0d64edc1/cover-art", None),
    ("Beyond", "光輝歲月-二十周年精選", "2003", "compilation", 1, "抗戰二十年", "Beyond - 抗战二十年.flac", "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/9e/7c/6e/9e7c6ef4-c1c6-f49f-7639-ac85d096b2b1/19UMGIM62501.rgb.jpg/1200x1200bb.jpg", "https://musicbrainz.org/release/6c0d5252-0b9a-4b17-9cfd-e8e236456bce", "无原文件专辑标签；依据曲长匹配，具体母带版本未确认。"),
    ("陳芳語", "Kimberley首張同名專輯", "2012-04-27", "studio", 1, "愛你", "陈芳语 - 爱你.flac", "https://is1-ssl.mzstatic.com/image/thumb/Music114/v4/51/7e/00/517e0095-7515-9a15-ebaf-92bec4ee4b72/886443414112.jpg/1200x1200bb.jpg", "https://www.yesasia.com/global/kimberley%E9%A6%96%E5%BC%A0%E5%90%8C%E5%90%8D%E5%B0%88%E8%BC%AF/1030825546-0-0-0-zh_CN/info.html", None),
    ("黃貫中", "Paul Wong Collection", "2013", "compilation", 3, "年少無知", "黄贯中 - 年少无知.wav", "https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/ae/e3/dc/aee3dce0-8565-282d-83d7-92bc6afed082/825646440443.jpg/1200x1200bb.jpg", "https://musicbrainz.org/artist/889da094-5a5b-48f0-ace4-6dd29f4ee4dc/recordings", "本地WAV为192kHz/32bit；高采样率不代表已确认原始母带质量。"),
]

library_path = ROOT / "library.json"
library = json.loads(library_path.read_text())
existing_ids = {a["id"] for a in library["albums"]}
created = []

for artist, title, release_date, kind, track_no, song, filename, cover_url, catalog_url, warning in entries:
    src = source_dir / filename
    if not src.is_file():
        raise FileNotFoundError(src)
    album_id = "other-" + artist.replace(" ", "-").replace("&", "and") + "-" + release_date[:4] + "-" + title.replace(" ", "-")
    if album_id in existing_ids:
        continue
    directory = ROOT / "artists" / safe_component(artist) / safe_component(release_date[:4] + " - " + title)
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f"01-{track_no:02d} - {safe_component(song)}{src.suffix.lower()}"
    if not dest.exists():
        shutil.copy2(src, dest)

    request = urllib.request.Request(cover_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read()
    with Image.open(BytesIO(raw)) as image:
        image.load()
        image = image.convert("RGB")
        width, height = image.size
        image.save(directory / "cover.jpg", quality=95, subsampling=0)
        image.thumbnail((1000, 1000))
        image.save(directory / "cover.webp", quality=88, method=6)
    original = ROOT / "covers" / "originals" / (directory.name + " - " + artist + ".jpg")
    original.write_bytes(raw)

    media = File(dest)
    info = media.info
    codec = {".flac": "FLAC", ".wav": "WAV", ".mp3": "MP3"}[dest.suffix.lower()]
    props = {"codec": codec, "sampleRate": getattr(info, "sample_rate", None),
             "bitDepth": getattr(info, "bits_per_sample", None), "channels": getattr(info, "channels", None),
             "duration": round(info.length, 3), "fileSize": dest.stat().st_size,
             "bitRate": getattr(info, "bitrate", None)}
    rel = str(dest.relative_to(ROOT))
    tid = album_id + f"-d01-t{track_no:02d}"
    asset = {"trackId": tid, "localPath": rel, "sourceUrl": "", "provider": "user-provided OneDrive",
             "rightsStatus": "personal-copy; redistribution-unverified", "status": "imported",
             "audioProperties": props, "suspected_transcode": None, "redistributionAllowed": False}
    track = {"id": tid, "artist": artist, "album": title, "title": song,
             "discNumber": 1, "trackNumber": track_no, "sequenceNumber": track_no,
             "duration": props["duration"], "durationSource": "local-file",
             "sourceStatus": "available", "sourceUrl": "", "format": codec,
             "localPath": rel, "sources": [{"provider": "release-catalog", "url": catalog_url, "status": "reference"}],
             "suspected_transcode": None, "audioProperties": props,
             "searchStatus": "local-user-source", "versionMatch": "album-track-match; master-unverified",
             "assets": [asset], "rightsStatus": asset["rightsStatus"],
             "redistributionAllowed": False, "versionReviewRequired": bool(warning)}
    if warning:
        track["versionReviewReason"] = warning
    album = {"id": album_id, "artist": artist, "title": title, "releaseDate": release_date,
             "releaseDatePrecision": "day" if len(release_date) == 10 else "month" if len(release_date) == 7 else "year",
             "year": int(release_date[:4]), "type": kind, "path": str(directory.relative_to(ROOT)),
             "cover": "cover.jpg", "coverWeb": "cover.webp",
             "coverSource": {"provider": "Apple Music artwork" if "mzstatic.com" in cover_url else "Artrockstore",
                             "url": cover_url, "width": width, "height": height,
                             "lowResolution": min(width, height) < 500,
                             "originalPath": str(original.relative_to(ROOT))},
             "catalogUrl": catalog_url, "tracklistCompleteness": "partial",
             "notes": "仅导入用户指定曲目；专辑其余曲目尚未编目。",
             "tracks": [track]}
    if warning:
        album["versionReviewReason"] = warning
    (directory / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=2) + "\n")
    library["albums"].append(album)
    existing_ids.add(album_id)
    created.append((artist, title, width, height))

library["albums"].sort(key=lambda a: (a.get("releaseDate") or "9999", a["artist"], a["title"]))
library["artists"] = sorted({a["artist"] for a in library["albums"]})
library["summary"]["albums"] = len(library["albums"])
library["summary"]["tracks"] = sum(len(a["tracks"]) for a in library["albums"])
library["updatedAt"] = "2026-09-27"
library_path.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(created, ensure_ascii=False))
