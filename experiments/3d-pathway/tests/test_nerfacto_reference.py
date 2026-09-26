from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
NERFSTUDIO_COMMIT = "50e0e3c70c775e89333256213363badbf074f29d"
TCNN_COMMIT = "0109538c37ac0bf613f2bac8de6cda48352feca7"
NERF_SYNTHETIC_SHA256 = "ce4e94e031c099a19ef04cfb6c71f1e47225d97d365be610b476e379a386c25f"


class NerfactoReferenceFoundationTest(unittest.TestCase):
    def test_primary_source_is_registered_for_module_10(self) -> None:
        sources = {
            item["id"]: item
            for item in json.loads((ROOT / "sources.json").read_text())["sources"]
        }
        self.assertIn("nerfstudio-nerfacto-2025", sources)
        implementation = sources["nerfstudio-nerfacto-2025"]
        self.assertEqual(
            implementation["primary_url"],
            f"https://github.com/nerfstudio-project/nerfstudio/tree/{NERFSTUDIO_COMMIT}",
        )
        self.assertIn("per-scene radiance field", implementation["claims"][0])

        curriculum = {
            item["id"]: item
            for item in json.loads((ROOT / "curriculum.json").read_text())["modules"]
        }
        self.assertIn("nerfstudio-nerfacto-2025", curriculum["10"]["sources"])

    def test_adapter_keeps_rendering_and_geometry_contracts_separate(self) -> None:
        adapters = {
            item["id"]: item
            for item in json.loads((ROOT / "reference-adapters.json").read_text())["adapters"]
        }
        self.assertIn("nerfstudio-nerfacto-reference", adapters)
        adapter = adapters["nerfstudio-nerfacto-reference"]
        self.assertEqual(adapter["status"], "not_landed")
        self.assertEqual(
            adapter["command"],
            "run.sh reference --adapter nerfacto --profile smoke --run-id ID",
        )
        self.assertEqual(adapter["modules"], ["10"])
        self.assertEqual(adapter["model_contract"]["method"], "nerfacto")
        self.assertEqual(adapter["model_contract"]["inference"], "per-scene-optimization")
        self.assertFalse(adapter["model_contract"]["completion_claim"])
        self.assertFalse(adapter["model_contract"]["posterior_sampling_claim"])
        self.assertEqual(
            adapter["evaluation_contract"]["rendering"],
            "held-out target RGB; separate from geometry",
        )
        self.assertEqual(
            adapter["evaluation_contract"]["geometry"],
            "held-out depth restricted to common-visible analytic truth",
        )
        self.assertEqual(
            adapter["evaluation_contract"]["surface_comparator"],
            "module 09 NeuS-Facto baseline on the identical controlled scene",
        )

    def test_nerf_synthetic_archive_has_a_verified_lock(self) -> None:
        assets = {
            item["id"]: item
            for item in json.loads((ROOT / "assets.lock.json").read_text())["assets"]
        }
        archive = assets["nerf-synthetic"]
        self.assertEqual(archive["sha256"], NERF_SYNTHETIC_SHA256)
        self.assertEqual(archive["byte_size"], 370385516)
        self.assertEqual(archive["digest_status"], "verified_2026-09-26")
        self.assertEqual(archive["extraction"], "safe-zip")
        self.assertEqual(archive["consumers"], ["nerfstudio-nerfacto-reference"])

    def test_radiance_field_environment_is_blackwell_pinned(self) -> None:
        locks = json.loads((ROOT / "insulas/locks.json").read_text())["insulas"]
        self.assertIn("radiance-field", locks)
        radiance = locks["radiance-field"]
        self.assertEqual(radiance["nerfstudio_source_commit"], NERFSTUDIO_COMMIT)
        self.assertEqual(radiance["tiny_cuda_nn_source_commit"], TCNN_COMMIT)
        self.assertEqual(radiance["tcnn_cuda_architectures"], "100")
        self.assertEqual(radiance["pytorch"], "2.7.1+cu128")

if __name__ == "__main__":
    unittest.main()
