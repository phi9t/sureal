import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from evidence.source_snapshot import file_sha256
from insula.launch_plan import (
    BAZEL_LINUX_X86_64_SHA256,
    BAZEL_VERSION,
    LaunchPlan,
    Mount,
    PlanError,
    RuntimeLockError,
    build_plan,
    gpu_driver_hashes_from_plan_record,
    gpu_driver_paths_from_plan_record,
    load_default_runtime_lock,
    load_runtime_lock,
    plan_data,
    record_plan,
    render_plan,
    run_plan,
    read_receipt_mounts,
    read_receipt_mount_sequence,
    verify_gpu_driver_hashes_from_plan_record,
)
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import (
    CURRENT_CPU_ROOTFS_NAME,
    CURRENT_GPU_ROOTFS_NAME,
    CURRENT_MOTION_CLI_ROOTFS_NAME,
)


AUTONOMY = Path(__file__).resolve().parents[1]


def write_rootfs(root: Path):
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/python").write_text("#!/bin/sh\n")
    (root / "bin/python").chmod(0o755)
    (root / "etc").mkdir()
    (root / "etc/issue").write_text("fixture rootfs\n")


def write_cpu_recipe_lock(path: Path, rootfs: Path, **overrides):
    lock = {
        "schema_version": 1,
        "rootfs_sha256": rootfs_identity(rootfs),
        "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile"),
        "requirements_sha256": file_sha256(AUTONOMY / "requirements-tracer.lock"),
        "test_tools_requirements_sha256": file_sha256(
            AUTONOMY / "insula/cpu-test-tools-requirements.lock"
        ),
        "bazel_version": BAZEL_VERSION,
        "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
    }
    lock.update(overrides)
    path.write_text(json.dumps(lock, indent=2) + "\n")
    return lock


def write_gpu_recipe_lock(path: Path, rootfs: Path, **overrides):
    lock = {
        "schema_version": 1,
        "rootfs_sha256": rootfs_identity(rootfs),
        "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile.gpu-bazel-rootfs-v6"),
        "requirements_sha256": file_sha256(AUTONOMY / "insula/gpu-requirements.lock"),
        "bazel_version": BAZEL_VERSION,
        "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
    }
    lock.update(overrides)
    path.write_text(json.dumps(lock, indent=2) + "\n")
    return lock


def write_motion_cli_lock(path: Path, rootfs: Path, **overrides):
    lock = {
        "schema_version": 1,
        "rootfs_sha256": rootfs_identity(rootfs),
        "image_id": "sha256:" + "1" * 64,
        "parent_image_id": "sha256:84fb83dd874d0cfff8e9ee3df0759d89f9ad85e9538c0071c9eb606a13d8c233",
        "recipe_hashes": {
            "Dockerfile": file_sha256(AUTONOMY / "motion/cli/motion_cli.Dockerfile"),
            "CMakeLists.txt": file_sha256(AUTONOMY / "motion/cli/CMakeLists.txt"),
            "motion_metrics_main.cc": file_sha256(
                AUTONOMY / "motion/cli/motion_metrics_main.cc"
            ),
        },
    }
    lock.update(overrides)
    path.write_text(json.dumps(lock, indent=2) + "\n")
    return lock


class RuntimeLockTests(unittest.TestCase):
    def test_missing_runtime_lock_is_an_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            rootfs = Path(temporary) / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            with self.assertRaisesRegex(RuntimeLockError, "runtime lock"):
                load_runtime_lock(rootfs, Path(temporary) / "missing.lock.json")

    def test_recipe_digest_form_checks_every_declared_field(self):
        cases = {
            "schema_version": {"schema_version": 2},
            "rootfs_sha256": {"rootfs_sha256": "0" * 64},
            "dockerfile_sha256": {"dockerfile_sha256": "0" * 64},
            "requirements_sha256": {"requirements_sha256": "0" * 64},
            "test_tools_requirements_sha256": {"test_tools_requirements_sha256": "0" * 64},
            "bazel_version": {"bazel_version": "0.0.0"},
            "bazel_linux_x86_64_sha256": {"bazel_linux_x86_64_sha256": "0" * 64},
        }
        with tempfile.TemporaryDirectory() as temporary:
            rootfs = Path(temporary) / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock_path = rootfs.with_name(rootfs.name + ".lock.json")
            write_cpu_recipe_lock(lock_path, rootfs)

            runtime = load_runtime_lock(rootfs, lock_path)
            self.assertEqual(runtime.form, "recipe-digest")
            self.assertEqual(runtime.data["rootfs_sha256"], rootfs_identity(rootfs))

            for field, override in cases.items():
                with self.subTest(field=field):
                    write_cpu_recipe_lock(lock_path, rootfs, **override)
                    with self.assertRaisesRegex(RuntimeLockError, field):
                        load_runtime_lock(rootfs, lock_path)

    def test_image_form_checks_recipe_parent_image_and_content(self):
        cases = {
            "image_id": {"image_id": ""},
            "rootfs_sha256": {"rootfs_sha256": "0" * 64},
            "recipe_hashes": {"recipe_hashes": {"Dockerfile": "0" * 64}},
            "parent_image_id": {"parent_image_id": "sha256:" + "2" * 64},
        }
        with tempfile.TemporaryDirectory() as temporary:
            rootfs = Path(temporary) / CURRENT_MOTION_CLI_ROOTFS_NAME
            write_rootfs(rootfs)
            lock_path = rootfs.with_name(rootfs.name + ".lock.json")
            write_motion_cli_lock(lock_path, rootfs)

            runtime = load_runtime_lock(rootfs, lock_path)
            self.assertEqual(runtime.form, "image")

            for field, override in cases.items():
                with self.subTest(field=field):
                    write_motion_cli_lock(lock_path, rootfs, **override)
                    with self.assertRaisesRegex(RuntimeLockError, field):
                        load_runtime_lock(rootfs, lock_path)

    def test_content_digest_is_cached_per_rootfs_path_and_lock_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            rootfs = Path(temporary) / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock_path = rootfs.with_name(rootfs.name + ".lock.json")
            lock = write_cpu_recipe_lock(lock_path, rootfs)
            expected = lock["rootfs_sha256"]

            with patch("insula.launch_plan.rootfs_identity", return_value=expected) as identity:
                load_runtime_lock(rootfs, lock_path)
                load_runtime_lock(rootfs, lock_path)
                self.assertEqual(identity.call_count, 1)

                lock["note"] = "same rootfs, new lock digest"
                lock_path.write_text(json.dumps(lock, indent=2) + "\n")
                load_runtime_lock(rootfs, lock_path)
                self.assertEqual(identity.call_count, 2)


class LaunchPlanTests(unittest.TestCase):
    def load_fixture_runtime(self, root: Path):
        rootfs = root / CURRENT_CPU_ROOTFS_NAME
        write_rootfs(rootfs)
        lock = rootfs.with_name(rootfs.name + ".lock.json")
        write_cpu_recipe_lock(lock, rootfs)
        return load_runtime_lock(rootfs, lock)

    def test_plan_is_readable_as_data_and_rendered_only_at_the_edge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            source = root / "source"
            output = root / "output"
            extra = root / "extra"
            for path in (code, source, output, extra):
                path.mkdir()
            (code / "main.py").write_text("print('ok')\n")
            (source / "input.txt").write_text("input\n")
            (extra / "table.txt").write_text("table\n")

            plan = build_plan(
                runtime,
                code=code,
                source=source,
                output=output,
                named_inputs={"/tmp/tables": extra},
                extra_environment={"EXTRA_FLAG": "1"},
                command=["python", "main.py"],
            )
            data = plan_data(plan)

            self.assertEqual(data["runtime"]["form"], "recipe-digest")
            self.assertEqual(data["working_directory"], "/experiment")
            self.assertEqual(data["command"], ["python", "main.py"])
            self.assertIn(
                {
                    "role": "code",
                    "host_path": str(code.resolve()),
                    "inside_path": "/experiment",
                    "mode": "read_only",
                    "kind": "bind",
                },
                data["mounts"],
            )
            self.assertIn(["--setenv", "PYTHONPATH", "/experiment"], data["environment"])
            self.assertIn(["--setenv", "EXTRA_FLAG", "1"], data["environment"])

            argv = render_plan(plan)
            self.assertEqual(argv[0], "bwrap")
            self.assertIn("--clearenv", argv)
            self.assertIn("/tmp/tables", argv)
            self.assertLess(argv.index("/tmp"), argv.index("/tmp/tables"))
            self.assertEqual(argv[-2:], ["python", "main.py"])

    def test_default_lock_loader_uses_rootfs_default_lock_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            rootfs = Path(temporary) / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_cpu_recipe_lock(lock, rootfs)

            runtime = load_default_runtime_lock(rootfs)

            self.assertEqual(runtime.rootfs, rootfs.resolve())
            self.assertEqual(runtime.lock_path, lock.resolve())
            self.assertEqual(runtime.data["rootfs_sha256"], rootfs_identity(rootfs))

    def test_run_plan_executes_rendered_plan_as_subprocess(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            output = root / "output"
            for path in (code, output):
                path.mkdir()
            plan = build_plan(runtime, code=code, output=output, command=["python", "-c", "pass"])
            completed = subprocess.CompletedProcess(render_plan(plan), 0, stdout="ok\n", stderr="")

            with patch("insula.launch_plan.subprocess.run", return_value=completed) as run:
                result = run_plan(plan, capture_output=True, text=True)

            self.assertIs(result, completed)
            run.assert_called_once_with(render_plan(plan), capture_output=True, text=True)

    def test_build_plan_coerces_named_and_writable_input_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            output = root / "output"
            read_only = root / "read-only"
            scratch = root / "scratch"
            for path in (code, output, read_only, scratch):
                path.mkdir()

            plan = build_plan(
                runtime,
                code=code,
                output=output,
                named_inputs={PurePosixPath("/tmp/tables"): str(read_only)},
                writable_inputs={PurePosixPath("/tmp/scratch"): str(scratch)},
                command=["true"],
            )

            mounts = {mount["role"]: mount for mount in plan_data(plan)["mounts"]}
            self.assertEqual(mounts["input:/tmp/tables"]["inside_path"], "/tmp/tables")
            self.assertEqual(mounts["input:/tmp/tables"]["host_path"], str(read_only.resolve()))
            self.assertEqual(mounts["input:/tmp/scratch"]["inside_path"], "/tmp/scratch")
            self.assertEqual(mounts["input:/tmp/scratch"]["host_path"], str(scratch.resolve()))
            json.dumps(record_plan(plan), sort_keys=True)

    def test_receipt_record_has_digests_without_host_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            output = root / "output"
            fixture = root / "fixture"
            for path in (code, output, fixture):
                path.mkdir()
            (code / "main.py").write_text("print('ok')\n")
            (fixture / "data.txt").write_text("data\n")

            plan = build_plan(
                runtime,
                code=code,
                output=output,
                named_inputs={"/tmp/fixture": fixture},
                command=["python", "main.py"],
            )
            record = record_plan(plan)
            raw = json.dumps(record, sort_keys=True)

            self.assertEqual(record["runtime"]["lock_sha256"], runtime.lock_sha256)
            self.assertEqual(record["runtime"]["form"], "recipe-digest")
            self.assertNotIn(str(root), raw)
            mounts = {mount["role"]: mount for mount in record["mounts"]}
            self.assertRegex(mounts["code"]["digest"], r"^[0-9a-f]{64}$")
            self.assertRegex(mounts["input:/tmp/fixture"]["digest"], r"^[0-9a-f]{64}$")
            self.assertNotIn("digest", mounts["output"])
            self.assertEqual(record["command"], ["python", "main.py"])

    def test_record_plan_keeps_declared_named_input_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            scientific = root / "scientific"
            output = scientific / "run-output"
            for path in (code, output):
                path.mkdir(parents=True)
            (scientific / "actual.txt").write_text("actual scientific bytes\n")
            source_snapshot_digest = "1" * 64
            scientific_root_digest = "2" * 64

            plan = build_plan(
                runtime,
                code=code,
                output=output,
                named_inputs={"/tmp/scientific": scientific},
                named_input_digests={"/tmp/scientific": scientific_root_digest},
                source_snapshot_digest=source_snapshot_digest,
                allow_readonly_inputs_cover_output=True,
                command=["python", "main.py"],
            )

            mounts = {mount["role"]: mount for mount in record_plan(plan)["mounts"]}
            self.assertEqual(plan.named_input_digests, (("/tmp/scientific", scientific_root_digest),))
            self.assertEqual(mounts["code"]["digest"], source_snapshot_digest)
            self.assertEqual(mounts["input:/tmp/scientific"]["digest"], scientific_root_digest)

    def test_declared_named_input_digest_requires_matching_named_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            output = root / "output"
            for path in (code, output):
                path.mkdir()

            with self.assertRaisesRegex(PlanError, "declared digest requires a named input"):
                build_plan(
                    runtime,
                    code=code,
                    output=output,
                    named_input_digests={"/tmp/scientific": "2" * 64},
                    command=["python", "main.py"],
                )

    def test_receipt_reader_normalizes_old_command_and_new_plan_mounts(self):
        retained = json.loads(
            (
                AUTONOMY
                / "research/balanced16-sustained-contract-red-verified.json"
            ).read_text()
        )
        retained_mounts = read_receipt_mounts(
            retained,
            include_digests=True,
            require_cleared_environment=True,
        )
        command = retained["command"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            source = root / "source"
            output = root / "output"
            for path in (code, source, output):
                path.mkdir()
            (code / "worker.py").write_text("print('fixture')\n")
            (source / "input.json").write_text("{}\n")
            local_command = list(command)
            for index, item in enumerate(local_command):
                if item in {"--ro-bind", "--bind"}:
                    inside = local_command[index + 2]
                    if inside == "/experiment":
                        local_command[index + 1] = str(code)
                    elif inside == "/source":
                        local_command[index + 1] = str(source)
                    elif inside == "/outputs":
                        local_command[index + 1] = str(output)
            old_mounts = read_receipt_mounts(
                {"command": local_command},
                include_digests=True,
                require_cleared_environment=True,
            )
            plan = build_plan(
                runtime,
                code=code,
                source=source,
                output=output,
                command=local_command[local_command.index("--") + 1 :],
            )
            plan_record = record_plan(plan)
            new_mounts = read_receipt_mounts(
                {"launch_plan": plan_record},
                require_cleared_environment=True,
            )
            without_clean_environment = copy.deepcopy(plan_record)
            without_clean_environment["environment"].pop("PYTHONPATH")
            with self.assertRaisesRegex(ValueError, "cleared environment"):
                read_receipt_mounts(
                    {"launch_plan": without_clean_environment},
                    require_cleared_environment=True,
                )
            worker_plan = build_plan(
                runtime,
                code=code,
                source=source,
                output=output,
                command=["python", "/experiment/worker.py"],
            )
            read_receipt_mounts({"launch_plan": record_plan(worker_plan)}, require_python_worker=True)
            with self.assertRaisesRegex(ValueError, "Python worker"):
                read_receipt_mounts({"launch_plan": plan_record}, require_python_worker=True)

        comparable = {"/experiment", "/source", "/tmp"}
        self.assertEqual(
            {inside: retained_mounts[inside]["mode"] for inside in comparable | {"/outputs"}},
            {inside: new_mounts[inside]["mode"] for inside in comparable | {"/outputs"}},
        )
        self.assertEqual(
            {inside: {key: old_mounts[inside].get(key) for key in ("mode", "digest")} for inside in comparable},
            {inside: {key: new_mounts[inside].get(key) for key in ("mode", "digest")} for inside in comparable},
        )
        self.assertEqual(old_mounts["/outputs"]["mode"], new_mounts["/outputs"]["mode"])
        self.assertNotIn("digest", old_mounts["/outputs"])
        self.assertNotIn("digest", new_mounts["/outputs"])

    def test_legacy_receipt_reader_uses_last_mount_for_duplicate_inside_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_source = root / "first-source"
            last_source = root / "last-source"
            for path in (first_source, last_source):
                path.mkdir()

            command = [
                "bwrap",
                "--unshare-all",
                "--die-with-parent",
                "--clearenv",
                "--ro-bind",
                str(first_source),
                "/source",
                "--ro-bind",
                str(last_source),
                "/source",
                "--",
                "python",
                "/experiment/worker.py",
            ]

            mounts = read_receipt_mounts({"command": command}, include_digests=False)

            self.assertEqual(mounts["/source"]["host_path"], str(last_source))
            self.assertEqual(mounts["/source"]["mode"], "read_only")

            ordered = read_receipt_mount_sequence({"command": command}, include_digests=False)
            self.assertEqual([mount["host_path"] for mount in ordered], [str(first_source), str(last_source)])

    def test_legacy_receipt_reader_defaults_to_not_hashing_old_mounts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            symlink = root / "source-link"
            symlink.symlink_to(source, target_is_directory=True)
            command = [
                "bwrap",
                "--unshare-all",
                "--die-with-parent",
                "--clearenv",
                "--ro-bind",
                str(symlink),
                "/source",
                "--",
                "python",
                "/experiment/worker.py",
            ]

            mounts = read_receipt_mounts({"command": command})

            self.assertEqual(mounts["/source"]["host_path"], str(symlink))
            self.assertNotIn("digest", mounts["/source"])

    def test_retained_bwrap_receipts_all_read_without_rewriting_evidence(self):
        cache_receipt = (
            Path.home()
            / ".cache/waystone/waymo-perception/insula/resource-legacy-seven-controller20261003a-v5/export-1000-resources/resource-admitted.json"
        )
        receipt_paths = sorted(AUTONOMY.rglob("*.json"))
        if cache_receipt.exists():
            receipt_paths.append(cache_receipt)
        checked = 0
        failures = []

        def visit(value):
            nonlocal checked
            if isinstance(value, dict):
                command = value.get("command")
                if isinstance(command, list) and command and command[0] == "bwrap":
                    checked += 1
                    try:
                        read_receipt_mounts(value, include_digests=False)
                    except ValueError as error:
                        failures.append(str(error))
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        for path in receipt_paths:
            with self.subTest(path=path):
                visit(json.loads(path.read_text()))

        self.assertGreater(checked, 0)
        self.assertEqual(failures, [], f"{len(failures)} of {checked} retained bwrap receipts failed")

    def test_plan_records_require_unshare_flags_and_clearenv_for_clean_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            output = root / "output"
            for path in (code, output):
                path.mkdir()
            plan = build_plan(runtime, code=code, output=output, command=["python", "/experiment/a.py"])
            record = record_plan(plan)

            self.assertEqual(record["unshare_flags"], ["--unshare-all", "--die-with-parent"])
            self.assertTrue(record["clear_environment"])
            read_receipt_mounts({"launch_plan": record}, require_cleared_environment=True)

            for name, mutate in {
                "clearenv": lambda candidate: candidate.pop("clear_environment"),
                "unshare": lambda candidate: candidate.update({"unshare_flags": ["--die-with-parent"]}),
                "pythonpath": lambda candidate: candidate["environment"].pop("PYTHONPATH"),
            }.items():
                with self.subTest(name=name):
                    candidate = copy.deepcopy(record)
                    mutate(candidate)
                    with self.assertRaisesRegex(ValueError, "cleared environment"):
                        read_receipt_mounts(
                            {"launch_plan": candidate},
                            require_cleared_environment=True,
                        )

    def test_mount_rules_name_the_colliding_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            source = root / "source"
            output = root / "output"
            writable = output / "scratch"
            for path in (code, source, output, writable):
                path.mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "code.*source|source.*code"):
                build_plan(runtime, code=code, source=code, output=output, command=["true"])

            with self.assertRaisesRegex(ValueError, "output.*input:/tmp/scratch|input:/tmp/scratch.*output"):
                build_plan(
                    runtime,
                    code=code,
                    source=source,
                    output=output,
                    writable_inputs={"/tmp/scratch": writable},
                    command=["true"],
                )

    def test_readonly_mounts_may_nest_and_named_inputs_are_restricted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            source = code / "source"
            output = root / "output"
            bad_input = root / "bad"
            for path in (source, output, bad_input):
                path.mkdir(parents=True)

            plan = build_plan(runtime, code=code, source=source, output=output, command=["true"])
            self.assertEqual(plan_data(plan)["command"], ["true"])

            with self.assertRaisesRegex(ValueError, "/home/input"):
                build_plan(
                    runtime,
                    code=code,
                    output=output,
                    named_inputs={"/home/input": bad_input},
                    command=["true"],
                )

    def test_readonly_named_input_covering_output_requires_explicit_option(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            scientific = root / "scientific"
            output = scientific / "run-output"
            code.mkdir()
            output.mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "input:/tmp/scientific.*output|output.*input:/tmp/scientific"):
                build_plan(
                    runtime,
                    code=code,
                    output=output,
                    named_inputs={"/tmp/scientific": scientific},
                    command=["true"],
                )

            plan = build_plan(
                runtime,
                code=code,
                output=output,
                named_inputs={"/tmp/scientific": scientific},
                command=["true"],
                allow_readonly_inputs_cover_output=True,
            )

            mounts = {mount["inside_path"]: mount for mount in plan_data(plan)["mounts"]}
            self.assertEqual(mounts["/tmp/scientific"]["mode"], "read_only")
            self.assertEqual(mounts["/outputs"]["mode"], "writable")

    def test_extra_environment_cannot_replace_module_owned_variables(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            output = root / "output"
            code.mkdir()
            output.mkdir()

            with self.assertRaisesRegex(ValueError, "PATH"):
                build_plan(
                    runtime,
                    code=code,
                    output=output,
                    extra_environment={"PATH": "/tmp/bin"},
                    command=["true"],
                )

    def test_gpu_plan_uses_requested_device_only_and_records_uuid_not_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_GPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_gpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)

            code = root / "code"
            output = root / "output"
            devices = root / "devices"
            driver_dir = root / "driver-libs"
            for path in (code, output, devices, driver_dir):
                path.mkdir()
            device_pairs = []
            for guest in ("/dev/nvidia1", "/dev/nvidiactl", "/dev/nvidia-uvm"):
                host = devices / Path(guest).name
                host.write_text("")
                device_pairs.append(f"{host}={guest}")
            for name in (
                "libcuda.so",
                "libnvidia-ptxjitcompiler.so",
                "libnvidia-nvvm.so",
            ):
                (driver_dir / name).write_text(name)

            environment = {
                "SUREAL_BAZEL_GPU_DEVICES": ",".join(device_pairs),
                "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(driver_dir),
                "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
            }
            with patch.dict(os.environ, environment, clear=False):
                plan = build_plan(
                    runtime,
                    code=code,
                    output=output,
                    gpu_index=1,
                    command=["python", "-c", "pass"],
                )

            data = plan_data(plan)
            driver_hashes = {
                name: file_sha256(driver_dir / name)
                for name in (
                    "libcuda.so",
                    "libnvidia-ptxjitcompiler.so",
                    "libnvidia-nvvm.so",
                )
            }
            driver_mounts = {
                mount["role"]: mount
                for mount in data["mounts"]
                if mount["role"].startswith("gpu-driver:")
            }
            for name, digest in driver_hashes.items():
                self.assertEqual(driver_mounts[f"gpu-driver:{name}"]["digest"], digest)
            self.assertEqual(
                data["devices"],
                [
                    {
                        "role": "gpu-device:/dev/nvidia1",
                        "host_path": str((devices / "nvidia1").resolve()),
                        "inside_path": "/dev/nvidia1",
                        "mode": "writable",
                        "kind": "dev-bind",
                    },
                    {
                        "role": "gpu-device:/dev/nvidiactl",
                        "host_path": str((devices / "nvidiactl").resolve()),
                        "inside_path": "/dev/nvidiactl",
                        "mode": "writable",
                        "kind": "dev-bind",
                    },
                    {
                        "role": "gpu-device:/dev/nvidia-uvm",
                        "host_path": str((devices / "nvidia-uvm").resolve()),
                        "inside_path": "/dev/nvidia-uvm",
                        "mode": "writable",
                        "kind": "dev-bind",
                    },
                ],
            )
            self.assertNotIn("/dev/nvidia0", json.dumps(data, sort_keys=True))
            self.assertIn(["--setenv", "CUDA_VISIBLE_DEVICES", "0"], data["environment"])
            self.assertEqual(
                data["gpu"],
                {"requested_index": 1, "device_uuid": "GPU-fixture-1"},
            )

            record = record_plan(plan)
            self.assertEqual(
                record["gpu"],
                {"requested_index": 1, "device_minor": 1, "device_uuid": "GPU-fixture-1"},
            )
            record_driver_mounts = {
                mount["role"]: mount
                for mount in record["mounts"]
                if mount["role"].startswith("gpu-driver:")
            }
            for name, digest in driver_hashes.items():
                self.assertEqual(record_driver_mounts[f"gpu-driver:{name}"]["digest"], digest)
            expected_driver_hashes = {
                f"gpu-driver:{name}": digest for name, digest in driver_hashes.items()
            }
            self.assertEqual(gpu_driver_hashes_from_plan_record(record), expected_driver_hashes)
            with patch.dict(os.environ, environment, clear=False):
                self.assertEqual(
                    verify_gpu_driver_hashes_from_plan_record({"launch_plan": record}),
                    expected_driver_hashes,
                )
                self.assertEqual(
                    {
                        name: digest
                        for name, (_path, digest) in gpu_driver_paths_from_plan_record(record).items()
                    },
                    driver_hashes,
                )
                tampered = copy.deepcopy(record)
                for mount in tampered["mounts"]:
                    if mount["role"] == "gpu-driver:libcuda.so":
                        mount["digest"] = "0" * 64
                        break
                with self.assertRaisesRegex(ValueError, "gpu-driver:libcuda.so.*differs"):
                    verify_gpu_driver_hashes_from_plan_record(tampered)
            (driver_dir / "libcuda.so").write_text("swapped libcuda")
            with self.assertRaisesRegex(PlanError, "gpu-driver:libcuda.so.*changed"):
                render_plan(plan)
            self.assertEqual(
                {
                    mount["role"]: mount["digest"]
                    for mount in record_plan(plan)["mounts"]
                    if mount["role"].startswith("gpu-driver:")
                },
                {f"gpu-driver:{name}": digest for name, digest in driver_hashes.items()},
            )
            raw_record = json.dumps(record, sort_keys=True)
            self.assertNotIn(str(devices), raw_record)
            self.assertNotIn("/dev/nvidia", raw_record)

    def test_gpu_device_override_rejects_different_gpu_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_GPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_gpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)

            code = root / "code"
            output = root / "output"
            devices = root / "devices"
            driver_dir = root / "driver-libs"
            for path in (code, output, devices, driver_dir):
                path.mkdir()
            for name in ("nvidia1", "nvidiactl", "nvidia-uvm"):
                (devices / name).write_text("")
            for name in (
                "libcuda.so",
                "libnvidia-ptxjitcompiler.so",
                "libnvidia-nvvm.so",
            ):
                (driver_dir / name).write_text(name)

            valid_control = [
                f"{devices / 'nvidiactl'}=/dev/nvidiactl",
                f"{devices / 'nvidia-uvm'}=/dev/nvidia-uvm",
            ]
            cases = {
                "guest": [
                    f"{devices / 'nvidia1'}=/dev/nvidia0",
                    *valid_control,
                ],
                "host": [
                    f"/dev/nvidia0=/dev/nvidia1",
                    *valid_control,
                ],
            }
            for side, device_pairs in cases.items():
                with self.subTest(side=side):
                    environment = {
                        "SUREAL_BAZEL_GPU_DEVICES": ",".join(device_pairs),
                        "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(driver_dir),
                        "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
                    }
                    with patch.dict(os.environ, environment, clear=False):
                        with self.assertRaisesRegex(PlanError, "/dev/nvidia0"):
                            build_plan(
                                runtime,
                                code=code,
                                output=output,
                                gpu_index=1,
                                command=["python", "-c", "pass"],
                            )

    def test_gpu_device_override_must_include_requested_device(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_GPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_gpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)

            code = root / "code"
            output = root / "output"
            devices = root / "devices"
            driver_dir = root / "driver-libs"
            for path in (code, output, devices, driver_dir):
                path.mkdir()
            for name in ("nvidiactl", "nvidia-uvm"):
                (devices / name).write_text("")
            for name in (
                "libcuda.so",
                "libnvidia-ptxjitcompiler.so",
                "libnvidia-nvvm.so",
            ):
                (driver_dir / name).write_text(name)

            environment = {
                "SUREAL_BAZEL_GPU_DEVICES": ",".join(
                    [
                        f"{devices / 'nvidiactl'}=/dev/nvidiactl",
                        f"{devices / 'nvidia-uvm'}=/dev/nvidia-uvm",
                    ]
                ),
                "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(driver_dir),
                "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
            }
            with patch.dict(os.environ, environment, clear=False):
                with self.assertRaisesRegex(PlanError, "omits requested /dev/nvidia1"):
                    build_plan(
                        runtime,
                        code=code,
                        output=output,
                        gpu_index=1,
                        command=["python", "-c", "pass"],
                    )

    def test_gpu_uuid_lookup_uses_device_minor_not_nvidia_smi_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_GPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_gpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)

            code = root / "code"
            output = root / "output"
            devices = root / "devices"
            driver_dir = root / "driver-libs"
            for path in (code, output, devices, driver_dir):
                path.mkdir()
            device_pairs = []
            for guest in ("/dev/nvidia1", "/dev/nvidiactl", "/dev/nvidia-uvm"):
                host = devices / Path(guest).name
                host.write_text("")
                device_pairs.append(f"{host}={guest}")
            for name in (
                "libcuda.so",
                "libnvidia-ptxjitcompiler.so",
                "libnvidia-nvvm.so",
            ):
                (driver_dir / name).write_text(name)

            environment = {
                "SUREAL_BAZEL_GPU_DEVICES": ",".join(device_pairs),
                "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(driver_dir),
            }
            proc_gpus = root / "proc/driver/nvidia/gpus"
            for bus, minor, uuid in (
                ("0000:8f:00.0", 0, "GPU-zero"),
                ("0000:90:00.0", 1, "GPU-one"),
            ):
                info = proc_gpus / bus / "information"
                info.parent.mkdir(parents=True)
                info.write_text(f"GPU UUID: \t {uuid}\nBus Location: \t {bus}\nDevice Minor: \t {minor}\n")

            with patch.dict(os.environ, environment, clear=False):
                with patch("insula.launch_plan._GPU_DRIVER_INFO_ROOT", proc_gpus):
                    with patch("insula.launch_plan.subprocess.check_output") as check_output:
                        plan = build_plan(
                            runtime,
                            code=code,
                            output=output,
                            gpu_index=1,
                            command=["python", "-c", "pass"],
                        )

            self.assertEqual(
                record_plan(plan)["gpu"],
                {"requested_index": 1, "device_minor": 1, "device_uuid": "GPU-one"},
            )
            check_output.assert_not_called()

    def test_gpu_device_override_accepts_remapped_host_paths_for_requested_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_GPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_gpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)

            code = root / "code"
            output = root / "output"
            devices = root / "remapped-devices"
            driver_dir = root / "driver-libs"
            for path in (code, output, devices, driver_dir):
                path.mkdir()
            device_pairs = []
            remaps = {
                "/dev/nvidia1": "gpu-one",
                "/dev/nvidiactl": "ctl",
                "/dev/nvidia-uvm": "uvm",
                "/dev/nvidia-uvm-tools": "uvm-tools",
                "/dev/nvidia-modeset": "modeset",
            }
            for guest, host_name in remaps.items():
                host = devices / host_name
                host.write_text("")
                device_pairs.append(f"{host}={guest}")
            for name in (
                "libcuda.so",
                "libnvidia-ptxjitcompiler.so",
                "libnvidia-nvvm.so",
            ):
                (driver_dir / name).write_text(name)

            environment = {
                "SUREAL_BAZEL_GPU_DEVICES": ",".join(device_pairs),
                "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(driver_dir),
                "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
            }
            with patch.dict(os.environ, environment, clear=False):
                plan = build_plan(
                    runtime,
                    code=code,
                    output=output,
                    gpu_index=1,
                    command=["python", "-c", "pass"],
                )

            data = plan_data(plan)
            devices_by_inside = {
                device["inside_path"]: device["host_path"] for device in data["devices"]
            }
            self.assertEqual(
                devices_by_inside,
                {guest: str((devices / host_name).resolve()) for guest, host_name in remaps.items()},
            )
            self.assertEqual(
                data["gpu"],
                {"requested_index": 1, "device_uuid": "GPU-fixture-1"},
            )

    def test_split_runtime_root_mounts_checked_entries_instead_of_whole_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            for name in ("experiment", "source", "outputs", "tmp", "proc", "dev", "opt"):
                (rootfs / name).mkdir(exist_ok=True)
            (rootfs / "opt" / "tool.txt").write_text("tool\n")
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_cpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)
            code = root / "code"
            source = root / "source"
            output = root / "output"
            readonly = rootfs / "opt" / "readonly"
            for path in (code, source, output, readonly):
                path.mkdir(parents=True, exist_ok=True)

            plan = build_plan(
                runtime,
                code=code,
                source=source,
                output=output,
                named_inputs={"/opt/readonly": readonly},
                command=["true"],
                split_runtime_root=True,
            )
            mounts = plan_data(plan)["mounts"]

            self.assertNotIn(
                {
                    "role": "runtime",
                    "host_path": str(rootfs.resolve()),
                    "inside_path": "/",
                    "mode": "read_only",
                    "kind": "bind",
                },
                mounts,
            )
            self.assertIn(
                {
                    "role": "runtime-entry:bin",
                    "host_path": str((rootfs / "bin").resolve()),
                    "inside_path": "/bin",
                    "mode": "read_only",
                    "kind": "bind",
                },
                mounts,
            )
            self.assertIn(
                {
                    "role": "runtime-entry:opt",
                    "host_path": str((rootfs / "opt").resolve()),
                    "inside_path": "/opt",
                    "mode": "read_only",
                    "kind": "bind",
                },
                mounts,
            )
            runtime_entry_paths = {
                mount["inside_path"] for mount in mounts if mount["role"].startswith("runtime-entry:")
            }
            self.assertFalse(
                {"/experiment", "/source", "/outputs", "/tmp", "/proc", "/dev"} & runtime_entry_paths
            )
            self.assertEqual(plan_data(plan)["command"], ["true"])

    def test_split_runtime_root_preserves_top_level_symlink_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_CPU_ROOTFS_NAME
            (rootfs / "usr/bin").mkdir(parents=True)
            (rootfs / "usr/lib").mkdir(parents=True)
            (rootfs / "usr/bin/python").write_text("#!/bin/sh\n")
            (rootfs / "usr/bin/python").chmod(0o755)
            os.symlink("usr/bin", rootfs / "bin")
            os.symlink("usr/lib", rootfs / "lib")
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_cpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)
            code = root / "code"
            output = root / "output"
            for path in (code, output):
                path.mkdir()

            plan = build_plan(
                runtime,
                code=code,
                output=output,
                command=["true"],
                split_runtime_root=True,
            )
            mounts = {mount["role"]: mount for mount in plan_data(plan)["mounts"]}
            argv = render_plan(plan)

            self.assertEqual(
                mounts["runtime-entry:bin"],
                {
                    "role": "runtime-entry:bin",
                    "inside_path": "/bin",
                    "mode": "read_only",
                    "kind": "symlink",
                    "symlink_target": "usr/bin",
                },
            )
            self.assertEqual(mounts["runtime-entry:lib"]["kind"], "symlink")
            self.assertIn("--symlink", argv)
            self.assertNotIn(str((rootfs / "bin").resolve()), argv)

    def test_split_runtime_root_reuses_overlap_rules_for_writable_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            writable = rootfs / "opt" / "cache"
            writable.mkdir(parents=True)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_cpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)
            code = root / "code"
            output = root / "output"
            for path in (code, output):
                path.mkdir()

            with self.assertRaisesRegex(
                PlanError,
                "runtime-entry:opt.*input:/opt/cache|input:/opt/cache.*runtime-entry:opt",
            ):
                build_plan(
                    runtime,
                    code=code,
                    output=output,
                    writable_inputs={"/opt/cache": writable},
                    command=["true"],
                    split_runtime_root=True,
                )

    def test_with_mounts_extends_existing_plan_through_public_validation(self):
        from insula.launch_plan import with_mounts

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            output = root / "output"
            resource = root / "resource"
            for path in (code, output, resource):
                path.mkdir()
            plan = build_plan(runtime, code=code, output=output, command=["python", "/experiment/a.py"])

            extended = with_mounts(
                plan,
                before_devices=[
                    Mount("resource-layer", "bind", "/tmp/resource-layer", "read_only", resource)
                ],
                command=["python", "/tmp/resource-layer/wrap.py", "/experiment/a.py"],
            )
            data = plan_data(extended)

            self.assertEqual(data["command"], ["python", "/tmp/resource-layer/wrap.py", "/experiment/a.py"])
            self.assertIn(
                {
                    "role": "resource-layer",
                    "host_path": str(resource.resolve()),
                    "inside_path": "/tmp/resource-layer",
                    "mode": "read_only",
                    "kind": "bind",
                },
                data["mounts"],
            )
            with self.assertRaisesRegex(PlanError, "writable mount overlaps"):
                with_mounts(
                    plan,
                    before_devices=[
                        Mount("overlap", "bind", "/tmp/overlap", "writable", output / "child")
                    ],
                )

    def test_with_mounts_preserves_plan_recording_options(self):
        from insula.launch_plan import with_mounts

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            scientific = root / "scientific"
            output = scientific / "run-output"
            extra = root / "extra"
            for path in (code, output, extra):
                path.mkdir(parents=True)
            plan = build_plan(
                runtime,
                code=code,
                output=output,
                named_inputs={"/tmp/scientific": scientific},
                command=["python", "/experiment/a.py"],
                source_snapshot_digest="snapshot-fixture",
                named_input_digests={"/tmp/scientific": "3" * 64},
                allow_readonly_inputs_cover_output=True,
            )

            extended = with_mounts(
                plan,
                before_devices=[Mount("extra", "bind", "/tmp/extra", "read_only", extra)],
            )
            mounts = {mount["role"]: mount for mount in record_plan(extended)["mounts"]}

            self.assertEqual(mounts["code"]["digest"], "snapshot-fixture")
            self.assertEqual(mounts["input:/tmp/scientific"]["digest"], "3" * 64)
            self.assertEqual(mounts["input:/tmp/scientific"]["inside_path"], "/tmp/scientific")

    def test_render_plan_never_renders_the_same_inside_path_twice(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            plan = LaunchPlan(
                runtime=runtime,
                mounts=(
                    Mount("runtime", "bind", "/", "read_only", runtime.rootfs),
                    Mount("tmp", "tmpfs", "/tmp", "writable"),
                ),
                environment=(),
                working_directory="/",
                command=("true",),
                unshare_flags=("--unshare-all",),
            )

            argv = render_plan(plan)
            rendered = []
            index = 1
            while index < argv.index("--"):
                option = argv[index]
                if option in {"--ro-bind", "--bind", "--dev-bind", "--symlink"}:
                    rendered.append(argv[index + 2])
                    index += 3
                elif option in {"--proc", "--dev", "--tmpfs"}:
                    rendered.append(argv[index + 1])
                    index += 2
                elif option == "--chdir":
                    index += 2
                elif option == "--setenv":
                    index += 3
                else:
                    index += 1

            duplicates = sorted({inside for inside in rendered if rendered.count(inside) > 1})
            self.assertEqual(duplicates, [])


if __name__ == "__main__":
    unittest.main()
