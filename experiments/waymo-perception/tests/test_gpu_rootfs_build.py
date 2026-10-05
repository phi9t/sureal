import hashlib
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from pipeline.runtime_identity import rootfs_identity


PACKAGE = Path(__file__).resolve().parents[1]
BUILD = PACKAGE / "gpu" / "build_bazel_rootfs_v6.sh"
DOCKERFILE = PACKAGE / "gpu" / "Dockerfile.bazel-rootfs-v6"
BAZEL_VERSION = "9.2.0"
BAZEL_LINUX_X86_64_SHA256 = (
    "7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694"
)
PACKAGE_INVENTORY = "numpy==2.5.3\ntorch==2.9.1+cu130\n"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_executable(path, body):
    path.write_text(textwrap.dedent(body).lstrip())
    path.chmod(0o755)


def write_fake_tools(fakebin):
    write_executable(
        fakebin / "docker",
        """
        #!/usr/bin/env bash
        set -euo pipefail
        printf '%s\\n' "$*" >> "${FAKE_DOCKER_LOG:?}"
        case "$1" in
          build)
            exit 0
            ;;
          image)
            [[ "$2" == inspect ]] || exit 2
            if [[ "$3" == surflo-insula:cuda13.2.1-locked ]]; then
              printf 'sha256:eaf68603ced6f9abb5ee401522a07774183a8412ff3d9de61278f09c0738749d\\n'
            else
              printf 'sha256:%064d\\n' 8
            fi
            ;;
          create)
            printf 'fake-gpu-container\\n'
            ;;
          export)
            printf 'fake gpu export stream'
            ;;
          rm)
            exit 0
            ;;
          *)
            printf 'unexpected docker command: %s\\n' "$*" >&2
            exit 2
            ;;
        esac
        """,
    )
    write_executable(
        fakebin / "tar",
        """
        #!/usr/bin/env bash
        set -euo pipefail
        dest=
        while [[ $# -gt 0 ]]; do
          case "$1" in
            -C)
              dest="$2"
              shift 2
              ;;
            *)
              shift
              ;;
          esac
        done
        [[ -n "${dest}" ]] || { echo 'missing -C destination' >&2; exit 2; }
        mkdir -p "${dest}/opt/waymo/bin" "${dest}/usr/local/bin" "${dest}/usr/local/cuda/bin" \
          "${dest}/usr/local/lib/python3.12/dist-packages" \
          "${dest}/etc" "${dest}/experiment" "${dest}/source" "${dest}/outputs" "${dest}/driver"
        printf '#!/bin/sh\\n' > "${dest}/opt/waymo/bin/python"
        chmod 0755 "${dest}/opt/waymo/bin/python"
        printf '#!/bin/sh\\nexec /opt/waymo/bin/python "$@"\\n' > "${dest}/usr/local/bin/python"
        chmod 0755 "${dest}/usr/local/bin/python"
        printf '/opt/waymo/lib/python3.12/site-packages\\n' \
          > "${dest}/usr/local/lib/python3.12/dist-packages/waymo-rootfs-site-packages.pth"
        printf '#!/bin/sh\\n' > "${dest}/usr/local/bin/bazel"
        chmod 0755 "${dest}/usr/local/bin/bazel"
        printf 'schema_version=1\\n' > "${dest}/etc/surflo-insula-contract"
        printf 'bazel 9.2.0\\n' > "${dest}/opt/bazel-version.txt"
        printf '%b' "${FAKE_NEW_PACKAGES:-numpy==2.5.3\\ntorch==2.9.1+cu130\\n}" \
          > "${dest}/opt/package-list.txt"
        """,
    )
    write_executable(
        fakebin / "bwrap",
        """
        #!/usr/bin/env python3
        import pathlib
        import sys

        root = None
        command = []
        args = sys.argv[1:]
        index = 0
        while index < len(args):
            if args[index] in {"--ro-bind", "--bind"} and index + 2 < len(args):
                if args[index + 2] == "/":
                    root = pathlib.Path(args[index + 1])
                index += 3
            elif args[index] == "--":
                command = args[index + 1:]
                break
            else:
                index += 1
        if root is None:
            print("missing rootfs bind", file=sys.stderr)
            raise SystemExit(2)
        if command == ["bazel", "--version"]:
            print((root / "opt/bazel-version.txt").read_text().strip())
        elif command == ["uv", "pip", "freeze", "--python", "/opt/waymo/bin/python"]:
            print((root / "opt/package-list.txt").read_text(), end="")
        else:
            print(f"unexpected command: {command}", file=sys.stderr)
            raise SystemExit(2)
        """,
    )


def write_gpu_rootfs(root, packages=PACKAGE_INVENTORY):
    (root / "opt/waymo/bin").mkdir(parents=True)
    (root / "usr/local/bin").mkdir(parents=True)
    (root / "usr/local/lib/python3.12/dist-packages").mkdir(parents=True)
    (root / "opt/waymo/bin/python").write_text("#!/bin/sh\n")
    (root / "opt/waymo/bin/python").chmod(0o755)
    (root / "usr/local/bin/python").write_text('#!/bin/sh\nexec /opt/waymo/bin/python "$@"\n')
    (root / "usr/local/bin/python").chmod(0o755)
    (root / "usr/local/lib/python3.12/dist-packages/waymo-rootfs-site-packages.pth").write_text(
        "/opt/waymo/lib/python3.12/site-packages\n"
    )
    (root / "opt").mkdir(exist_ok=True)
    (root / "opt/package-list.txt").write_text(packages)
    (root / "etc").mkdir()
    (root / "etc/surflo-insula-contract").write_text("schema_version=1\n")


class GpuRootfsBuildTests(unittest.TestCase):
    def test_build_creates_versioned_bazel_rootfs_and_preserves_current_gpu_rootfs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fakebin = root / "fakebin"
            fakebin.mkdir()
            write_fake_tools(fakebin)
            tmpdir = root / "tmp"
            tmpdir.mkdir()

            home = root / "home"
            previous = home / ".cache/waystone/waymo-perception/gpu-rootfs"
            previous.mkdir(parents=True)
            write_gpu_rootfs(previous)
            previous_lock = previous.with_name(previous.name + ".lock.json")
            previous_lock.write_text(
                json.dumps({"rootfs_sha256": rootfs_identity(previous)}, indent=2) + "\n"
            )
            previous_identity = rootfs_identity(previous)
            previous_lock_bytes = previous_lock.read_bytes()

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
            env["FAKE_DOCKER_LOG"] = str(root / "docker.log")
            env["TMPDIR"] = str(tmpdir)
            env.pop("WAYMO_GPU_INSULA_ROOT", None)
            env.pop("WAYMO_GPU_INSULA_PREVIOUS_ROOT", None)

            result = subprocess.run(
                ["bash", str(BUILD)],
                cwd=PACKAGE / "gpu",
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            destination = home / ".cache/waystone/waymo-perception/gpu-rootfs-v6"
            self.assertIn(f"rootfs={destination}", result.stdout)
            self.assertTrue(destination.is_dir())
            pth = destination / "usr/local/lib/python3.12/dist-packages/waymo-rootfs-site-packages.pth"
            self.assertEqual(
                pth.read_text(),
                "/opt/waymo/lib/python3.12/site-packages\n",
            )
            self.assertEqual(previous_identity, rootfs_identity(previous))
            self.assertEqual(previous_lock_bytes, previous_lock.read_bytes())

            lock = json.loads(destination.with_name(destination.name + ".lock.json").read_text())
            self.assertEqual(lock["schema_version"], 1)
            self.assertEqual(lock["platform"], "linux/amd64")
            self.assertEqual(lock["rootfs_sha256"], rootfs_identity(destination))
            self.assertEqual(lock["requirements_sha256"], sha256(PACKAGE / "gpu/requirements.lock"))
            self.assertEqual(lock["dockerfile_sha256"], sha256(DOCKERFILE))
            self.assertEqual(lock["bazel_version"], BAZEL_VERSION)
            self.assertEqual(
                lock["bazel_linux_x86_64_sha256"], BAZEL_LINUX_X86_64_SHA256
            )

    def test_build_rejects_python_package_inventory_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fakebin = root / "fakebin"
            fakebin.mkdir()
            write_fake_tools(fakebin)
            tmpdir = root / "tmp"
            tmpdir.mkdir()

            previous = root / "gpu-rootfs"
            previous.mkdir()
            write_gpu_rootfs(previous)
            previous_lock = previous.with_name(previous.name + ".lock.json")
            previous_lock.write_text(
                json.dumps({"rootfs_sha256": rootfs_identity(previous)}) + "\n"
            )
            destination = root / "gpu-rootfs-v6"

            env = os.environ.copy()
            env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
            env["FAKE_DOCKER_LOG"] = str(root / "docker.log")
            env["FAKE_NEW_PACKAGES"] = "numpy==2.5.4\ntorch==2.9.1+cu130\n"
            env["TMPDIR"] = str(tmpdir)
            env["WAYMO_GPU_INSULA_PREVIOUS_ROOT"] = str(previous)
            env["WAYMO_GPU_INSULA_ROOT"] = str(destination)

            result = subprocess.run(
                ["bash", str(BUILD)],
                cwd=PACKAGE / "gpu",
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Python package inventory differs", result.stderr)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
