"""Read-only logical-size inventory. Never follow reparse points or hide errors."""
import argparse
import heapq
import json
import os
import re
import shutil
import stat
from pathlib import Path

REPARSE = 0x400
PROTECTED = {'$recycle.bin', 'system volume information', 'config.msi',
             'recovery', 'documents and settings'}


def is_link(st):
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, 'st_file_attributes', 0) & REPARSE)


def checked_path(path):
    """Check every component without resolving links."""
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents), path]:
        if is_link(os.lstat(part)):
            raise ValueError(f'Reparse point / symlink in path: {part}')
    return path


def inventory(path, top=20):
    root = checked_path(path)
    result = dict(root=str(root), files=0, logical_bytes=0, skipped_links=0,
                  errors=0, error_samples=[], largest=[])
    biggest = []
    stack = [str(root)]
    while stack:
        current = stack.pop()
        try:
            st = os.lstat(current)
            if is_link(st):
                result['skipped_links'] += 1
                continue
            if stat.S_ISREG(st.st_mode):
                result['files'] += 1
                result['logical_bytes'] += st.st_size
                if top:
                    heapq.heappush(biggest, (st.st_size, current))
                    if len(biggest) > top:
                        heapq.heappop(biggest)
            elif stat.S_ISDIR(st.st_mode):
                with os.scandir(current) as entries:
                    for entry in entries:
                        stack.append(entry.path)
        except OSError as exc:
            result['errors'] += 1
            if len(result['error_samples']) < 20:
                result['error_samples'].append(dict(path=current, error=str(exc)))
    result['largest'] = [dict(bytes=n, path=p) for n, p in sorted(biggest, reverse=True)]
    return result


def scan(path):
    """Compatibility helper. Use inventory() to inspect completeness."""
    report = inventory(path, top=0)
    return report['files'], report['logical_bytes']


def normalize(target):
    if re.fullmatch(r'[A-Za-z]:?[\\/]?', target):
        return target[0].upper() + ':\\'
    return target


def disk_space(root):
    try:
        return shutil.disk_usage(root.anchor)._asdict()
    except OSError as exc:
        return {'error': str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', nargs='?', default='C:')
    parser.add_argument('--json', type=Path)
    parser.add_argument('--top', type=int, default=20)
    args = parser.parse_args()
    if args.top < 0:
        parser.error('--top must be nonnegative')
    root = checked_path(normalize(args.target))
    before = disk_space(root)
    rows, skipped, errors = [], [], []
    with os.scandir(root) as entries:
        children = sorted(entries, key=lambda e: e.name.casefold())
    for entry in children:
        try:
            if is_link(entry.stat(follow_symlinks=False)):
                skipped.append(dict(path=entry.path, reason='reparse point'))
                continue
            if root == Path(root.anchor) and entry.name.casefold() in PROTECTED:
                skipped.append(dict(path=entry.path, reason='protected; not measured'))
                continue
            row = inventory(entry.path, args.top)
            rows.append(row)
            print(f"{entry.name}: {row['logical_bytes'] / 2**30:.3f} GiB, "
                  f"{row['files']} files, {row['errors']} errors, "
                  f"{row['skipped_links']} links skipped", flush=True)
        except (OSError, ValueError) as exc:
            errors.append(dict(path=entry.path, error=str(exc)))
    report = dict(root=str(root), disk_before=before,
                  disk_after=disk_space(root),
                  logical_bytes=sum(r['logical_bytes'] for r in rows),
                  errors=len(errors) + sum(r['errors'] for r in rows),
                  root_errors=errors, skipped=skipped,
                  rows=sorted(rows, key=lambda r: r['logical_bytes'], reverse=True),
                  note='Logical file lengths are not allocated disk usage. Hard links, '
                       'compression, sparse files, permissions and excluded paths affect totals; '
                       'used minus logical bytes does not identify hidden storage.')
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Visible logical total: {report['logical_bytes'] / 2**30:.3f} GiB; "
          f"errors: {report['errors']}; excluded roots: {len(skipped)}")
    print(report['note'])


if __name__ == '__main__':
    main()
