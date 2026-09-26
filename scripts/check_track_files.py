"""Audit current catalog-to-MP3 mapping without audio hashes or decoding."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
library = json.loads((ROOT / 'library.json').read_text())
playlist = json.loads((ROOT / 'tracks.json').read_text())
physical = {p.relative_to(ROOT).as_posix() for base in ('artists', 'live', 'collections')
            for p in (ROOT / base).rglob('*') if p.is_file() and p.suffix.lower() == '.mp3'}
tracks = [t for a in library['albums'] for t in a['tracks']]
local = [t for t in tracks if t.get('localPath')]
path_counts = Counter(t['localPath'] for t in local)
rows, errors, notices = [], [], []
registered_recordings = set()
for album in library['albums']:
    directory = ROOT / album['path']
    album_json = directory / 'album.json'
    if not album_json.is_file():
        notices.append({'kind': 'missing-album-json', 'path': album_json.relative_to(ROOT).as_posix()})
    else:
        disk = json.loads(album_json.read_text())
        if disk != album:
            notices.append({'kind': 'album-json-differs-from-library', 'path': album_json.relative_to(ROOT).as_posix()})
    for cover in ('cover.jpg', 'cover.webp'):
        if not (directory / cover).is_file():
            notices.append({'kind': 'missing-cover', 'path': (directory / cover).relative_to(ROOT).as_posix()})
    for record in album.get('fullRecordings', []):
        for path in record.get('localFiles', []):
            registered_recordings.add(path)
            if not (ROOT / path).is_file():
                notices.append({'kind': 'historical-recording-path-missing', 'path': path})
    for name in ('recording.json', 'extended-source.json'):
        if (directory / name).is_file():
            # Only use actual MP3 paths present in these auxiliary records.
            def paths(value):
                if isinstance(value, dict):
                    for x in value.values(): yield from paths(x)
                elif isinstance(value, list):
                    for x in value: yield from paths(x)
                elif isinstance(value, str) and value.endswith('.mp3'):
                    yield value
            registered_recordings.update(paths(json.loads((directory / name).read_text())))
    for track in album['tracks']:
        path = track.get('localPath') or ''
        issues = []
        if path:
            if Path(path).is_absolute() or '..' in Path(path).parts: issues.append('not-repository-relative')
            if path not in physical: issues.append('mp3-file-missing')
            if path_counts[path] != 1: issues.append('shared-by-multiple-tracks')
            assets = [a.get('localPath') for a in track.get('assets', [])]
            if assets != [path]: issues.append('active-assets-not-single-matching-file')
            # A different format or source suffix with the same disc/track prefix
            # is a potential duplicate. Explicit .full-source recordings are separate.
            prefix = Path(path).name.split(' - ', 1)[0] + ' - '
            siblings = [p.relative_to(ROOT).as_posix() for p in (ROOT / path).parent.glob('*')
                        if p.is_file() and p.name.startswith(prefix)
                        and p.suffix.lower() in ('.mp3', '.flac', '.wav', '.m4a', '.opus', '.webm')
                        and '.full-source.' not in p.name]
            if siblings != [path]: issues.append('multiple-or-missing-track-slot-files')
        elif track.get('sourceStatus') == 'available':
            issues.append('available-without-file')
        row = {'id': track['id'], 'artist': track['artist'], 'album': track['album'],
               'title': track['title'], 'localPath': path, 'sourceStatus': track['sourceStatus'],
               'result': 'error' if issues else ('unique-mp3' if path else 'no-local-audio'), 'issues': issues}
        rows.append(row)
        if issues: errors.append(row)
for key, count in Counter(t['id'] for t in tracks).items():
    if count > 1: errors.append({'duplicateTrackId': key, 'count': count})
expected = {(t['id'], t['localPath']) for t in local}
actual = [(t['id'], t['src']) for t in playlist]
if set(actual) != expected or len(actual) != len(expected): errors.append({'kind': 'playlist-mapping-mismatch'})
extra = sorted(physical - set(path_counts))
unknown = [p for p in extra if p not in registered_recordings]
if unknown: errors.append({'unregisteredMP3': unknown})
report = {'checkedAt': datetime.now(timezone.utc).isoformat(),
          'scope': 'One MP3 per catalog recording/version; names shared by different releases are not merged.',
          'validLocalTrackMapping': not errors, 'albumEntries': len(library['albums']),
          'catalogTracks': len(tracks), 'localTracks': len(local), 'uniqueTrackPaths': len(path_counts),
          'physicalMP3Files': len(physical), 'noLocalAudio': len(tracks)-len(local),
          'sourceStatuses': dict(Counter(t['sourceStatus'] for t in tracks)),
          'independentRecordings': extra, 'errors': errors, 'catalogNotices': notices,
          'hashesComputed': False, 'audioDecoded': False, 'tracks': rows}
(ROOT / 'reports/track-file-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k != 'tracks'},ensure_ascii=False,indent=2))
raise SystemExit(0 if not errors else 1)
