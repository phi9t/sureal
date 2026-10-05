import unittest

from tools.suites import classify

IMPORT = '''ERROR: test_x (unittest.loader._FailedTest.test_x)
ImportError: Failed to import test module: test_x
Traceback (most recent call last):
ModuleNotFoundError: No module named '%s'

Ran 1 test in 0.000s

FAILED (errors=1)
'''


class ClassifyTests(unittest.TestCase):
    def test_success_reports_the_number_of_tests(self):
        self.assertEqual(classify(0, 'Ran 7 tests in 0.1s\n\nOK\n', set()), ('passed', 7))

    def test_missing_third_party_package_is_unavailable(self):
        self.assertEqual(classify(1, IMPORT % 'torch', {'pipeline'}), ('unavailable', 'torch'))

    def test_missing_local_module_is_a_failure(self):
        self.assertEqual(classify(1, IMPORT % 'pipeline', {'pipeline'}), ('failed', 'FAILED (errors=1)'))

    def test_missing_sandbox_mount_is_unavailable_but_a_missing_file_under_an_existing_root_is_not(self):
        output = "FileNotFoundError: [Errno 2] No such file or directory: '%s/receipt.json'\n\nFAILED (errors=1)\n"
        self.assertEqual(classify(1, output % '/absent-sandbox-mount', set()), ('unavailable', '/absent-sandbox-mount'))
        self.assertEqual(classify(1, output % '/tmp', set()), ('failed', 'FAILED (errors=1)'))

    def test_any_other_error_beside_a_missing_package_is_a_failure(self):
        output = IMPORT % 'torch' + 'AssertionError: 1 != 0\n'
        self.assertEqual(classify(1, output, set())[0], 'failed')

    def test_failure_without_a_recognised_exception_is_a_failure(self):
        self.assertEqual(classify(2, 'Segmentation fault\n', set()), ('failed', 'exit 2'))


if __name__ == '__main__':
    unittest.main()
