"""Missing runtime facts and mutable source must fail independently."""
import json
from pathlib import Path
import stat
import tempfile
import unittest

try:
    from audit_support.runtime import rootfs_digest, check_measurements, check_bwrap
except ImportError:
    rootfs_digest = check_measurements = check_bwrap = None


class RuntimeOracleTests(unittest.TestCase):
    def fixture(self):
        host = {"command":["bwrap","--", "python", "run.py"],"exit_code":0,"timed_out":False,
            "peak_rss_kib":123,"elapsed_seconds":1.0,
            "measurement":"wait4.ru_maxrss_KiB_largest_waited_child",
            "kernel_scope":{"path":"/user.slice/app.slice/sureal-sustained-collab-49-a.scope",
                "memory_max_bytes":268435456,"memory_swap_max_bytes":0,"oom":0,"oom_kill":0,
                "members_verified":True,"process_ids":[111]},
            "stage_lifecycle":{"caller_pid":111,"scope_members_before":[111],
                "scope_members_after":[111],"subreaper_verified":True,"remaining_children":[]}}
        worker = {"worker_argv":["python","run.py"],"worker_pid":2,"exit_code":0,
            "measurement":"in-runtime getrusage SELF and waited CHILDREN KiB",
            "self_peak_rss_kib":123,"waited_child_peak_rss_kib":90,"peak_rss_kib":123,
            "elapsed_seconds":0.8,"child_lifecycle":{"subreaper_verified":True,"remaining_children":[]}}
        return host,worker

    def test_missing_or_wrong_kernel_cap_and_unwaited_children_fail_closed(self):
        self.assertIsNotNone(check_measurements,"Independent kernel/resource oracle absent")
        host,worker = self.fixture()
        check_measurements(host,worker,host["command"],worker["worker_argv"],268435456,10)
        host["kernel_scope"]["memory_max_bytes"] = "max"
        with self.assertRaises(ValueError):
            check_measurements(host,worker,host["command"],worker["worker_argv"],268435456,10)
        host,worker = self.fixture()
        worker["child_lifecycle"]["remaining_children"] = [19]
        with self.assertRaises(ValueError):
            check_measurements(host,worker,host["command"],worker["worker_argv"],268435456,10)

    def test_rootfs_digest_changes_for_content_mode_and_link_mutations(self):
        self.assertIsNotNone(rootfs_digest,"Independent rootfs oracle absent")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/"file").write_bytes(b"one")
            (root/"link").symlink_to("file")
            first = rootfs_digest(root)
            (root/"file").write_bytes(b"two")
            self.assertNotEqual(rootfs_digest(root),first)
            second = rootfs_digest(root)
            (root/"file").chmod(0o755)
            self.assertNotEqual(rootfs_digest(root),second)
            third = rootfs_digest(root)
            (root/"link").unlink(); (root/"link").symlink_to("other")
            self.assertNotEqual(rootfs_digest(root),third)

    def test_source_writable_bind_and_missing_chdir_are_not_accepted(self):
        self.assertIsNotNone(check_bwrap,"Independent final argv oracle absent")
        argv = ["bwrap","--unshare-all","--die-with-parent","--clearenv",
            "--ro-bind","/rootfs","/","--ro-bind","/source","/source",
            "--ro-bind","/reference","/experiment","--bind","/output","/outputs",
            "--tmpfs","/tmp","--setenv","HOME","/tmp/private-home",
            "--setenv","PATH","/usr/local/bin:/usr/bin:/bin","--setenv","PYTHONNOUSERSITE","1",
            "--setenv","PYTHONDONTWRITEBYTECODE","1","--setenv","PYTHONPATH","/source:/experiment",
            "--chdir","/source","--","python","/source/scripts/collab_live.py"]
        check_bwrap(argv,"/rootfs","/source","/reference","/output")
        argv[7] = "--bind"
        with self.assertRaises(ValueError):
            check_bwrap(argv,"/rootfs","/source","/reference","/output")

    def test_absent_namespace_isolation_cannot_be_claimed_as_insula(self):
        self.assertIsNotNone(check_bwrap)
        argv = ["bwrap","--ro-bind","/rootfs","/","--ro-bind","/source","/source",
            "--ro-bind","/reference","/experiment","--bind","/output","/outputs",
            "--tmpfs","/tmp","--setenv","HOME","/tmp/private-home",
            "--setenv","PATH","/usr/local/bin:/usr/bin:/bin","--setenv","PYTHONNOUSERSITE","1",
            "--setenv","PYTHONDONTWRITEBYTECODE","1","--setenv","PYTHONPATH","/source:/experiment",
            "--chdir","/source","--","python","/source/scripts/collab_live.py"]
        with self.assertRaises(ValueError):
            check_bwrap(argv,"/rootfs","/source","/reference","/output")

    def test_readonly_subdirectory_shadow_cannot_replace_source(self):
        argv=["bwrap","--unshare-all","--die-with-parent","--clearenv",
            "--ro-bind","/rootfs","/","--ro-bind","/source","/source",
            "--ro-bind","/reference","/experiment","--bind","/output","/outputs",
            "--tmpfs","/tmp","--setenv","HOME","/tmp/private-home",
            "--setenv","PATH","/usr/local/bin:/usr/bin:/bin","--setenv","PYTHONNOUSERSITE","1",
            "--setenv","PYTHONDONTWRITEBYTECODE","1","--setenv","PYTHONPATH","/source:/experiment",
            "--chdir","/source","--ro-bind","/replacement","/source/scripts/_collab",
            "--","python","/source/scripts/collab_live.py"]
        with self.assertRaises(ValueError):
            check_bwrap(argv,"/rootfs","/source","/reference","/output")


if __name__ == "__main__":
    unittest.main()
