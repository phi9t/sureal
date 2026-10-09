# 03: Machine-identifier boundary test

**What to build:** A boundary test, ported from milano's `scripts/check_identifiers.py`, that fails when an active tracked file contains any of:
- a host name;
- a `/dataNN/` path;
- a `/home/<user>/` path;
- an e-mail address outside the allowed attribution.

Retained records are exempt under ADR 0001, through the same exemption style as `storage_boundary_test`. Existing hits go into an explicit baseline allowlist that may only shrink.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] **Live first.** The scan runs over the real tree. The hit counts by kind and by directory are recorded, and each class of hit is triaged as: fix now, retained or exempt, or baselined.
- [ ] **The test** uses milano's pattern-splitting trick so that it doesn't match itself, and it is part of the repo gate.
- [ ] **Baseline:** an allowlist file with a reason for each entry. A test fails if a baselined entry no longer exists, which keeps the baseline shrinking.
- [ ] **Self-tests:** positive, negative, and the real repo scanning clean against the baseline.
- [ ] **Gates pass**, with counts recorded.
