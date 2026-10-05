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
BUILD = PACKAGE / "build.sh"
BAZEL_VERSION = "9.2.0"
BAZEL_LINUX_X86_64_SHA256 = (
    "7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694"
)
PACKAGE_INVENTORY = "numpy==2.3.2\npip==25.2\n"
TEST_TOOL_PACKAGE_INVENTORY = (
    "iniconfig==2.3.0\n"
    "packaging==26.3\n"
    "pluggy==1.6.0\n"
    "pygments==2.21.0\n"
    "pytest==9.1.1\n"
)


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
            printf 'sha256:%064d\\n' 7
            ;;
          create)
            printf 'fake-container\\n'
            ;;
          export)
            printf 'fake export stream'
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
        mkdir -p "${dest}/usr/bin" "${dest}/usr/local/bin" "${dest}/opt" \
          "${dest}/etc" "${dest}/experiment" "${dest}/source" "${dest}/outputs" \
          "${dest}/bazel-cache"
        printf '#!/bin/sh\\n' > "${dest}/usr/bin/python"
        chmod 0755 "${dest}/usr/bin/python"
        for tool in git curl g++ ar; do
          printf '#!/bin/sh\\n' > "${dest}/usr/bin/${tool}"
          chmod 0755 "${dest}/usr/bin/${tool}"
        done
        printf '#!/bin/sh\\n' > "${dest}/usr/local/bin/bazel"
        chmod 0755 "${dest}/usr/local/bin/bazel"
        printf 'schema_version=1\\n' > "${dest}/etc/surflo-insula-contract"
        printf 'bazel 9.2.0\\n' > "${dest}/opt/bazel-version.txt"
        printf '%b' "${FAKE_NEW_PACKAGES:-numpy==2.3.2\\npip==25.2\\n}" \
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
        elif command == ["python", "-m", "pip", "freeze", "--all"]:
            print((root / "opt/package-list.txt").read_text(), end="")
        elif command == ["sh", "-lc", "command -v git >/dev/null && command -v curl >/dev/null && command -v g++ >/dev/null && command -v ar >/dev/null && python -m pytest --version >/dev/null"]:
            missing = [
                name
                for name in ("git", "curl", "g++", "ar")
                if not (root / "usr/bin" / name).is_file()
            ]
            if "pytest==" not in (root / "opt/package-list.txt").read_text():
                missing.append("pytest")
            if missing:
                print("missing " + ", ".join(missing), file=sys.stderr)
                raise SystemExit(1)
        else:
            print(f"unexpected command: {command}", file=sys.stderr)
            raise SystemExit(2)
        """,
    )


def write_rootfs(root, packages=PACKAGE_INVENTORY):
    (root / "usr/bin").mkdir(parents=True)
    (root / "usr/bin/python").write_text("#!/bin/sh\n")
    (root / "usr/bin/python").chmod(0o755)
    (root / "opt").mkdir()
    (root / "opt/package-list.txt").write_text(packages)
    (root / "etc").mkdir()
    (root / "etc/surflo-insula-contract").write_text("schema_version=1\n")


class CpuRootfsBuildTests(unittest.TestCase):
    def test_build_creates_next_version_lock_and_preserves_previous_rootfs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fakebin = root / "fakebin"
            fakebin.mkdir()
            write_fake_tools(fakebin)

            home = root / "home"
            previous = home / ".cache/waystone/waymo-perception/insula/rootfs-v3"
            previous.mkdir(parents=True)
            write_rootfs(previous)
            previous_lock = previous.with_name(previous.name + ".lock.json")
            previous_lock.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "rootfs_sha256": rootfs_identity(previous),
                    },
                    indent=2,
                )
                + "\n"
            )
            previous_identity = rootfs_identity(previous)
            previous_lock_bytes = previous_lock.read_bytes()

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
            env["FAKE_DOCKER_LOG"] = str(root / "docker.log")
            env["FAKE_NEW_PACKAGES"] = PACKAGE_INVENTORY + TEST_TOOL_PACKAGE_INVENTORY
            env.pop("WAYMO_INSULA_ROOT", None)
            env.pop("WAYMO_INSULA_PREVIOUS_ROOT", None)

            result = subprocess.run(
                [str(BUILD)],
                cwd=PACKAGE,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            destination = home / ".cache/waystone/waymo-perception/insula/rootfs-v4"
            self.assertIn(f"rootfs={destination}", result.stdout)
            self.assertTrue(destination.is_dir())
            for name in ("git", "curl", "g++", "ar"):
                self.assertTrue((destination / "usr/bin" / name).is_file(), name)
            self.assertTrue((destination / "bazel-cache").is_dir())
            self.assertEqual(previous_identity, rootfs_identity(previous))
            self.assertEqual(previous_lock_bytes, previous_lock.read_bytes())

            lock = json.loads(destination.with_name(destination.name + ".lock.json").read_text())
            self.assertEqual(lock["schema_version"], 1)
            self.assertEqual(lock["platform"], "linux/amd64")
            self.assertEqual(lock["rootfs_sha256"], rootfs_identity(destination))
            self.assertEqual(lock["requirements_sha256"], sha256(PACKAGE / "requirements-tracer.lock"))
            self.assertEqual(
                lock["test_tools_requirements_sha256"],
                sha256(PACKAGE / "requirements-test-tools.lock"),
            )
            self.assertEqual(lock["dockerfile_sha256"], sha256(PACKAGE / "insula/Dockerfile"))
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

            previous = root / "rootfs-v3"
            previous.mkdir()
            write_rootfs(previous, packages="numpy==2.3.2\npip==25.2\n")
            previous_lock = previous.with_name(previous.name + ".lock.json")
            previous_lock.write_text(
                json.dumps({"rootfs_sha256": rootfs_identity(previous)}) + "\n"
            )
            destination = root / "rootfs-v4"

            env = os.environ.copy()
            env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
            env["FAKE_DOCKER_LOG"] = str(root / "docker.log")
            env["FAKE_NEW_PACKAGES"] = "numpy==2.3.3\npip==25.2\n" + TEST_TOOL_PACKAGE_INVENTORY
            env["WAYMO_INSULA_PREVIOUS_ROOT"] = str(previous)
            env["WAYMO_INSULA_ROOT"] = str(destination)

            result = subprocess.run(
                [str(BUILD)],
                cwd=PACKAGE,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Python package inventory differs", result.stderr)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
