import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from evidence import pins


class PinTests(unittest.TestCase):
    def repository(self, directory):
        root = Path(directory)
        (root / 'research').mkdir()
        (root / 'area').mkdir()
        (root / 'area/cited.py').write_text('cited\n')
        (root / 'area/free.py').write_text('free\n')
        digest = hashlib.sha256(b'cited\n').hexdigest()
        (root / 'research/receipt.json').write_text('{"source_sha256":{"area/cited.py":"%s"},"long":"%s"}'
                                                    % (digest, digest + 'ab'))
        for command in (['init', '-q'], ['add', '-A'],
                        ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'fixture']):
            subprocess.run(['git', *command], cwd=root, check=True)
        return root

    def test_status_separates_cited_from_free_and_ignores_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.repository(directory)
            self.assertEqual(pins.status(root), {'area/cited.py': ['research/receipt.json'], 'area/free.py': []})

    def test_longer_hex_runs_are_not_digests(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(len(pins.citations(self.repository(directory))), 1)

    def test_check_reports_modified_and_removed_cited_files_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.repository(directory)
            self.assertEqual(pins.changed(root), {})
            (root / 'area/free.py').write_text('edited\n')
            (root / 'area/new.py').write_text('new\n')
            self.assertEqual(pins.changed(root), {})
            (root / 'area/cited.py').write_text('edited\n')
            self.assertEqual(pins.changed(root), {'area/cited.py': ['research/receipt.json']})

    def test_check_reports_deleted_cited_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.repository(directory)
            (root / 'area/cited.py').unlink()
            self.assertEqual(pins.changed(root), {'area/cited.py': ['research/receipt.json']})

    def test_check_reports_pure_move_of_cited_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.repository(directory)
            subprocess.run(['git', 'mv', 'area/cited.py', 'area/moved.py'], cwd=root, check=True)
            self.assertEqual(pins.changed(root), {'area/cited.py -> area/moved.py': ['research/receipt.json']})

    def test_check_reports_move_plus_edit_of_cited_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.repository(directory)
            subprocess.run(['git', 'mv', 'area/cited.py', 'area/moved.py'], cwd=root, check=True)
            (root / 'area/moved.py').write_text('cited\n# edited\n')
            self.assertEqual(pins.changed(root), {'area/cited.py -> area/moved.py': ['research/receipt.json']})

    def test_check_ignores_move_of_uncited_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.repository(directory)
            subprocess.run(['git', 'mv', 'area/free.py', 'area/moved_free.py'], cwd=root, check=True)
            self.assertEqual(pins.changed(root), {})

    def test_check_reports_pinned_file_when_package_directory_moved(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            old = repo / 'oldpkg'
            package = old
            (package / 'research').mkdir(parents=True)
            (package / 'area').mkdir()
            (package / 'area/cited.py').write_text('cited\n')
            digest = hashlib.sha256(b'cited\n').hexdigest()
            (package / 'research/receipt.json').write_text(
                '{"source_sha256":{"area/cited.py":"%s"}}' % digest
            )
            for command in (['init', '-q'], ['add', '-A'],
                            ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'fixture']):
                subprocess.run(['git', *command], cwd=repo, check=True)
            subprocess.run(['git', 'mv', 'oldpkg', 'newpkg'], cwd=repo, check=True)

            self.assertEqual(
                pins.changed(repo / 'newpkg'),
                {'oldpkg/area/cited.py -> newpkg/area/cited.py': ['research/receipt.json']},
            )


if __name__ == '__main__':
    unittest.main()
