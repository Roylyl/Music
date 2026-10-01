"""Import the reviewed QQ Music MP3 batch without changing its source files.

The plan records title, album, edition, and release-order decisions. Run this
script only after reviewing reports/qq-import-plan.json.
"""

from collections import Counter
from datetime import date
from io import BytesIO
from pathlib import Path
import json
import re
import shutil
import urllib.request

from mutagen.id3 import APIC, TALB, TDRC, TIT2, TPE1, TPE2, TPOS, TRCK
from mutagen.mp3 import MP3
from PIL import Image, ImageOps
from windows_paths import safe_component


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT.parent / "roylyl.github.io" / "music"
SOURCE = Path("/Users/roylyl/Music/QQ音乐")
PLAN = json.loads((ROOT / "reports/qq-import-plan.json").read_text())
METADATA = json.loads((ROOT / "reports/qq-import-metadata.json").read_text())
MB = {(row["artist"], row["album"]): row for row in METADATA}
EXTRA_DATES = {
    ("久石让", "梦之歌：久石让精选"): "2020-02-21",
    ("刘维", "小小星球"): "2020-03-24",
    ("周杰伦", "最伟大的作品"): "2022-07-08",
    ("林俊杰", "Like You Do 如你"): "2021-04-23",
    ("林俊杰", "幸存者"): "2020-10-20",
    ("Luis Fonsi", "Despacito 缓缓 (Mandarin Version)"): "2017-08-04",
    ("林俊杰", "In The Joy"): "2023-04-07",
    ("林俊杰", "SHOW THE WORLD"): "2019-06-20",
    ("林俊杰", "无滤镜 (feat. 藤原浩)"): "2020-07-30",
    ("林俊杰", "7千3百多天"): "2022-11-01",
    ("林俊杰", "Stay With You (英文版)"): "2020-08-09",
    ("林俊杰", "谢幕"): "2023-03-25",
    ("毛不易", "明日之子 第7期"): "2017-07-29",
    ("蔡徐坤", "YOUNG"): "2019-07-26",
    ("AC/DC", "Back In Black"): "1980-07-25",
    ("五月天", "第二人生（明日版）"): "2011-12-16",
    ("周杰伦", "不能说的秘密 电影原声带"): "2007-08-13",
}
ARTWORK = {
    ("林俊杰", "一定会/After The Rain"): "https://coverartarchive.org/release-group/94de82ef-b661-4fa5-9084-8af3ecc963e0/front-500",
    ("林俊杰", "Like You Do 如你"): "https://coverartarchive.org/release-group/1b11df81-21f0-45d2-ab07-9ddaf074a19f/front-500",
    ("林俊杰", "我们很好"): "https://coverartarchive.org/release-group/29642013-b4d4-4729-9c1b-118d0c9d2721/front-500",
    ("Luis Fonsi", "Despacito 缓缓 (Mandarin Version)"): "https://coverartarchive.org/release-group/b628f869-61a9-4892-8aad-b224e61ee867/front-500",
    ("林俊杰", "感爵这一刻"): "https://is1-ssl.mzstatic.com/image/thumb/Music113/v4/f9/38/30/f9383050-3f28-252a-b0ca-73b805fa3d07/190295049300.jpg/1200x1200bb.jpg",
}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def safe(value):
    return re.sub(r'[\\/:*?"<>|]', lambda m: {
        "/": "／", "\\": "／", ":": "：", "*": "＊", "?": "？",
        '"': "＂", "<": "＜", ">": "＞", "|": "｜",
    }[m.group()], value).strip()


def qq_properties(path, media):
    info = media.info
    return {"codec": "MP3", "sampleRate": info.sample_rate, "bitDepth": None,
            "channels": info.channels, "duration": round(info.length, 3),
            "fileSize": path.stat().st_size, "bitRate": info.bitrate}


def release_date(row):
    key = (row["artist"], row["album"])
    if key in EXTRA_DATES:
        return EXTRA_DATES[key]
    original_artist = row["source"].split("-", 1)[0]
    candidate = MB.get((original_artist, row["qqAlbum"]))
    if candidate and candidate.get("mb"):
        return candidate["mb"][0].get("date")
    if key == ("陈奕迅 & eason and the duo band", "L.O.V.E."):
        return "2018-12-11"
    return None


def cover_for(album, rows):
    folder = ROOT / album["path"]
    jpeg = folder / "cover.jpg"
    webp = folder / "cover.webp"
    if jpeg.exists() and webp.exists():
        return jpeg
    preferred = sorted(rows, key=lambda row: row["qqAlbum"] != album["title"])
    raw = None
    source = None
    for row in preferred:
        tags = MP3(SOURCE / row["source"]).tags
        images = tags.getall("APIC") if tags else []
        if images:
            raw = images[0].data
            source = "QQ音乐文件内嵌封面"
            break
    if raw is None:
        url = ARTWORK.get((album["artist"], album["title"]))
        if not url:
            raise ValueError("缺少专辑封面：" + album["path"])
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "RoylylMusicImport/1.0"}), timeout=30) as response:
            raw = response.read()
        source = url
    with Image.open(BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.save(jpeg, "JPEG", quality=93, optimize=True)
        image.thumbnail((900, 900))
        image.save(webp, "WEBP", quality=86, method=6)
    album["coverSource"] = {"provider": source}
    return jpeg


def tag_copy(source, destination, row, album, cover_bytes):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".importing")
    shutil.copyfile(source, temporary)
    audio = MP3(temporary)
    if audio.info.bitrate != 320000 or audio.info.sample_rate != 44100:
        temporary.unlink()
        raise ValueError("源文件不符合预期的320kbps/44.1kHz：" + source.name)
    if audio.tags is None:
        audio.add_tags()
    audio.tags.clear()
    values = [(TIT2, row["title"]), (TPE1, row.get("performer", row["artist"])), (TPE2, album["artist"]),
              (TALB, album["title"]), (TRCK, row["track"]), (TPOS, row["disc"])]
    if album.get("releaseDate"):
        values.append((TDRC, album["releaseDate"]))
    for frame, value in values:
        audio.tags.add(frame(encoding=3, text=str(value)))
    audio.tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Front cover", data=cover_bytes))
    audio.save(v2_version=3, v1=0)
    temporary.replace(destination)
    return qq_properties(destination, MP3(destination))


def main():
    library = json.loads((ROOT / "library.json").read_text())
    albums = library["albums"]
    tracks_by_id = {track["id"]: track for album in albums for track in album["tracks"]}
    albums_by_track = {track["id"]: album for album in albums for track in album["tracks"]}
    groups = {}
    for row in PLAN:
        groups.setdefault((row["artist"], row["album"]), []).append(row)
    covers = {}
    for (artist, title), rows in groups.items():
        existing = next((album for album in albums if album["artist"] == artist and album["title"] == title), None)
        if existing is None and all(row["existing"] for row in rows):
            continue
        if existing is None:
            stamp = next((release_date(row) for row in rows if release_date(row)), None)
            folder = Path("artists") / safe_component(artist) / safe_component(f"{stamp[:4] if stamp else '年份待核'} - {title}")
            existing = {"id": "qq-album-" + safe(artist) + "-" + safe(title), "artist": artist,
                        "title": title, "releaseDate": stamp,
                        "releaseDatePrecision": "day" if stamp and len(stamp) == 10 else "year" if stamp else None,
                        "year": int(stamp[:4]) if stamp else None,
                        "type": "compilation" if (artist, title) == ("久石让", "梦之歌：久石让精选") else "live" if (artist, title) == ("毛不易", "明日之子 第7期") else "studio" if len(rows) >= 8 else "ep" if len(rows) > 1 else "single",
                        "path": str(folder), "cover": "cover.jpg", "coverWeb": "cover.webp",
                        "coverSource": None, "catalogUrl": "", "tracklistCompleteness": "partial",
                        "notes": "QQ音乐下载文件导入；未确认的发行信息留空。", "tracks": []}
            (ROOT / folder).mkdir(parents=True, exist_ok=True)
            albums.append(existing)
        cover = cover_for(existing, rows)
        with Image.open(cover) as image:
            image.thumbnail((900, 900))
            stream = BytesIO()
            image.convert("RGB").save(stream, "JPEG", quality=88)
            covers[existing["path"]] = stream.getvalue()

    imported, replaced = [], []
    for row in PLAN:
        source = SOURCE / row["source"]
        before = qq_properties(source, MP3(source))
        if row["existing"]:
            track = tracks_by_id[row["existing"][0]]
            album = albums_by_track[track["id"]]
            destination = ROOT / track["localPath"]
            if not destination.exists():
                raise FileNotFoundError(destination)
            cover = ROOT / album["path"] / "cover.jpg"
            with Image.open(cover) as image:
                image.thumbnail((900, 900))
                stream = BytesIO()
                image.convert("RGB").save(stream, "JPEG", quality=88)
                artwork = stream.getvalue()
            tag_row = dict(row, title=track["title"], artist=track["artist"],
                           track=track["trackNumber"], disc=track["discNumber"])
            previous = {"localPath": track["localPath"],
                        "sourceAudioProperties": track.get("sourceAudioProperties"),
                        "sourceFileName": track.get("sourceFileName")}
            track.setdefault("sourceAssetHistory", []).append(previous)
            replaced.append(row["source"])
        else:
            album = next(a for a in albums if a["artist"] == row["artist"] and a["title"] == row["album"])
            filename = f'{row["disc"]:02d}-{row["track"]:02d} - {safe_component(row["title"])}.mp3'
            destination = ROOT / album["path"] / filename
            if destination.exists():
                raise FileExistsError(destination)
            artwork = covers[album["path"]]
            tag_row = row
            track_id = f'qq-{safe(row["artist"])}-{safe(row["album"])}-d{row["disc"]:02d}-t{row["track"]:02d}'
            if track_id in tracks_by_id:
                raise ValueError("重复曲目ID：" + track_id)
            track = {"id": track_id, "artist": row.get("performer", row["artist"]), "album": album["title"],
                     "title": row["title"], "discNumber": row["disc"], "trackNumber": row["track"],
                     "sequenceNumber": row["track"], "duration": None, "durationSource": "local-file",
                     "sourceStatus": "available", "sourceUrl": "", "format": "MP3",
                     "localPath": str(destination.relative_to(ROOT)), "sources": [],
                     "suspected_transcode": None, "audioProperties": None,
                     "searchStatus": "local-user-source",
                     "versionMatch": "QQ文件名、专辑标签与发行目录核对；母带版本未核实",
                     "assets": [], "rightsStatus": "personal-copy; redistribution-unverified",
                     "redistributionAllowed": False, "versionReviewRequired": False}
            album["tracks"].append(track)
            tracks_by_id[track_id] = track
            imported.append(row["source"])
        after = tag_copy(source, destination, tag_row, album, artwork)
        track.update(duration=after["duration"], audioProperties=after,
                     sourceAudioProperties=before, sourceFileName=row["source"],
                     sourceStatus="available", format="MP3", sourceUrl="",
                     qualityAudit="verified-qq-320-header")
        track["assets"] = [{"trackId": track["id"], "localPath": track["localPath"],
                            "sourceUrl": "", "provider": "用户提供的QQ音乐下载目录",
                            "rightsStatus": track["rightsStatus"], "status": "imported",
                            "audioProperties": after, "sourceAudioProperties": before,
                            "suspected_transcode": None, "redistributionAllowed": False}]
    for album in albums:
        album["tracks"].sort(key=lambda track: (track["discNumber"], track["trackNumber"], track["title"]))
        write_json(ROOT / album["path"] / "album.json", album)
    albums.sort(key=lambda album: (album.get("releaseDate") or "9999", album["artist"], album["title"]))
    library["updatedAt"] = str(date.today())
    library["artists"] = sorted({album["artist"] for album in albums})
    all_tracks = [track for album in albums for track in album["tracks"]]
    library["summary"].update(albums=len(albums), tracks=len(all_tracks),
                              status=dict(Counter(track["sourceStatus"] for track in all_tracks)),
                              types=dict(Counter(album["type"] for album in albums)),
                              localTracks=sum(bool(track["localPath"]) for track in all_tracks),
                              localFormats=dict(Counter(track["format"] for track in all_tracks if track["localPath"])),
                              assetBytes=sum(asset["audioProperties"]["fileSize"] for track in all_tracks for asset in track.get("assets", []) if asset.get("audioProperties")))
    write_json(ROOT / "library.json", library)
    report = {"sourceFiles": 172, "importedTracks": len(imported), "replacedTracks": len(replaced),
              "duplicateSourceSkipped": ["林俊杰-交换余生.mp3"],
              "newFiles": imported, "replacedFiles": replaced,
              "note": "320kbps是QQ下载文件的实际MP3码率；仅凭码率不能证实原始母带质量。"}
    write_json(ROOT / "reports/qq-import-results.json", report)
    print(json.dumps({key: report[key] for key in ("sourceFiles", "importedTracks", "replacedTracks", "duplicateSourceSkipped")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
