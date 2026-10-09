import unittest

from evidence import publish


class PublicationIsolationTests(unittest.TestCase):
    def test_evidence_publication_entrypoint_is_retired(self):
        with self.assertRaisesRegex(SystemExit, "retention.publish_research_journal"):
            publish.main()


if __name__ == "__main__":
    unittest.main()
