from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent


def fake_engine(path: Path) -> Path:
    engine = path / "fake-container-engine"
    engine.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            if [[ "${1:-}" == image && "${2:-}" == inspect ]]; then
                if [[ "${FAKE_IMAGE_MISSING:-0}" == 1 ]]; then
                    printf 'fixture image missing\\n' >&2
                    exit 69
                fi
                printf 'sha256:fixture-classical-image\\n'
                exit 0
            fi
            if [[ "${1:-}" != run ]]; then
                printf 'unexpected command: %s\\n' "$*" >&2
                exit 70
            fi
            [[ " $* " == *" --network none "* ]]
            [[ " $* " == *" --pull=never "* ]]
            [[ " $* " == *" --user "* ]]
            [[ " $* " == *" sha256:fixture-classical-image "* ]]
            if [[ "${FAKE_COLMAP_FAIL:-0}" == 1 ]]; then
                printf 'injected COLMAP failure\\n' >&2
                exit 71
            fi
            host=''
            previous=''
            for argument in "$@"; do
                if [[ "$previous" == -v && "$argument" == *:/work ]]; then
                    host="${argument%:/work}"
                fi
                previous="$argument"
            done
            [[ -n "$host" ]]
            if [[ -n "${FAKE_COLMAP_DELAY:-}" ]]; then
                sleep "$FAKE_COLMAP_DELAY"
            fi
            image_count=$(find "$host/input/images" -maxdepth 1 -type f -name '*.pgm' | wc -l)
            expected_count=5
            if [[ " $* " == *" --Mapper.min_num_matches 12 "* ]]; then
                expected_count=9
            fi
            [[ "$image_count" -eq "$expected_count" ]]
            mkdir -p "$host/output/sparse/0"
            printf 'fixture adapter completed\\n'
            printf 'COLMAP %s fixture\\n' "${FAKE_COLMAP_VERSION:-3.9.1}" > "$host/output/colmap-version.txt"
            printf '%s\\n' "${FAKE_COLMAP_PACKAGE_VERSION:-3.9.1-2build2}" > "$host/output/package-version.txt"
            cat > "$host/output/insula-manifest.txt" <<'EOF'
            schema_version=1
            kind=classical-geometry
            ubuntu=24.04
            colmap=3.9.1-2build2
            network_policy=build-and-fetch-only
            EOF
            cat > "$host/output/sparse/0/cameras.txt" <<'EOF'
            # Camera list
            1 PINHOLE 640 480 520 520 319.5 239.5
            EOF
            printf '# Image list, two lines of data per image\\n' > "$host/output/sparse/0/images.txt"
            for zero_index in $(seq 0 $((image_count - 1))); do
                image_id=$((zero_index + 1))
                printf '%s 1 0 0 0 0 0 0 1 frame-%03d.pgm\\n\\n' "$image_id" "$zero_index" >> "$host/output/sparse/0/images.txt"
            done
            printf '# 3D point list\\n' > "$host/output/sparse/0/points3D.txt"
            point_count="${FAKE_COLMAP_POINTS:-1200}"
            for point_id in $(seq 1 "$point_count"); do
                printf '%s 0.1 0.2 4.0 128 128 128 0.50 1 0 2 0\\n' "$point_id" >> "$host/output/sparse/0/points3D.txt"
            done
            printf 'fixture cameras binary\\n' > "$host/output/sparse/0/cameras.bin"
            printf 'fixture images binary\\n' > "$host/output/sparse/0/images.bin"
            printf 'fixture points binary\\n' > "$host/output/sparse/0/points3D.bin"
            {
                printf 'ply\\nformat ascii 1.0\\nelement vertex %s\\n' "$point_count"
                printf 'property float x\\nproperty float y\\nproperty float z\\nend_header\\n'
                for point_id in $(seq 1 "$point_count"); do
                    printf '0.1 0.2 4.0\\n'
                done
            } > "$host/output/sparse.ply"
            python3 - "$host/output/database.db" <<'PY'
            import sqlite3
            import sys

            connection = sqlite3.connect(sys.argv[1])
            for table in ("cameras", "images", "keypoints", "descriptors", "matches", "two_view_geometries"):
                connection.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
            connection.commit()
            connection.close()
            PY
            if [[ "${FAKE_COLMAP_SYMLINK:-0}" == 1 ]]; then
                ln -s /etc/passwd "$host/output/forbidden-link"
            fi
            """
        ),
        encoding="utf-8",
    )
    engine.chmod(0o755)
    return engine


def run_cli(*args: str, cache: Path, engine: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
    environment["SURFLO_PATHWAY_CONTAINER_ENGINE"] = str(engine)
    environment.update(extra_env or {})
    return subprocess.run(
        [str(ROOT / "run.sh"), *args],
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


class ColmapReferenceAdapterTest(unittest.TestCase):
    def test_sqlite_validation_does_not_create_wal_sidecars(self) -> None:
        import sqlite3
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from reference_runner import _validate_sqlite_database

        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "database.db"
            connection = sqlite3.connect(database)
            connection.execute("PRAGMA journal_mode=WAL")
            for table in ("cameras", "images", "keypoints", "descriptors", "matches", "two_view_geometries"):
                connection.execute(f"CREATE TABLE {table} (id INTEGER)")
            connection.commit()
            connection.close()
            self.assertFalse(Path(f"{database}-wal").exists())
            self.assertFalse(Path(f"{database}-shm").exists())

            _validate_sqlite_database(database)

            self.assertFalse(Path(f"{database}-wal").exists())
            self.assertFalse(Path(f"{database}-shm").exists())

    def test_generated_scene_is_deterministic_and_records_full_calibration(self) -> None:
        from sys import path as import_path
        import_path.insert(0, str(ROOT / "pipeline"))
        from contracts import load_json
        from reference_scene import generate_colmap_scene

        scene = load_json(ROOT / "shared-scene.json")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = generate_colmap_scene(root / "first", scene, "smoke")
            second = generate_colmap_scene(root / "second", scene, "smoke")
            self.assertEqual(first, second)
            self.assertEqual([frame["sha256"] for frame in first["frames"]], [frame["sha256"] for frame in second["frames"]])
            self.assertIn("fixture", first)
            self.assertEqual(first["fixture"], scene["reference_fixture"])
            self.assertEqual(len(first["frames"]), 5)
            for frame, camera_x in zip(first["frames"], scene["reference_fixture"]["camera_x_smoke_m"]):
                self.assertEqual(frame["K"], [[520.0, 0.0, 319.5], [0.0, 520.0, 239.5], [0.0, 0.0, 1.0]])
                self.assertEqual(
                    frame["R_world_to_camera"],
                    [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]],
                )
                self.assertEqual(frame["t_world_to_camera_m"], [-camera_x, 0.0, 0.0])
                self.assertEqual(frame["camera_center_m"], [camera_x, 0.0, 0.0])
                image = root / "first" / "images" / frame["name"]
                header, dimensions, maximum, pixels = image.read_bytes().split(b"\n", 3)
                self.assertEqual(header, b"P5")
                self.assertEqual(dimensions, b"640 480")
                self.assertEqual(maximum, b"255")
                self.assertEqual(len(pixels), 640 * 480)

    def test_reference_plan_is_explicitly_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = run_cli(
                "--emit-plan", "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "plan",
                cache=root / "cache", engine=fake_engine(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                json.loads(completed.stdout),
                {
                    "adapter": "colmap-sfm",
                    "command": "reference",
                    "network_mode": "offline",
                    "profile": "smoke",
                    "run_id": "plan",
                    "schema_version": 1,
                },
            )

    def test_reference_run_generates_images_validates_model_and_promotes_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "colmap-ok",
                cache=cache, engine=fake_engine(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "reference-runs" / "colmap-ok" / "colmap-sfm"
            result = json.loads((run_dir / "result.json").read_text())
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["network_mode"], "offline")
            self.assertEqual(result["adapter"], "colmap-sfm")
            self.assertEqual(result["metrics"]["registered_images"], 5)
            self.assertEqual(result["metrics"]["sparse_points"], 1200)
            self.assertAlmostEqual(result["metrics"]["mean_reprojection_error_px"], 0.5)
            self.assertEqual(result["tool"]["version"], "COLMAP 3.9.1 fixture")
            self.assertEqual(result["tool"]["package_version"], "3.9.1-2build2")
            self.assertEqual(len(list((run_dir / "input" / "images").glob("*.pgm"))), 5)
            self.assertTrue((run_dir / "output" / "sparse" / "0" / "points3D.txt").is_file())
            self.assertTrue((run_dir / "output" / "sparse.ply").is_file())
            self.assertFalse(any((cache / "reference-staging").glob("*")))

            from sys import path as import_path
            import_path.insert(0, str(ROOT / "pipeline"))
            from reference_runner import validate_reference_result

            validate_reference_result(run_dir, "colmap-sfm")
            points = run_dir / "output" / "sparse" / "0" / "points3D.txt"
            points.write_text(points.read_text() + "4 0 0 2 0 0 0 1.0 1 0 2 0\n")
            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                validate_reference_result(run_dir, "colmap-sfm")

    def test_reference_validator_semantically_checks_required_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "artifact-contract",
                cache=cache, engine=fake_engine(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "reference-runs" / "artifact-contract" / "colmap-sfm"
            required = (
                "output/database.db", "output/sparse/0/cameras.bin", "output/sparse/0/images.bin",
                "output/sparse/0/points3D.bin", "output/sparse.ply", "output/package-version.txt",
                "output/insula-manifest.txt", "adapter.log", "report.md",
            )
            for relative in required:
                self.assertTrue((run_dir / relative).is_file(), relative)

            from sys import path as import_path
            import_path.insert(0, str(ROOT / "pipeline"))
            from contracts import sha256_file
            from reference_runner import validate_reference_result

            ply = run_dir / "output" / "sparse.ply"
            ply.write_text(ply.read_text().replace("element vertex 1200", "element vertex 1199"))
            result_path = run_dir / "result.json"
            payload = json.loads(result_path.read_text())
            payload["provenance"]["artifacts_sha256"]["output/sparse.ply"] = sha256_file(ply)
            result_path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "PLY vertex count mismatch"):
                validate_reference_result(run_dir, "colmap-sfm")

    def test_reference_validator_enforces_schema_and_config_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "validate-reference",
                cache=cache, engine=fake_engine(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "reference-runs" / "validate-reference" / "colmap-sfm"
            result_path = run_dir / "result.json"
            original = result_path.read_bytes()

            from sys import path as import_path
            import_path.insert(0, str(ROOT / "pipeline"))
            from reference_runner import validate_reference_result

            payload = json.loads(original)
            payload.pop("tool")
            result_path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "schema missing keys"):
                validate_reference_result(run_dir, "colmap-sfm")

            result_path.write_bytes(original)
            payload = json.loads(original)
            payload["provenance"]["config"]["profile"] = "full"
            result_path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "config hash mismatch"):
                validate_reference_result(run_dir, "colmap-sfm")

    def test_reference_validator_binds_scope_tool_acceptance_and_finite_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "metadata-contract",
                cache=cache, engine=fake_engine(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "reference-runs" / "metadata-contract" / "colmap-sfm"
            result_path = run_dir / "result.json"
            original = result_path.read_bytes()

            from sys import path as import_path
            import_path.insert(0, str(ROOT / "pipeline"))
            from reference_runner import validate_reference_result

            cases = (
                ("module_ids", lambda payload: payload.__setitem__("module_ids", ["06"]), "module scope mismatch"),
                ("tool", lambda payload: payload["tool"].__setitem__("version", "COLMAP 4.0.0"), "tool version mismatch"),
                ("acceptance", lambda payload: payload["acceptance"].__setitem__("sparse_points_min", 1), "acceptance mismatch"),
                ("runtime", lambda payload: payload["resources"].__setitem__("runtime_seconds", float("nan")), "non-finite"),
            )
            for name, mutate, message in cases:
                with self.subTest(name=name):
                    payload = json.loads(original)
                    mutate(payload)
                    result_path.write_text(json.dumps(payload))
                    with self.assertRaisesRegex(ValueError, message):
                        validate_reference_result(run_dir, "colmap-sfm")
            result_path.write_bytes(original)

    def test_reference_failure_leaves_no_partial_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "colmap-fail",
                cache=cache, engine=fake_engine(root), extra_env={"FAKE_COLMAP_FAIL": "1"},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("injected COLMAP failure", completed.stderr)
            self.assertFalse((cache / "reference-runs" / "colmap-fail").exists())
            self.assertFalse(any((cache / "reference-staging").glob("*")))

    def test_reference_rejects_an_unpinned_colmap_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "wrong-version",
                cache=cache, engine=fake_engine(root), extra_env={"FAKE_COLMAP_VERSION": "4.0.0"},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("COLMAP version mismatch", completed.stderr)
            self.assertFalse((cache / "reference-runs" / "wrong-version").exists())

    def test_reference_rejects_an_unpinned_package_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "wrong-package",
                cache=cache, engine=fake_engine(root), extra_env={"FAKE_COLMAP_PACKAGE_VERSION": "3.9.1-2build3"},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("COLMAP package version mismatch", completed.stderr)
            self.assertFalse((cache / "reference-runs" / "wrong-package").exists())

    def test_reference_enforces_the_registry_acceptance_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "too-sparse",
                cache=cache, engine=fake_engine(root), extra_env={"FAKE_COLMAP_POINTS": "999"},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("below the locked acceptance threshold", completed.stderr)
            self.assertFalse((cache / "reference-runs" / "too-sparse").exists())

    def test_full_profile_uses_nine_frames_and_its_locked_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "full", "--run-id", "full-fixture",
                cache=cache, engine=fake_engine(root), extra_env={"FAKE_COLMAP_POINTS": "2000"},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "reference-runs" / "full-fixture" / "colmap-sfm"
            result = json.loads((run_dir / "result.json").read_text())
            self.assertEqual(result["metrics"]["registered_images"], 9)
            self.assertEqual(result["metrics"]["sparse_points"], 2000)
            self.assertEqual(result["acceptance"]["registered_images_min"], 7)
            self.assertEqual(len(list((run_dir / "input" / "images").glob("*.pgm"))), 9)

    def test_missing_image_fails_before_creating_cache_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "missing-image",
                cache=cache, engine=fake_engine(root), extra_env={"FAKE_IMAGE_MISSING": "1"},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("classical Insula is not built", completed.stderr)
            self.assertFalse(cache.exists())

    def test_symlink_artifacts_and_cache_descendants_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "artifact-cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "artifact-link",
                cache=cache, engine=fake_engine(root), extra_env={"FAKE_COLMAP_SYMLINK": "1"},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("symlink artifact is forbidden", completed.stderr)
            self.assertFalse((cache / "reference-runs" / "artifact-link").exists())

            linked_cache = root / "linked-cache"
            linked_cache.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (linked_cache / "reference-staging").symlink_to(outside, target_is_directory=True)
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "cache-link",
                cache=linked_cache, engine=fake_engine(root),
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("cache descendant must be a real directory", completed.stderr)

    def test_same_run_id_has_only_one_atomic_winner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            engine = fake_engine(root)
            environment = os.environ.copy()
            environment.update({
                "SURFLO_PATHWAY_CACHE_ROOT": str(cache),
                "SURFLO_PATHWAY_CONTAINER_ENGINE": str(engine),
                "FAKE_COLMAP_DELAY": "0.2",
            })
            command = [
                str(ROOT / "run.sh"), "reference", "--adapter", "colmap-sfm",
                "--profile", "smoke", "--run-id", "same-id",
            ]
            processes = [
                subprocess.Popen(command, cwd=REPO_ROOT, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for _ in range(2)
            ]
            outcomes = [process.communicate(timeout=30) + (process.returncode,) for process in processes]
            self.assertEqual(sorted(outcome[2] for outcome in outcomes), [0, 2], outcomes)
            run_dir = cache / "reference-runs" / "same-id" / "colmap-sfm"
            self.assertTrue((run_dir / "result.json").is_file())
            self.assertFalse(any((cache / "reference-staging").glob("*")))

    def test_real_colmap_reconstructs_the_generated_smoke_scene(self) -> None:
        require_real = os.environ.get("SURFLO_REQUIRE_COLMAP_REFERENCE") == "1"
        docker = shutil.which("docker")
        if docker is None:
            if require_real:
                self.fail("SURFLO_REQUIRE_COLMAP_REFERENCE=1 but Docker is unavailable")
            self.skipTest("Docker is unavailable")
        image = subprocess.run(
            [docker, "image", "inspect", "surflo-pathway-classical:1"],
            text=True,
            capture_output=True,
            check=False,
        )
        if image.returncode != 0:
            if require_real:
                self.fail("SURFLO_REQUIRE_COLMAP_REFERENCE=1 but the classical Insula is not built")
            self.skipTest("classical Insula is not built")
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            completed = run_cli(
                "reference", "--adapter", "colmap-sfm", "--profile", "smoke", "--run-id", "real-colmap",
                cache=cache, engine=Path(docker),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(
                (cache / "reference-runs" / "real-colmap" / "colmap-sfm" / "result.json").read_text()
            )
            self.assertGreaterEqual(result["metrics"]["registered_images"], 4)
            self.assertGreaterEqual(result["metrics"]["sparse_points"], 3)


if __name__ == "__main__":
    unittest.main()
