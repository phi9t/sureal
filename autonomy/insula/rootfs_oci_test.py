"""Rootfs OCI artifacts preserve checked Insula runtime locks."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import file_sha256
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION, load_runtime_lock
from insula.rootfs_oci import (
    ArchiveTools,
    CommandError,
    RootfsOciError,
    RootfsSpec,
    oras_annotation_document,
    pack_rootfs_bundle,
    pull_rootfs_artifact,
    push_rootfs_artifact,
    run_command,
    write_local_layout_artifact,
)
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import default_lock


AUTONOMY = Path(__file__).resolve().parents[1]


def _write_rootfs(rootfs: Path, payload: bytes = b"original\n") -> None:
    (rootfs / "bin").mkdir(parents=True)
    python = rootfs / "bin" / "python"
    python.write_bytes(b"#!/bin/sh\n")
    python.chmod(0o755)
    (rootfs / "etc").mkdir()
    (rootfs / "etc" / "issue").write_bytes(payload)
    (rootfs / "usr" / "lib").mkdir(parents=True)
    (rootfs / "usr" / "lib" / "libfixture.so").write_bytes(b"lib\n")
    (rootfs / "python").symlink_to("bin/python")


def _write_lock(rootfs: Path) -> Path:
    lock = rootfs.with_name(rootfs.name + ".lock.json")
    data = {
        "schema_version": 1,
        "rootfs_sha256": rootfs_identity(rootfs),
        "dockerfile_sha256": file_sha256(AUTONOMY / "insula" / "Dockerfile"),
        "requirements_sha256": file_sha256(AUTONOMY / "requirements-tracer.lock"),
        "test_tools_requirements_sha256": file_sha256(
            AUTONOMY / "insula" / "cpu-test-tools-requirements.lock"
        ),
        "bazel_version": BAZEL_VERSION,
        "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
    }
    lock.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return lock


def _write_fake_zstd(path: Path) -> Path:
    path.write_text(
        """#!/bin/sh
set -eu
input=
output=
next_is_output=0
for arg in "$@"; do
  if [ "$next_is_output" = 1 ]; then
    output="$arg"
    next_is_output=0
    continue
  fi
  case "$arg" in
    -o) next_is_output=1 ;;
    -*) ;;
    *) input="$arg" ;;
  esac
done
if [ -n "$output" ]; then
  if [ -n "$input" ]; then
    cat "$input" > "$output"
  else
    cat > "$output"
  fi
elif [ -n "$input" ]; then
  cat "$input"
else
  cat
fi
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


class RootfsOciTests(unittest.TestCase):
    def fixture(self, root: Path, payload: bytes = b"original\n") -> tuple[RootfsSpec, ArchiveTools]:
        rootfs = root / "fixture-rootfs"
        _write_rootfs(rootfs, payload)
        lock = _write_lock(rootfs)
        tools = ArchiveTools(zstd_bin=_write_fake_zstd(root / "fake-zstd"))
        return RootfsSpec(role="cpu", rootfs=rootfs, lock=lock), tools

    def test_packing_same_tree_produces_same_archive_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec, tools = self.fixture(root)

            first = pack_rootfs_bundle(spec, root / "work-one", max_part_bytes=1024, tools=tools)
            second = pack_rootfs_bundle(spec, root / "work-two", max_part_bytes=1024, tools=tools)

            manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
            annotations = first.oci_annotations()
            self.assertEqual(first.archive_sha256, second.archive_sha256)
            self.assertEqual(annotations["io.sureal.file.count"], str(len(first.parts) + 2))
            self.assertEqual(annotations["io.sureal.file.0000.path"], "lock/fixture-rootfs.lock.json")
            self.assertEqual(annotations["io.sureal.file.0001.path"], "manifest/rootfs-manifest.json")
            self.assertEqual(annotations["io.sureal.file.0002.path"], "rootfs/fixture-rootfs.tar.zst.part0000")
            self.assertEqual(annotations["io.sureal.rootfs.entry.count"], "3")
            self.assertFalse(any(key.startswith("io.sureal.rootfs.entry.0") for key in annotations))
            self.assertEqual(manifest["rootfs_sha256"], rootfs_identity(spec.rootfs))
            self.assertEqual(
                manifest["rootfs_files"],
                [
                    {
                        "path": "bin/python",
                        "sha256": file_sha256(spec.rootfs / "bin" / "python"),
                        "size": 10,
                    },
                    {
                        "path": "etc/issue",
                        "sha256": file_sha256(spec.rootfs / "etc" / "issue"),
                        "size": 9,
                    },
                    {
                        "path": "usr/lib/libfixture.so",
                        "sha256": file_sha256(spec.rootfs / "usr" / "lib" / "libfixture.so"),
                        "size": 4,
                    },
                ],
            )

    def test_dry_run_round_trip_preserves_rootfs_sha256(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec, tools = self.fixture(root)
            registry = root / "registry"
            pushed = push_rootfs_artifact(
                spec,
                dry_run=True,
                registry=registry,
                work_dir=root / "push",
                max_part_bytes=128,
                tools=tools,
            )

            target = root / "restore-cache" / spec.rootfs.name
            restored = pull_rootfs_artifact(
                role=spec.role,
                dry_run=True,
                registry=registry,
                digest=pushed.digest,
                target_rootfs=target,
                work_dir=root / "pull",
                tools=tools,
            )

            runtime = load_runtime_lock(target, default_lock(target))
            self.assertEqual(restored.rootfs_sha256, rootfs_identity(spec.rootfs))
            self.assertEqual(runtime.data["rootfs_sha256"], rootfs_identity(spec.rootfs))

    def test_tampered_part_fails_before_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec, tools = self.fixture(root)
            registry = root / "registry"
            pushed = push_rootfs_artifact(
                spec,
                dry_run=True,
                registry=registry,
                work_dir=root / "push",
                max_part_bytes=128,
                tools=tools,
            )
            part = pushed.parts[0]
            blob = registry / pushed.package / "blobs" / "sha256" / part["sha256"]
            blob.write_bytes(b"x" * int(part["size"]))

            with self.assertRaisesRegex(RootfsOciError, "sha256 mismatch"):
                pull_rootfs_artifact(
                    role=spec.role,
                    dry_run=True,
                    registry=registry,
                    digest=pushed.digest,
                    target_rootfs=root / "restore-cache" / spec.rootfs.name,
                    work_dir=root / "pull",
                    tools=tools,
                )

    def test_existing_target_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec, tools = self.fixture(root)
            registry = root / "registry"
            pushed = push_rootfs_artifact(
                spec,
                dry_run=True,
                registry=registry,
                work_dir=root / "push",
                max_part_bytes=128,
                tools=tools,
            )
            target = root / "restore-cache" / spec.rootfs.name
            target.mkdir(parents=True)

            with self.assertRaisesRegex(RootfsOciError, "target rootfs exists"):
                pull_rootfs_artifact(
                    role=spec.role,
                    dry_run=True,
                    registry=registry,
                    digest=pushed.digest,
                    target_rootfs=target,
                    work_dir=root / "pull",
                    tools=tools,
                )

    def test_lock_mismatch_leaves_staged_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec, tools = self.fixture(root)
            bundle = pack_rootfs_bundle(spec, root / "bundle", max_part_bytes=128, tools=tools)
            bad_lock = json.loads(bundle.lock_artifact_path.read_text(encoding="utf-8"))
            bad_lock["rootfs_sha256"] = "0" * 64
            bundle.lock_artifact_path.write_text(json.dumps(bad_lock, indent=2) + "\n", encoding="utf-8")
            manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
            lock_sha256 = file_sha256(bundle.lock_artifact_path)
            manifest["lock_sha256"] = lock_sha256
            manifest["lock"]["sha256"] = lock_sha256
            manifest["lock"]["size"] = bundle.lock_artifact_path.stat().st_size
            bundle.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            digest = write_local_layout_artifact(
                registry=root / "registry",
                package="sureal-rootfs-cpu",
                tag="bad-lock",
                artifact_dir=bundle.artifact_dir,
                annotations=bundle.oci_annotations(),
            )
            target = root / "restore-cache" / spec.rootfs.name

            with self.assertRaisesRegex(RootfsOciError, "rootfs_sha256"):
                pull_rootfs_artifact(
                    role=spec.role,
                    dry_run=True,
                    registry=root / "registry",
                    digest=digest,
                    target_rootfs=target,
                    work_dir=root / "pull",
                    tools=tools,
                )

            staged = sorted(path / target.name for path in target.parent.glob("." + target.name + ".restore.*"))
            self.assertEqual(len(staged), 1)
            self.assertTrue(staged[0].is_dir())
            self.assertTrue(default_lock(staged[0]).is_file())

    def test_existing_tag_with_different_content_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec, tools = self.fixture(root)
            registry = root / "registry"
            push_rootfs_artifact(
                spec,
                dry_run=True,
                registry=registry,
                work_dir=root / "push-one",
                tag="stable",
                max_part_bytes=128,
                tools=tools,
            )
            changed, _ = self.fixture(root / "changed", payload=b"changed\n")

            with self.assertRaisesRegex(RootfsOciError, "already exists with different content"):
                push_rootfs_artifact(
                    changed,
                    dry_run=True,
                    registry=registry,
                    work_dir=root / "push-two",
                    tag="stable",
                    max_part_bytes=128,
                    tools=tools,
                )

    def test_command_output_redacts_tokens(self):
        secret = "ghp_secret_token_value"
        with self.assertRaises(CommandError) as raised:
            run_command(
                [
                    sys.executable,
                    "-c",
                    "import os, sys; print(os.environ['TOKEN']); "
                    "sys.stderr.write(os.environ['TOKEN'] + '\\n'); sys.exit(7)",
                ],
                env_extra={"TOKEN": secret},
                secrets=[secret],
            )
        self.assertNotIn(secret, str(raised.exception))
        self.assertIn("<redacted>", str(raised.exception))


class OrasAnnotationDocumentTests(unittest.TestCase):
    def test_manifest_annotations_use_the_oras_manifest_key(self):
        document = oras_annotation_document({"io.sureal.artifact.kind": "rootfs"})
        self.assertEqual(document, {"$manifest": {"io.sureal.artifact.kind": "rootfs"}})


if __name__ == "__main__":
    unittest.main()
