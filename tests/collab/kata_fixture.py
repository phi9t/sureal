"""Real, independently isolated Kata daemon; never targets a user's database."""
from contextlib import AbstractContextManager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from test_admission import git


class KataFixture(AbstractContextManager):
    def __enter__(self):
        from scripts._collab.contracts import Project
        self.tmp = tempfile.TemporaryDirectory(prefix="sureal-kata49-")
        self.root = Path(self.tmp.name)
        self.home = self.root / "kata-home"
        self.home.mkdir(mode=0o700)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir(mode=0o700)
        self.env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.home),
            "KATA_HOME": str(self.home),
            "XDG_RUNTIME_DIR": str(self.runtime),
            "USER": "sureal-fixture",
        }
        self.binary = str(Path(shutil.which("kata")).resolve())
        started = self.call("daemon", "start", "--listen", "127.0.0.1:0")
        self.daemon_pid = started["pid"]
        self.health = self.call("health")
        if Path(self.health["db_path"]) != self.home / "kata.db":
            raise RuntimeError("isolated daemon identity not proven")
        import sqlite3
        self.baseline = self.root / "native-baseline.db"
        with sqlite3.connect(self.home / "kata.db") as source, sqlite3.connect(self.baseline) as target:
            source.backup(target)
        identity = self.call("projects", "create", "sureal-test49")["project"]
        self.foreign = self.call("projects", "create", "foreign-test49")["project"]
        self.source = self.root / "source"
        self.source.mkdir()
        git(self.source, "init", "--initial-branch=phi9t/mainline")
        git(self.source, "config", "user.name", "Fixture")
        git(self.source, "config", "user.email", "fixture@example.invalid")
        (self.source / "docs").mkdir()
        for name in ("docs/49.md", "docs/50.md", "docs/plan.md"):
            (self.source / name).write_text("# " + name + "\nFixture goal and acceptance.\n")
        git(self.source, "add", ".")
        git(self.source, "commit", "-m", "fixture definitions")
        self.base = git(self.source, "rev-parse", "HEAD").decode().strip()
        self.project = Project("fixture49", self.source, self.root / "state", self.source / ".git",
                               "refs/heads/phi9t/mainline", self.base, {"policy": "local-only"},
                               {"name": identity["name"], "project_id": identity["id"], "project_uid": identity["uid"],
                                "db_path": self.health["db_path"], "home": str(self.home),
                                "database_schema_version": 25, "api_schema_version": "0.10.0", "version": "v0.14.3", "started_at": self.health["started_at"]},
                               {"kata": {"path": self.binary, "sha256": hashlib.sha256(Path(self.binary).read_bytes()).hexdigest()}},
                               {}, {"lead": "sureal/fixture49-lead"}, "fixture-admission")
        return self

    def call(self, *args, home=None):
        environment = dict(self.env)
        if home is not None:
            home.mkdir(mode=0o700, exist_ok=False)
            environment["KATA_HOME"] = str(home)
        result = subprocess.run([self.binary, "--json", "--as", "sureal/fixture49-lead", *args],
                                cwd=self.root, env=environment, capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise RuntimeError(result.stderr)
        if args[0] == "import" and not result.stdout:
            return {"observed_import_exit_code": 0}
        return json.loads(result.stdout)

    def definition(self, task_id, dependencies=()):
        from scripts._collab.contracts import TaskDefinition, digest
        source_commit = git(self.source, "rev-parse", "HEAD").decode().strip()
        pins = {}
        for key, path in (("spec", "docs/" + task_id + ".md"), ("plan", "docs/plan.md")):
            pins[key] = {"path": path, "blob": git(self.source, "rev-parse", source_commit + ":" + path).decode().strip(),
                         "sha256": hashlib.sha256((self.source / path).read_bytes()).hexdigest()}
        goals = {"49": "Durable journal and shared project admission",
                 "50": "Two worker dispatch and safe ownership handoff"}
        definition = {"schema_version": 1, "task_id": task_id, "source_commit": source_commit,
                      **pins, "goal": goals[task_id], "dependencies": list(dependencies)}
        return TaskDefinition(task_id, source_commit, pins["spec"], pins["plan"], definition["goal"],
                              tuple(dependencies), digest(definition))

    def __exit__(self, *exc):
        # Re-read isolated identity before the only authorized daemon stop.
        if Path(self.call("health")["db_path"]) != self.home / "kata.db":
            raise RuntimeError("fixture stop identity changed; retaining workspace")
        self.call("daemon", "stop")
        self.tmp.cleanup()
