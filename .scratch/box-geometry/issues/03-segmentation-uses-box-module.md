# 03: Segmentation uses the box module

**What to build:** The NLZ overlap check and foreground support decide box membership through the geometry box module, so segmentation and detection count box points the same way. The real-NLZ validator keeps its independent homogeneous-transform copy on purpose. See `.scratch/box-geometry/spec.md`.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Parity cases for NLZ overlap and foreground support membership pass against the old copies before the switch, and stay in the suite afterwards
- [ ] NLZ overlap and foreground support call the module; their own validation messages and contracts (all sensor returns, ±1 flags, native classes) are unchanged
- [ ] The real-NLZ validator is unchanged apart from a one-line note that its copy is a deliberate independent implementation
- [ ] The NLZ overlap and foreground support tests pass unchanged
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded
