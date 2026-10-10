# C++ Style

Sureal's C++ is small and mostly serves native fixtures, live-gate tools and
reference integrations. Keep it boring, readable and close to the scientific
boundary it supports.

## Files

- Implementation files use `.cc`.
- Headers use `.hh`; do not add new `.h`, `.hpp`, `.hxx` or `.cpp` files.
- Native tests use `*_test.cc` and sit beside the source they exercise.
- CUDA files, when needed, use `.cu` and `.cuh`.
- Do not reformat or otherwise edit retained evidence, source snapshots,
  `autonomy/research/**`, `parallax/research/**`, or files protected by source
  pins.

## Formatting

Run the Bazel-pinned clang-format checker through `//:repo_gate`. The
repository `.clang-format` is adapted from Milano's whitespace-only
configuration: it keeps include order, string literals, comments and macro
bodies under author control while enforcing indentation and wrapping.

- The column limit is 120.
- Use one statement per line.
- Do not add minified one-line programs or dense compound statements.
- Let clang-format decide indentation, continuation alignment and brace
  placement.

## Includes

Group includes in this order, with a blank line between groups:

1. The file's own header.
2. Project headers.
3. Third-party headers.
4. C and C++ standard library headers.

Keep include ordering meaningful inside each group. The formatter deliberately
does not sort includes, so authors remain responsible for grouping.

## Names

- Namespaces, functions, local variables and non-constant data members use
  `lower_snake_case`.
- Types use `PascalCase`.
- Constants with static storage duration use `kPascalCase`.
- Private data members end in `_`.
- Macros are rare; when needed, use `UPPER_SNAKE_CASE` with a project or
  package prefix.
- Keep upstream API spellings when overriding or implementing an external
  interface.

## Ownership

Use RAII for owned resources. Prefer values, `std::unique_ptr`, containers and
scope-bound handles over manual lifetime management.

Raw `new` and `delete` are allowed only at a boundary where an external API
takes or returns ownership. Add a nearby comment that names the ownership
contract in that case.

## Casts And Modern C++

- Use C++ casts: `static_cast`, `const_cast`, `reinterpret_cast` or
  `dynamic_cast`.
- Do not use C-style casts.
- Use `nullptr`, `override`, `explicit` constructors and `enum class`.
- Keep functions small enough that validation, parsing and output logic stay
  easy to audit.

## Namespaces

Do not write `using namespace` in headers or at file scope. Prefer qualified
names. Narrow aliases are acceptable inside functions or an anonymous namespace
when they make a local block clearer.

Close named namespaces with a comment:

```cc
}  // namespace autonomy
```

## Errors

Match the current native-tool error model. Short command-line tools validate
with a small `require` helper that throws `std::runtime_error`; `main` catches
`std::exception`, writes the message to stderr and returns non-zero.

Do not introduce a status framework only for style consistency. Use exceptions
for today's native tools unless a module has a stronger local contract.
