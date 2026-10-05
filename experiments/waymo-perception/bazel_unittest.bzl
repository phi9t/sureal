def _repo_python_unittest_impl(ctx):
    repo_root = "${TEST_SRCDIR}/${TEST_WORKSPACE}"
    pythonpath = ":".join([repo_root + "/" + root for root in ctx.attr.import_roots])
    script = ctx.actions.declare_file(ctx.label.name + ".sh")
    ctx.actions.write(
        script,
        """#!/usr/bin/env bash
set -euo pipefail
repo_root="${TEST_SRCDIR}/${TEST_WORKSPACE}"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="%s${PYTHONPATH:+:${PYTHONPATH}}"
exec /usr/local/bin/python "${repo_root}/%s" "$@"
""" % (pythonpath, ctx.file.src.short_path),
        is_executable = True,
    )
    return [DefaultInfo(executable = script, runfiles = ctx.runfiles(files = [ctx.file.src] + ctx.files.deps))]


repo_python_unit_test = rule(
    implementation = _repo_python_unittest_impl,
    attrs = {
        "src": attr.label(allow_single_file = [".py"], mandatory = True),
        "deps": attr.label_list(allow_files = [".py"]),
        "import_roots": attr.string_list(default = ["experiments/waymo-perception"]),
    },
    test = True,
)
