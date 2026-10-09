# 04: Shrink resources.command to the legacy reader and close the seam

**What to build:**

- `resources.command` keeps only what is needed to read and re-check legacy, command-line-only receipts.
- The boundary test catches private launch-plan imports in any formatting.
- The resource-helper allowlist and the "not public" test are deleted.
- The copied Python-worker check and GPU device list exist once.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] **The private-import scan catches parenthesised and multi-line imports.** A self-test proves it catches both forms, and the scan finds no active violations.
- [ ] **`RESOURCE_COMMAND_LEGACY_HELPERS` and the test that pins those helpers as not public are deleted.** Any helper that remains is a legacy-receipt reader, and that is documented in the module.
- [ ] **One copy of each:** the Python-worker check exists once, and so does the GPU device list.
- [ ] **No other check is weakened.** The boundary test's other patterns and exclusions are unchanged, except where they become stricter.
- [ ] The `insula` and `autonomy/ARCHITECTURE.md` docs describe the receipt-checking rule: compare plans for new receipts, use the legacy parser only for receipts with no plan record.
- [ ] **Live acceptance** is repeated on the final code with the same runs as ticket 03, and the fresh receipts verify. Record the results in Comments.
- [ ] The golden argv test is unchanged and passes, and the retained-receipt sweep matches the baseline exactly.
- [ ] **Gates pass:** CPU, parallax, and CUDA on GPU 1 when it is free. Counts recorded.
