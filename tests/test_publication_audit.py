from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import shlex
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
    "docs/coherent-scene-hypotheses.md",
    "LICENSE.md",
    "MISSION.md",
    "README.md",
    "RELEASING.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "UPSTREAM.md",
    "pyproject.toml",
}
LIVING_DOCUMENTS = (
    "README.md",
    "CONTRIBUTING.md",
    "RELEASING.md",
    "AGENTS.md",
    "CONTEXT-MAP.md",
    "autonomy/README.md",
    "autonomy/ARCHITECTURE.md",
    "autonomy/advanced/README.md",
    "autonomy/architecture/README.md",
    "autonomy/explorer/README.md",
    "autonomy/resources/README.md",
    "autonomy/scripts/HDFS_AUTH.md",
    "autonomy/tier1/README.md",
    "autonomy/tracking/README.md",
    "autonomy/viewer/README.md",
    "parallax/README.md",
)
STALE_COMPONENT_PATHS = (
    "experiments/waymo-perception",
    "experiments/3d-pathway",
)
STALE_PATH_EXCLUDED_MARKDOWN_PREFIXES = (
    ".scratch/",
    "docs/adr/",
    "docs/research/",
    "docs/superpowers/plans/",
    "docs/superpowers/specs/",
)


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
            "docs/coherent-scene-hypotheses.md": (
                "# Coherent scene hypotheses\n\n"
                "Inherited reconstruction system. Sureal experimental infrastructure. "
                "Proposed learned research. Repository-recorded GPU measurements were "
                "not independently rerun. Support labels do not certify object "
                "completeness.\n"
            ),
            "LICENSE.md": (
                "Gaussian-Splatting License\n"
                "non-commercial research and evaluation\n"
            ),
            "README.md": (
                "# Sureal\n\n"
                f"Sureal is a fork of [Surflo]({UPSTREAM_URL}). The installed "
                "package and Python imports remain surflo.\n\n"
                "Use is limited to non-commercial research and evaluation. "
                "See [LICENSE.md](LICENSE.md) and "
                "[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).\n\n"
                "[Coherent scene hypotheses](docs/coherent-scene-hypotheses.md)\n\n"
                f"Repository: {TARGET_URL}\n"
            ),
            "MISSION.md": (
                "# Mission\n\n"
                "See [Coherent scene hypotheses](docs/coherent-scene-hypotheses.md).\n\n"
                r"$z \sim p_\psi(z\mid O)$" "\n"
            ),
            "RELEASING.md": "# Releasing\n",
            "SECURITY.md": "# Security\n",
            "THIRD_PARTY_NOTICES.md": (
                "# Third-party notices\n\nGaussian-Splatting License\n"
            ),
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
        generated_paths = (
            ".venv/bin/python",
            ".worktrees/candidate/HEAD",
            "build/generated.txt",
            "checkpoints/model.pt",
            "datasets/raw.bin",
            "outputs/result.json",
            "training/logs/run.log",
            "training/outputs/result.json",
            "wandb/latest-run",
        )
        for path in generated_paths:
            self.fixture.write(path, "x")
        self.fixture.write("large.dat", b"0123456789")
        run("git", "add", "-f", *generated_paths, "large.dat", cwd=self.fixture.root)

        errors = publication_audit.static_errors(self.fixture.root, max_blob_bytes=9)

        for path in generated_paths:
            self.assertTrue(any(path in error for error in errors), (path, errors))
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

    def test_staged_blob_is_the_audit_source_of_truth(self) -> None:
        sentinel = "github_pat_" + "B" * 82
        self.fixture.write("staged.txt", f"credential: {sentinel}\n")
        run("git", "add", "staged.txt", cwd=self.fixture.root)
        self.fixture.write("staged.txt", "safe unstaged replacement\n")

        errors = publication_audit.static_errors(self.fixture.root)
        serialized = json.dumps(errors)

        self.assertTrue(any("staged.txt" in error for error in errors), errors)
        self.assertTrue(any("GitHub token" in error for error in errors), errors)
        self.assertNotIn(sentinel, serialized)

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

    def test_license_and_notice_links_and_contents_are_required(self) -> None:
        readme = (self.fixture.root / "README.md").read_text(encoding="utf-8")
        self.fixture.write(
            "README.md",
            readme.replace("[LICENSE.md](LICENSE.md)", "license")
            .replace("[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)", "notices"),
        )
        self.fixture.write("LICENSE.md", "unrelated terms\n")
        self.fixture.write("THIRD_PARTY_NOTICES.md", "# Empty notices\n")
        run(
            "git",
            "add",
            "README.md",
            "LICENSE.md",
            "THIRD_PARTY_NOTICES.md",
            cwd=self.fixture.root,
        )

        errors = publication_audit.static_errors(self.fixture.root)

        for text in (
            "README.md: missing required license link: LICENSE.md",
            "README.md: missing required license link: THIRD_PARTY_NOTICES.md",
            "LICENSE.md: Gaussian-Splatting License text is not preserved",
            "THIRD_PARTY_NOTICES.md: Gaussian-Splatting License notice is not preserved",
        ):
            self.assertIn(text, errors)


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
                "100644", "3" * 40, "parallax/pipeline/audit.py"
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
                "parallax/pipeline/audit.py",
            ],
            commands,
        )
        self.assertIn(["bash", "-n", "script with space.sh"], commands)
        self.assertIn(["git", "diff", "--check", "HEAD"], commands)
        self.assertIn(
            [
                sys.executable,
                "parallax/pipeline/audit.py",
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
            root = Path(directory)
            with mock.patch.dict(
                "os.environ",
                {"GIT_CEILING_DIRECTORIES": str(root.parent)},
            ):
                report = publication_audit.audit_repository(root)

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["tracked_files"], 0)
        self.assertEqual(report["gitlinks"], 0)
        self.assertTrue(any("repository" in error for error in report["errors"]))


class RepositoryIdentityTests(unittest.TestCase):
    def living_markdown(self) -> list[str]:
        tracked_markdown = run(
            "git",
            "ls-files",
            "*.md",
            cwd=REPOSITORY_ROOT,
        ).stdout.splitlines()
        return [
            path
            for path in tracked_markdown
            if "/research/" not in path
            and not path.startswith(STALE_PATH_EXCLUDED_MARKDOWN_PREFIXES)
        ]

    def test_context_map_points_at_moved_autonomy_glossary(self) -> None:
        context_map = (REPOSITORY_ROOT / "CONTEXT-MAP.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("[autonomy/CONTEXT.md](autonomy/CONTEXT.md)", context_map)
        old_glossary = "/".join(("experiments", "waymo-perception", "CONTEXT.md"))
        self.assertNotIn(old_glossary, context_map)

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
            "[Executable pathway labs](parallax/README.md)",
            "[Waymo perception pipeline](autonomy/README.md)",
        ):
            self.assertIn(link, readme)
        for tier in ("Portable", "Smoke", "Full B200"):
            self.assertIn(tier, readme)

    def test_living_documents_name_the_current_component_paths(self) -> None:
        living_markdown = self.living_markdown()
        self.assertIn("autonomy/README.md", living_markdown)
        self.assertIn("autonomy/architecture/ideas/residual_bev.md", living_markdown)

        for relative_path in living_markdown:
            with self.subTest(path=relative_path):
                content = (REPOSITORY_ROOT / relative_path).read_text(
                    encoding="utf-8"
                )
                for stale_path in STALE_COMPONENT_PATHS:
                    self.assertNotIn(stale_path, content)

    def test_living_document_relative_links_resolve(self) -> None:
        link_pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
        living_markdown = self.living_markdown()
        for relative_path in living_markdown:
            document = REPOSITORY_ROOT / relative_path
            content = document.read_text(encoding="utf-8")
            for match in link_pattern.finditer(content):
                target = match.group(1).strip()
                if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                target = target.split("#", 1)[0].strip()
                if not target:
                    continue
                target = target.removeprefix("<").removesuffix(">")
                resolved = (document.parent / target).resolve()
                with self.subTest(document=relative_path, target=target):
                    self.assertTrue(resolved.exists(), f"{relative_path} -> {target}")

    def test_living_document_repo_relative_command_entrypoints_exist(self) -> None:
        command_names = {
            "./bazelw",
            "autonomy/dataset/gcs.sh",
            "autonomy/dataset/setup-gcs.sh",
            "parallax/run.sh",
        }
        python_names = {"python", "python3"}

        def repo_path(candidate: str) -> Path | None:
            normalized = candidate.removeprefix("./")
            if normalized == "bazelw":
                return REPOSITORY_ROOT / normalized
            if normalized.startswith(
                ("autonomy/", "parallax/", "scripts/", "install/", "examples/")
            ):
                return REPOSITORY_ROOT / normalized
            return None

        for relative_path in self.living_markdown():
            content = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
            for line_number, line in enumerate(content.splitlines(), start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith(("#", "$")):
                    continue
                if stripped.endswith("\\"):
                    stripped = stripped[:-1].rstrip()
                try:
                    tokens = shlex.split(stripped)
                except ValueError:
                    continue

                for token in tokens:
                    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*=.*", token):
                        break
                    value = token.split("=", 1)[1]
                    path = repo_path(value)
                    if path is not None:
                        with self.subTest(
                            document=relative_path,
                            line=line_number,
                            value=value,
                        ):
                            self.assertTrue(
                                path.exists(),
                                f"{relative_path}:{line_number}: {value}",
                            )
                while tokens and re.fullmatch(r"[A-Z_][A-Z0-9_]*=.*", tokens[0]):
                    tokens.pop(0)
                if not tokens:
                    continue

                command = tokens[0]
                if command in command_names:
                    path = repo_path(command)
                    with self.subTest(
                        document=relative_path,
                        line=line_number,
                        command=command,
                    ):
                        self.assertIsNotNone(path)
                        self.assertTrue(
                            path.exists(),
                            f"{relative_path}:{line_number}: {command}",
                        )
                    continue
                if command == "bash" and len(tokens) > 1:
                    path = repo_path(tokens[1])
                elif (
                    command in python_names
                    and len(tokens) > 1
                    and not tokens[1].startswith("-")
                ):
                    path = repo_path(tokens[1])
                else:
                    path = None
                if path is not None:
                    with self.subTest(
                        document=relative_path,
                        line=line_number,
                        command=stripped,
                    ):
                        self.assertTrue(
                            path.exists(),
                            f"{relative_path}:{line_number}: {stripped}",
                        )

    def test_contributing_validation_tiers_use_bazel_wrapper(self) -> None:
        contributing = (REPOSITORY_ROOT / "CONTRIBUTING.md").read_text(
            encoding="utf-8"
        )
        releasing = (REPOSITORY_ROOT / "RELEASING.md").read_text(
            encoding="utf-8"
        )

        for content in (contributing, releasing):
            self.assertIn("./bazelw test //parallax/...", content)
            self.assertIn("./bazelw test //autonomy/...", content)
            self.assertNotIn("PYTHONPATH=parallax python -m unittest discover", content)

    def test_perception_readme_points_to_architecture_note_instead_of_planned_layout(self) -> None:
        readme = (REPOSITORY_ROOT / "autonomy/README.md").read_text(encoding="utf-8")

        self.assertNotIn("## Planned layout", readme)
        self.assertIn("[Architecture note](ARCHITECTURE.md)", readme)

    def test_canonical_assessment_separates_evidence_from_research_direction(
        self,
    ) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        mission = (REPOSITORY_ROOT / "MISSION.md").read_text(encoding="utf-8")
        assessment_path = REPOSITORY_ROOT / "docs/coherent-scene-hypotheses.md"

        self.assertTrue(assessment_path.is_file())
        assessment = assessment_path.read_text(encoding="utf-8")
        self.assertIn(
            "[Coherent scene hypotheses](docs/coherent-scene-hypotheses.md)",
            readme,
        )
        for phrase in (
            "Inherited reconstruction system",
            "Sureal experimental infrastructure",
            "Proposed learned research",
            "repository-recorded GPU measurements",
            "not independently rerun",
            "support labels",
            "do not certify object completeness",
        ):
            self.assertIn(phrase, assessment)
        self.assertIn("docs/coherent-scene-hypotheses.md", mission)
        self.assertIn(r"p_\psi(z\mid O)", mission)
        self.assertLessEqual(len(mission.splitlines()), 120)
        for public_document in (mission, assessment):
            self.assertNotIn(":chatgpt-content-reference", public_document)

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
                "./bazelw --emit-plan test //parallax/...",
                "./bazelw --emit-plan test //autonomy/...",
                "./bazelw test //parallax/...",
                "./bazelw test //autonomy/...",
                "not evidence for a fresh B200 measurement",
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
                "./bazelw test //parallax/...",
                "./bazelw test //autonomy/...",
                "not evidence for a fresh B200 measurement",
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

    def test_publication_tooling_provenance_is_recorded(self) -> None:
        notices = (REPOSITORY_ROOT / "THIRD_PARTY_NOTICES.md").read_text(
            encoding="utf-8"
        )

        expected = (
            "actions/checkout",
            "d23441a48e516b6c34aea4fa41551a30e30af803",
            "actions/setup-python",
            "ece7cb06caefa5fff74198d8649806c4678c61a1",
            "gitleaks/gitleaks-action",
            "ff98106e4c7b2bc287b24eaf42907196329070c7",
            "build 1.6.1",
            "twine 7.0.0",
            "tomli 2.4.1",
            "MIT License",
            "Apache License 2.0",
        )
        for value in expected:
            self.assertIn(value, notices)

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
            "node_modules/index.js",
            "autonomy/viewer/web/node_modules/three/package.json",
            "autonomy/viewer/web/dist/index.html",
            "autonomy/viewer/.venv/bin/python",
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


class PublicationWorkflowTests(unittest.TestCase):
    def workflow(self) -> str:
        return (REPOSITORY_ROOT / ".github/workflows/publication.yml").read_text(
            encoding="utf-8"
        )

    def test_publication_workflow_is_sha_pinned_and_least_privilege(self) -> None:
        workflow = self.workflow()
        expected_actions = {
            "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
            "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
            "gitleaks/gitleaks-action@ff98106e4c7b2bc287b24eaf42907196329070c7",
        }
        references = re.findall(
            r"^\s*-?\s*uses:\s*(\S+?)(?:\s+#.*)?$", workflow, re.MULTILINE
        )

        self.assertTrue(expected_actions.issubset(references))
        self.assertTrue(references)
        for reference in references:
            self.assertRegex(reference, r"@[0-9a-f]{40}$")
        self.assertRegex(workflow, r"(?m)^permissions:\n  contents: read$")
        self.assertNotIn("write-all", workflow)

    def test_publication_workflow_runs_a_recursive_full_history_checkout(self) -> None:
        workflow = self.workflow()

        self.assertIn("name: publication", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertRegex(workflow, r"(?m)^\s+branches: \[main\]$")
        self.assertGreaterEqual(workflow.count("fetch-depth: 0"), 2)
        self.assertGreaterEqual(workflow.count("submodules: recursive"), 2)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertGreaterEqual(workflow.count("timeout-minutes:"), 2)

    def test_publication_workflow_runs_audit_tests_build_and_twine(self) -> None:
        workflow = self.workflow()

        for text in (
            "python-version: \"3.10\"",
            "build==1.6.1",
            "twine==7.0.0",
            "tomli==2.4.1",
            "python -m unittest tests.test_publication_audit -v",
            "python scripts/publication_audit.py --root .",
            "python -m build",
            "python -m twine check dist/*",
            "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
        ):
            self.assertIn(text, workflow)
        lowered = workflow.lower()
        self.assertNotIn("cuda", lowered)
        self.assertNotIn("upload-artifact", lowered)
        self.assertNotIn("hf download", lowered)

    def test_publication_workflow_runs_required_cpu_numerical_contracts(self) -> None:
        workflow = self.workflow()
        match = re.search(
            r"(?ms)^  numerical-contracts:\n(?P<body>.*?)(?=^  [a-z0-9-]+:\n|\Z)",
            workflow,
        )

        self.assertIsNotNone(match)
        job = match.group("body") if match is not None else ""
        for text in (
            "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
            "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
            "fetch-depth: 0",
            "submodules: recursive",
            'python-version: "3.10"',
            "numpy==1.26.4",
            "PYTHONPATH=parallax python -m unittest discover -s parallax/tests -p 'test_*.py' -v",
        ):
            self.assertIn(text, job)
        timeout = re.search(r"(?m)^    timeout-minutes: (\d+)$", job)
        self.assertIsNotNone(timeout)
        self.assertGreaterEqual(int(timeout.group(1)), 20)
        self.assertNotIn("SURFLO_REQUIRE_", job)

    def test_real_repository_passes_publication_audit(self) -> None:
        report = publication_audit.audit_repository(REPOSITORY_ROOT)

        self.assertEqual(report["status"], "pass", report["errors"])
        self.assertEqual(report["errors"], [])
        self.assertGreater(report["tracked_files"], 0)
        self.assertEqual(report["gitlinks"], 2)


if __name__ == "__main__":
    unittest.main()
