"""Keep source cover images and a concise cover inventory in the music repo."""
from pathlib import Path
from io import BytesIO
import json
import urllib.request
import urllib.parse

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "library.json"
data = json.loads(LIBRARY.read_text())
originals = ROOT / "covers" / "originals"
originals.mkdir(parents=True, exist_ok=True)
inventory = []

for album in data["albums"]:
    folder = ROOT / album["path"]
    cover = folder / "cover.jpg"
    web = folder / "cover.webp"
    source = album.get("coverSource", {})
    if not cover.is_file() or not web.is_file():
        raise FileNotFoundError(f"缺少封面：{album['path']}")

    # OneDrive originals were retained when the catalog was built. Preserve
    # the downloaded source bytes for other providers as well.
    url = source.get("url")
    if url and not source.get("originalPath"):
        target = originals / (folder.name + " - " + album["title"] + ".jpg")
        if not target.exists():
            parsed = urllib.parse.urlsplit(url)
            encoded = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, urllib.parse.quote(parsed.path), parsed.query, parsed.fragment))
            request = urllib.request.Request(encoded, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    raw = response.read()
                with Image.open(BytesIO(raw)) as image:
                    image.verify()
                target.write_bytes(raw)
            except Exception as exc:
                print(f"原图暂不可获取：{album['title']}：{exc}")
        if target.is_file():
            source["originalPath"] = str(target.relative_to(ROOT))

    with Image.open(cover) as image:
        jpg_size = image.size
        if image.format != "JPEG":
            raise ValueError(f"cover.jpg格式错误：{album['path']}")
    with Image.open(web) as image:
        web_size = image.size
        if image.format != "WEBP":
            raise ValueError(f"cover.webp格式错误：{album['path']}")
    source["width"], source["height"] = jpg_size
    source["lowResolution"] = min(jpg_size) < 500
    album["coverSource"] = source
    (folder / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=2) + "\n")
    inventory.append({
        "title": album["title"],
        "releaseDate": album["releaseDate"],
        "type": album["type"],
        "albumPath": album["path"],
        "coverJpg": str(cover.relative_to(ROOT)),
        "coverWebp": str(web.relative_to(ROOT)),
        "jpgPixels": list(jpg_size),
        "webpPixels": list(web_size),
        "provider": source.get("provider"),
        "sourceUrl": url,
        "originalPath": source.get("originalPath"),
        "lowResolution": source["lowResolution"],
    })

LIBRARY.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
(ROOT / "reports" / "covers.json").write_text(
    json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"
)
print(f"已整理{len(inventory)}张封面；低分辨率{sum(x['lowResolution'] for x in inventory)}张")
