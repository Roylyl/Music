"""Check every local audio tag, embedded cover and basic audio properties."""
from io import BytesIO
from pathlib import Path
import base64
import json

from mutagen import File
from mutagen.apev2 import APEv2, APENoHeaderError
from mutagen.flac import Picture
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
library = json.loads((ROOT / "library.json").read_text())
entries = json.loads((ROOT / "reports/metadata-standardization.json").read_text())["files"]
baseline = json.loads((ROOT / "reports/metadata-clean-baseline.json").read_text())
expected_covers = {}
for album in library["albums"]:
    with Image.open(ROOT / album["path"] / "cover.jpg") as image:
        image = image.convert("RGB")
        image.thumbnail((900, 900))
        output = BytesIO()
        image.save(output, format="JPEG", quality=86, optimize=True)
        expected_covers[album["path"]] = output.getvalue()

errors = []
for album in library["albums"]:
    for filename, expected_format in (("cover.jpg", "JPEG"), ("cover.webp", "WEBP")):
        path = ROOT / album["path"] / filename
        with Image.open(path) as image:
            image.load()
            if image.format != expected_format or any(key in image.info for key in ("exif", "xmp", "comment")):
                errors.append({"path": str(path.relative_to(ROOT)), "error": "cover format or ancillary metadata"})
checked = []
for entry in entries:
    rel = entry["path"]
    path = ROOT / rel
    media = File(path)
    suffix = path.suffix.lower()
    expected = {"title": entry["title"], "artist": entry["artist"], "album": entry["album"],
                "albumartist": entry["albumArtist"], "date": entry["date"]}
    if entry["trackNumber"] is not None:
        expected.update(tracknumber=str(entry["trackNumber"]), discnumber=str(entry["discNumber"]))
    if suffix == ".mp3":
        mapping = {"title": "TIT2", "artist": "TPE1", "album": "TALB", "albumartist": "TPE2",
                   "date": "TDRC", "tracknumber": "TRCK", "discnumber": "TPOS"}
        values = {key: str(media.tags.get(frame, "")) for key, frame in mapping.items()}
        unexpected = {frame.FrameID for frame in media.tags.values()} - set(mapping.values()) - {"APIC"}
        pictures = media.tags.getall("APIC")
        cover = pictures[0].data if len(pictures) == 1 and pictures[0].type == 3 else None
        try:
            APEv2(path)
            errors.append({"path": rel, "error": "APEv2 remains"})
        except APENoHeaderError:
            pass
        with path.open("rb") as handle:
            handle.seek(-128, 2)
            if handle.read(3) == b"TAG":
                errors.append({"path": rel, "error": "ID3v1 remains"})
    elif suffix == ".m4a":
        mapping = {"title": "\xa9nam", "artist": "\xa9ART", "album": "\xa9alb",
                   "albumartist": "aART", "date": "\xa9day"}
        values = {key: media.get(tag, [""])[0] for key, tag in mapping.items()}
        values.update(tracknumber=str(media["trkn"][0][0]), discnumber=str(media["disk"][0][0]))
        unexpected = set(media.keys()) - set(mapping.values()) - {"trkn", "disk", "covr", "----:com.apple.iTunes:iTunSMPB"}
        pictures = media.get("covr", [])
        cover = bytes(pictures[0]) if len(pictures) == 1 else None
    else:
        values = {key: media.get(key, [""])[0] for key in expected}
        unexpected = {key.lower() for key in media.keys()} - set(expected) - {"metadata_block_picture"}
        pictures = media.pictures if suffix == ".flac" else [Picture(base64.b64decode(value)) for value in media.get("metadata_block_picture", [])]
        cover = pictures[0].data if len(pictures) == 1 and pictures[0].type == 3 else None
    if unexpected:
        errors.append({"path": rel, "error": "non-whitelisted metadata", "keys": sorted(unexpected)})
    for key, value in expected.items():
        if values.get(key, "") != value:
            errors.append({"path": rel, "error": "field mismatch", "field": key})
    if cover != expected_covers[str(path.parent.relative_to(ROOT))]:
        errors.append({"path": rel, "error": "cover does not match album"})
    else:
        with Image.open(BytesIO(cover)) as image:
            image.load()
            if image.format != "JPEG":
                errors.append({"path": rel, "error": "cover is not JPEG"})
    before = baseline[rel]
    info = media.info
    if (abs(info.length - before["duration"]) > 0.05 or info.channels != before["channels"]
            or getattr(info, "sample_rate", 48000) != before["sampleRate"]
            or getattr(info, "bits_per_sample", None) != before["bits"]):
        errors.append({"path": rel, "error": "audio properties changed", "beforeDuration": before["duration"], "afterDuration": info.length})
    checked.append(rel)

physical = {str(path.relative_to(ROOT)) for base in ("artists", "live", "collections")
            for path in (ROOT / base).rglob("*")
            if path.suffix.lower() in (".mp3", ".flac", ".m4a", ".opus", ".webm", ".wav")}
if set(checked) != physical:
    errors.append({"error": "physical file coverage mismatch", "unhandled": sorted(physical - set(checked))})
result = {"valid": not errors, "audioFilesChecked": len(checked), "albumCoverFilesChecked": len(library["albums"]) * 2, "errors": errors,
          "checks": ["metadata whitelist", "catalog field equality", "single decodable front cover matching album",
                     "no MP3 ID3v1 or APEv2", "unchanged duration sample rate channels bit depth", "all physical audio covered"],
          "hashesComputed": False}
(ROOT / "reports/metadata-clean-validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"valid": result["valid"], "checked": len(checked), "errors": errors[:10]}, ensure_ascii=False))
if errors:
    raise SystemExit(1)
