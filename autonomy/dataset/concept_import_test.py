import importlib
import unittest


DATASET_MODULES = [
    "cohort_checkpoint",
    "cohort_resume",
    "cohort_selection",
    "bounded_sidecar_eviction",
    "component_archive",
    "component_archive_validate",
    "compressed_component_archive",
    "compressed_component_archive_validate",
    "compressed_sidecar_eviction",
    "scientific_admission",
    "scientific_component",
    "scientific_dataset",
    "scientific_preparation",
    "scientific_publication",
    "scientific_sidecar_reader",
    "scientific_sidecar_validate",
    "scientific_sidecars",
    "scene_archive",
    "scene_archive_validate",
    "sensor_records",
    "shard_inventory",
    "sidecar_eviction",
    "source_integrity",
    "staged_source",
    "tfrecord_reader",
    "verified_eviction",
]


class DatasetConceptImportTests(unittest.TestCase):
    def test_dataset_modules_import_by_concept_package_path(self):
        for name in DATASET_MODULES:
            with self.subTest(name=name):
                module = importlib.import_module(f"dataset.{name}")
                self.assertEqual(module.__name__, f"dataset.{name}")


if __name__ == "__main__":
    unittest.main()
