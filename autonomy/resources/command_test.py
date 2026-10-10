import copy,json,tempfile,unittest
from pathlib import Path

from evidence.source_snapshot import file_sha256
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION, build_plan, load_runtime_lock, plan_data, record_plan
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME


AUTONOMY = Path(__file__).resolve().parents[1]


def write_rootfs(root):
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/python").write_text("#!/bin/sh\n")
    (root / "bin/python").chmod(0o755)


def write_cpu_lock(lock_path, rootfs):
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rootfs_sha256": rootfs_identity(rootfs),
                "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile"),
                "requirements_sha256": file_sha256(AUTONOMY / "requirements-tracer.lock"),
                "test_tools_requirements_sha256": file_sha256(
                    AUTONOMY / "insula/cpu-test-tools-requirements.lock"
                ),
                "bazel_version": BAZEL_VERSION,
                "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
            },
            sort_keys=True,
        )
        + "\n"
    )


class ResourceCommandTests(unittest.TestCase):
    def api(self):
        try:
            from resources.command import wrap_command
        except ImportError:
            self.fail('actual stage command must bind its resource wrapper')
        return wrap_command

    def test_actual_command_changes_in_place_with_literal_worker_arguments(self):
        wrap=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);code=root/'code';(code/'resources').mkdir(parents=True);(code/'evidence').mkdir();output=root/'resources';output.mkdir()
            (code/'resources/execute_worker.py').write_text('wrapper');(code/'evidence/source_snapshot.py').write_text('helper')
            command=['bwrap','--unshare-all','--die-with-parent','--ro-bind','/native-code','/experiment','--bind','/native-output','/outputs','--','python','/experiment/cohort/worker.py','literal$(touch bad)']
            original=copy.deepcopy(command);argv=wrap(command,code,output)
            self.assertEqual(argv,['/experiment/cohort/worker.py','literal$(touch bad)'])
            self.assertEqual(command[-5:],['python','/tmp/resource-layer/resources/execute_worker.py','/tmp/resource-output','/experiment/cohort/worker.py','literal$(touch bad)'])
            self.assertEqual(command[:command.index('--')],original[:original.index('--')]+['--ro-bind',str(code),'/tmp/resource-layer','--ro-bind',str(code/'resources'),'/experiment/resources','--ro-bind',str(code/'evidence'),'/experiment/evidence','--bind',str(output),'/tmp/resource-output'])
            self.assertFalse((root/'bad').exists())

    def test_missing_namespace_wrong_interpreter_or_conflicting_resource_mount_refused(self):
        wrap=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);code=root/'code';(code/'resources').mkdir(parents=True);(code/'evidence').mkdir();out=root/'out';out.mkdir()
            (code/'resources/execute_worker.py').write_text('wrapper');(code/'evidence/source_snapshot.py').write_text('helper')
            base=['bwrap','--unshare-all','--die-with-parent','--','python','/experiment/worker.py']
            for fault in ['namespace','interpreter','collision','double-separator','not-script']:
                command=copy.deepcopy(base)
                if fault=='namespace':command.remove('--unshare-all')
                elif fault=='interpreter':command[command.index('python')]='bash'
                elif fault=='collision':command[command.index('--'):command.index('--')]=['--bind','/other','/experiment/evidence']
                elif fault=='double-separator':command.append('--')
                else:command[-1]='relative.py'
                before=command.copy()
                with self.subTest(fault=fault),self.assertRaises(ValueError):wrap(command,code,out)
                self.assertEqual(command,before)

    def test_launch_plan_resource_wrapper_extends_plan_as_data(self):
        from insula.launch_plan import wrap_resource_plan

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rootfs = root / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_cpu_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)
            native_code = root / "native-code"
            native_source = root / "native-source"
            native_output = root / "native-output"
            resource_code = root / "resource-code"
            resource_output = root / "resource-output"
            for path in (
                native_code,
                native_source,
                native_output,
                resource_code / "resources",
                resource_code / "evidence",
                resource_output,
            ):
                path.mkdir(parents=True)
            (resource_code / "resources/execute_worker.py").write_text("wrapper\n")
            (resource_code / "evidence/source_snapshot.py").write_text("helper\n")
            plan = build_plan(
                runtime,
                code=native_code,
                source=native_source,
                output=native_output,
                command=["python", "/experiment/cohort/worker.py", "literal$(touch bad)"],
            )

            wrapped, worker_argv = wrap_resource_plan(plan, resource_code, resource_output)
            data = plan_data(wrapped)
            mounts = {mount["role"]: mount for mount in data["mounts"]}

            self.assertEqual(worker_argv, ["/experiment/cohort/worker.py", "literal$(touch bad)"])
            self.assertEqual(
                data["command"],
                [
                    "python",
                    "/tmp/resource-layer/resources/execute_worker.py",
                    "/tmp/resource-output",
                    "/experiment/cohort/worker.py",
                    "literal$(touch bad)",
                ],
            )
            self.assertEqual(mounts["resource-layer"]["inside_path"], "/tmp/resource-layer")
            self.assertEqual(mounts["resource-layer"]["host_path"], str(resource_code.resolve()))
            self.assertEqual(mounts["resource-experiment-resources"]["inside_path"], "/experiment/resources")
            self.assertEqual(mounts["resource-experiment-evidence"]["inside_path"], "/experiment/evidence")
            self.assertEqual(mounts["resource-output"]["mode"], "writable")
            self.assertEqual(mounts["resource-output"]["host_path"], str(resource_output.resolve()))
            self.assertFalse((root / "bad").exists())

    def test_launch_plan_resource_wrapper_extends_plan_record_as_data(self):
        from insula.launch_plan import wrap_resource_plan_record

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rootfs = root / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_cpu_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)
            native_code = root / "native-code"
            native_output = root / "native-output"
            resource_code = root / "resource-code"
            resource_output = root / "resource-output"
            for path in (
                native_code,
                native_output,
                resource_code / "resources",
                resource_code / "evidence",
                resource_output,
            ):
                path.mkdir(parents=True)
            (resource_code / "resources/execute_worker.py").write_text("wrapper\n")
            (resource_code / "evidence/source_snapshot.py").write_text("helper\n")
            plan = build_plan(
                runtime,
                code=native_code,
                output=native_output,
                command=["python", "/experiment/cohort/worker.py"],
            )

            wrapped, worker_argv = wrap_resource_plan_record(
                record_plan(plan),
                resource_code,
                resource_output,
            )
            mounts = {mount["role"]: mount for mount in wrapped["mounts"]}

            self.assertEqual(worker_argv, ["/experiment/cohort/worker.py"])
            self.assertEqual(
                wrapped["command"],
                [
                    "python",
                    "/tmp/resource-layer/resources/execute_worker.py",
                    "/tmp/resource-output",
                    "/experiment/cohort/worker.py",
                ],
            )
            self.assertRegex(mounts["resource-layer"]["digest"], r"^[0-9a-f]{64}$")
            self.assertRegex(
                mounts["resource-experiment-resources"]["digest"],
                r"^[0-9a-f]{64}$",
            )
            self.assertEqual(mounts["resource-output"]["inside_path"], "/tmp/resource-output")
            self.assertNotIn("host_path", mounts["resource-layer"])

if __name__=='__main__':unittest.main()
