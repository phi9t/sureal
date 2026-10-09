import copy
import unittest

from evidence.score_records import populated_level2_classes, read_level2_per_class

ALL_NATIVE_CLASSES = ("1", "2", "3", "4")


def valid_score_record():
    return {
        "1": {"AP": 0.11, "APH": 0.21},
        "2": {"AP": 0.12, "APH": 0.22},
        "3": {"AP": 0.13, "APH": 0.23},
        "4": {"AP": 0.14, "APH": 0.24},
    }


class ScoreRecordTests(unittest.TestCase):
    def test_valid_score_record_is_preserved_without_aliasing(self):
        record = valid_score_record()

        parsed = read_level2_per_class(record, classes=ALL_NATIVE_CLASSES)

        self.assertEqual(parsed, record)
        self.assertIsNot(parsed, record)
        self.assertIsNot(parsed["1"], record["1"])

    def test_populated_class_record_uses_caller_supplied_class_set(self):
        record = valid_score_record()
        del record["4"]

        parsed = read_level2_per_class(record, classes=("1", "2", "3"))

        self.assertEqual(parsed, record)
        self.assertEqual(list(parsed), ["1", "2", "3"])

    def test_rejects_incomplete_or_unknown_class_set(self):
        for mutate in [
            lambda record: record.pop("4"),
            lambda record: record.update({"5": {"AP": 0.15, "APH": 0.25}}),
        ]:
            with self.subTest(mutate=mutate):
                record = valid_score_record()
                mutate(record)
                with self.assertRaises(ValueError):
                    read_level2_per_class(record, classes=ALL_NATIVE_CLASSES)

    def test_rejects_extra_class_relative_to_populated_class_set(self):
        with self.assertRaises(ValueError):
            read_level2_per_class(valid_score_record(), classes=("1", "2", "3"))

    def test_populated_level2_classes_come_from_positive_groundtruth_counts(self):
        record = {"groundtruth_by_class": {"1": 3, "2": 0, "3": 11, "4": 0}}

        self.assertEqual(populated_level2_classes(record), ("1", "3"))

    def test_rejects_malformed_metric_rows(self):
        for mutate in [
            lambda record: record.__setitem__("4", {"APH": 0.24}),
            lambda record: record.__setitem__("4", {"AP": 0.14}),
            lambda record: record["4"].update({"AOS": 0.2}),
            lambda record: record.__setitem__("4", 0.24),
        ]:
            with self.subTest(mutate=mutate):
                record = valid_score_record()
                mutate(record)
                with self.assertRaises(ValueError):
                    read_level2_per_class(record, classes=ALL_NATIVE_CLASSES)

    def test_rejects_non_numeric_nonfinite_or_out_of_range_values(self):
        for value in [True, "0.24", float("nan"), float("inf"), -0.01, 1.01]:
            with self.subTest(value=value):
                record = copy.deepcopy(valid_score_record())
                record["4"]["APH"] = value
                with self.assertRaises(ValueError):
                    read_level2_per_class(record, classes=ALL_NATIVE_CLASSES)


if __name__ == "__main__":
    unittest.main()
