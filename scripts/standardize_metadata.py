"""Normalize active audio names, tags, and embedded album artwork."""
from io import BytesIO
from pathlib import Path
import base64
import json
import re

from mutagen.apev2 import delete as delete_ape

from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, TALB, TDRC, TIT2, TPE1, TPE2, TPOS, TRCK
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
library_file = ROOT / "library.json"
library = json.loads(library_file.read_text())
renamed = {}

# The converted WAV is the selected track. Keep the earlier OneDrive FLAC as
# a separate source version and give the selected file the plain canonical name.
for album in library["albums"]:
    for track in album["tracks"]:
        old = track.get("localPath", "")
        if not old.endswith(".from-wav.flac"):
            continue
        primary = ROOT / old
        standard = primary.with_name(primary.name.replace(".from-wav.flac", ".flac"))
        alternative = standard.with_name(standard.stem + " [OneDrive].flac")
        if alternative.exists():
            raise FileExistsError(alternative)
        standard.rename(alternative)
        primary.rename(standard)
        renamed[str(primary.relative_to(ROOT))] = str(standard.relative_to(ROOT))
        renamed[str((ROOT / old).with_name(standard.name).relative_to(ROOT))] = str(alternative.relative_to(ROOT))

# The two original paths above overlap. The previous standard path maps to the
# alternative; the converted path maps to the new standard, each in one pass.
def replace_paths(value):
    if isinstance(value, dict):
        return {key: replace_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_paths(item) for item in value]
    return renamed.get(value, value) if isinstance(value, str) else value


library = replace_paths(library)
library_file.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n")
for album in library["albums"]:
    (ROOT / album["path"] / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=2) + "\n")
for name in ("wav-conversions.json", "download-results.jsonl", "local-import-results.jsonl"):
    path = ROOT / "reports" / name
    if not path.exists():
        continue
    if path.suffix == ".jsonl":
        path.write_text("\n".join(json.dumps(replace_paths(json.loads(line)), ensure_ascii=False)
                                  for line in path.read_text().splitlines()) + "\n")
    else:
        path.write_text(json.dumps(replace_paths(json.loads(path.read_text())), ensure_ascii=False, indent=2) + "\n")

file_entries = {}
for album in library["albums"]:
    for track in album["tracks"]:
        for asset in track.get("assets", []):
            path = asset.get("localPath")
            if path and (ROOT / path).is_file():
                if path in file_entries and file_entries[path][1]["id"] != track["id"]:
                    raise ValueError("同一文件对应多个曲目：" + path)
                file_entries[path] = (album, track)

for album in library["albums"]:
    for track in album["tracks"]:
        prefix = f"{track['discNumber']:02d}-{track['trackNumber']:02d} - {track['title']}.alternative-"
        for path in (ROOT / album["path"]).glob(prefix + "*.mp3"):
            file_entries[str(path.relative_to(ROOT))] = (album, track)
        alternate = f"{track['discNumber']:02d}-{track['trackNumber']:02d} - {track['title']} [Alternative 1].mp3"
        path = ROOT / album["path"] / alternate
        if path.is_file():
            file_entries[str(path.relative_to(ROOT))] = (album, track)

    # Source recordings are deliberately not attributed to a numbered song.
    extras = {
        "full-concert.opus": album["title"] + ("（节选录音）" if album["title"] == "我们也爱南京" else "（演出录音）"),
        "full-concert.mp3": album["title"] + ("（节选录音）" if album["title"] == "我们也爱南京" else "（演出录音）"),
        "01-09 - 这个世界会好吗.full-source.flac": "这个世界会好吗（长音轨，含未归属片段）",
        "01-09 - 这个世界会好吗.full-source.mp3": "这个世界会好吗（长音轨，含未归属片段）",
    }
    for name, title in extras.items():
        path = ROOT / album["path"] / name
        if path.is_file():
            file_entries[str(path.relative_to(ROOT))] = (album, {
                "id": album["id"] + "-source", "title": title, "artist": album["artist"],
                "trackNumber": None, "discNumber": None,
            })

physical = {str(path.relative_to(ROOT)) for base in ("artists", "live", "collections")
            for path in (ROOT / base).rglob("*")
            if path.suffix.lower() in (".mp3", ".flac", ".m4a", ".opus", ".wav", ".webm")}
if physical != set(file_entries):
    raise ValueError("尚未建立标签映射的音频：" + repr(sorted(physical - set(file_entries))))


def embedded_jpeg(album):
    with Image.open(ROOT / album["path"] / album["cover"]) as image:
        image = image.convert("RGB")
        image.thumbnail((900, 900))
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=86, optimize=True)
        return buffer.getvalue()


images = {album["id"]: embedded_jpeg(album) for album in library["albums"]}
report = []
for relative, (album, track) in file_entries.items():
    path = ROOT / relative
    cover = images[album["id"]]
    title, artist, album_title = track["title"], track["artist"], album["title"]
    album_artist = album.get("albumArtist") or album["artist"]
    date = album.get("releaseDate") or str(album.get("year") or "")
    number = str(track["trackNumber"]) if track["trackNumber"] is not None else ""
    disc = str(track["discNumber"]) if track["discNumber"] is not None else ""
    ext = path.suffix.lower()
    if ext == ".flac":
        media = FLAC(path)
        media.clear()
        media.tags.vendor = "Music Library"
        for key, value in (("TITLE", title), ("ARTIST", artist), ("ALBUM", album_title),
                           ("ALBUMARTIST", album_artist), ("TRACKNUMBER", number),
                           ("DISCNUMBER", disc), ("DATE", date)):
            if value:
                media[key] = [value]
        media.clear_pictures()
        picture = Picture()
        picture.type, picture.mime, picture.desc, picture.data = 3, "image/jpeg", "Front cover", cover
        with Image.open(BytesIO(cover)) as image:
            picture.width, picture.height = image.size
            picture.depth = 24
        media.add_picture(picture)
        media.save()
    elif ext == ".mp3":
        # APEv2 and ID3v1 can contain another independent copy of the old tags.
        delete_ape(path)
        media = MP3(path)
        media.delete()
        media = MP3(path)
        if media.tags is None:
            media.add_tags()
        tags = media.tags
        for key in ("TIT2", "TPE1", "TPE2", "TALB", "TRCK", "TPOS", "TDRC", "APIC"):
            tags.delall(key)
        tags.add(TIT2(encoding=3, text=title))
        tags.add(TPE1(encoding=3, text=artist))
        tags.add(TPE2(encoding=3, text=album_artist))
        tags.add(TALB(encoding=3, text=album_title))
        if number:
            tags.add(TRCK(encoding=3, text=number))
        if disc:
            tags.add(TPOS(encoding=3, text=disc))
        if date:
            tags.add(TDRC(encoding=3, text=date))
        tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Front cover", data=cover))
        media.save(v2_version=3, v1=0)
    elif ext == ".m4a":
        media = MP4(path)
        # Preserve only the numeric AAC priming/padding data needed for gapless
        # playback. Account, purchase, comments, lyrics and URLs are removed.
        gapless = media.get("----:com.apple.iTunes:iTunSMPB")
        if gapless and not all(re.fullmatch(rb"[0-9A-Fa-f ]+", bytes(x)) for x in gapless):
            gapless = None
        media.clear()
        if gapless:
            media["----:com.apple.iTunes:iTunSMPB"] = gapless
        media["\xa9nam"], media["\xa9ART"], media["aART"] = [title], [artist], [album_artist]
        media["\xa9alb"], media["trkn"], media["disk"] = [album_title], [(track["trackNumber"], 0)], [(track["discNumber"], 0)]
        if date:
            media["\xa9day"] = [date]
        media["covr"] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]
        media.save()
    elif ext == ".opus":
        media = OggOpus(path)
        media.clear()
        media.tags.vendor = "Music Library"
        for key, value in (("TITLE", title), ("ARTIST", artist), ("ALBUM", album_title),
                           ("ALBUMARTIST", album_artist), ("TRACKNUMBER", number),
                           ("DISCNUMBER", disc), ("DATE", date)):
            if value:
                media[key] = [value]
        picture = Picture()
        picture.type, picture.mime, picture.desc, picture.data = 3, "image/jpeg", "Front cover", cover
        with Image.open(BytesIO(cover)) as image:
            picture.width, picture.height = image.size
            picture.depth = 24
        media["METADATA_BLOCK_PICTURE"] = [base64.b64encode(picture.write()).decode("ascii")]
        media.save()
    else:
        raise ValueError("未支持的音频格式：" + relative)
    report.append({"path": relative, "artist": artist, "album": album_title,
                   "title": title, "trackNumber": track["trackNumber"],
                   "discNumber": track["discNumber"], "albumArtist": album_artist,
                   "date": date, "coverEmbedded": True})

(ROOT / "reports" / "metadata-standardization.json").write_text(
    json.dumps({"policy": "clear-original-tags-then-write-whitelist", "renamed": renamed, "taggedFiles": len(report), "files": report},
               ensure_ascii=False, indent=2) + "\n")
print(f"重命名{len(renamed)}个文件路径，统一写入{len(report)}个音频文件的标签和封面。")
