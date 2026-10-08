"""Wire-format failures must not become admissible protocol records."""
import hashlib
import importlib
import unittest


def module(test, name):
    try:
        return importlib.import_module("scripts._collab." + name)
    except ModuleNotFoundError as error:
        if error.name not in {"scripts._collab", "scripts._collab." + name}:
            raise
        test.fail("planned collaboration module is not implemented: " + name)


class ContractsTests(unittest.TestCase):
    def test_digest_has_literal_canonical_unicode_bytes(self):
        api = module(self, "contracts")
        value = {"schema_version": 1, "word": "é", "count": 3}
        expected = hashlib.sha256(b'{"count":3,"schema_version":1,"word":"\xc3\xa9"}').hexdigest()
        self.assertEqual(api.digest(value), expected)

    def test_duplicate_float_and_unknown_schema_are_refused(self):
        api = module(self, "contracts")
        for raw in ('{"schema_version":1,"x":1,"x":2}',
                    '{"schema_version":1,"x":0.1}',
                    '{"schema_version":1,"x":NaN}',
                    '{"schema_version":2}'):
            with self.subTest(raw=raw), self.assertRaises(api.Refusal):
                api.loads(raw)
        with self.assertRaises(api.Refusal):
            api.digest({"schema_version": 1, "nested": [0.5]})


if __name__ == "__main__":
    unittest.main()
