# Semantic Polyglot Repository Layout

## Sureal Final Concept Map

Sureal follows the semantic layout directly under `autonomy/`. Active code is
owned by concept, not by language, runtime, file kind, or temporary study stage:

```text
autonomy/
├── association/         association runtime contracts and provenance
├── camera/              native camera components, publication, replay, eviction
├── dataset/             source admission, point/sidecar data, tracer contracts
├── detection/           detector models, native box jobs, exports, diagnostics
├── evidence/            source snapshots, pins, journals, release evidence
├── evaluation/          metric/evaluator checks and perception gate audits
├── geometry/            reconstruction, native ranges, scene validation
├── inspection/          viewer/export tooling
├── insula/              rootfs recipes, sandbox planning, Bazel wrapper launch
├── motion/              motion ingestion, metrics, and command recipes
├── range_view/          range frontend and range/pillar probes
├── resources/           resource staging, archive, retention primitives
├── retention/           sustained/native-cache publication and retention
├── segmentation/        semantic/SAM support and recovery checks
├── studies/             cross-concept study orchestration and study records
└── training_execution/  sustained training controller and admissions
```

Cross-concept workflows live at the concept level that owns the workflow. For
example, a sequential scientific cohort lifecycle that dispatches both
`dataset` and `camera` commands is a `studies` workflow, not a `dataset`
command. A lower concept must not depend upward merely to run a higher-level
orchestration.

Source pins are snapshot bindings. They identify the source bytes captured for a
receipt, not a promise that the current working tree still matches the historical
receipt. Historical schema 1 receipts use component-relative paths; schema 2
source snapshot receipts use repository paths rooted at `autonomy/`. New
receipts should bind the executable Bazel target and its source/data closure.

`bazelw` is the root entrypoint for tests and builds. It resolves the `autonomy`
root, reexecutes `insula.bazel_launcher`, preserves the caller working
directory through the internal argument, and does not require legacy child
directory mounts under `/experiment`.

## 1. Primary rule: directories express concepts, not languages

Do **not** structure the repository as:

```text
cpp/
rust/
python/
cuda/
```

unless those directories happen to represent meaningful product boundaries, which normally they do not.

Instead:

```text
scheduler/
runtime/
tensor_ops/
storage/
protocol/
training/
serving/
telemetry/
```

Each component contains whatever implementation languages are appropriate.

The filesystem answers:

> **What part of the system is this?**

The build graph answers:

> **How is this artifact built?**

The package managers answer:

> **What external dependencies does this ecosystem need?**

These are separate concerns.

---

# 2. Repository root

A good root therefore looks more like:

```text
repo/
├── MODULE.bazel
├── MODULE.bazel.lock
├── BUILD.bazel
├── .bazelrc
├── .bazelversion
│
├── Cargo.toml
├── Cargo.lock
├── rust-toolchain.toml
│
├── pyproject.toml
├── uv.lock
├── .python-version
│
├── justfile
│
├── bazel/
│   ├── rules/
│   ├── macros/
│   ├── toolchains/
│   └── platforms/
│
├── scheduler/
├── runtime/
├── tensor_ops/
├── protocol/
├── storage/
└── tests/
```

The root manifests are **workspace indexes**, not indications that the repository is fundamentally a Rust or Python repository.

Cargo workspaces explicitly allow members at arbitrary nested paths such as `member1`, `path/to/member2`, and globbed paths. All workspace crates share the root `Cargo.lock`.

uv workspaces work similarly: members are directories selected by paths/globs, each member has its own `pyproject.toml`, and the workspace shares one `uv.lock`.

So neither ecosystem requires:

```text
rust/...
python/...
```

---

# 3. Think of Cargo and uv as projections over the tree

Suppose our actual architecture is:

```text
repo/
├── scheduler/
├── runtime/
├── tensor_ops/
├── tokenizer/
├── storage/
└── telemetry/
```

The Cargo workspace might see:

```text
scheduler/
runtime/
tokenizer/
storage/engine/
```

while uv sees:

```text
tensor_ops/
tokenizer/bindings/
telemetry/
```

and Bazel sees **all of it**.

Conceptually:

```text
                       semantic repository tree

        scheduler     tensor_ops     tokenizer      telemetry
            │             │              │              │
            │             │              │              │
      ┌─────┴─────────────┴──────────────┴──────────────┐
      │                                                  │
      ▼                                                  ▼
 Cargo projection                                  uv projection
      │                                                  │
 Cargo.toml                                          pyproject.toml
 Cargo.lock                                             uv.lock
      │                                                  │
      └──────────────────────┬───────────────────────────┘
                             │
                             ▼
                            Bazel
                             │
                    complete system graph
```

This is the mental model I would standardize.

---

# 4. Example: Python-heavy Torch component with C++ and CUDA

A component like a custom attention implementation should be organized around **attention**, not around its languages:

```text
tensor_ops/
├── BUILD.bazel
├── pyproject.toml
│
├── tensor_ops/
│   ├── __init__.py
│   ├── attention.py
│   ├── attention_test.py
│   └── dispatch.py
│
├── attention/
│   ├── attention.h
│   ├── attention.cc
│   ├── attention_test.cc
│   │
│   ├── attention_kernel.cuh
│   ├── attention_kernel.cu
│   └── attention_kernel_test.cu
│
└── bindings/
    ├── torch_extension.cc
    └── torch_extension_test.cc
```

This directory tells you something useful:

```text
tensor_ops/
    attention/
    bindings/
```

Compare that with:

```text
python/tensor_ops/
cpp/tensor_ops/
cuda/tensor_ops/
```

The second representation physically tears apart one conceptual component because its implementation happens to cross language boundaries.

That is exactly what we want to avoid.

---

# 5. Bazel package follows semantic ownership

Its `BUILD.bazel` can simply express the implementation graph:

```python
cc_library(
    name = "attention",
    srcs = ["attention/attention.cc"],
    hdrs = ["attention/attention.h"],
)

cc_test(
    name = "attention_test",
    srcs = ["attention/attention_test.cc"],
    deps = [":attention"],
)

cuda_library(
    name = "attention_kernel",
    srcs = ["attention/attention_kernel.cu"],
    hdrs = ["attention/attention_kernel.cuh"],
)

cuda_test(
    name = "attention_kernel_test",
    srcs = ["attention/attention_kernel_test.cu"],
    deps = [":attention_kernel"],
)

py_library(
    name = "python_api",
    srcs = glob(["tensor_ops/*.py"]),
)

repo_torch_extension(
    name = "extension",
    binding_srcs = ["bindings/torch_extension.cc"],
    deps = [
        ":attention",
        ":attention_kernel",
    ],
)
```

The exact CUDA/extension macros are repository infrastructure choices.

The important structure is:

```text
//tensor_ops:attention
//tensor_ops:attention_kernel
//tensor_ops:extension
//tensor_ops:python_api
```

not:

```text
//cpp:attention
//cuda:attention
//python:tensor_ops
```

Target names should usually describe the **artifact or responsibility**, not its implementation language.

---

# 6. Interop becomes an explicit build edge

For a Torch extension:

```text
Python API
    │
    ▼
Torch extension
    │
    ├──── C++
    │
    └──── CUDA
```

Bazel models that literally:

```text
:tensor_ops
      │
      ▼
:extension
   ┌──┴───────────┐
   ▼              ▼
:attention    :attention_kernel
```

There is no special reason the underlying source files need different top-level directories.

In fact, keeping them together makes the graph easier to understand.

---

# 7. Example: Rust ↔ Python through PyO3

The same idea applies to PyO3.

Suppose `tokenizer` is fundamentally one component:

```text
tokenizer/
├── BUILD.bazel
├── Cargo.toml
│
├── src/
│   ├── lib.rs
│   ├── trie.rs
│   └── normalize.rs
│
├── tests/
│   └── public_api.rs
│
└── bindings/
    ├── BUILD.bazel
    ├── Cargo.toml
    ├── pyproject.toml
    │
    ├── src/
    │   └── lib.rs
    │
    └── tokenizer/
        ├── __init__.py
        ├── api.py
        └── api_test.py
```

The distinction here is semantic:

```text
tokenizer/
    core implementation
    bindings/
```

rather than:

```text
rust/tokenizer/
python/tokenizer/
```

The `bindings` directory happens to contain both a Cargo package and a Python package because its job is to implement the Rust/Python boundary.

That is perfectly reasonable.

---

# 8. The same directory can belong to two workspaces

This is an especially useful consequence.

For example:

```text
tokenizer/bindings/
├── Cargo.toml
├── pyproject.toml
└── BUILD.bazel
```

can simultaneously be:

```text
a Cargo workspace member
+
a uv workspace member
+
a Bazel package
```

Those are not competing interpretations.

They describe different aspects of the same component:

```text
Cargo.toml
    → Rust dependency/package semantics

pyproject.toml
    → Python dependency/package semantics

BUILD.bazel
    → actual artifact/dependency/build graph
```

That is exactly the sort of overlap we should permit.

---

# 9. Root Cargo workspace

The root Cargo workspace can simply enumerate whichever semantic directories contain Rust crates:

```toml
[workspace]
resolver = "3"

members = [
    "scheduler",
    "runtime",
    "tokenizer",
    "tokenizer/bindings",
    "storage/engine",
]
```

There is no need for them to share a parent directory.

Cargo explicitly supports nested paths and globs for workspace membership.

So:

```bash
cargo test -p tokenizer
cargo test -p scheduler
cargo check --workspace
```

remain normal.

---

# 10. Root uv workspace

Likewise the uv workspace could look conceptually like:

```toml
[tool.uv.workspace]
members = [
    "tensor_ops",
    "tokenizer/bindings",
    "telemetry",
    "training/*",
]
```

Each selected directory owns its own `pyproject.toml`.

uv explicitly allows workspace-member globs and shares one lockfile across those packages.

So:

```bash
uv run --package tensor-ops pytest
uv run --package telemetry pytest
```

can operate across packages that live wherever they naturally belong architecturally.

---

# 11. Bazel consumes those workspaces

Rust stays:

```text
Cargo.toml
     │
     ▼
 Cargo.lock
     │
     ▼
rules_rust crate universe
     │
     ▼
    Bazel
```

`rules_rust` explicitly supports ingesting the workspace `Cargo.toml` and `Cargo.lock` to generate the Bazel crate dependency universe.

The directory location of those crates is not the important part.

Similarly:

```text
pyproject.toml
      │
      ▼
   uv.lock
      │
      ▼
 rules_python
      │
      ▼
     Bazel
```

Current `rules_python` supports using `uv.lock` as the metadata source for `pip.parse`; that support is still described as experimental, so we should pin and test the exact version we use.

---

# 12. Native build systems stop at their natural boundary

This modifies one part of the previous policy.

Previously:

> Cargo and uv should always independently build their part of the project.

I would weaken that to:

> Cargo and uv must remain excellent native interfaces **within their own ecosystem boundary**.

For example:

```text
tokenizer Rust core
```

should work naturally with:

```bash
cargo test -p tokenizer
```

and:

```text
tensor_ops Python logic
```

should work naturally with:

```bash
uv run --package tensor-ops pytest ...
```

But when the test is:

```text
Python
   ↓
PyTorch extension
   ↓
C++
   ↓
CUDA
```

the authoritative test is:

```bash
bazel test //tensor_ops:...
```

not an increasingly elaborate attempt to make uv independently reproduce Bazel.

Likewise:

```text
Python
    ↓
PyO3
    ↓
Rust
```

has a natural Bazel integration boundary.

---

# 13. Do not hide one build system inside another

We should generally avoid:

```text
Cargo build.rs
    ↓
calls bazel
```

or:

```text
Python build backend
    ↓
secretly invokes bazel
```

or:

```text
Bazel
    ↓
runs cargo build over the entire crate
```

Those approaches obscure the actual dependency graph.

Instead Bazel should compile the relevant source through native Bazel rules:

```text
rust_library
cc_library
cuda_library
py_library
```

and compose them explicitly.

Cargo and uv supply ecosystem metadata/dependency resolution.

---

# 14. Interop rules are worth first-class repository macros

For this repository, I would eventually establish a small set of explicit interop abstractions under:

```text
bazel/rules/
```

Conceptually:

```text
repo_pybind_extension(...)
repo_torch_extension(...)
repo_pyo3_extension(...)
```

Their purpose would be to encode once:

```text
shared-library production
Python extension naming
runfiles
RPATH / loader handling
Python import path
ABI/toolchain contracts
test environment
```

Then a semantic component can say:

```python
repo_pyo3_extension(
    name = "bindings",
    crate = ":tokenizer",
    module_name = "_tokenizer",
)
```

instead of every component reinventing Rust/Python loading.

Similarly:

```python
repo_torch_extension(
    name = "ops",
    deps = [
        ":attention",
        ":attention_kernel",
    ],
)
```

These are precisely the kinds of cross-language semantics that belong in Bazel.

---

# 15. Bazel package boundaries should also remain semantic

Do not mechanically put a `BUILD.bazel` in every directory.

Use it where a meaningful ownership/build boundary exists.

For example:

```text
tensor_ops/
├── BUILD.bazel
├── attention/
├── normalization/
└── bindings/
```

may reasonably be one Bazel package if all three belong to one tightly coupled component.

As it grows:

```text
tensor_ops/
├── BUILD.bazel
├── attention/
│   └── BUILD.bazel
├── normalization/
│   └── BUILD.bazel
└── bindings/
    └── BUILD.bazel
```

might become more appropriate.

The rule is:

> Split Bazel packages when dependency/visibility/ownership boundaries justify it, not because files happen to have different extensions.

---

# 16. Our test convention still works naturally

Inside any semantic component:

```text
foo.h
foo.cc
foo_test.cc

foo.cuh
foo.cu
foo_test.cu

foo.py
foo_test.py
```

Rust remains idiomatic:

```rust
// foo.rs

#[cfg(test)]
mod tests {
    ...
}
```

with crate integration tests:

```text
tests/*.rs
```

So a mixed component might genuinely look like:

```text
attention/
├── attention.py
├── attention_test.py
│
├── attention.h
├── attention.cc
├── attention_test.cc
│
├── attention_kernel.cuh
├── attention_kernel.cu
├── attention_kernel_test.cu
│
└── BUILD.bazel
```

I think that's a very good layout.

The fact that three languages are present tells us:

> this concept has three implementation layers.

It does **not** mean the repository structure is wrong.

---

# 17. The build-system model becomes

```text
                         semantic tree
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
    scheduler             tensor_ops            tokenizer
        │                     │                     │
    Rust + C++          Python+C++/CUDA        Rust+Python
        │                     │                     │
        └───────────── ecosystem metadata ──────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
            Cargo                             uv
              │                               │
          Cargo.lock                        uv.lock
              │                               │
              └───────────────┬───────────────┘
                              ▼
                            Bazel
                              │
                     complete artifact DAG
```

Filesystem structure is determined by the **top half**.

Build tooling handles the **bottom half**.

---

# 18. Final repository principle

> **Organize the repository by conceptual ownership, not implementation language.**
>
> Rust, Python, C++, and CUDA sources may freely coexist within a semantic component when they jointly implement that component.
>
> Cargo workspaces and uv workspaces are projections over this semantic tree and may contain members at arbitrary nested locations.
>
> Bazel is the composition layer. It models language-specific targets and cross-language edges explicitly, without requiring language-specific top-level directory hierarchies.
>
> Cargo remains authoritative for Rust package metadata and third-party dependency resolution. uv remains authoritative for Python package metadata and third-party dependency resolution. Bazel consumes both and owns hermetic compilation, cross-language integration, testing, packaging, remote execution, and release artifacts.
>
> A directory should be split because the architecture demands another ownership/dependency boundary—not because the implementation changes language.

The shortest formulation is:

```text
Filesystem = architecture.

Cargo/uv = ecosystem projections.

Bazel = system graph.
```
