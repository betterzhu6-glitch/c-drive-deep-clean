import contextlib
import importlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from scan_disk import inventory, checked_path


class ScannerTests(unittest.TestCase):
    def test_sizes_and_largest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'sub').mkdir()
            (root / 'a').write_bytes(b'123')
            (root / 'sub/b').write_bytes(b'12345')
            report = inventory(root, top=1)
            self.assertEqual((report['files'], report['logical_bytes'], report['errors']), (2, 8, 0))
            self.assertEqual(report['largest'][0]['bytes'], 5)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction test')
    def test_nested_junction_and_root_are_not_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, outside = root / 'source', root / 'outside'
            source.mkdir()
            outside.mkdir()
            (source / 'a').write_bytes(b'abc')
            (outside / 'private').write_bytes(b'x' * 500)
            link = source / 'junction'
            run = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(outside)], capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            try:
                report = inventory(source)
                self.assertEqual((report['files'], report['logical_bytes'], report['skipped_links']), (1, 3, 1))
                with self.assertRaises(ValueError):
                    checked_path(link)
                with self.assertRaises(ValueError):
                    checked_path(link / 'private')
            finally:
                os.rmdir(link)  # Remove only this verified test junction, not its target.
            self.assertTrue((outside / 'private').exists())

    def test_missing_is_error(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                inventory(Path(temp) / 'missing')

    def test_access_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('scan_disk.os.scandir', side_effect=PermissionError('denied')):
                report = inventory(temp)
            self.assertEqual(report['errors'], 1)
            self.assertIn('denied', report['error_samples'][0]['error'])

    def test_imports_have_no_actions(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            importlib.import_module('admin_diag')
            importlib.import_module('recycle_purge')
        self.assertEqual(output.getvalue(), '')

    def test_recycle_default_is_preview(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/recycle_purge.py'
        run = subprocess.run([sys.executable, str(script), '--drive', 'C'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0)
        self.assertIn('No files were deleted', run.stdout)
        refused = subprocess.run([sys.executable, str(script), '--apply', '--confirm-drive', 'D'], capture_output=True)
        self.assertNotEqual(refused.returncode, 0)


if __name__ == '__main__':
    unittest.main()
