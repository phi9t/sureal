import copy
import unittest
from dataset.scientific_admission import admit_scene, check_raw_capacity


class ScientificAdmissionTests(unittest.TestCase):
    def fixture(self):
        manifest = {"scenes": {"scene": {"official_split": "training", "research_splits": ["train"]}},
                    "components": ["lidar", "lidar_segmentation"],
                    "excluded_engineering_segments": ["engineering"],
                    "hdfs_root": "hdfs://cluster/root"}
        records = {}
        for component in manifest["components"]:
            records[component] = {"scene": "scene", "component": component,
                "official_split": "training", "research_splits": ["train"],
                "sha256": "a" * 64, "hdfs_roundtrip_sha256": "a" * 64,
                "hdfs_uri": f"hdfs://cluster/root/training/{component}/scene.parquet",
                "source_metadata": {"generation": "123", "size": "100",
                    "storage_url": f"gs://waymo_open_dataset_v_2_0_1/training/{component}/scene.parquet#123"},
                "inventory": {"rows": 0 if component == "lidar_segmentation" else 5}}
        return manifest, records

    def test_present_empty_annotations_and_identity(self):
        m, r = self.fixture()
        result = admit_scene(m, r, "scene")
        self.assertEqual(result["scene"], "scene")
        self.assertEqual(result["research_splits"], ["train"])
        self.assertEqual(result["components"]["lidar_segmentation"]["inventory"]["rows"], 0)
        result["components"]["lidar"]["sha256"] = "b" * 64
        self.assertEqual(r["lidar"]["sha256"], "a" * 64)

    def test_accepts_new_dataset_blob_source_records(self):
        m, r = self.fixture()
        m.pop("hdfs_root")
        for component, record in r.items():
            record.pop("hdfs_uri")
            record.pop("hdfs_roundtrip_sha256")
            record["blob"] = {
                "key": f"datasets/waymo-perception-v2.0.1/scene/raw-training-{component}/source.parquet",
                "sha256": record["sha256"],
                "bytes": int(record["source_metadata"]["size"]),
                "verified_by_readback": True,
            }
            record["store_descriptor"] = {"kind": "waystone", "project": "sureal"}

        result = admit_scene(m, r, "scene")

        self.assertEqual(
            result["components"]["lidar"]["blob"]["key"],
            "datasets/waymo-perception-v2.0.1/scene/raw-training-lidar/source.parquet",
        )

    def test_missing_duplicate_and_wrong_component_rejected(self):
        m, r = self.fixture()
        for mutation in (lambda x: x.pop("lidar"),
                         lambda x: x.update(duplicate=copy.deepcopy(x["lidar"])),
                         lambda x: x["lidar"].update(component="camera_image")):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(r); mutation(bad)
                with self.assertRaises(ValueError): admit_scene(m, bad, "scene")

    def test_generation_hash_size_and_uri_conflicts_rejected(self):
        m, r = self.fixture()
        for field, value in (("generation", "124"), ("generation", True),
                             ("size", "0"), ("storage_url", "gs://other/file#123")):
            bad = copy.deepcopy(r); bad["lidar"]["source_metadata"][field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError): admit_scene(m, bad, "scene")
        for field, value in (("sha256", "invalid"), ("hdfs_roundtrip_sha256", "b" * 64),
                             ("hdfs_uri", "hdfs://cluster/other")):
            bad = copy.deepcopy(r); bad["lidar"][field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError): admit_scene(m, bad, "scene")

    def test_engineering_unknown_and_split_leakage_rejected(self):
        m, r = self.fixture()
        with self.assertRaises(ValueError): admit_scene(m, r, "missing")
        bad = copy.deepcopy(m); bad["excluded_engineering_segments"] = ["scene"]
        with self.assertRaises(ValueError): admit_scene(bad, r, "scene")
        for splits in (["train", "development"], ["train", "validation"], ["camera_validation"]):
            bad = copy.deepcopy(m); bad["scenes"]["scene"]["research_splits"] = splits
            with self.assertRaises(ValueError): admit_scene(bad, r, "scene")
        bad = copy.deepcopy(r); bad["lidar"]["research_splits"] = ["development"]
        with self.assertRaises(ValueError): admit_scene(m, bad, "scene")

    def test_raw_capacity_exact_boundary_and_invalid_counts(self):
        self.assertEqual(check_raw_capacity(120, 80, 200, active_objects=0), 200)
        for args in ((120,81,200,0), (120,80,200,1), (-1,80,200,0),
                     (120,True,200,0), (120,80,200,True)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    check_raw_capacity(*args[:3], active_objects=args[3])


if __name__ == "__main__": unittest.main()
