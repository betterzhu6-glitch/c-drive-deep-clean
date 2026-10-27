"""Explicit opt-in wrapper for Windows' current-user, single-drive Recycle Bin API."""
import argparse
import json
import locale
import os
import subprocess
from pathlib import Path
from scan_disk import disk_space


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--drive', choices=list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'), default='C')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-drive', help='Repeat drive letter after reviewing irreversible deletion')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.apply:
        print(f'Preview only: would empty the current user Recycle Bin on {args.drive}:. '
              'This is irreversible. No files were deleted.')
        return
    if args.confirm_drive != args.drive or args.output is None:
        parser.error('--apply requires matching --confirm-drive and --output')
    if os.name != 'nt':
        parser.error('Windows only')
    # Verify report can be created before the irreversible action.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as report:
        before = disk_space(Path(args.drive + ':\\'))
        command = [str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
                   '-NoProfile', '-NonInteractive', '-Command',
                   f"$ErrorActionPreference='Stop'; Clear-RecycleBin -DriveLetter {args.drive} -Force -ErrorAction Stop"]
        try:
            run = subprocess.run(command, capture_output=True, timeout=120)
            result = dict(returncode=run.returncode,
                          stdout=run.stdout.decode(locale.getpreferredencoding(False), errors='replace'),
                          stderr=run.stderr.decode(locale.getpreferredencoding(False), errors='replace'))
        except (OSError, subprocess.TimeoutExpired) as exc:
            result = dict(error=str(exc), note='Action may have partially completed; inspect the Recycle Bin.')
        result.update(drive=args.drive, before=before, after=disk_space(Path(args.drive + ':\\')))
        json.dump(result, report, ensure_ascii=False, indent=2)
    print(args.output)
    if result.get('returncode') != 0:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
