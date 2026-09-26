"""Remove JPEG ancillary metadata without recompressing the cover pixels."""
from pathlib import Path
import json
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
albums = json.loads((ROOT / "library.json").read_text())["albums"]
changed = []
for album in albums:
    path = ROOT / album["path"] / "cover.jpg"
    original = path.read_bytes()
    if original[:2] != b"\xff\xd8":
        raise ValueError(path)
    output = bytearray(original[:2])
    position = 2
    while position < len(original):
        start = position
        if original[position] != 255:
            raise ValueError("Invalid JPEG marker: " + str(path))
        while original[position] == 255:
            position += 1
        marker = original[position]
        position += 1
        if marker in (0xDA, 0xD9):
            output.extend(original[start:])
            break
        length = int.from_bytes(original[position:position + 2], "big")
        end = position + length
        if marker not in (0xE1, 0xED, 0xFE):  # EXIF/XMP, Photoshop and comments
            output.extend(original[start:end])
        position = end
    if bytes(output) != original:
        path.write_bytes(output)
        changed.append(str(path.relative_to(ROOT)))
    with Image.open(path) as image:
        image.load()
        if any(key in image.info for key in ("exif", "xmp", "comment")):
            raise ValueError("Metadata remains: " + str(path))
(ROOT / "reports/cover-metadata-cleanup.json").write_text(json.dumps({
    "method": "JPEG ancillary marker removal; no pixel recompression", "files": changed,
}, ensure_ascii=False, indent=2) + "\n")
print("已无损移除封面附加信息：", len(changed))
