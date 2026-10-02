# Balanced16 fitting comparison

Both candidates completed 2,000 updates on the same 16 native training frames from 13 scenes. Exact16-frame initial/final inference and Adam-state replay,48 independent frame/checkpoint losses, native proposal/export checks, and all three official metric reruns passed for each candidate. The stronger fixture link passed separately in live CPU Insula.

**Decision: neither candidate passes the first-tier all-class fitting gate. Do not advance to larger training on this evidence.**

| Class | Baseline final APH | Residual BEV final APH | Required |
|---|---:|---:|---:|
| Vehicle | 0.306981 | 0.266018 | 0.8 |
| Pedestrian | 0.237434 | 0.154996 | 0.8 |
| Sign | 0.022506 | 0.002694 | 0.8 |
| Cyclist | 0.002078 | 0.004545 | 0.8 |

The criterion requires every class to reach0.8 at both1000 and2000 updates; neither checkpoint qualifies. All30 uncovered GT observations remain evaluation targets.

| Candidate | Final mean loss | Synchronized optimization seconds | Parameters |
|---|---:|---:|---:|
| baseline | 1.073230 | 138.047 | 4,847,144 |
| residual_bev | 1.266910 | 130.448 | 4,847,144 |

Time-to-fit was not reached within2,000 updates; optimization time is not total verification overhead. Both candidates ran on NVIDIA B200. Peak GPU allocation was about1.73GB/1.82GB and process RSS about3.14millionKiB. Scientific retention remained14.863838GiB under the15GiB cap. The first residual attempt stopped at reservation; retry used measured1400MiB reservation with the same recipe and inputs.

The loss reduction primarily suppresses background. For baseline, mean negative focal loss fell1558.205→0.0718, versus positive0.7084→0.2417. Final positive-anchor class scores were particularly weak for cyclists. This is diagnostic, not proof of a causal mechanism. A low foreground-prior bias, class-gradient accounting, retained support and proposal ranking are separate controlled hypotheses.

Task33 closes with a negative experimental result. Task34 remains specified, not trained. Detection, segmentation, scene understanding and heldout research goals remain open.

Evidence: [strict comparison receipt](balanced-study-recovery-20261002.json), [strict fixture admission](balanced16-fixture-link-verified.json), and candidate quality-parallel-v3 receipts. Partial superseded serial scoring artifacts are retained and are not acceptance evidence.

## Decoder-version qualification (2026-10-02)

The historical cohort scorer imports `gpu.scored_proposals_v2`; its worker namespace `scoring-parallel-v3` denotes orchestration, not decoderV3. The APH values above remain historicalV2 measurements. Corrected periodic-heading APH has not been rerun for these16-frame heads.

The negative promotion decision is supported independently by historical detection AP: terminal vehicle/pedestrian/sign/cyclist AP is[.411214,.289355,.0316432,.00210084] for baseline and[.319798,.185227,.0120622,.0132919] for residualBEV. All are below.8, and APH cannot exceed AP. A heading-only pi-branch correction does not establish improved detection ranking/localization; corrected APH and any training change still require their own live receipts. Keep these values separate from the fully corrected all-class single-batch suite.
