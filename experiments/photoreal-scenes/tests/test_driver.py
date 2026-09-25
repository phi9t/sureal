from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))


class RenderDriverTest(unittest.TestCase):
    def test_episode_publish_is_atomic_hardlinked_and_requires_overwrite(self) -> None:
        try:
            import exchange
        except ModuleNotFoundError as error:
            self.fail(f"exchange publisher is missing: {error}")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "runs" / "fixture"
            (source / "scene_a").mkdir(parents=True)
            original = source / "manifest.json"
            original.write_text("{}\n", encoding="utf-8")
            (source / "scene_a" / "surface.npz").write_bytes(b"surface")
            context_a = source / "scene_a" / "context.png"
            context_a.write_bytes(b"shared")
            context_b = source / "scene_b" / "context.png"
            context_b.parent.mkdir()
            os.link(context_a, context_b)
            artifacts = {
                str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(source.rglob("*"))
                if path.is_file()
            }
            (source / "validation.json").write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "episode_manifest_sha256": artifacts["manifest.json"],
                        "artifact_sha256": artifacts,
                    }
                ),
                encoding="utf-8",
            )
            destination = exchange.publish_episode(
                source, root / "exchange", "fixture", overwrite=False
            )
            published = destination / "manifest.json"
            self.assertEqual(os.stat(original).st_ino, os.stat(published).st_ino)
            self.assertTrue(
                os.path.samefile(
                    destination / "scene_a" / "context.png",
                    destination / "scene_b" / "context.png",
                )
            )
            with self.assertRaises(FileExistsError):
                exchange.publish_episode(
                    source, root / "exchange", "fixture", overwrite=False
                )
            exchange.publish_episode(source, root / "exchange", "fixture", overwrite=True)
            self.assertTrue((destination / "validation.json").is_file())
            (source / "scene_a" / "surface.npz").write_bytes(b"corrupt")
            with self.assertRaisesRegex(RuntimeError, "stale validation"):
                exchange.publish_episode(
                    source, root / "exchange", "fixture", overwrite=True
                )

    def test_probe_plan_is_offline_and_uses_surflo_exchange_episode(self) -> None:
        import json
        import subprocess

        result = subprocess.run(
            [str(ROOT / "probe.sh"), "--emit-plan", "--run-id", "fixture"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["run_id"], "fixture")
        self.assertEqual(plan["publisher_network_mode"], "offline")
        self.assertEqual(plan["surflo_network_mode"], "offline")
        self.assertEqual(
            plan["episode"], "/cache/surflo/photoreal-scenes/episodes/fixture"
        )
        self.assertEqual(plan["seeds"], [0, 1, 2, 3])
        self.assertEqual(plan["num_query_points"], 100_000)
        self.assertEqual(plan["num_steps"], 100)
        self.assertFalse(plan["overwrite"])
        self.assertFalse(plan["update_tracked_results"])

        explicit = subprocess.run(
            [
                str(ROOT / "probe.sh"),
                "--emit-plan",
                "--run-id",
                "fixture",
                "--overwrite",
                "--update-tracked-results",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        explicit_plan = json.loads(explicit.stdout)
        self.assertTrue(explicit_plan["overwrite"])
        self.assertTrue(explicit_plan["update_tracked_results"])

    def test_blender_command_is_headless_and_carries_explicit_contract(self) -> None:
        try:
            import driver
        except ModuleNotFoundError as error:
            self.fail(f"render driver is missing: {error}")
        command = driver.blender_command(
            output=Path("/cache/blender/runs/.episode.tmp"),
            asset_root=Path("/cache/blender/assets"),
            profile="draft",
            device="CPU",
            seed=20260925,
        )
        self.assertEqual(command[:3], ["blender", "--background", "--factory-startup"])
        self.assertIn("--python", command)
        self.assertEqual(command[command.index("--profile") + 1], "draft")
        self.assertEqual(command[command.index("--device") + 1], "CPU")
        self.assertEqual(command[command.index("--seed") + 1], "20260925")

    def test_offline_render_verifies_assets_before_blender_or_staging(self) -> None:
        try:
            import driver
        except ModuleNotFoundError as error:
            self.fail(f"render driver is missing: {error}")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            invoked = []

            def runner(*_args, **_kwargs):
                invoked.append(True)
                raise AssertionError("Blender must not run with missing assets")

            with self.assertRaisesRegex(FileNotFoundError, "missing locked asset"):
                driver.render_episode(
                    profile="draft",
                    device="CPU",
                    run_id="fixture",
                    overwrite=False,
                    asset_root=root / "assets",
                    run_root=root / "runs",
                    runner=runner,
                )
            self.assertEqual(invoked, [])
            self.assertFalse((root / "runs").exists())

    def test_driver_rejects_zero_exit_without_renderer_success_record(self) -> None:
        import driver

        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertTrue(hasattr(driver, "require_renderer_job"))
            with self.assertRaisesRegex(RuntimeError, "success record"):
                driver.require_renderer_job(Path(temp_dir))

    def test_blender_job_bootstrap_resolves_sibling_modules(self) -> None:
        blender = shutil.which("blender")
        if blender is None:
            self.skipTest("Blender is exercised in the Blender Insula")
        import subprocess

        result = subprocess.run(
            [
                blender,
                "--background",
                "--factory-startup",
                "--python",
                str(ROOT / "pipeline" / "blender_job.py"),
                "--",
                "--help",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        self.assertIn("usage:", output)
        self.assertIn("--output", output)

    def test_blender_constructs_complete_scene_from_locked_assets(self) -> None:
        blender = shutil.which("blender")
        asset_root = Path(os.environ.get("PHOTOREAL_ASSET_ROOT", "/missing"))
        if blender is None or not (asset_root / "Sofa_01" / "Sofa_01_2k.gltf").is_file():
            self.skipTest("Blender and fetched assets are exercised in the Blender Insula")
        import subprocess

        result = subprocess.run(
            [
                blender,
                "--background",
                "--factory-startup",
                "--python",
                str(ROOT / "tests" / "blender_scene_smoke.py"),
                "--",
                str(asset_root),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        self.assertIn("SCENE_SMOKE_OK", output, output)
        self.assertNotIn("Traceback", output)

    def test_draft_cpu_dispatch_is_explicit_and_offline(self) -> None:
        result = __import__("subprocess").run(
            [str(ROOT / "run.sh"), "--emit-plan", "render-draft", "--device", "CPU"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        import json

        plan = json.loads(result.stdout)
        self.assertEqual(plan["network_mode"], "offline")
        self.assertEqual(plan["profile"], "draft")
        self.assertEqual(plan["device"], "CPU")


if __name__ == "__main__":
    unittest.main()
