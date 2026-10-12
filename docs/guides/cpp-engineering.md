# C++ Engineering

Sureal's C++ and CUDA code is small and mostly serves native fixtures,
live-gate tools, rootfs smoke tests and 3D reference integrations. Keep it
boring, explicit, RAII-based and close to the scientific boundary it supports.

This guide applies to active C++ and CUDA under `autonomy/` and `parallax/`.
Do not edit retained evidence, source snapshots, `autonomy/research/**`,
`parallax/research/**`, procedure records, or archived harness files to make a
style check pass.

## File Names And Suffixes

Use only these suffixes for native code:

| File kind | Suffix | Example |
|---|---:|---|
| C++ source | `.cc` | `autonomy/camera/project_camera.cc` |
| C++ header | `.hh` | `<concept>/projection.hh` |
| CUDA source | `.cu` | `<concept>/range_grid.cu` |
| CUDA header | `.cuh` | `<concept>/range_grid.cuh` |
| Native C++ test | `*_test.cc` | `<concept>/projection_test.cc` |

Do not add `.cpp`, `.h`, `.hpp` or `.hxx` files under active `autonomy/` or
`parallax/` C++ scopes.

## File Layout

Use this order in `.cc` and `.cu` files:

1. The file's own header, when one exists.
2. A blank line.
3. Other project headers.
4. A blank line.
5. Third-party, CUDA, generated and platform headers.
6. A blank line.
7. C and C++ standard library headers.
8. A blank line.
9. The project namespace when the file is library code, or an anonymous
   namespace for private helpers in a standalone command-line tool.
10. Constants, private helper types, private helper functions, exported
    functions, then `main` or registration macros at the bottom.

Headers use this order:

1. `#pragma once`.
2. A blank line.
3. Third-party, CUDA, generated and platform headers required by declarations.
4. A blank line.
5. Standard library headers required by declarations.
6. A blank line.
7. Project headers only when the declaration truly needs a complete type or
   inline helper; otherwise forward declare.
8. The project namespace.

Include what you use. A header must compile when included first in an empty
translation unit with the normal Bazel target flags. Do not rely on another
include to provide a type, macro or function.

## Naming

Use these names unless an upstream API, generated header or third-party
interface requires a different spelling:

| Entity | Rule | Examples |
|---|---|---|
| Namespaces | `lower_snake`, rooted at the concept | `autonomy`, `parallax` |
| File and directory names | `lower_snake` | `rootfs_compiler_smoke_test.cc` |
| Classes and structs | `PascalCase` | `FrameRecord`, `RunStats` |
| Functions | `lower_snake` | `load_associations`, `dominant_map_id` |
| CUDA kernels | `lower_snake` ending in `_kernel` | `range_grid_kernel` |
| Kernel launch wrappers | `launch_` plus the operation name | `launch_range_grid` |
| Variables and parameters | `lower_snake` | `frame_index`, `output_path` |
| Non-constant data members | `lower_snake_` | `stream_`, `state_` |
| Constants | `kPascalCase` | `kMaxRows`, `kThreads` |
| Enum types | `PascalCase` `enum class` | `Mode` |
| Enum values | `PascalCase` | `Baseline`, `Occlusion` |
| Template parameters | Descriptive `PascalCase` | `Record`, `Scalar` |
| Macros | `UPPER_SNAKE_CASE` with a concept prefix | `AUTONOMY_REQUIRE` |

Keep upstream names when overriding or implementing an external interface.
Generated protobuf accessors, ORB-SLAM APIs, OpenCV names and CUDA runtime names
keep their upstream spelling.

## Ownership And Lifetime

Use RAII for every resource that can be scoped:

- Prefer values, containers and `std::unique_ptr` for exclusive ownership.
- Use `std::shared_ptr` only when multiple owners really exist.
- Store file handles, streams, CUDA streams, CUDA events, locks and temporary
  working state in objects whose destructors release or restore them.
- Use `std::lock_guard` or `std::unique_lock` for locks. Manual lock/unlock
  pairs are not allowed.
- Raw `new` and `delete` are allowed only where an external API takes ownership
  or requires a raw pointer handoff. Add a nearby comment containing `owns` or
  `ownership` that states who owns the object after the line runs.
- Destructors, deleters and `noexcept` paths must not throw. Catch and suppress
  or report failures in a no-throw way.

Prefer return values over output parameters. Use output parameters only when a
protobuf, CUDA, OpenCV, ORB-SLAM or other external API requires them.

## Modern C++17

Use modern C++17 consistently:

- Mark every single-argument constructor `explicit`.
- Write `override` on every virtual override.
- Use `final` when a class is not designed for inheritance.
- Define or delete copy and move operations deliberately for owning types.
- Use `enum class`, never plain `enum`.
- Use `nullptr`, never `NULL` or `0`, for null pointers.
- Use C++ casts: `static_cast`, `reinterpret_cast`, `const_cast` or
  `dynamic_cast`. Do not use C-style casts.
- Keep variables in the narrowest scope and initialize them at declaration.
- Use `const` for immutable values and references.
- Use `auto` when the initializer makes the type obvious or the type is noisy;
  spell the type when it improves readability or guards a boundary conversion.

Keep functions small and focused. About 40 lines is the target. A longer
function needs a clear reason, usually because a command-line harness, external
library interaction or unavoidable switch is clearer in one place.

## Namespaces

Do not write `using namespace` in headers or at file scope. Prefer qualified
names. Narrow aliases are acceptable inside functions or an anonymous namespace
when they make a local block clearer.

Close named namespaces with a comment:

```cc
}  // namespace autonomy
```

## Errors And Invariants

Match the current native-tool error model. Short command-line tools validate
inputs with a small `require` helper that throws `std::runtime_error`; `main`
catches `std::exception`, writes the message to stderr and returns non-zero.

Use this model unless a module has a stronger local contract:

- Validate input files, sizes, parse results, dimensions and numeric values at
  the boundary.
- Throw `std::runtime_error` for command-line tool failures.
- Let helper functions return values rather than filling output parameters.
- Do not introduce a status framework only for style consistency.
- Error messages name the violated contract and include the relevant file,
  mode, shape, device or identifier when that helps reproduce the failure.

## Output

Stdout is for command results only: machine-readable summaries, explicit PASS
lines, paths requested by the caller, or final measured values. Diagnostics,
usage errors and exception messages go to stderr.

Do not print secrets. Do not write to HDFS or shared caches from native tools
unless a ticket and launch plan explicitly authorize that behavior.

## Comments

Write comments that preserve intent a future maintainer cannot read from the
code alone:

- Explain ownership transfers, lifetime constraints, synchronization
  requirements and compatibility with external APIs.
- Put comments immediately above the code they justify, or on the same line for
  a short ownership note.
- Public declarations in headers should document non-obvious contracts,
  thread-safety, ownership and valid timing for returned values.
- Do not narrate the statement below the comment.
- Keep TODOs actionable and tied to a tracked task or clear deferred decision.

## CUDA Kernels And Launches

CUDA source lives in `.cu` files. Use `.cuh` only for CUDA declarations or
templates that must be included by another CUDA translation unit.

These rules apply when Sureal adds or changes CUDA:

- Name kernels `*_kernel`.
- Name launch wrappers `launch_*`.
- Validate device, dtype, layout, shape and contiguity before launch.
- Return immediately for empty outputs when the operation has no work.
- Do not implicitly use CUDA's default stream.
- Compute block counts through a helper or a local `const auto blocks`.
- Use `static_cast` for grid/block index widening and launch-size narrowing.
- Use `reinterpret_cast` only at true CUDA or external-library pointer
  boundaries.
- Pass shared-memory size explicitly when a kernel uses `extern __shared__`.
- Check every kernel launch with `cudaGetLastError()` through the module's
  local error wrapper or `std::runtime_error` conversion.
- Check every CUDA driver/runtime call and preserve the failing operation in
  the error message.
- Do not synchronize the device in a launch wrapper unless the semantic
  contract requires a blocking operation.

## Formatting

Formatting is decided by the repository `.clang-format`, never by hand. Run it
through the Bazel-pinned gate:

```bash
./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate
```

The config is Google-based C++ with a 120-column limit. It deliberately leaves
four things to the author, so formatting never changes anything but whitespace:
includes are not sorted, long string literals are not broken, comments are not
reflowed, and macro bodies are left as written.

## Tests

Native tests use `*_test.cc`, sit beside the source they exercise and are built
by Bazel. Keep them deterministic and value-based. If a native command is
exercised through a Python test, the C++ source still follows this guide and
the Bazel target is the verification boundary.

## Mechanical Lint

`harness/lint/check_cxx.py` scans tracked active C++ under `autonomy/` and
`parallax/`. It is aware of comments and string literals, excludes historical
archives and submodules through `harness/lint/pinned_sources.py`, and rejects:

- forbidden suffixes: `.cpp`, `.h`, `.hpp`, `.hxx`;
- headers without `#pragma once`;
- `using namespace` in headers or at file scope;
- `NULL`;
- plain `enum`;
- C-style casts of common scalar and pointer types;
- raw `new` or `delete` without a nearby `owns` or `ownership` comment;
- lines longer than 120 columns.

`//:repo_gate` runs the checker.

## Known Deviations

Existing C++ issues that entered lint scope when the lint-side source freeze was
retired are recorded in the shrink-only
`harness/lint/cxx_lint_baseline.json`:

- `autonomy/camera/project_camera.cc`
- `autonomy/motion/cli/motion_metrics_main.cc`
- `autonomy/motion/ingestion/fnv_bytes_fixture.cc`
- `autonomy/motion/ingestion/motion_causal_project.cc`
- `autonomy/motion/ingestion/native_camera_token_fixture.cc`
- `autonomy/motion/ingestion/native_current_geometry_reference.cc`
- `autonomy/motion/ingestion/native_delta_component_fixture.cc`
- `autonomy/motion/ingestion/native_delta_component_reference.cc`
- `autonomy/motion/ingestion/native_geometry_corruption_fixture.cc`
- `autonomy/motion/ingestion/native_geometry_metadata_fixture.cc`
- `autonomy/motion/ingestion/native_metric_handoff_fixture.cc`
- `autonomy/motion/ingestion/native_metric_handoff_reference.cc`
- `autonomy/motion/ingestion/native_source_inventory.cc`
- `autonomy/motion/ingestion/native_source_link_fixture.cc`
- `autonomy/motion/pooled/motion_metrics_pooled_main.cc`

Current unbaselined deviations:

- `parallax/insulas/orb-slam/surflo_rgbd.cc` has `truth_cloud`,
  `run_sequence` and `main` functions longer than the target 40-line size. They
  predate this guide and remain because splitting the ORB-SLAM harness is a
  behavior change outside this ticket.
