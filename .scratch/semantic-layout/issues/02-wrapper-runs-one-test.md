# 02: One wrapper command runs Bazel inside Insula

**What to build:** A contributor types one repository-level wrapper command and a Bazel test of one existing perception unit test runs inside the new CPU rootfs and passes. The wrapper is the only entry point: it verifies the rootfs, enters the sandbox, and runs Bazel with persistent caches. This ticket also settles which Bazel spawn strategy and server mode work when nested inside the Insula sandbox.

**Blocked by:** 01 (A new version of the CPU rootfs carries Bazel 9.2)

**Status:** ready-for-agent

- [ ] The repository root has the Bazel module file, its committed lock file, the Bazel version file and the Bazel configuration; packages are declared only for the two research programs
- [ ] The Python toolchain is the rootfs interpreter with its installed packages; Bazel fetches no third-party Python package
- [ ] The wrapper clears the environment, sets a fixed home, mounts the rootfs read-only, and mounts the repository and one git-ignored cache directory that is also listed in the Bazel ignore file
- [ ] A second run of the same test is served from the persistent cache
- [ ] The wrapper has a mode that prints the sandbox command as data without running it, covered by a unit test
- [ ] The wrapper refuses to run, with a clear message, when the rootfs does not match its lock; covered by a unit test
- [ ] The working spawn strategy and server mode are recorded in the Bazel configuration with a one-line reason each
- [ ] Network is available inside the sandbox during the build
