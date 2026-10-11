"""Unit tests for Sureal's mechanical C++ lint."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import check_cxx


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def formatted_findings(root: Path) -> list[str]:
    return [finding.format() for finding in check_cxx.check_repository(root).findings]


class CheckCxxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def track(self, relative: str, text: str) -> None:
        write(self.root, relative, text)
        subprocess.run(["git", "add", relative], cwd=self.root, check=True)

    def test_clean_active_cxx_passes(self) -> None:
        self.track(
            "autonomy/native/example.hh",
            "#pragma once\n\nnamespace autonomy {\n\nenum class Mode { Ready };\n\n}  // namespace autonomy\n",
        )
        self.track(
            "parallax/native/example.cc",
            (
                "namespace parallax {\n\n"
                "void make() {\n"
                "  using namespace std;\n"
                "  // external API owns the returned pointer\n"
                "  auto* value = new int(1);\n"
                "  // this scope owns value until the callback returns\n"
                "  delete value;\n"
                "}\n\n"
                "}  // namespace parallax\n"
            ),
        )

        self.assertEqual(formatted_findings(self.root), [])

    def test_forbidden_suffixes_are_flagged(self) -> None:
        self.track("autonomy/native/bad.cpp", "int main() { return 0; }\n")
        self.track("autonomy/native/bad.h", "#pragma once\n")
        self.track("parallax/native/bad.hpp", "#pragma once\n")
        self.track("parallax/native/bad.hxx", "#pragma once\n")

        self.assertEqual(
            formatted_findings(self.root),
            [
                "autonomy/native/bad.cpp:1: forbidden-suffix: use .cc, .hh, .cu or .cuh for C++ and CUDA",
                "autonomy/native/bad.h:1: forbidden-suffix: use .cc, .hh, .cu or .cuh for C++ and CUDA",
                "parallax/native/bad.hpp:1: forbidden-suffix: use .cc, .hh, .cu or .cuh for C++ and CUDA",
                "parallax/native/bad.hxx:1: forbidden-suffix: use .cc, .hh, .cu or .cuh for C++ and CUDA",
            ],
        )

    def test_headers_require_pragma_once(self) -> None:
        self.track("autonomy/native/example.hh", "namespace autonomy {}\n")
        self.track("parallax/native/example.cuh", "namespace parallax {}\n")

        self.assertEqual(
            formatted_findings(self.root),
            [
                "autonomy/native/example.hh:1: pragma-once: headers must start with #pragma once",
                "parallax/native/example.cuh:1: pragma-once: headers must start with #pragma once",
            ],
        )

    def test_using_namespace_is_flagged_in_headers_and_file_scope(self) -> None:
        self.track(
            "autonomy/native/example.hh",
            "#pragma once\nnamespace autonomy {\nusing namespace std;\n}\n",
        )
        self.track(
            "parallax/native/example.cc",
            "namespace parallax\n{\nusing namespace std;\n}\n",
        )

        self.assertEqual(
            formatted_findings(self.root),
            [
                "autonomy/native/example.hh:3: using-namespace: do not use using namespace in headers or at file scope",
                "parallax/native/example.cc:3: using-namespace: do not use using namespace in headers or at file scope",
            ],
        )

    def test_using_namespace_inside_function_scope_is_allowed_in_sources(self) -> None:
        self.track(
            "autonomy/native/example.cc",
            "namespace autonomy {\nvoid run() {\n  using namespace std;\n}\n}  // namespace autonomy\n",
        )

        self.assertEqual(formatted_findings(self.root), [])

    def test_comments_strings_and_raw_strings_are_ignored(self) -> None:
        self.track(
            "autonomy/native/example.cc",
            (
                "const char* first = \"using namespace std; NULL enum Kind { A }; (int)value\";\n"
                "const char* second = R\"text(delete value; new int(1);)text\";\n"
                "// using namespace std; NULL enum Kind { A }; (int)value\n"
            ),
        )

        self.assertEqual(formatted_findings(self.root), [])

    def test_null_plain_enum_and_c_style_casts_are_flagged(self) -> None:
        self.track(
            "autonomy/native/example.cc",
            (
                "void* ptr = NULL;\n"
                "enum Kind { Ready };\n"
                "auto count = (int64_t)value;\n"
                "auto name = (const char*)raw;\n"
                "auto bytes = (void*)raw;\n"
            ),
        )

        self.assertEqual(
            formatted_findings(self.root),
            [
                "autonomy/native/example.cc:1: null: use nullptr instead of NULL",
                "autonomy/native/example.cc:2: plain-enum: use enum class instead of plain enum",
                "autonomy/native/example.cc:3: c-style-cast: use an explicit C++ cast",
                "autonomy/native/example.cc:4: c-style-cast: use an explicit C++ cast",
                "autonomy/native/example.cc:5: c-style-cast: use an explicit C++ cast",
            ],
        )

    def test_enum_class_is_allowed_and_enum_struct_is_flagged(self) -> None:
        self.track(
            "autonomy/native/example.hh",
            "#pragma once\nnamespace autonomy {\nenum class Good { Ready };\nenum struct Bad { Ready };\n}\n",
        )

        self.assertEqual(
            formatted_findings(self.root),
            ["autonomy/native/example.hh:4: plain-enum: use enum class instead of plain enum"],
        )

    def test_over_120_column_line_is_flagged(self) -> None:
        self.track("autonomy/native/example.cc", "int " + "value" * 24 + ";\n")

        self.assertEqual(
            formatted_findings(self.root),
            ["autonomy/native/example.cc:1: line-length: line has 125 columns, above 120"],
        )

    def test_raw_new_and_delete_need_ownership_comments(self) -> None:
        self.track(
            "autonomy/native/example.cc",
            "void run() {\n  auto* value = new int(1);\n  delete value;\n}\n",
        )

        self.assertEqual(
            formatted_findings(self.root),
            [
                "autonomy/native/example.cc:2: raw-new: raw new requires a nearby owns/ownership comment",
                "autonomy/native/example.cc:3: raw-delete: raw delete requires a nearby owns/ownership comment",
            ],
        )

    def test_ownership_comments_and_deleted_special_members_are_allowed(self) -> None:
        self.track(
            "autonomy/native/example.hh",
            (
                "#pragma once\n"
                "class Example {\n"
                " public:\n"
                "  Example(const Example&) = delete;\n"
                "  Example& operator=(const Example&) = delete;\n"
                "};\n"
                "void run() {\n"
                "  auto* value = new int(1);  // external API owns this pointer\n"
                "  delete value;  // deletes the owned value after the callback\n"
                "}\n"
            ),
        )

        self.assertEqual(formatted_findings(self.root), [])

    def test_archives_and_submodules_are_excluded_but_receipt_pinned_sources_are_checked(self) -> None:
        write(self.root, "autonomy/retained_receipt_sweep.py", "RETAINED_SOURCE_PIN_FIELDS = ('source_pins',)\n")
        write(
            self.root,
            "autonomy/research/receipt.json",
            json.dumps({"source_pins": {"autonomy/native/pinned.cc": "a" * 64}}),
        )
        self.track("autonomy/native/pinned.cc", "using namespace std;\n")
        self.track("autonomy/native/free.cc", "int main() {\n  return 0;\n}\n")
        self.track("autonomy/research/frozen.cc", "using namespace std;\n")
        self.track("parallax/submodules/vendor/bad.cc", "using namespace std;\n")

        result = check_cxx.check_repository(self.root)

        self.assertEqual(
            [finding.format() for finding in result.findings],
            [
                "autonomy/native/pinned.cc:1: using-namespace: do not use using namespace in headers or at file scope"
            ],
        )
        self.assertEqual(result.targets.checked_files, ("autonomy/native/free.cc", "autonomy/native/pinned.cc"))
        self.assertNotIn("autonomy/native/pinned.cc", result.targets.excluded_files)
        self.assertIn("autonomy/research/frozen.cc", result.targets.excluded_files)
        self.assertIn("parallax/submodules/vendor/bad.cc", result.targets.excluded_files)

    def test_real_tree_passes(self) -> None:
        result = check_cxx.check_repository(check_cxx.repository_root())

        self.assertEqual(result.returncode, 0, result.format_findings())


if __name__ == "__main__":
    unittest.main()
