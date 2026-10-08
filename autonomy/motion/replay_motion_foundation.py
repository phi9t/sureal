#!/usr/bin/env python3
"""Replay locked Motion foundation gates; refuse reused output directories."""
import argparse
import json
import os
import pathlib
import re
import resource
import shutil
import subprocess
import time

from evidence.source_snapshot import file_sha256 as sha
from evidence.source_snapshot import is_regular_file
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run-id", required=True)
args = parser.parse_args()
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", args.run_id):
    parser.error("run-id must be a safe, bounded directory name")

MOTION = pathlib.Path(__file__).resolve().parent
AUTONOMY = MOTION.parent
CACHE = pathlib.Path.home() / ".cache/waystone/waymo-perception"
run_root = CACHE / "insula" / args.run_id
run_root.mkdir()
code = run_root / "code"
code.mkdir()
(code / "motion/cli").mkdir(parents=True)
(code / "motion/ingestion").mkdir(parents=True)
(code / "motion/pooled").mkdir(parents=True)
(code / "check_tensorflow.py").write_text(
    "import importlib.util\n"
    "assert importlib.util.find_spec('tensorflow') is None\n"
    "print('TensorFlow absent')\n"
)
for source, target in [
    ("motion_causal_project.cc", "project.cc"),
    ("native_source_link_fixture.cc", "prefix.cc"),
    ("native_source_inventory.cc", "native_source_inventory.cc"),
]:
    shutil.copy(MOTION / "ingestion" / source, code / target)
for source, target in [
    ("cli/motion_native_cli_test.py", "motion/cli/motion_native_cli_test.py"),
    ("cli/motion_joint_cli_test.py", "motion/cli/motion_joint_cli_test.py"),
    ("ingestion/motion_causal_projection_test.py", "motion/ingestion/motion_causal_projection_test.py"),
    ("pooled/motion_pooled_cli_test.py", "motion/pooled/motion_pooled_cli_test.py"),
    ("pooled/CMakeLists.txt", "motion/pooled/CMakeLists.txt"),
    ("pooled/motion_metrics_pooled_main.cc", "motion/pooled/motion_metrics_pooled_main.cc"),
]:
    shutil.copy(MOTION / source, code / target)

inputs = run_root / "inputs"
inputs.mkdir()
parents = {}
for split, folder in [
    ("training", "motion-native-link-v5"),
    ("validation", "motion-validation-native-link-v1"),
]:
    parent = AUTONOMY / "research" / ("motion-" + split + "-native-link-verified.json")
    receipt = json.loads(parent.read_text())
    assert (
        receipt["exit_code"] == 0
        and receipt["future_rejection_exit_code"] != 0
        and receipt["key_and_duplicate_refusals"]
    )
    assert all(sha(path) == digest for path, digest in receipt["artifacts"].items())
    parents[str(parent)] = sha(parent)
    os.link(CACHE / "insula" / folder / "output/merged.pb", inputs / (split + ".pb"))

rootfs = CACHE / "motion-cli-rootfs-v2"
lock = json.loads(pathlib.Path(str(rootfs) + ".lock.json").read_text())
verify_rootfs(rootfs, lock["rootfs_sha256"])
pins = {
    str(path): sha(path)
    for directory in [code, inputs]
    for path in pathlib.Path(directory).rglob("*")
    if is_regular_file(path)
}
output = run_root / "output"
output.mkdir()
checks = []
start = time.monotonic()


def execute(name, shell, expected=0):
    command = launch_plan(rootfs, code, inputs, output, ["/bin/sh", "-c", shell])
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    (output / (name + ".log")).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, (name, result.stderr)
    checks.append(
        {
            "name": name,
            "command": command,
            "exit_code": result.returncode,
            "expected_exit_code": expected,
        }
    )
    print(name, result.returncode, result.stdout[-180:], result.stderr[-180:], flush=True)
    return result


build = (
    "g++ -std=c++17 -O2 -I/generated /experiment/project.cc "
    "/motion-build/libwod_motion_proto.a -lprotobuf -pthread -o /outputs/motion_causal_project && "
    "g++ -std=c++17 -O2 -I/generated /experiment/prefix.cc "
    "/motion-build/libwod_motion_proto.a -lprotobuf -pthread -o /outputs/prefix && "
    "cmake -S /experiment/motion/pooled -B /outputs/pooled-build > /outputs/build.log 2>&1 && "
    "cmake --build /outputs/pooled-build -j2 >> /outputs/build.log 2>&1"
)
execute("tensorflow-absence", "python /experiment/check_tensorflow.py")
execute("build", build)
native = execute(
    "native-regressions",
    "/motion-build/motion_metrics_test --gtest_color=no && "
    "/motion-build/motion_metrics_utils_test --gtest_color=no",
)
assert "[  PASSED  ] 19 tests." in native.stdout
assert "[  PASSED  ] 23 tests." in native.stdout

# Existing boundary fixture modules execute in the same pinned native runtime.
for name, directory, pattern, count in [
    ("native_cli", "motion/cli", "motion_native_cli_test.py", 6),
    ("joint_cli", "motion/cli", "motion_joint_cli_test.py", 2),
    ("causal_projection", "motion/ingestion", "motion_causal_projection_test.py", 5),
    ("pooled_cli", "motion/pooled", "motion_pooled_cli_test.py", 6),
]:
    test_command = f"python -m unittest discover -s /experiment/{directory} -p {pattern} -v"
    result = execute(name, test_command)
    assert "Ran " + str(count) + " tests" in result.stderr and "\nOK\n" in result.stderr

for split, folder in [
    ("training", "motion-native-link-v5"),
    ("validation", "motion-validation-native-link-v1"),
]:
    execute(
        split + "-prefix",
        "/outputs/motion_causal_project /source/"
        + split
        + ".pb /outputs/"
        + split
        + "-observations.pb && /outputs/prefix check /source/"
        + split
        + ".pb /outputs/"
        + split
        + "-observations.pb /outputs/"
        + split
        + "-future-injection.pb",
    )
    assert sha(output / (split + "-observations.pb")) == sha(
        CACHE / "insula" / folder / "output/observations.pb"
    )
    refused = execute(
        split + "-future-refusal",
        "/outputs/motion_causal_project /outputs/"
        + split
        + "-future-injection.pb /outputs/forbidden-"
        + split
        + ".pb",
        1,
    )
    assert "sensor coverage must be history/current only" in refused.stderr
    assert not (output / ("forbidden-" + split + ".pb")).exists()

assert all(sha(path) == digest for path, digest in pins.items())
record = {
    "checks": checks,
    "runtime_lock": lock,
    "pins": pins,
    "parent_receipts": parents,
    "native_regressions_passed": 42,
    "boundary_fixture_groups_passed": 19,
    "real_prefixes_replayed_exact": 2,
    "real_future_sensor_refusals": 2,
    "elapsed_seconds": time.monotonic() - start,
    "peak_children_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    "artifacts": {str(path): sha(path) for path in regular_files(output)},
    "scope": (
        "fresh foundation replay: native Motion regressions, single/joint/pooled/causal "
        "boundary fixtures and two exact real-source causal prefixes; scientific cohort/models remain separate"
    ),
}
(run_root / "receipt.json").write_text(json.dumps(record, indent=2))
print("PASS current Motion foundation replay", flush=True)
