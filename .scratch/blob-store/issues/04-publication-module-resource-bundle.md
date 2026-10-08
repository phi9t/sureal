# 04: Publication module, starting with the resource bundle

**What to build:** A publication is described by a publication spec and published by one module that stages, archives, stores, reads back, writes one manifest blob and audits. The resource bundle that the sustained run publishes in-process is the first spec, end to end.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The publication module lives in the retention concept; its interface is publish(spec) -> receipt and audit(receipt)
- [ ] A publication spec declares payload, inventory, area, child, kind, staging style (hardlink or copy), archive or direct mode, and release flag
- [ ] A publication is chunk archives plus one manifest blob listing every chunk's `{key, sha256, bytes}` and the file inventory; blob keys follow `<area>/<child>/<run-id>/<kind>/<name>` with no UUID or digest segment
- [ ] The module computes its own disk reservation from what it stages; a repeat publication of the same run and kind with different bytes is refused
- [ ] Receipts record only the store descriptor, the pinned tool digest, a readback flag and per-blob `{key, sha256, bytes}`: no command lines, local paths or log paths
- [ ] The resource bundle is a spec (hardlink staging, no release); the sustained run publishes through the module and the checkpoint reader reads the new shape
- [ ] One audit reads the new shape and rejects a tampered key, digest, size or a missing chunk; tests drive publish and audit with an in-memory blob store
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded
