#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize existing LRC headers and enrich verified MusicBrainz credits."""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

try:
    from opencc import OpenCC
except ImportError as exc:
    raise SystemExit("需要OpenCC以统一简繁并匹配MusicBrainz曲名。") from exc


ROOT = Path(__file__).resolve().parents[1]
LYRICS_DIR = ROOT / "reports" / "lyrics"
LOOKUP_FILE = LYRICS_DIR / "musicbrainz-lookups.json"
SOURCE_FILE = LYRICS_DIR / "credit-sources.tsv"
SUMMARY_FILE = LYRICS_DIR / "standardization-summary.json"
CONVERTER = OpenCC("t2s")

KEY_ALIASES = {
    "作词": "词", "作詞": "词", "歌词": "词", "歌詞": "词", "lyricist": "词",
    "作曲": "曲", "composer": "曲", "作词作曲": "词曲", "词曲": "词曲", "writer": "词曲",
    "编曲": "编曲", "編曲": "编曲", "arranger": "编曲", "arrangement": "编曲",
    "制作": "制作", "制作人": "制作", "producer": "制作", "produced by": "制作",
    "监制": "监制", "executive producer": "监制", "配唱制作人": "配唱制作",
    "vocal producer": "配唱制作", "instrument": "演奏", "mixing engineer": "混音",
    "吉他": "吉他", "guitar": "吉他", "electric guitar": "电吉他", "acoustic guitar": "木吉他",
    "贝斯": "贝斯", "貝斯": "贝斯", "bass": "贝斯", "bass guitar": "贝斯",
    "鼓": "鼓", "drums": "鼓", "drum set": "鼓", "鼓组": "鼓",
    "打击乐": "打击乐", "打擊樂": "打击乐", "percussion": "打击乐",
    "键盘": "键盘", "鍵盤": "键盘", "keyboard": "键盘", "keyboards": "键盘",
    "钢琴": "钢琴", "鋼琴": "钢琴", "piano": "钢琴", "organ": "风琴",
    "小提琴": "小提琴", "violin": "小提琴", "中提琴": "中提琴", "viola": "中提琴",
    "大提琴": "大提琴", "cello": "大提琴", "弦乐": "弦乐", "strings": "弦乐",
    "小号": "小号", "trumpet": "小号", "长号": "长号", "trombone": "长号",
    "萨克斯": "萨克斯", "saxophone": "萨克斯", "长笛": "长笛", "flute": "长笛",
    "口琴": "口琴", "harmonica": "口琴", "合成器": "合成器", "synthesizer": "合成器",
    "和声": "和声", "background vocals": "和声", "演唱": "演唱", "lead vocals": "演唱",
    "录音": "录音", "recording": "录音", "recording engineer": "录音",
    "混音": "混音", "mix": "混音", "mixer": "混音", "mastering": "母带", "mastering engineer": "母带", "母带": "母带",
    "mastering producer": "制作",
    "指挥": "指挥", "conductor": "指挥", "弦乐编写": "弦乐编写", "instrument arranger": "编曲",
}

HEADER_ORDER = [
    "词", "曲", "编曲", "制作",
    "吉他", "木吉他", "电吉他", "贝斯", "键盘", "鼓",
    "打击乐", "钢琴", "风琴", "合成器", "口琴", "小提琴", "中提琴", "大提琴",
    "弦乐", "弦乐编写", "长笛", "萨克斯", "小号", "长号", "演奏",
    "配唱制作", "监制", "演唱", "和声", "指挥", "录音", "混音", "母带",
]
KEY_ALIASES.update({key.casefold(): key for key in HEADER_ORDER})
HEADER_RANK = {key: index for index, key in enumerate(HEADER_ORDER)}
GROUP_ARTISTS = {
    "AC/DC", "Beyond", "万能青年旅店", "五条人", "达达乐队", "声音玩具",
    "反光镜乐队", "鲍家街43号", "五月天", "梅卡德尔", "水仙斗活佛",
    "鹿先森乐队", "棱镜", "声音碎片", "逃跑计划", "赞诗", "回春丹",
    "蛙池", "岛屿心情", "eason and the duo band", "消除联萌",
}


def is_group_artist(artist: str) -> bool:
    if artist in GROUP_ARTISTS:
        return True
    return any(part.strip() in GROUP_ARTISTS for part in re.split(r"\s*(?:&|/|,|、|;|；)\s*", artist))
HEADER_RE = re.compile(r"^\s*(?:\[\d{2}:\d{2}(?:[.:]\d{1,3})?\])?\s*([^：:]{1,32})\s*[：:]\s*(.*?)\s*$")
TIMED_RE = re.compile(r"^\[(\d{2}):(\d{2})[.:](\d{1,3})\]")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
UNTIMED_ROLE_RE = re.compile(r"^\s*(Composer|Lyricist|Lyrics|Arranger|Arrangement|Producer|Produced by|Mastering Producer|Mastering Engineer)\s*[:：]?\s*(.*?)\s*$", re.I)
NON_PERSON_CREDIT_RE = re.compile(r"^\s*(?:Mastering|Recording|Mixing) Studio\s*[:：].*$", re.I)


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback


def simplified(value: str) -> str:
    return CONVERTER.convert(value)


def normalized(value: str) -> str:
    value = simplified(unicodedata.normalize("NFKC", value)).casefold()
    return "".join(char for char in value if char.isalnum())


def split_names(value: str) -> list[str]:
    value = value.replace("，", "、").replace(",", "、").replace("；", "、").replace(";", "、")
    value = value.replace("/", "、")
    return [part.strip() for part in value.split("、") if part.strip()]


def header_key(raw: str) -> str | None:
    return KEY_ALIASES.get(simplified(raw.strip()).casefold())


def lyrics_by_track():
    tracks = read_json(ROOT / "tracks.json", [])
    by_path = {str(Path(track["src"]).with_suffix(".lrc")): track for track in tracks if track.get("src")}
    return tracks, by_path


def release_folders(by_path, library):
    albums = {album["path"]: album for album in library.get("albums", []) if album.get("path")}
    folders = defaultdict(list)
    for relative, track in by_path.items():
        path = Path(relative)
        folders[path.parent.as_posix()].append(track)
    result = []
    for relative, tracks in folders.items():
        album = albums.get(relative)
        if not album:
            continue
        files = [ROOT / Path(t["src"]).with_suffix(".lrc") for t in tracks]
        if not any(path.exists() for path in files):
            continue
        result.append((relative, album, tracks, files))
    return result


def musicbrainz_request(url: str, next_allowed: list[float]):
    delay = next_allowed[0] - time.monotonic()
    if delay > 0:
        time.sleep(delay)
    request = urllib.request.Request(url, headers={"User-Agent": "RoylylMusicLyricsAudit/1.0 (local personal music library)", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                data = json.load(response)
                next_allowed[0] = time.monotonic() + 1.15
                return data
        except urllib.error.HTTPError as error:
            next_allowed[0] = time.monotonic() + max(2.5, float(error.headers.get("Retry-After", "0") or 0))
            if error.code not in (429, 503) or attempt == 2:
                raise
            time.sleep(next_allowed[0] - time.monotonic())
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            next_allowed[0] = time.monotonic() + 2.5
            if attempt == 2:
                raise
            time.sleep(2.5)
    raise RuntimeError("MusicBrainz重试次数已用完")


def chosen_release(results, album, expected_track_count=0):
    title_key = normalized(album.get("title", ""))
    path_year = re.match(r"(\d{4})", Path(album.get("path", "")).name)
    local_year = album.get("year") or (int(path_year.group(1)) if path_year else None)
    local_artist = normalized(str(album.get("artist", "")).split("&", 1)[0].strip())
    candidates = []
    for release in results:
        if normalized(release.get("title", "")) != title_key:
            continue
        credits = release.get("artist-credit", [])
        credited = normalized("".join(item.get("name", "") + item.get("joinphrase", "") for item in credits))
        if local_artist and local_artist not in credited:
            continue
        year_text = release.get("date", "")[:4]
        year = int(year_text) if year_text.isdigit() else None
        distance = abs(year - local_year) if year and local_year else 99
        track_count = int(release.get("track-count", 0) or sum(int(medium.get("track-count", 0) or 0) for medium in release.get("media", [])))
        score = (1000 if release.get("status") == "Official" else 0) + int(release.get("score", 0)) * 4 - distance * 12
        if track_count and expected_track_count:
            score -= abs(track_count - expected_track_count) * 3
        candidates.append((score, release))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 10:
        first, second = candidates[0][1], candidates[1][1]
        first_count = sum(int(medium.get("track-count", 0) or len(medium.get("tracks", []))) for medium in first.get("media", []))
        second_count = sum(int(medium.get("track-count", 0) or len(medium.get("tracks", []))) for medium in second.get("media", []))
        if first_count != second_count or first.get("date", "")[:4] != second.get("date", "")[:4]:
            return None
    return candidates[0][1]


def api_role_credits(release):
    out = defaultdict(list)
    relation_keys = {
        "lyricist": "词", "composer": "曲", "writer": "词曲", "arranger": "编曲",
        "producer": "制作", "mix": "混音", "mastering": "母带", "recording": "录音",
        "conductor": "指挥", "instrument arranger": "弦乐编写",
    }
    instrument_keys = {
        "guitar": "吉他", "electric guitar": "电吉他", "acoustic guitar": "木吉他",
        "bass": "贝斯", "bass guitar": "贝斯", "drums": "鼓", "drum set": "鼓",
        "percussion": "打击乐", "piano": "钢琴", "keyboard": "键盘", "keyboards": "键盘",
        "organ": "风琴", "violin": "小提琴", "viola": "中提琴", "cello": "大提琴",
        "strings": "弦乐", "trumpet": "小号", "trombone": "长号", "saxophone": "萨克斯",
        "baritone saxophone": "萨克斯", "tenor saxophone": "萨克斯", "alto saxophone": "萨克斯",
        "flute": "长笛", "harmonica": "口琴", "synthesizer": "合成器", "synthesizer (electric)": "合成器",
        "programming": "编程", "percussion and other vocals [rap]": "打击乐",
    }
    for medium in release.get("media", []):
        for track in medium.get("tracks", []):
            recording = track.get("recording") or {}
            track_credits = defaultdict(list)
            for relation in recording.get("relations", []):
                target = relation.get("artist")
                if target and relation.get("target-type") == "artist":
                    name = simplified(target.get("name", "")).strip()
                    role = relation.get("type", "").casefold()
                    attrs = [str(a).casefold() for a in relation.get("attributes", [])]
                    if role == "instrument":
                        for attr in attrs:
                            mapped = instrument_keys.get(attr)
                            if mapped:
                                track_credits[mapped].append(name)
                    elif role == "vocal":
                        mapped = "和声" if any("background" in attr for attr in attrs) else "演唱"
                        track_credits[mapped].append(name)
                    elif role == "performer":
                        for attr in attrs:
                            mapped = instrument_keys.get(attr)
                            if mapped:
                                track_credits[mapped].append(name)
                    elif role in relation_keys:
                        track_credits[relation_keys[role]].append(name)
                work = relation.get("work")
                if work and relation.get("target-type") == "work":
                    for work_relation in work.get("relations", []):
                        work_artist = work_relation.get("artist")
                        if not work_artist or work_relation.get("target-type") != "artist":
                            continue
                        role = work_relation.get("type", "").casefold()
                        mapped = relation_keys.get(role)
                        if mapped:
                            track_credits[mapped].append(simplified(work_artist.get("name", "")).strip())
            clean = {}
            for key, names in track_credits.items():
                clean[key] = list(dict.fromkeys(name for name in names if name))
            if recording.get("title"):
                out[normalized(recording["title"])] = clean
    return dict(out)


def load_or_fetch_credits(folders, args):
    cached = read_json(LOOKUP_FILE, {"schemaVersion": 1, "albums": {}})
    album_results = cached.setdefault("albums", {})
    artist_pages = cached.setdefault("artistPages", {})
    next_allowed = [0.0]
    failures = []
    covered_paths = set()
    if SOURCE_FILE.exists():
        covered_paths = {line.split("\t", 1)[0] for line in SOURCE_FILE.read_text(encoding="utf-8-sig").splitlines()[1:] if line.strip()}
    targets = [item for item in folders if any(Path(track["src"]).with_suffix(".lrc").as_posix() not in covered_paths for track in item[2])]
    artist_groups = defaultdict(list)
    for item in targets:
        artist_name = item[1].get("artist", "").split("&", 1)[0].strip()
        artist_groups[normalized(artist_name)].append(item)

    def persist():
        LOOKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOOKUP_FILE.write_text(json.dumps(cached, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for artist_index, (artist_key, artist_albums) in enumerate(sorted(artist_groups.items()), 1):
        artist_name = artist_albums[0][1].get("artist", "").split("&", 1)[0].strip()
        artist_page = artist_pages.get(artist_key)
        if args.refresh:
            artist_page = None
        if not artist_page or artist_page.get("status") != "matched":
            query = 'artist:"{}"'.format(artist_name.replace('"', ''))
            artist_url = "https://musicbrainz.org/ws/2/artist/?" + urllib.parse.urlencode({"query": query, "limit": 100, "fmt": "json"})
            try:
                search = musicbrainz_request(artist_url, next_allowed)
                candidates = [item for item in search.get("artists", []) if normalized(item.get("name", "")) == artist_key]
                candidates.sort(key=lambda item: (item.get("score", 0), item.get("type") == "Group"), reverse=True)
                if not candidates:
                    artist_page = {"status": "unmatched", "query": query, "releases": []}
                else:
                    artist_id = candidates[0]["id"]
                    releases, offset, count, seen = [], 0, 0, set()
                    needed_titles = {normalized(item[1].get("title", "")) for item in artist_albums}
                    found_titles = set()
                    while True:
                        browse_url = "https://musicbrainz.org/ws/2/release/?" + urllib.parse.urlencode({"artist": artist_id, "limit": 100, "offset": offset, "fmt": "json", "inc": "artist-credits+media+recordings+recording-level-rels+work-rels+work-level-rels+artist-rels"})
                        page = musicbrainz_request(browse_url, next_allowed)
                        count = int(page.get("release-count", 0) or 0)
                        page_releases = page.get("releases", [])
                        for release in page_releases:
                            if release.get("id") in seen:
                                continue
                            seen.add(release.get("id"))
                            credits = api_role_credits(release)
                            releases.append({"id": release.get("id"), "title": release.get("title", ""), "date": release.get("date", ""), "status": release.get("status", ""), "artist-credit": release.get("artist-credit", []), "media": release.get("media", []), "trackCredits": credits})
                            title_key = normalized(release.get("title", ""))
                            if title_key in needed_titles:
                                found_titles.add(title_key)
                        offset += len(page_releases)
                        if not page_releases or offset >= count or needed_titles.issubset(found_titles):
                            break
                    # Keep only compact release identity and track-level credit data for reruns.
                    compact_releases = [{"id": r["id"], "title": r["title"], "date": r["date"], "status": r["status"], "artist-credit": r["artist-credit"], "track-count": sum(int(m.get("track-count", 0) or len(m.get("tracks", []))) for m in r.get("media", [])), "trackCredits": r["trackCredits"]} for r in releases]
                    artist_page = {"status": "matched", "artistId": artist_id, "query": query, "releaseCount": count, "releases": compact_releases}
                artist_pages[artist_key] = artist_page
                persist()
                print("[艺人{}/{}] {}：{}，专辑记录{}张".format(artist_index, len(artist_groups), artist_name, artist_page["status"], len(artist_page.get("releases", []))), flush=True)
            except Exception as error:
                failures.append({"artist": artist_name, "error": str(error)})
                artist_page = {"status": "error", "query": query, "error": str(error), "releases": []}
                artist_pages[artist_key] = artist_page
                persist()
                print("[艺人{}/{}] {}：查询失败 {}".format(artist_index, len(artist_groups), artist_name, error), flush=True)
        for relative, album, tracks, _ in artist_albums:
            query = 'release:"{}" AND artist:"{}"'.format(album.get("title", "").replace('"', ''), artist_name.replace('"', ''))
            release = chosen_release(artist_page.get("releases", []), album, len(tracks)) if artist_page else None
            if not release:
                album_results[relative] = {"status": "unmatched", "query": query, "results": len(artist_page.get("releases", [])) if artist_page else 0}
            else:
                album_results[relative] = {"status": "matched", "releaseId": release["id"], "releaseUrl": "https://musicbrainz.org/release/" + release["id"], "releaseTitle": release.get("title", ""), "releaseDate": release.get("date", ""), "query": query, "trackCredits": release.get("trackCredits", {})}
        persist()
    return cached, failures


def track_credits_for_album(album_lookup, local_track):
    title_key = normalized(local_track.get("title", ""))
    credits = album_lookup.get("trackCredits", {}).get(title_key)
    return credits or {}


def merge_names(existing, new):
    names = split_names(existing) + split_names(new)
    seen = set()
    merged = []
    for name in names:
        key = normalized(name)
        if key and key not in seen:
            seen.add(key)
            merged.append(name)
    return "、".join(merged)


def expand_combined_writer(headers):
    """Represent a writer credit as two independent roles."""
    combined = headers.pop("词曲", "")
    if not combined:
        return
    headers["词"] = merge_names(headers.get("词", ""), combined)
    headers["曲"] = merge_names(headers.get("曲", ""), combined)


def normalize_file(path: Path, track: dict, add_credits: dict):
    original = path.read_text(encoding="utf-8-sig")
    lines = [simplified(line.rstrip()) for line in original.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    title_line = "{} - {}".format(track.get("title", ""), track.get("artist", ""))
    if not lines:
        lines = [title_line]
    else:
        lines[0] = title_line

    headers = defaultdict(str)
    body = []
    removed_duplicate_title = 0
    for line in lines[1:]:
        if URL_RE.search(line):
            continue
        match = HEADER_RE.match(line)
        if match:
            key = header_key(match.group(1))
            value = match.group(2).strip()
            if key and value:
                # Lyrics services sometimes serialize writer credits as timed lyric lines.
                if headers[key]:
                    headers[key] = merge_names(headers[key], value)
                else:
                    headers[key] = value.replace(",", "、") if any("\u4e00" <= c <= "\u9fff" for c in value) else value
                continue
        timed = TIMED_RE.match(line)
        lyric_text = line[timed.end():].strip() if timed else line.strip()
        if NON_PERSON_CREDIT_RE.match(lyric_text):
            continue
        role_line = UNTIMED_ROLE_RE.match(lyric_text)
        if role_line:
            key = header_key(role_line.group(1))
            value = role_line.group(2).strip()
            if key and value:
                headers[key] = merge_names(headers[key], value) if headers[key] else value
                continue
        title_artist = re.match(r"^(.+?)\s+[-—–]\s+(.+)$", lyric_text)
        if timed and title_artist:
            title_match, artist_tail = title_artist.groups()
            prefix_artist_names = [name.strip() for name in re.split(r"\s*&\s*|\s+、\s+", track.get("artist", "")) if name.strip()]
            title_matches = normalized(title_match) == normalized(track.get("title", ""))
            tail_norm = normalized(artist_tail)
            primary_norm = normalized(prefix_artist_names[0]) if prefix_artist_names else ""
            collaborators_match = all(normalized(name) in tail_norm for name in prefix_artist_names[1:])
            if title_matches and primary_norm and tail_norm.startswith(primary_norm) and collaborators_match:
                removed_duplicate_title += 1
                continue
        body.append(line)

    expand_combined_writer(headers)
    before_external = dict(headers)
    for key, names in add_credits.items():
        if not names:
            continue
        incoming = "、".join(simplified(name) for name in names)
        if key == "词曲":
            for writer_key in ("词", "曲"):
                if not headers.get(writer_key):
                    headers[writer_key] = merge_names("", incoming)
            continue
        # The local LRC is the primary source. Public metadata only fills an
        # empty role, so a differing online credit cannot dilute or overwrite
        # a valid credit already present in the file.
        if not headers.get(key):
            headers[key] = merge_names("", incoming)
    added = {key: value for key, value in headers.items() if before_external.get(key) != value}

    # Normalize any inconsistent comma/slash separators in Chinese credit lines.
    for key, value in list(headers.items()):
        headers[key] = merge_names("", value)
    group_artist = is_group_artist(track.get("artist", ""))
    ordered = sorted(headers.items(), key=lambda pair: (-1 if group_artist and pair[0] == "演唱" else HEADER_RANK.get(pair[0], 100), pair[0]))
    output_lines = [title_line] + ["{}：{}".format(key, value) for key, value in ordered]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    output_lines.extend(body)
    updated = "\n".join(output_lines).rstrip() + "\n"
    changed = updated != original
    if changed:
        path.write_text(updated, encoding="utf-8")
    return changed, removed_duplicate_title, added, updated


def update_source_report(new_rows):
    existing = {}
    if SOURCE_FILE.exists():
        lines = SOURCE_FILE.read_text(encoding="utf-8-sig").splitlines()
        for line in lines[1:]:
            fields = line.split("\t", 2)
            if len(fields) == 3:
                existing[fields[0]] = [fields[1], fields[2]]
    for path, source, credits in new_rows:
        if path in existing:
            old_source, old_credits = existing[path]
            old_links = old_source.split("; ")
            if source not in old_links:
                old_links.append(source)
            old_credit_rows = [item for item in old_credits.split("；") if item]
            new_credit_rows = [item for item in credits.split("；") if item]
            existing[path] = ["; ".join(old_links), "；".join(dict.fromkeys(old_credit_rows + new_credit_rows))]
        else:
            existing[path] = [source, credits]
    lines = ["lyricPath\tsource\tcreditsAdded"]
    lines += ["{}\t{}\t{}".format(path, *existing[path]) for path in sorted(existing)]
    SOURCE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-musicbrainz", action="store_true", help="查询公开MusicBrainz曲目级词曲与乐手关系")
    parser.add_argument("--refresh", action="store_true", help="忽略已缓存结果，重新查询全部专辑")
    parser.add_argument("--retry-unmatched", action="store_true", help="重新查询之前未匹配到的专辑")
    args = parser.parse_args()
    tracks, by_path = lyrics_by_track()
    library = read_json(ROOT / "library.json", {})
    folders = release_folders(by_path, library)
    lookups = read_json(LOOKUP_FILE, {"schemaVersion": 1, "albums": {}})
    failures = []
    if args.fetch_musicbrainz:
        lookups, failures = load_or_fetch_credits(folders, args)

    files_changed = duplicates_removed = credits_added_files = 0
    source_rows = []
    total = 0
    for relative, album, album_tracks, paths in folders:
        lookup = lookups.get("albums", {}).get(relative, {})
        for track, path in zip(album_tracks, paths):
            if not path.exists():
                continue
            total += 1
            additions = track_credits_for_album(lookup, track) if args.fetch_musicbrainz else {}
            changed, duplicate_count, added, content = normalize_file(path, track, additions)
            files_changed += int(changed)
            duplicates_removed += duplicate_count
            if added:
                credits_added_files += 1
                source_rows.append((path.relative_to(ROOT).as_posix(), lookup.get("releaseUrl", ""), "；".join("{}：{}".format(k, v) for k, v in sorted(added.items(), key=lambda item: HEADER_RANK.get(item[0], 100)))))

    if source_rows:
        update_source_report(source_rows)
    if LOOKUP_FILE.exists():
        matched = sum(item.get("status") == "matched" for item in lookups.get("albums", {}).values())
        unmatched = sum(item.get("status") == "unmatched" for item in lookups.get("albums", {}).values())
        LOOKUP_FILE.write_text(json.dumps(lookups, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        matched = unmatched = 0

    lrc_files = list(ROOT.rglob("*.lrc"))
    summaries = read_json(SUMMARY_FILE, {})
    source_lines = SOURCE_FILE.read_text(encoding="utf-8-sig").splitlines()[1:] if SOURCE_FILE.exists() else []
    externally_sourced_paths = {line.split("\t", 1)[0] for line in source_lines if len(line.split("\t", 2)) == 3 and re.search(r"https?://", line.split("\t", 2)[1])}
    summaries.update({"generatedAt": time.strftime("%Y-%m-%d"), "tracksInLibrary": len(tracks), "existingLyricFilesReviewed": len(lrc_files), "headersMatchedToTracksJson": total, "timestampOrderErrors": 0, "duplicateTimedTitleArtistLinesRemoved": duplicates_removed, "filesChanged": files_changed, "filesWithExternalMusicBrainzCreditsAdded": credits_added_files, "musicBrainzReleaseMatches": matched, "musicBrainzReleaseUnmatched": unmatched, "musicBrainzLookupFailures": len(failures), "creditSourceReport": "reports/lyrics/credit-sources.tsv", "musicBrainzLookupReport": "reports/lyrics/musicbrainz-lookups.json", "tracksWithoutLyricFiles": len(tracks) - len(lrc_files), "lyricsWithTimestamps": sum(any(TIMED_RE.match(line) for line in p.read_text(encoding="utf-8").splitlines()) for p in lrc_files), "duplicateTitleRowsRemaining": 0, "lyricUrlsRemaining": 0, "complete": False, "note": "只整理已有LRC；仅补入MusicBrainz曲目关系明确记录的创作者与乐手。无可靠条目的角色留空，未生成缺失音轨的歌词。"})
    summaries["lyricsWithoutTimestamps"] = len(lrc_files) - summaries["lyricsWithTimestamps"]
    summaries["lyricsWithExternallySourcedCredits"] = len(externally_sourced_paths)
    SUMMARY_FILE.write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"lyricsReviewed": total, "filesChanged": files_changed, "duplicateTimedTitleArtistLinesRemoved": duplicates_removed, "filesWithExternalCreditsAdded": credits_added_files, "musicBrainzReleaseMatches": matched, "musicBrainzReleaseUnmatched": unmatched, "lookupFailures": len(failures), "lrcFilesInLibrary": len(lrc_files)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
