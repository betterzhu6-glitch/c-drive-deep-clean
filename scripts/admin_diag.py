"""Read-only storage diagnostics; reports denied access, never requests elevation."""
import argparse
import json
import locale
import os
import re
import subprocess
from pathlib import Path
from scan_disk import disk_space, inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--drive', default=os.environ.get('TARGET_DRIVE', 'C'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch('[A-Za-z]', args.drive):
        parser.error('--drive must be one letter')
    root = Path(args.drive.upper() + ':\\')
    commands = []
    for command in (['vssadmin.exe', 'list', 'shadowstorage', '/for=' + str(root)[:2]],
                    ['fsutil.exe', 'fsinfo', 'ntfsinfo', str(root)[:2]]):
        try:
            run = subprocess.run(command, capture_output=True, timeout=30)
            commands.append(dict(command=command, returncode=run.returncode,
                                 stdout=run.stdout.decode(locale.getpreferredencoding(False), errors='replace'),
                                 stderr=run.stderr.decode(locale.getpreferredencoding(False), errors='replace')))
        except (OSError, subprocess.TimeoutExpired) as exc:
            commands.append(dict(command=command, error=str(exc)))
    directories = []
    for name in ('$Recycle.Bin', 'System Volume Information', 'Recovery', 'Config.Msi'):
        try:
            directories.append(inventory(root / name, top=0))
        except (OSError, ValueError) as exc:
            directories.append(dict(root=str(root / name), error=str(exc)))
    result = dict(disk=disk_space(root), commands=commands, directories=directories,
                  note='Access denied is unknown, not zero. NTFS metadata does not measure reserved storage. '
                       'This script never removes restore points, changes reserved storage or takes ownership.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
