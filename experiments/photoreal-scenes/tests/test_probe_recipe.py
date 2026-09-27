from __future__ import annotations

import json
import importlib.util
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _load_summary_module():
    path = ROOT / "pipeline" / "probe_summary.py"
    if not path.is_file():
        raise AssertionError(f"probe summary module is missing: {path}")
    spec = importlib.util.spec_from_file_location("photoreal_probe_summary", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_recipe_module():
    path = ROOT / "verify_recipe.py"
    spec = importlib.util.spec_from_file_location("photoreal_verify_recipe", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_provenance_module():
    path = ROOT / "pipeline" / "provenance.py"
    if not path.is_file():
        raise AssertionError(f"provenance module is missing: {path}")
    spec = importlib.util.spec_from_file_location("photoreal_provenance", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PhotorealRecipeTest(unittest.TestCase):
    def test_strict_evidence_rejects_artifact_changed_after_validation(self) -> None:
        verifier = _load_recipe_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = root / "manifest.json"
            payload = root / "payload.bin"
            manifest.write_text("{}\n", encoding="utf-8")
            payload.write_bytes(b"original")
            artifacts = {
                item.name: hashlib.sha256(item.read_bytes()).hexdigest()
                for item in (manifest, payload)
            }
            validation = root / "validation.json"
            validation.write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "episode_manifest_sha256": artifacts["manifest.json"],
                        "artifact_sha256": artifacts,
                    }
                ),
                encoding="utf-8",
            )
            verifier._verify_validation_report(validation, root)
            payload.write_bytes(b"changed")
            with self.assertRaisesRegex(verifier.RecipeError, "artifact hash mismatch"):
                verifier._verify_validation_report(validation, root)

    def _write_self_contained_recipe(
        self, root: Path, *, tracked_results: dict[str, object]
    ) -> Path:
        tracked_results = json.loads(json.dumps(tracked_results))
        recipe = json.loads((ROOT / "recipe.json").read_text(encoding="utf-8"))
        recipe["executor"] = str(ROOT / "run.sh")
        recipe["renderer_insula"]["build"] = str(ROOT / "build.sh")
        recipe["renderer_insula"]["enter"] = str(ROOT / "enter.sh")
        recipe["renderer_insula"]["dockerfile"] = str(ROOT / "insula" / "Dockerfile")
        recipe["surflo_insula"]["enter"] = str(ROOT.parent / "insula-scout" / "enter.sh")
        recipe["surflo_insula"]["probe"] = str(
            ROOT.parent / "insula-scout" / "synthetic_ambiguity" / "probe.py"
        )
        recipe["assets"]["lock"] = str(ROOT / "assets.lock.json")
        recipe["probe"]["model_lock"] = str(ROOT / "model.lock.json")
        recipe["analytic_baseline"] = str(ROOT.parent / "insula-scout" / "synthetic_results.json")
        provenance = _load_provenance_module()
        declared = recipe["source"]["implementation_files"]
        absolute_sources = sorted(
            str((ROOT / item).resolve()) if not Path(item).is_absolute() else item
            for item in declared
        )
        recipe["source"]["implementation_files"] = absolute_sources
        recipe["source"]["implementation_sha256"] = (
            provenance.compute_implementation_sha256(root, absolute_sources)
        )
        tracked_results["source"] = {
            "base_revision": recipe["source"]["base_revision"],
            "implementation_sha256": recipe["source"]["implementation_sha256"],
            "worktree_state": recipe["source"]["worktree_state"],
        }
        results_path = root / "results.json"
        results_path.write_text(json.dumps(tracked_results), encoding="utf-8")
        recipe["evidence"]["tracked_results"] = str(results_path)
        recipe_path = root / "recipe.json"
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        return recipe_path

    def test_compact_results_capture_all_measurements_without_outcome_gate(self) -> None:
        summary = _load_summary_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_path = root / "raw.json"
            manifest_path = root / "manifest.json"
            validation_path = root / "validation.json"
            baseline_path = root / "baseline.json"
            raw_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "episode_manifest_sha256": "a" * 64,
                        "checkpoint": {"sha256": "b" * 64},
                        "vggt": {
                            "repository": "facebook/VGGT-1B",
                            "revision": "c" * 40,
                            "files": {
                                "config.json": "d" * 64,
                                "model.safetensors": "e" * 64,
                            },
                        },
                        "source": {
                            "base_revision": "f" * 40,
                            "implementation_sha256": "1" * 64,
                            "worktree_state": "uncommitted_overlay",
                        },
                        "settings": {
                            "inference_mode": "plain",
                            "seeds": [0, 1, 2, 3],
                            "num_query_points": 100000,
                            "num_steps": 100,
                        },
                        "runs": [
                            {
                                "seed": seed,
                                "wall_seconds": 10.0 + seed,
                                "peak_vram_gib": 8.0,
                                "camera_rmse_after_observed_alignment": 0.01,
                                "observed_common_recall": 0.8,
                                "unobserved_common_recall": 0.4,
                                "exclusive_hidden_support_a": 0.0,
                                "exclusive_hidden_support_b": 0.0,
                                "completion_candidate_precision_to_either_hypothesis": 0.0,
                                "hypothesis": {"label": "unsupported"},
                            }
                            for seed in range(4)
                        ],
                        "aggregate": {
                            "labels": ["unsupported"] * 4,
                            "baseline_behavior": "no_supported_hidden_completion",
                        },
                    }
                ),
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "renderer": {"profile": "benchmark", "device": "OPTIX"},
                        "scenes": {
                            "scene_a": {"visibility": {"hidden_object_target_fraction": 0.6}},
                            "scene_b": {"visibility": {"hidden_object_target_fraction": 0.3}},
                        },
                    }
                ),
                encoding="utf-8",
            )
            baseline_path.write_text(
                json.dumps(
                    {"aggregate": {"baseline_behavior": "at_least_one_hybrid_completion"}}
                ),
                encoding="utf-8",
            )
            raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
            raw_payload["episode_manifest_sha256"] = hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()
            raw_path.write_text(json.dumps(raw_payload), encoding="utf-8")
            expected_raw_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
            validation_path.write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "episode_manifest_sha256": hashlib.sha256(
                            manifest_path.read_bytes()
                        ).hexdigest(),
                        "artifact_sha256": {
                            "manifest.json": hashlib.sha256(
                                manifest_path.read_bytes()
                            ).hexdigest()
                        },
                    }
                ),
                encoding="utf-8",
            )
            payload = summary.build_summary(
                raw_path,
                manifest_path,
                validation_path,
                baseline_path,
                measurement_date_utc="2026-09-25",
            )
            expected_validation_sha = hashlib.sha256(validation_path.read_bytes()).hexdigest()
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["measurement_date_utc"], "2026-09-25")
        self.assertNotIn("date_utc", payload)
        self.assertTrue(payload["acceptance"]["valid_measurements"])
        self.assertEqual([run["seed"] for run in payload["runs"]], [0, 1, 2, 3])
        self.assertEqual(payload["runs"][0]["support_label"], "unsupported")
        self.assertNotIn("label", payload["runs"][0])
        self.assertEqual(payload["aggregate"]["support_labels"], ["unsupported"] * 4)
        self.assertNotIn("labels", payload["aggregate"])
        self.assertEqual(payload["artifacts"]["raw_results_sha256"], expected_raw_sha)
        self.assertEqual(
            payload["artifacts"]["validation_report_sha256"],
            expected_validation_sha,
        )
        self.assertEqual(
            payload["comparison"]["analytic_baseline_behavior"],
            "at_least_one_hybrid_completion",
        )
        self.assertEqual(payload["model_provenance"]["checkpoint_sha256"], "b" * 64)
        self.assertEqual(payload["model_provenance"]["vggt"]["revision"], "c" * 40)
        self.assertEqual(payload["source"]["implementation_sha256"], "1" * 64)

    def test_recipe_rejects_legacy_derived_summary_schema(self) -> None:
        verifier = _load_recipe_module()
        tracked = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
        tracked["schema_version"] = 1
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recipe_path = self._write_self_contained_recipe(
                root, tracked_results=tracked
            )
            with self.assertRaisesRegex(
                verifier.RecipeError, "derived results must use schema version 2"
            ):
                verifier.validate_recipe(recipe_path, cache_root=root / "cache")

    def test_recipe_declares_a_recomputed_source_overlay(self) -> None:
        provenance = _load_provenance_module()
        recipe_path = ROOT / "recipe.json"
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        source = recipe["source"]
        self.assertEqual(source["worktree_state"], "uncommitted_overlay")
        self.assertNotIn("revision", source)
        self.assertEqual(
            source["implementation_sha256"],
            provenance.compute_implementation_sha256(
                recipe_path.parent, source["implementation_files"]
            ),
        )

    def test_recipe_rejects_model_pin_not_used_by_tracked_results(self) -> None:
        tracked = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recipe_path = self._write_self_contained_recipe(root, tracked_results=tracked)
            recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
            model_lock = json.loads((ROOT / "model.lock.json").read_text(encoding="utf-8"))
            model_lock["checkpoint"]["sha256"] = "0" * 64
            changed_lock = root / "changed-model.lock.json"
            changed_lock.write_text(json.dumps(model_lock), encoding="utf-8")
            recipe["probe"]["model_lock"] = str(changed_lock)
            recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "verify_recipe.py"),
                    "--recipe",
                    str(recipe_path),
                    "--cache-root",
                    temp_dir,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checkpoint pin does not match tracked evidence", result.stderr)

    def test_recipe_rejects_raw_model_or_source_provenance_mismatch(self) -> None:
        tracked = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
        for changed, message in (
            ("vggt", "VGGT pins do not match raw probe evidence"),
            ("source", "source overlay does not match raw probe evidence"),
        ):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                recipe_path = self._write_self_contained_recipe(root, tracked_results=tracked)
                recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
                tracked_fixture = json.loads((root / "results.json").read_text(encoding="utf-8"))
                raw = {
                    "settings": {"inference_mode": "plain"},
                    "checkpoint": {
                        "sha256": tracked_fixture["model_provenance"]["checkpoint_sha256"]
                    },
                    "vggt": json.loads(
                        json.dumps(tracked_fixture["model_provenance"]["vggt"])
                    ),
                    "source": json.loads(json.dumps(tracked_fixture["source"])),
                }
                if changed == "vggt":
                    raw["vggt"]["revision"] = "0" * 40
                else:
                    raw["source"]["implementation_sha256"] = "0" * 64
                cache_root = root / "cache"
                raw_path = cache_root / recipe["evidence"]["probe_results_cache_path"]
                raw_path.parent.mkdir(parents=True)
                raw_path.write_text(json.dumps(raw), encoding="utf-8")
                tracked_fixture["artifacts"]["raw_results_sha256"] = hashlib.sha256(
                    raw_path.read_bytes()
                ).hexdigest()
                (root / "results.json").write_text(
                    json.dumps(tracked_fixture), encoding="utf-8"
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "verify_recipe.py"),
                        "--recipe",
                        str(recipe_path),
                        "--cache-root",
                        str(cache_root),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)

    def test_tracked_recipe_validates_without_cached_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "verify_recipe.py"),
                    "--recipe",
                    str(ROOT / "recipe.json"),
                    "--cache-root",
                    temp_dir,
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(
            [stage["id"] for stage in payload["stages"]],
            ["build", "fetch", "render", "validate", "probe"],
        )
        self.assertEqual(payload["probe"]["inference_mode"], "plain")
        self.assertEqual(payload["probe"]["seeds"], [0, 1, 2, 3])
        self.assertEqual(payload["probe"]["num_query_points"], 100_000)
        self.assertEqual(payload["probe"]["num_steps"], 100)
        self.assertFalse(payload["artifacts"]["episode_manifest"]["present"])
        self.assertFalse(payload["artifacts"]["probe_results"]["present"])
        self.assertEqual(
            payload["analytic_baseline"]["baseline_behavior"],
            "at_least_one_hybrid_completion",
        )

    def test_recipe_rejects_cpu_benchmark_or_nonoffline_probe(self) -> None:
        recipe = ROOT / "recipe.json"
        self.assertTrue(recipe.is_file(), recipe)
        for field, value, message in (
            ("device", "CPU", "OPTIX"),
            ("probe_network_mode", "networked", "offline"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                invalid = self._write_self_contained_recipe(
                    root,
                    tracked_results=json.loads((ROOT / "results.json").read_text(encoding="utf-8")),
                )
                payload = json.loads(invalid.read_text(encoding="utf-8"))
                if field == "device":
                    payload["episode"]["device"] = value
                else:
                    next(stage for stage in payload["stages"] if stage["id"] == "probe")[
                        "network_mode"
                    ] = value
                invalid.write_text(json.dumps(payload), encoding="utf-8")
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "verify_recipe.py"),
                        "--recipe",
                        str(invalid),
                        "--cache-root",
                        temp_dir,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_recipe_rejects_pass_results_from_nonbenchmark_episode(self) -> None:
        baseline = json.loads(
            (ROOT.parent / "insula-scout" / "synthetic_results.json").read_text(
                encoding="utf-8"
            )
        )["aggregate"]["baseline_behavior"]
        tracked = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
        tracked["episode"]["profile"] = "draft"
        tracked["episode"]["device"] = "CPU"
        tracked["comparison"]["analytic_baseline_behavior"] = baseline
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recipe_path = self._write_self_contained_recipe(root, tracked_results=tracked)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "verify_recipe.py"),
                    "--recipe",
                    str(recipe_path),
                    "--cache-root",
                    temp_dir,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tracked pass results must use benchmark OPTIX", result.stderr)


if __name__ == "__main__":
    unittest.main()
