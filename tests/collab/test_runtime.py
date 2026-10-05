"""Additive runtime plans must preserve pinned helpers and actual source isolation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "experiments/collaboration/runtime/entry.py"


class RuntimeTests(unittest.TestCase):
    def test_plan_refuses_missing_readonly_mount_destinations_before_execution(self):
        api = self.entry()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('rootfs', 'source', 'output'):
                (root/name).mkdir()
            reference = ROOT/'autonomy'
            lock = {'schema_version': 1, 'kind': 'collaboration-runtime-lock',
                'rootfs_sha256': hashlib.sha256(b'').hexdigest(),
                'dockerfile_sha256': hashlib.sha256((ENTRY.parent/'Dockerfile').read_bytes()).hexdigest(),
                'requirements_sha256': hashlib.sha256((ENTRY.parent/'requirements.lock').read_bytes()).hexdigest(),
                'helpers': {name: hashlib.sha256((reference/name).read_bytes()).hexdigest()
                    for name in ('pipeline/insula_entry.py', 'pipeline/runtime_identity.py')}}
            path = root/'runtime.lock.json'
            path.write_text(json.dumps(lock))
            with self.assertRaisesRegex(ValueError, 'mount destination'):
                api.make_plan(root/'rootfs', reference, root/'source', root/'output',
                              ['python', '/source/scripts/collab_live.py'], path)
            self.assertEqual(list((root/'output').iterdir()), [])

    def entry(self):
        self.assertTrue(ENTRY.is_file(), "planned additive runtime entry is not implemented")
        spec = importlib.util.spec_from_file_location("collab_runtime_entry", ENTRY)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_plan_rewrites_existing_source_context_and_keeps_one_native_output(self):
        api = self.entry()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("rootfs", "source", "output"):
                (root / name).mkdir()
            reference = ROOT / "autonomy"
            for name in ('experiment', 'source', 'outputs'):
                (root/'rootfs'/name).mkdir()
            identity_spec = importlib.util.spec_from_file_location('fixture_runtime_identity',
                reference/'pipeline/runtime_identity.py')
            identity = importlib.util.module_from_spec(identity_spec)
            identity_spec.loader.exec_module(identity)
            lock = {"schema_version": 1, "kind": "collaboration-runtime-lock",
                    "rootfs_sha256": identity.rootfs_identity(root/'rootfs'),
                    "dockerfile_sha256": hashlib.sha256((ENTRY.parent / "Dockerfile").read_bytes()).hexdigest(),
                    "requirements_sha256": hashlib.sha256((ENTRY.parent / "requirements.lock").read_bytes()).hexdigest(),
                    "helpers": {path: hashlib.sha256((reference / path).read_bytes()).hexdigest()
                                for path in ("pipeline/insula_entry.py", "pipeline/runtime_identity.py")}}
            lock_path = root / "runtime.lock.json"
            lock_path.write_text(json.dumps(lock))
            command = api.make_plan(root / "rootfs", reference, root / "source", root / "output",
                                    ["python", "/source/tests/collab/live_support.py"], lock_path)
            index = command.index("--chdir")
            self.assertEqual(command[index + 1], "/source")
            index = command.index("PYTHONPATH")
            self.assertEqual(command[index + 1], "/source:/experiment")
            self.assertEqual(command.count("--bind"), 1)
            self.assertIn("--unshare-all", command)
            self.assertIn("--die-with-parent", command)
            lock["rootfs_sha256"] = "0" * 64
            lock_path.write_text(json.dumps(lock))
            with self.assertRaises(ValueError):
                api.make_plan(root / "rootfs", reference, root / "source", root / "output",
                              ["python", "/source/tests/collab/live_support.py"], lock_path)


if __name__ == "__main__":
    unittest.main()
