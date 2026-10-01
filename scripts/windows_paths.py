"""Windows-safe path components and a read-only checkout path check.

Run: python3 scripts/windows_paths.py [repository ...]
Checks the current files Git will include, without staging changes or hashing.
"""

from pathlib import Path
import re
import subprocess
import sys

REPLACEMENTS = dict(zip('\\/:*?"<>|', '／／：＊？＂＜＞｜'))
RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])$', re.I)


def safe_component(value):
    value = ''.join(REPLACEMENTS.get(c, c) if ord(c) >= 32 else '_' for c in value)
    value = value.strip().rstrip('. ')
    if not value:
        return '_'
    if RESERVED.fullmatch(value.split('.')[0].rstrip(' ')):
        value = '_' + value
    return value


def check_repository(root):
    paths = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root
    ).decode().split('\0')
    errors = set()
    components = {}
    count = 0
    for relative in sorted(set(filter(None, paths))):
        if not (root / relative).exists():
            continue  # Unstaged renames leave the old path in the index.
        count += 1
        parts = relative.split('/')
        for i, part in enumerate(parts):
            if (part.endswith(('.', ' ')) or any(c in REPLACEMENTS or ord(c) < 32 for c in part)
                    or RESERVED.fullmatch(part.split('.')[0].rstrip(' '))):
                errors.add('Invalid component: ' + '/'.join(parts[:i + 1]))
            prefix = '/'.join(parts[:i + 1])
            folded = prefix.casefold()
            if folded in components and components[folded] != prefix:
                errors.add('Case collision: ' + components[folded] + ' / ' + prefix)
            components[folded] = prefix
    print(f'{root.name}: {count} files, {len(errors)} Windows path errors')
    for error in sorted(errors):
        print(error)
    return bool(errors)


if __name__ == '__main__':
    roots = [Path(p).resolve() for p in sys.argv[1:]] or [Path(__file__).resolve().parents[1]]
    sys.exit(int(any([check_repository(root) for root in roots])))
