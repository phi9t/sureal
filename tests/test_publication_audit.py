from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import publication_audit


TARGET_URL = "https://github.com/phi9t/sureal"
UPSTREAM_URL = "https://github.com/Anttwo/Surflo"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PUBLIC_FILES = {
    ".github/workflows/publication.yml",
    ".gitignore",
    ".gitmodules",
    "CONTRIBUTING.md",
    "LICENSE.md",
    "README.md",
    "RELEASING.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "UPSTREAM.md",
    "pyproject.toml",
}


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class PublicationFixture:
    def __init__(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix="sureal publication fixture "
        )
        self.root = Path(self._temporary_directory.name)
        run("git", "init", "-q", cwd=self.root)
        run("git", "config", "user.email", "test@example.invalid", cwd=self.root)
        run("git", "config", "user.name", "Publication Test", cwd=self.root)
        self._write_valid_files()
        self.add_and_commit()

    def cleanup(self) -> None:
        self._temporary_directory.cleanup()

    def write(self, relative_path: str, content: str | bytes) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def remove(self, relative_path: str) -> None:
        (self.root / relative_path).unlink()
        run("git", "add", "-u", "--", relative_path, cwd=self.root)

    def add_and_commit(self) -> None:
        run("git", "add", "-A", cwd=self.root)
        result = run("git", "diff", "--cached", "--quiet", cwd=self.root, check=False)
        if result.returncode:
            run("git", "commit", "-qm", "fixture", cwd=self.root)

    def add_gitlink(self, path: str, *, declare: bool = True) -> None:
        object_id = run("git", "rev-parse", "HEAD", cwd=self.root).stdout.strip()
        run(
            "git",
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{object_id},{path}",
            cwd=self.root,
        )
        if declare:
            modules = (self.root / ".gitmodules").read_text(encoding="utf-8")
            modules += (
                f'\n[submodule "{path}"]\n'
                f"\tpath = {path}\n"
                f"\turl = https://example.invalid/{path}.git\n"
            )
            self.write(".gitmodules", modules)
            run("git", "add", ".gitmodules", cwd=self.root)

    def _write_valid_files(self) -> None:
        contents = {
            ".github/workflows/publication.yml": "name: publication\n",
            ".gitignore": "build/\ndist/\n*.egg-info/\n__pycache__/\n*.pyc\n",
            ".gitmodules": "",
            "CONTRIBUTING.md": "# Contributing\n",
            "LICENSE.md": "non-commercial research and evaluation\n",
            "README.md": (
                "# Sureal\n\n"
                f"Sureal is a fork of [Surflo]({UPSTREAM_URL}). The installed "
                "package and Python imports remain surflo.\n\n"
                "Use is limited to non-commercial research and evaluation.\n\n"
                f"Repository: {TARGET_URL}\n"
            ),
            "RELEASING.md": "# Releasing\n",
            "SECURITY.md": "# Security\n",
            "THIRD_PARTY_NOTICES.md": "# Third-party notices\n",
            "UPSTREAM.md": f"# Upstream\n\n{UPSTREAM_URL}\n",
            "pyproject.toml": (
                "[project]\n"
                'name = "surflo"\n'
                'version = "0.1.0"\n'
                'description = "Sureal research code"\n'
                'requires-python = ">=3.10"\n\n'
                "[project.urls]\n"
                f'Homepage = "{TARGET_URL}"\n'
                f'Repository = "{TARGET_URL}"\n'
                f'Upstream = "{UPSTREAM_URL}"\n'
            ),
        }
        self.assert_complete_fixture(contents)
        for path, content in contents.items():
            self.write(path, content)

    @staticmethod
    def assert_complete_fixture(contents: dict[str, str]) -> None:
        missing = REQUIRED_PUBLIC_FILES - contents.keys()
        if missing:
            raise AssertionError(f"fixture is missing required files: {sorted(missing)}")


class StaticAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = PublicationFixture()

    def tearDown(self) -> None:
        self.fixture.cleanup()

    def test_valid_public_fixture_has_no_static_errors(self) -> None:
        self.assertEqual(publication_audit.static_errors(self.fixture.root), [])

    def test_missing_required_file_and_identity_copy_are_reported(self) -> None:
        self.fixture.remove("SECURITY.md")
        self.fixture.write("README.md", "# A repository without lineage\n")
        self.fixture.add_and_commit()

        errors = publication_audit.static_errors(self.fixture.root)

        self.assertTrue(any("SECURITY.md" in error for error in errors), errors)
        for text in ("Sureal", "fork of Surflo", "surflo", TARGET_URL, UPSTREAM_URL):
            self.assertTrue(any(text in error for error in errors), (text, errors))

    def test_gitlinks_must_match_gitmodules_without_initialized_submodule(self) -> None:
        self.fixture.add_gitlink("submodules/declared", declare=True)
        self.assertEqual(publication_audit.static_errors(self.fixture.root), [])

        self.fixture.add_gitlink("submodules/undeclared", declare=False)
        errors = publication_audit.static_errors(self.fixture.root)
        self.assertTrue(any("submodules/undeclared" in error for error in errors), errors)

        self.fixture.write(
            ".gitmodules",
            '[submodule "missing"]\n\tpath = submodules/missing\n'
            "\turl = https://example.invalid/missing.git\n",
        )
        run("git", "add", ".gitmodules", cwd=self.fixture.root)
        errors = publication_audit.static_errors(self.fixture.root)
        self.assertTrue(any("submodules/missing" in error for error in errors), errors)

    def test_tracked_generated_and_oversized_files_are_rejected(self) -> None:
        self.fixture.write("build/generated.txt", "generated\n")
        self.fixture.write("large.dat", b"0123456789")
        run("git", "add", "-f", "build/generated.txt", "large.dat", cwd=self.fixture.root)

        errors = publication_audit.static_errors(self.fixture.root, max_blob_bytes=9)

        self.assertTrue(any("build/generated.txt" in error for error in errors), errors)
        self.assertTrue(any("large.dat" in error and "9" in error for error in errors), errors)

    def test_ignored_generated_file_is_not_rejected(self) -> None:
        self.fixture.write("build/ignored.txt", "not tracked\n")

        self.assertEqual(publication_audit.static_errors(self.fixture.root), [])

    def test_secret_error_is_redacted(self) -> None:
        sentinel = "github_pat_" + "A" * 82
        self.fixture.write("notes.txt", f"temporary credential: {sentinel}\n")
        run("git", "add", "notes.txt", cwd=self.fixture.root)

        errors = publication_audit.static_errors(self.fixture.root)
        serialized = json.dumps(errors)

        self.assertTrue(any("notes.txt" in error for error in errors), errors)
        self.assertTrue(any("GitHub token" in error for error in errors), errors)
        self.assertNotIn(sentinel, serialized)
        self.assertNotIn("A" * 40, serialized)

    def test_invalid_or_wrong_package_metadata_is_reported(self) -> None:
        cases = {
            "invalid": "[project\n",
            "wrong name": '[project]\nname = "sureal"\n',
        }
        for label, content in cases.items():
            with self.subTest(label=label):
                self.fixture.write("pyproject.toml", content)
                run("git", "add", "pyproject.toml", cwd=self.fixture.root)
                errors = publication_audit.static_errors(self.fixture.root)
                self.assertTrue(
                    any("pyproject.toml" in error for error in errors), errors
                )


class PortableAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = PublicationFixture()

    def tearDown(self) -> None:
        self.fixture.cleanup()

    def test_portable_checks_use_argument_lists_and_collect_failures(self) -> None:
        entries = [
            publication_audit.IndexEntry("100644", "1" * 40, "check with space.py"),
            publication_audit.IndexEntry("100755", "2" * 40, "script with space.sh"),
            publication_audit.IndexEntry(
                "100644", "3" * 40, "experiments/3d-pathway/pipeline/audit.py"
            ),
        ]

        def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            self.assertIsInstance(args, list)
            self.assertNotIn("shell", kwargs)
            return_code = 7 if args[:2] == ["bash", "-n"] else 0
            return subprocess.CompletedProcess(args, return_code, b"", b"")

        with (
            mock.patch.object(publication_audit, "_index_entries", return_value=entries),
            mock.patch.object(
                publication_audit.subprocess, "run", side_effect=fake_run
            ) as run_mock,
        ):
            errors = publication_audit.portable_command_errors(self.fixture.root)

        commands = [call.args[0] for call in run_mock.call_args_list]
        self.assertIn(
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "check with space.py",
                "experiments/3d-pathway/pipeline/audit.py",
            ],
            commands,
        )
        self.assertIn(["bash", "-n", "script with space.sh"], commands)
        self.assertIn(["git", "diff", "--check", "HEAD"], commands)
        self.assertIn(
            [
                sys.executable,
                "experiments/3d-pathway/pipeline/audit.py",
                "--offline",
            ],
            commands,
        )
        self.assertEqual(
            errors,
            ["portable command failed (exit 7): bash -n script with space.sh"],
        )

    def test_cli_prints_machine_readable_pass_and_fail_results(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            return_code = publication_audit.main(["--root", str(self.fixture.root)])
        report = json.loads(stdout.getvalue())
        self.assertEqual(return_code, 0)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["errors"], [])

        self.fixture.remove("SECURITY.md")
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            return_code = publication_audit.main(["--root", str(self.fixture.root)])
        report = json.loads(stdout.getvalue())
        self.assertEqual(return_code, 1)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("SECURITY.md" in error for error in report["errors"]))

    def test_non_git_root_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="not a repository ") as directory:
            report = publication_audit.audit_repository(Path(directory))

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["tracked_files"], 0)
        self.assertEqual(report["gitlinks"], 0)
        self.assertTrue(any("repository" in error for error in report["errors"]))


class RepositoryIdentityTests(unittest.TestCase):
    def test_repository_declares_sureal_identity_and_surflo_compatibility(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("# Sureal", readme)
        self.assertIn(f"fork of [Surflo]({UPSTREAM_URL})", readme)
        self.assertIn(
            "git clone --recursive git@github.com:phi9t/sureal.git", readme
        )
        self.assertIn("Python package and import name remain `surflo`", readme)
        self.assertIn("non-commercial research and evaluation", readme)
        for link in (
            "[Research mission](MISSION.md)",
            "[3D reconstruction pathway](docs/3d-reconstruction-pathway.md)",
            "[Executable pathway labs](experiments/3d-pathway/README.md)",
        ):
            self.assertIn(link, readme)
        for tier in ("Portable", "Smoke", "Full B200"):
            self.assertIn(tier, readme)

    def test_package_metadata_keeps_surflo_name_and_points_to_both_repositories(
        self,
    ) -> None:
        metadata = publication_audit.tomllib.loads(
            (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]

        self.assertEqual(metadata["name"], "surflo")
        self.assertEqual(metadata["version"], "0.1.0")
        self.assertEqual(metadata["requires-python"], "==3.10.*")
        self.assertEqual(metadata["license"], {"file": "LICENSE.md"})
        self.assertEqual(metadata["urls"]["Homepage"], TARGET_URL)
        self.assertEqual(metadata["urls"]["Repository"], TARGET_URL)
        self.assertEqual(metadata["urls"]["Upstream"], UPSTREAM_URL)
        self.assertEqual(metadata["urls"]["Paper"], "https://arxiv.org/abs/2606.13644")

    def test_public_docs_cover_contribution_security_release_and_lineage(self) -> None:
        expected = {
            "UPSTREAM.md": (
                UPSTREAM_URL,
                "complete Git history",
                "surflo",
                "Sureal additions",
            ),
            "CONTRIBUTING.md": (
                "pull request",
                "non-commercial research and evaluation",
                "python scripts/publication_audit.py --root .",
                "smoke",
                "full",
            ),
            "SECURITY.md": (
                "main",
                "https://github.com/phi9t/sureal/security/advisories/new",
                "Do not",
                "research code",
            ),
            "RELEASING.md": (
                "python scripts/publication_audit.py --root .",
                "python -m build",
                "gitleaks git",
                "--no-local",
                "git ls-remote",
                "force",
            ),
        }
        for relative_path, phrases in expected.items():
            with self.subTest(path=relative_path):
                content = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
                for phrase in phrases:
                    self.assertIn(phrase, content)

    def test_original_surflo_citation_and_license_remain_present(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        license_text = (REPOSITORY_ROOT / "LICENSE.md").read_text(encoding="utf-8")
        notices = (REPOSITORY_ROOT / "THIRD_PARTY_NOTICES.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Original Surflo paper citation", readme)
        self.assertIn("@article{guedon2026surflo", readme)
        self.assertIn("Gaussian-Splatting License", license_text)
        self.assertIn("Gaussian-Splatting License", notices)
        self.assertIn("may not be used commercially", notices)

    def test_publication_generated_paths_remain_ignored(self) -> None:
        paths = (
            ".worktrees/publication-test/file",
            ".env",
            ".venv/bin/python",
            "package.egg-info/PKG-INFO",
            "pkg/__pycache__/module.cpython-310.pyc",
            "pkg/module.pyc",
            "checkpoints/model.pt",
            "outputs/result.json",
            "wandb/latest-run",
            "training/logs/run.log",
            "training/outputs/result.json",
        )
        for path in paths:
            with self.subTest(path=path):
                result = run(
                    "git",
                    "check-ignore",
                    "--no-index",
                    "-q",
                    "--",
                    path,
                    cwd=REPOSITORY_ROOT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, path)


if __name__ == "__main__":
    unittest.main()
