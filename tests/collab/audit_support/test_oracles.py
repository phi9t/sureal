"""Behavior tests for independently retained raw Git and audit evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from audit_support.raw_git import verify_retention


AUDITOR = Path(__file__).resolve().parents[1] / "audit_live.py"


def git(root, *args, data=None):
    return subprocess.run(["git", "-C", str(root), *args], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True).stdout


class MaterializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="a49 oracle ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Independent oracle")
        git(self.repo, "config", "user.email", "oracle@localhost")
        (self.repo / "file with spaces.txt").write_bytes(b"raw\r\n$() `literal`\n")
        (self.repo / ".gitattributes").write_text("file* export-ignore\n")
        (self.repo / "executable").write_text("#!/bin/sh\nexit 0\n")
        (self.repo / "executable").chmod(0o755)
        (self.repo / "link").symlink_to("file with spaces.txt")
        git(self.repo, "add", "--all")
        git(self.repo, "commit", "-qm", "raw fixture base")
        self.parent = git(self.repo, "rev-parse", "HEAD").decode().strip()
        (self.repo / "second").write_bytes(b"new\n")
        git(self.repo, "add", "second")
        git(self.repo, "commit", "-qm", "candidate")
        self.candidate = git(self.repo, "rev-parse", "HEAD").decode().strip()
        self.source = self.root / "source"
        self.receipt = self.root / "materialization.json"

    def materialize(self, candidate=None):
        return subprocess.run(["python3", str(AUDITOR), "materialize",
            "--repository", str(self.repo), "--candidate", candidate or self.candidate,
            "--source", str(self.source), "--receipt", str(self.receipt),
            "--owner", "a49-unit"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_raw_materialization_preserves_bytes_modes_links_and_rebuilds_tree(self):
        # Ignoring export attributes, omitting links or applying CRLF conversion is a bug.
        result = self.materialize()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.source / "file with spaces.txt").read_bytes(),
                         b"raw\r\n$() `literal`\n")
        self.assertEqual(os.readlink(self.source / "link"), "file with spaces.txt")
        self.assertEqual((self.source / "executable").stat().st_mode & 0o777, 0o755)
        self.assertFalse((self.source / ".git").exists())
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt["candidate"], self.candidate)
        self.assertEqual(receipt["parent"], self.parent)
        self.assertEqual(receipt["rebuilt_tree"],
                         git(self.repo, "rev-parse", "HEAD^{tree}").decode().strip())

    def verify(self):
        return subprocess.run(["python3", str(AUDITOR), "verify-materialization",
            "--receipt", str(self.receipt), "--candidate", self.candidate],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_changed_bytes_extra_files_and_modes_cannot_certify_retained_source(self):
        # Trusting the prior manifest rather than reopening bytes would accept all three.
        self.assertEqual(self.materialize().returncode, 0)
        path = self.source / "second"
        path.write_bytes(b"wrong\n")
        self.assertEqual(self.verify().returncode, 2)
        path.write_bytes(b"new\n")
        path.chmod(0o755)
        self.assertEqual(self.verify().returncode, 2)
        path.chmod(0o644)
        (self.source / "extra").write_text("extra")
        self.assertEqual(self.verify().returncode, 2)

    def test_gitlink_is_manifest_only_and_keeps_exact_object_identity(self):
        # Checking out a submodule makes an unadmitted directory a hidden model input.
        git(self.repo, "update-index", "--add", "--cacheinfo", "160000," + self.parent + ",submodule")
        git(self.repo, "commit", "-qm", "gitlink")
        self.candidate = git(self.repo, "rev-parse", "HEAD").decode().strip()
        result = self.materialize()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertFalse((self.source / "submodule").exists())
        value = json.loads(self.receipt.read_text())
        entry = next(x for x in value["entries"] if x["path"] == "submodule")
        self.assertEqual(entry["oid"], self.parent)
        self.assertEqual(entry["mode"], "160000")
        self.assertTrue(entry["excluded"])
        self.assertEqual(self.verify().returncode, 0)

    def test_escaping_link_refused_before_materialization(self):
        (self.repo / "link").unlink()
        (self.repo / "link").symlink_to("../outside")
        git(self.repo, "add", "link")
        git(self.repo, "commit", "-qm", "escaping link")
        self.candidate = git(self.repo, "rev-parse", "HEAD").decode().strip()
        result = self.materialize()
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.source.exists())

    def test_retain_recovers_candidate_in_independent_bare_repository(self):
        # A mutable branch name alone cannot recover a candidate after branch deletion.
        retained = self.root / "retained"
        result = subprocess.run(["python3", str(AUDITOR), "retain", "--repository", str(self.repo),
            "--candidate", self.candidate, "--output", str(retained), "--owner", "a49-unit"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(git(retained / "objects.git", "cat-file", "commit", self.candidate),
                         git(self.repo, "cat-file", "commit", self.candidate))
        manifest = json.loads((retained / "retention.json").read_text())
        self.assertEqual(manifest["candidate"], self.candidate)
        self.assertEqual(manifest["pack_sha256"], hashlib.sha256((retained / "objects.pack").read_bytes()).hexdigest())

    def test_hash_valid_unrelated_pack_cannot_use_existing_cold_repository(self):
        retained=self.root/"retained"
        command=["python3",str(AUDITOR),"retain","--repository",str(self.repo),"--candidate",self.candidate,
                 "--output",str(retained),"--owner","a49-unit"]
        completed=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.assertEqual(completed.returncode,0,completed.stderr.decode())
        manifest=retained/"retention.json"
        verify_retention(manifest,self.candidate)
        # A genuine parent-only pack has valid Git/checksum bytes but lacks this candidate.
        names=git(self.repo,"rev-list","--objects",self.parent)
        wrong=git(self.repo,"pack-objects","--stdout",data=names)
        (retained/"objects.pack").write_bytes(wrong)
        receipt=json.loads(manifest.read_text());receipt.update(pack_sha256=hashlib.sha256(wrong).hexdigest(),
            bytes=len(wrong),object_count=len(names.splitlines()))
        manifest.write_text(json.dumps(receipt))
        with self.assertRaises(ValueError):
            verify_retention(manifest,self.candidate)

    def test_symlink_traversal_cannot_be_hidden_by_dotdot_normalization(self):
        # a/inside -> root, then '..' escapes even though lexical normalization looks safe.
        (self.repo/"a").mkdir()
        (self.repo/"a"/"inside").symlink_to("..")
        (self.repo/"hidden_escape").symlink_to("a/inside/..")
        git(self.repo,"add","a","hidden_escape")
        git(self.repo,"commit","-qm","hidden symlink traversal")
        self.candidate=git(self.repo,"rev-parse","HEAD").decode().strip()
        result=self.materialize()
        self.assertEqual(result.returncode,2)
        self.assertFalse(self.source.exists())

    def test_special_permission_bits_are_source_mutation(self):
        self.assertEqual(self.materialize().returncode,0)
        (self.source/"executable").chmod(0o4755)
        self.assertEqual(self.verify().returncode,2)


if __name__ == "__main__":
    unittest.main()
