import tempfile
import unittest
import os
from pathlib import Path

from tools import layers

LAYERS = (('low',), ('mid', 'peer'), ('high', layers.ROOT))


class LayerTests(unittest.TestCase):
    def problems(self, files, known=frozenset()):
        with tempfile.TemporaryDirectory() as directory:
            for name, text in files.items():
                path = Path(directory) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            return layers.check(directory, LAYERS, known, sorted(files))

    def test_downward_qualified_bare_and_internal_imports_pass(self):
        self.assertEqual(self.problems({
            'low/base.py': 'import json\n', 'low/other.py': 'from base import x\nimport low.base\n',
            'mid/use.py': 'from low.base import x\nimport base\n', 'top.py': 'from mid import use\n',
        }), [])

    def test_upward_and_peer_imports_are_reported_with_location(self):
        found = self.problems({'low/base.py': '\nfrom mid.use import x\n', 'mid/use.py': 'import widget\n',
                               'peer/widget.py': ''})
        self.assertEqual(found, ["low/base.py:2: imports 'mid.use' from higher area 'mid'",
                                 "mid/use.py:1: imports 'widget' from peer area 'peer'"])

    def test_bare_name_defined_by_several_other_areas_is_ambiguous(self):
        found = self.problems({'low/models.py': '', 'mid/models.py': '', 'high/run.py': 'import models\n'})
        self.assertEqual(len(found), 1)
        self.assertIn("provided by ['low', 'mid']", found[0])

    def test_known_exception_is_scoped_and_must_stay_in_use(self):
        files = {'low/base.py': 'import use\n', 'mid/use.py': ''}
        self.assertEqual(self.problems(files, frozenset({('low/base.py', 'mid')})), [])
        self.assertIn('remove it from KNOWN_UPWARD',
                      self.problems({**files, 'low/base.py': ''}, frozenset({('low/base.py', 'mid')}))[0])

    def test_undeclared_area_is_reported(self):
        self.assertEqual(self.problems({'new/thing.py': ''}), ["new/thing.py: area 'new' has no declared layer"])

    def test_sources_fall_back_to_package_files_when_git_metadata_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as fake_bin:
            package = Path(directory)
            (package / 'low').mkdir()
            (package / 'low/base.py').write_text('')
            (package / 'top.py').write_text('')
            (package / 'research').mkdir()
            (package / 'research/frozen.py').write_text('')
            (package / 'low/__pycache__').mkdir()
            (package / 'low/__pycache__/ignored.py').write_text('')

            fake_git = Path(fake_bin) / 'git'
            fake_git.write_text('#!/bin/sh\nexit 128\n')
            fake_git.chmod(0o755)

            old_path = os.environ.get('PATH', '')
            try:
                os.environ['PATH'] = fake_bin
                self.assertEqual(layers.sources(package), ['low/base.py', 'top.py'])
            finally:
                os.environ['PATH'] = old_path

    def test_current_tree_follows_the_declared_layers(self):
        self.assertEqual(layers.check(), [])


if __name__ == '__main__':
    unittest.main()
