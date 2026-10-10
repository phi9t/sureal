"""Runs ShellCheck over tracked, unpinned shell files in the real repository."""

from __future__ import annotations

import argparse
import sys
import unittest

from scripts import shellcheck_repo


def _parse_shellcheck_arg() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--shellcheck", required=True)
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    return args.shellcheck


SHELLCHECK = _parse_shellcheck_arg()


class RepoGateShellCheckTests(unittest.TestCase):
    def test_real_repository_shell_scripts_pass_shellcheck(self) -> None:
        root = shellcheck_repo.repository_root()
        result = shellcheck_repo.run_shellcheck(SHELLCHECK, root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
