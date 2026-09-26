from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

import numpy as np

from tests.test_colmap_reference import ROOT, fake_engine, run_cli


COLMAP_MVS_COMMIT = "be5e29168d4aff238409d60424812df66aac919f"


def fake_mvs_engine(path: Path) -> Path:
    engine = path / "fake-mvs-container-engine"
    engine.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail
            if [[ "${{1:-}}" == image && "${{2:-}}" == inspect ]]; then
                printf 'sha256:cd5cf2427f8c07cea7308256ec7baa33c76e7b95fc3f4fb67873a0e5c8b1aa0a\\n'
                exit 0
            fi
            [[ "${{1:-}}" == run ]]
            [[ " $* " == *" --network none "* ]]
            [[ " $* " == *" --pull=never "* ]]
            [[ " $* " == *" --gpus all "* ]]
            [[ " $* " == *" --cidfile "* ]]
            [[ " $* " == *" --user "* ]]
            [[ " $* " == *" -e CUDA_CACHE_PATH=/cuda-cache "* ]]
            [[ " $* " == *":/cuda-cache "* ]]
            [[ " $* " == *" sha256:cd5cf2427f8c07cea7308256ec7baa33c76e7b95fc3f4fb67873a0e5c8b1aa0a "* ]]
            [[ " $* " == *" patch_match_stereo "* ]]
            [[ " $* " == *" stereo_fusion "* ]]
            [[ " $* " == *" poisson_mesher "* ]]
            [[ " $* " == *" --PoissonMeshing.trim 5"* ]]
            host=''
            previous=''
            for argument in "$@"; do
                if [[ "$previous" == -v && "$argument" == *:/work ]]; then
                    host="${{argument%:/work}}"
                fi
                previous="$argument"
            done
            [[ -n "$host" ]]
            python3 - "$host" <<'PY'
            import json
            import os
            from pathlib import Path
            import shutil
            import sqlite3
            import struct
            import sys
            from array import array

            root = Path(sys.argv[1])
            manifest = json.loads((root / "input/scene-manifest.json").read_text())
            assert manifest["profile"] in {{"smoke", "full"}}
            expected_frames = 5 if manifest["profile"] == "smoke" else 9
            assert len(manifest["frames"]) == expected_frames
            assert all((root / "input" / frame["depth_name"]).is_file() for frame in manifest["frames"])
            output = root / "output"
            model = output / "sparse/0"
            depth_maps = output / "dense/stereo/depth_maps"
            normal_maps = output / "dense/stereo/normal_maps"
            model.mkdir(parents=True)
            depth_maps.mkdir(parents=True)
            normal_maps.mkdir(parents=True)
            (output / "colmap-version.txt").write_text("COLMAP 4.2.0 fixture\\n")
            (output / "source-commit.txt").write_text("{COLMAP_MVS_COMMIT}\\n")
            (output / "insula-manifest.txt").write_text(
                "schema_version=1\\n"
                "kind=classical-mvs\\n"
                "ubuntu=24.04\\n"
                "cuda=12.9.1\\n"
                "cuda_architectures=100\\n"
                "colmap=4.2.0\\n"
                "colmap_commit={COLMAP_MVS_COMMIT}\\n"
                "network_policy=build-and-fetch-only\\n"
            )
            (model / "cameras.txt").write_text("# Camera list\\n1 PINHOLE 640 480 520 520 319.5 239.5\\n")
            image_records = ["# Image list, two lines per image"]
            for image_id, frame in enumerate(manifest["frames"], 1):
                tx, ty, tz = frame["t_world_to_camera_m"]
                image_records.extend([
                    f"{{image_id}} 0 1 0 0 {{tx}} {{ty}} {{tz}} 1 {{frame['name']}}",
                    "",
                ])
                width = manifest["intrinsics"]["width"]
                height = manifest["intrinsics"]["height"]
                (depth_maps / f"{{frame['name']}}.geometric.bin").write_bytes(
                    f"{{width}}&{{height}}&1&".encode()
                    + (array("f", [4.0]) * (width * height)).tobytes()
                )
                shutil.copyfile(
                    depth_maps / f"{{frame['name']}}.geometric.bin",
                    depth_maps / f"{{frame['name']}}.photometric.bin",
                )
                (normal_maps / f"{{frame['name']}}.geometric.bin").write_bytes(
                    f"{{width}}&{{height}}&3&".encode()
                    + (array("f", [1.0]) * (width * height * 3)).tobytes()
                )
                shutil.copyfile(
                    normal_maps / f"{{frame['name']}}.geometric.bin",
                    normal_maps / f"{{frame['name']}}.photometric.bin",
                )
            (model / "images.txt").write_text("\\n".join(image_records) + "\\n")
            point_count = 2000
            points = ["# 3D point list"]
            points.extend(
                f"{{point_id}} 0 0 -4 128 128 128 0.25 1 0 2 0"
                for point_id in range(1, point_count + 1)
            )
            (model / "points3D.txt").write_text("\\n".join(points) + "\\n")
            with (model / "cameras.bin").open("wb") as stream:
                stream.write(struct.pack("<QiiQQ4d", 1, 1, 1, 640, 480, 520, 520, 319.5, 239.5))
            with (model / "images.bin").open("wb") as stream:
                stream.write(struct.pack("<Q", len(manifest["frames"])))
                for image_id, frame in enumerate(manifest["frames"], 1):
                    tx, ty, tz = frame["t_world_to_camera_m"]
                    stream.write(struct.pack("<i7di", image_id, 0, 1, 0, 0, tx, ty, tz, 1))
                    stream.write(frame["name"].encode() + b"\\0")
                    stream.write(struct.pack("<Q", 0))
            with (model / "points3D.bin").open("wb") as stream:
                stream.write(struct.pack("<Q", point_count))
                for point_id in range(1, point_count + 1):
                    stream.write(struct.pack("<Q3d3Bd", point_id, 0, 0, -4, 128, 128, 128, 0.25))
                    stream.write(struct.pack("<Qiiii", 2, 1, 0, 2, 0))
            sparse_header = (
                "ply\\nformat ascii 1.0\\n"
                f"element vertex {{point_count}}\\n"
                "property float x\\nproperty float y\\nproperty float z\\nend_header\\n"
            )
            (output / "sparse.ply").write_text(sparse_header + "0 0 -4\\n" * point_count)
            truth = root / "input/ground-truth-visible.ply"
            truth_lines = truth.read_text().splitlines()
            end = truth_lines.index("end_header")
            vertices = truth_lines[end + 1 :]
            dense_limit = int(os.environ.get("FAKE_MVS_DENSE_LIMIT", "0"))
            if dense_limit:
                dense_vertices = vertices[:dense_limit]
            else:
                dense_vertices = vertices
            fused_header = [
                "ply", "format ascii 1.0", f"element vertex {{len(dense_vertices)}}",
                "property float x", "property float y", "property float z",
                "property float nx", "property float ny", "property float nz", "end_header",
            ]
            (output / "dense/fused.ply").write_text(
                "\\n".join(fused_header + [f"{{vertex}} 0 0 1" for vertex in dense_vertices]) + "\\n"
            )
            face_count = 2000
            mesh_header = (
                "ply\\nformat ascii 1.0\\n"
                f"element vertex {{len(vertices)}}\\n"
                "property float x\\nproperty float y\\nproperty float z\\n"
                f"element face {{face_count}}\\n"
                "property list uchar int vertex_indices\\nend_header\\n"
            )
            (output / "dense/meshed-poisson.ply").write_text(
                mesh_header + "\\n".join(vertices) + "\\n" + "".join(
                    f"3 {{(face // 159) * 160 + face % 159}} "
                    f"{{(face // 159) * 160 + face % 159 + 1}} "
                    f"{{(face // 159) * 160 + face % 159 + 160}}\\n"
                    for face in range(face_count)
                )
            )
            connection = sqlite3.connect(output / "database.db")
            connection.execute("CREATE TABLE cameras (camera_id INTEGER PRIMARY KEY, model INTEGER, width INTEGER, height INTEGER, params BLOB, prior_focal_length INTEGER)")
            connection.execute("CREATE TABLE images (image_id INTEGER PRIMARY KEY, name TEXT, camera_id INTEGER)")
            connection.execute("CREATE TABLE keypoints (image_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB)")
            connection.execute("CREATE TABLE descriptors (image_id INTEGER PRIMARY KEY, type INTEGER, rows INTEGER, cols INTEGER, data BLOB)")
            connection.execute("CREATE TABLE matches (pair_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB)")
            connection.execute("CREATE TABLE two_view_geometries (pair_id INTEGER PRIMARY KEY, rows INTEGER, cols INTEGER, data BLOB, config INTEGER)")
            connection.execute("INSERT INTO cameras VALUES (1, 1, 640, 480, ?, 1)", (struct.pack("<4d", 520, 520, 319.5, 239.5),))
            for image_id, frame in enumerate(manifest["frames"], 1):
                connection.execute("INSERT INTO images VALUES (?, ?, 1)", (image_id, frame["name"]))
                connection.execute("INSERT INTO keypoints VALUES (?, 1, 4, ?)", (image_id, bytes(16)))
                connection.execute("INSERT INTO descriptors VALUES (?, 0, 1, 128, ?)", (image_id, bytes(128)))
            for image_id in range(1, len(manifest["frames"])):
                pair_id = image_id * 2147483647 + image_id + 1
                payload = struct.pack("<2I", 0, 0)
                connection.execute("INSERT INTO matches VALUES (?, 1, 2, ?)", (pair_id, payload))
                connection.execute("INSERT INTO two_view_geometries VALUES (?, 1, 2, ?, 2)", (pair_id, payload))
            connection.commit()
            connection.close()
            (output / "resource-usage.txt").write_text("Maximum resident set size (kbytes): 12345\\n")
            print("fixture dense MVS completed")
            PY
            """
        ),
        encoding="utf-8",
    )
    engine.chmod(0o755)
    return engine


class ColmapMvsReferenceAdapterTest(unittest.TestCase):
    def test_canonical_sampling_is_order_and_duplicate_invariant(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _canonical_sample

        points = np.array([[0.001, 0.001, 0.001], [0.002, 0.001, 0.001], [1, 2, 3]])
        first, first_support = _canonical_sample(points)
        second, second_support = _canonical_sample(points[[2, 0, 1, 0]])
        np.testing.assert_array_equal(first, second)
        self.assertEqual(first_support.shape, second_support.shape)
        self.assertGreater(int(second_support.max()), int(first_support.max()))

    def test_metric_validation_is_exact_for_counts_and_tolerant_for_floats(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _metrics_match

        recomputed = {"dense_points": 1000, "accuracy_mean_m": 0.125}
        self.assertTrue(
            _metrics_match(
                {"dense_points": 1000, "accuracy_mean_m": 0.125 + 1e-12}, recomputed
            )
        )
        self.assertFalse(
            _metrics_match(
                {"dense_points": 1000.0, "accuracy_mean_m": 0.125}, recomputed
            )
        )
        self.assertFalse(
            _metrics_match(
                {"dense_points": 1000, "accuracy_mean_m": 0.126}, recomputed
            )
        )

    def test_dense_map_parser_rejects_truncated_payload(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _read_colmap_dense_map

        with tempfile.TemporaryDirectory() as temporary:
            dense_map = Path(temporary) / "depth.bin"
            dense_map.write_bytes(b"2&2&1&" + np.ones(3, dtype="<f4").tobytes())
            with self.assertRaisesRegex(ValueError, "payload"):
                _read_colmap_dense_map(dense_map)

    def test_mesh_parser_rejects_forged_face_count(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _read_ply_xyz

        with tempfile.TemporaryDirectory() as temporary:
            mesh = Path(temporary) / "mesh.ply"
            mesh.write_text(
                "ply\nformat ascii 1.0\nelement vertex 3\n"
                "property float x\nproperty float y\nproperty float z\n"
                "element face 2\nproperty list uchar int vertex_indices\nend_header\n"
                "0 0 0\n1 0 0\n0 1 0\n3 0 1 2\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "truncated.*faces"):
                _read_ply_xyz(mesh, validate_faces=True)

    def test_mesh_parser_counts_only_unique_nondegenerate_faces(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _read_ply_xyz

        header = (
            "ply\nformat ascii 1.0\nelement vertex 4\n"
            "property float x\nproperty float y\nproperty float z\n"
            "element face 2\nproperty list uchar int vertex_indices\nend_header\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            mesh = Path(temporary) / "mesh.ply"
            mesh.write_text(
                header + "0 0 0\n1 0 0\n0 1 0\n2 0 0\n3 0 1 2\n3 2 1 0\n",
                encoding="ascii",
            )
            _, valid_faces = _read_ply_xyz(mesh, validate_faces=True)
            self.assertEqual(valid_faces, 1)
            mesh.write_text(
                header + "0 0 0\n1 0 0\n0 1 0\n2 0 0\n3 0 1 2\n4 0 1 2 2\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "invalid.*face indices"):
                _read_ply_xyz(mesh, validate_faces=True)
            mesh.write_text(
                header + "0 0 0\n1 0 0\n0 1 0\n2 0 0\n3 0 1 2\n3 0 1 3\n",
                encoding="ascii",
            )
            _, valid_faces = _read_ply_xyz(mesh, validate_faces=True)
            self.assertEqual(valid_faces, 1)

    def test_manifest_paths_cannot_escape_the_input_directory(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _manifest_input_path

        with tempfile.TemporaryDirectory() as temporary:
            input_root = Path(temporary) / "input"
            input_root.mkdir()
            (Path(temporary) / "outside.npy").write_bytes(b"outside")
            with self.assertRaisesRegex(ValueError, "escapes"):
                _manifest_input_path(input_root, "../outside.npy")

    def test_geometry_metrics_rejects_an_escaping_truth_manifest_path(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _geometry_metrics

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference",
                "--adapter",
                "colmap-mvs",
                "--profile",
                "smoke",
                "--run-id",
                "mvs-escaping-truth",
                cache=cache,
                engine=fake_mvs_engine(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "reference-runs/mvs-escaping-truth/colmap-mvs"
            outside = root / "outside.ply"
            shutil.copyfile(run_dir / "input/ground-truth-visible.ply", outside)
            manifest_path = run_dir / "input/scene-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["ground_truth"]["visible_surface"]["path"] = os.path.relpath(
                outside, run_dir / "input"
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "escapes"):
                _geometry_metrics(run_dir)

    def test_geometry_metrics_rejects_an_undeclared_registered_image(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _geometry_metrics

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference",
                "--adapter",
                "colmap-mvs",
                "--profile",
                "smoke",
                "--run-id",
                "mvs-undeclared-image",
                cache=cache,
                engine=fake_mvs_engine(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "reference-runs/mvs-undeclared-image/colmap-mvs"
            images = run_dir / "output/sparse/0/images.txt"
            with images.open("a", encoding="utf-8") as stream:
                stream.write("999 1 0 0 0 0 0 0 1 intruder.pgm\n\n")
            with self.assertRaisesRegex(ValueError, "not declared"):
                _geometry_metrics(run_dir)

    def test_placeholder_database_and_binary_models_are_rejected(self) -> None:
        import sqlite3
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _validate_colmap_binary_model, _validate_mvs_database

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "database.db"
            connection = sqlite3.connect(database)
            for table in ("cameras", "images", "keypoints", "descriptors", "matches", "two_view_geometries"):
                connection.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
            connection.commit()
            connection.close()
            with self.assertRaisesRegex(ValueError, "schema mismatch"):
                _validate_mvs_database(database, {"frame-000.pgm"})

            model = root / "model"
            model.mkdir()
            for name in ("cameras.bin", "images.bin", "points3D.bin"):
                (model / name).write_bytes(b"placeholder")
            with self.assertRaisesRegex(ValueError, "COLMAP binary"):
                _validate_colmap_binary_model(model, {"frame-000.pgm"}, 1)

    def test_fused_points_require_oriented_normals(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _read_ply_xyz

        with tempfile.TemporaryDirectory() as temporary:
            fused = Path(temporary) / "fused.ply"
            fused.write_text(
                "ply\nformat ascii 1.0\nelement vertex 1\n"
                "property float x\nproperty float y\nproperty float z\nend_header\n0 0 1\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "oriented normals"):
                _read_ply_xyz(fused, require_normals=True)

    def test_monitor_drains_verbose_child_output_without_pipe_deadlock(self) -> None:
        """COLMAP logs can exceed pipe capacity before the monitored process exits."""
        helper = textwrap.dedent(
            f"""\
            import sys
            sys.path.insert(0, {str(ROOT / "pipeline")!r})
            import mvs_reference_runner
            mvs_reference_runner._gpu_process_memory_bytes = lambda _container_id: 0
            command = [
                sys.executable,
                "-c",
                "import os; os.write(1, b'x' * 2_000_000); os.write(2, b'y' * 2_000_000)",
            ]
            completed, peak_gpu = mvs_reference_runner._run_monitored(command)
            assert completed.returncode == 0
            assert len(completed.stdout) == 2_000_000
            assert len(completed.stderr) == 2_000_000
            assert peak_gpu == 0
            """
        )
        completed = subprocess.run(
            [sys.executable, "-c", helper],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_gpu_memory_counts_only_processes_in_the_run_container(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        import mvs_reference_runner

        container_id = "a" * 64
        with tempfile.TemporaryDirectory() as temporary:
            proc_root = Path(temporary)
            for pid, cgroup in {
                101: f"0::/docker/{container_id}\n",
                202: f"0::/docker/{'b' * 64}\n",
            }.items():
                (proc_root / str(pid)).mkdir()
                (proc_root / str(pid) / "cgroup").write_text(cgroup, encoding="utf-8")
            completed = subprocess.CompletedProcess(
                ["nvidia-smi"],
                0,
                "101, 2048\n202, 8192\n",
                "",
            )
            with (
                mock.patch.object(mvs_reference_runner.shutil, "which", return_value="/usr/bin/nvidia-smi"),
                mock.patch.object(mvs_reference_runner.subprocess, "run", return_value=completed),
            ):
                measured = mvs_reference_runner._gpu_process_memory_bytes(container_id, proc_root)
        self.assertEqual(measured, 2048 * 1024 * 1024)

    def test_cpu_memory_parser_accepts_gnu_time_verbose_indentation(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import _peak_cpu_memory_bytes

        with tempfile.TemporaryDirectory() as temporary:
            resource = Path(temporary) / "resource-usage.txt"
            resource.write_text("\tMaximum resident set size (kbytes): 3412\n", encoding="utf-8")
            self.assertEqual(_peak_cpu_memory_bytes(resource), 3412 * 1024)

    def test_pinned_release_contains_the_upstream_blackwell_patchmatch_fix(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from mvs_reference_runner import PINNED_COLMAP_COMMIT, PINNED_COLMAP_VERSION

        self.assertEqual(PINNED_COLMAP_VERSION, "4.2.0")
        self.assertEqual(PINNED_COLMAP_COMMIT, "be5e29168d4aff238409d60424812df66aac919f")
        dockerfile = (ROOT / "insulas/classical-mvs/Dockerfile").read_text(encoding="utf-8")
        self.assertIn(f"ARG COLMAP_GIT_COMMIT={PINNED_COLMAP_COMMIT}", dockerfile)
        self.assertIn("libopenimageio-dev", dockerfile)
        self.assertIn("RUN mkdir -p /usr/include/opencv4", dockerfile)

    def test_controlled_scene_uses_unique_tile_appearance_for_pose_observability(self) -> None:
        scene = json.loads((ROOT / "shared-scene.json").read_text())
        fixture = scene["reference_fixture"]
        tile_count = len(fixture["tile_center_x_angles"]) * len(fixture["tile_center_y_angles"])
        self.assertEqual(fixture["texture_count"], tile_count + 1)
        self.assertEqual(fixture["tile_texture_assignment"], "unique-per-tile")
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from reference_scene import _scene_textures

        textures = _scene_textures(scene)
        self.assertEqual(textures[0].shape, (1024, 1024))
        self.assertEqual({texture.shape for texture in textures[1:]}, {(256, 256)})

    def test_reference_plan_declares_dense_mvs_as_offline(self) -> None:
        """Removing the MVS CLI route must make the public dispatch contract fail."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = run_cli(
                "--emit-plan",
                "reference",
                "--adapter",
                "colmap-mvs",
                "--profile",
                "smoke",
                "--run-id",
                "mvs-plan",
                cache=root / "cache",
                engine=fake_engine(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                json.loads(completed.stdout),
                {
                    "adapter": "colmap-mvs",
                    "command": "reference",
                    "network_mode": "offline",
                    "profile": "smoke",
                    "run_id": "mvs-plan",
                    "schema_version": 1,
                },
            )

    def test_mvs_scene_emits_deterministic_metric_depth_and_visible_surface_truth(self) -> None:
        """Dropping metric GT generation must break the dense-geometry evaluation contract."""
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from contracts import load_json
        import reference_scene

        self.assertTrue(hasattr(reference_scene, "generate_colmap_mvs_scene"))
        generate_colmap_mvs_scene = reference_scene.generate_colmap_mvs_scene

        scene = load_json(ROOT / "shared-scene.json")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = generate_colmap_mvs_scene(root / "first", scene, "smoke")
            second = generate_colmap_mvs_scene(root / "second", scene, "smoke")

            self.assertEqual(first, second)
            self.assertEqual(first["ground_truth"]["units"], "metres")
            self.assertEqual(first["ground_truth"]["sample_stride_pixels"], 4)
            self.assertEqual(first["ground_truth"]["visible_surface"]["format"], "ply-ascii-xyz")
            self.assertGreater(first["ground_truth"]["visible_surface"]["vertex_count"], 90_000)
            self.assertEqual(len(first["frames"]), 5)

            for first_frame, second_frame in zip(first["frames"], second["frames"]):
                self.assertEqual(first_frame["depth_sha256"], second_frame["depth_sha256"])
                depth = np.load(root / "first" / first_frame["depth_name"])
                self.assertEqual(depth.shape, (480, 640))
                self.assertEqual(depth.dtype, np.float32)
                self.assertTrue(np.isfinite(depth).all())
                self.assertAlmostEqual(float(depth[239, 319]), 4.35, places=5)
                self.assertGreaterEqual(float(depth.min()), 2.7)
                self.assertEqual(float(depth.max()), 6.0)

            truth = root / "first" / first["ground_truth"]["visible_surface"]["path"]
            header = truth.read_bytes().split(b"end_header\n", 1)[0].decode("ascii")
            self.assertIn(
                f"element vertex {first['ground_truth']['visible_surface']['vertex_count']}",
                header,
            )

    def test_full_manifest_cannot_be_validated_as_smoke(self) -> None:
        from sys import path as import_path

        import_path.insert(0, str(ROOT / "pipeline"))
        from contracts import load_json
        from mvs_reference_runner import _validate_manifest_contract
        from reference_scene import generate_colmap_mvs_scene

        with tempfile.TemporaryDirectory() as temporary:
            manifest = generate_colmap_mvs_scene(
                Path(temporary) / "scene", load_json(ROOT / "shared-scene.json"), "full"
            )
            with self.assertRaisesRegex(ValueError, "profile contract"):
                _validate_manifest_contract(manifest, "smoke")

    def test_smoke_reference_scores_dense_geometry_and_promotes_atomically(self) -> None:
        """Removing real dense artifacts or metric scoring must fail the maintained reference contract."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference",
                "--adapter",
                "colmap-mvs",
                "--profile",
                "smoke",
                "--run-id",
                "mvs-smoke",
                cache=cache,
                engine=fake_mvs_engine(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "reference-runs" / "mvs-smoke" / "colmap-mvs"
            result = json.loads((run_dir / "result.json").read_text())
            self.assertEqual(result["adapter"], "colmap-mvs")
            self.assertEqual(result["module_ids"], ["06"])
            self.assertEqual(result["network_mode"], "offline")
            self.assertEqual(result["tool"]["source_commit"], COLMAP_MVS_COMMIT)
            self.assertEqual(result["metrics"]["registered_images"], 5)
            self.assertEqual(result["metrics"]["sparse_points"], 2000)
            self.assertEqual(result["metrics"]["dense_points"], 96_000)
            self.assertEqual(result["metrics"]["mesh_faces"], 2000)
            self.assertLess(result["metrics"]["camera_alignment_rmse_m"], 1e-10)
            self.assertLess(result["metrics"]["accuracy_mean_m"], 1e-7)
            self.assertLess(result["metrics"]["completeness_mean_m"], 1e-7)
            self.assertEqual(result["metrics"]["fscore_10cm"], 1.0)
            for relative in (
                "input/ground-truth-visible.ply",
                "output/dense/fused.ply",
                "output/dense/meshed-poisson.ply",
                "output/source-commit.txt",
                "output/insula-manifest.txt",
                "output/resource-summary.json",
                "adapter.log",
                "report.md",
            ):
                self.assertTrue((run_dir / relative).is_file(), relative)
            self.assertFalse(any((cache / "reference-staging").glob("*")))

            from sys import path as import_path

            import_path.insert(0, str(ROOT / "pipeline"))
            from mvs_reference_runner import validate_mvs_reference_result

            validate_mvs_reference_result(run_dir)
            self.assertNotIn("visible-support failure", (run_dir / "report.md").read_text())

            result["resources"]["peak_cpu_memory_bytes"] = 1
            (run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "resource summary mismatch"):
                validate_mvs_reference_result(run_dir)

    def test_full_reference_uses_nine_views_and_full_acceptance(self) -> None:
        """Collapsing full MVS to the smoke view set must fail profile parity."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference",
                "--adapter",
                "colmap-mvs",
                "--profile",
                "full",
                "--run-id",
                "mvs-full",
                cache=cache,
                engine=fake_mvs_engine(root),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(
                (cache / "reference-runs/mvs-full/colmap-mvs/result.json").read_text()
            )
            self.assertEqual(result["metrics"]["registered_images"], 9)
            self.assertEqual(result["metrics"]["dense_points"], 172_800)
            self.assertEqual(result["acceptance"]["registered_images_min"], 7)

    def test_reference_rejects_dense_support_below_the_registry_threshold(self) -> None:
        """Removing most fused points must prevent atomic promotion."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            completed = run_cli(
                "reference",
                "--adapter",
                "colmap-mvs",
                "--profile",
                "smoke",
                "--run-id",
                "mvs-too-sparse",
                cache=cache,
                engine=fake_mvs_engine(root),
                extra_env={"FAKE_MVS_DENSE_LIMIT": "500"},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("below the locked acceptance threshold", completed.stderr)
            self.assertFalse((cache / "reference-runs/mvs-too-sparse").exists())
            self.assertFalse(any((cache / "reference-staging").glob("*")))

    def test_real_colmap_mvs_reconstructs_and_meshes_the_smoke_scene(self) -> None:
        require_real = os.environ.get("SURFLO_REQUIRE_COLMAP_MVS_REFERENCE") == "1"
        docker = shutil.which("docker")
        if docker is None:
            if require_real:
                self.fail("SURFLO_REQUIRE_COLMAP_MVS_REFERENCE=1 but Docker is unavailable")
            self.skipTest("Docker is unavailable")
        image = subprocess.run(
            [docker, "image", "inspect", "surflo-pathway-classical-mvs:1"],
            text=True,
            capture_output=True,
            check=False,
        )
        if image.returncode != 0:
            if require_real:
                self.fail("SURFLO_REQUIRE_COLMAP_MVS_REFERENCE=1 but the MVS Insula is not built")
            self.skipTest("MVS Insula is not built")
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            completed = run_cli(
                "reference",
                "--adapter",
                "colmap-mvs",
                "--profile",
                "smoke",
                "--run-id",
                "real-colmap-mvs",
                cache=cache,
                engine=Path(docker),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(
                (cache / "reference-runs/real-colmap-mvs/colmap-mvs/result.json").read_text()
            )
            self.assertEqual(result["tool"]["source_commit"], COLMAP_MVS_COMMIT)
            self.assertGreaterEqual(result["metrics"]["dense_points"], 10_000)
            self.assertGreaterEqual(result["metrics"]["mesh_faces"], 1_000)
            self.assertGreaterEqual(result["metrics"]["fscore_10cm"], 0.25)

    def test_real_colmap_mvs_full_profile_on_b200(self) -> None:
        if os.environ.get("SURFLO_REQUIRE_COLMAP_MVS_FULL") != "1":
            self.skipTest("set SURFLO_REQUIRE_COLMAP_MVS_FULL=1 for the B200 full-profile gate")
        docker = shutil.which("docker")
        if docker is None:
            self.fail("SURFLO_REQUIRE_COLMAP_MVS_FULL=1 but Docker is unavailable")
        image = subprocess.run(
            [docker, "image", "inspect", "surflo-pathway-classical-mvs:1"],
            text=True,
            capture_output=True,
            check=False,
        )
        if image.returncode != 0:
            self.fail("SURFLO_REQUIRE_COLMAP_MVS_FULL=1 but the MVS Insula is not built")
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            completed = run_cli(
                "reference",
                "--adapter",
                "colmap-mvs",
                "--profile",
                "full",
                "--run-id",
                "real-colmap-mvs-full",
                cache=cache,
                engine=Path(docker),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(
                (cache / "reference-runs/real-colmap-mvs-full/colmap-mvs/result.json").read_text()
            )
            self.assertEqual(result["metrics"]["registered_images"], 9)
            self.assertGreaterEqual(result["metrics"]["dense_points"], 20_000)
            self.assertGreaterEqual(result["metrics"]["mesh_faces"], 1_000)
            self.assertGreaterEqual(result["metrics"]["fscore_10cm"], 0.30)
            self.assertEqual(result["resources"]["gpu_measurement_status"], "measured")


if __name__ == "__main__":
    unittest.main()
