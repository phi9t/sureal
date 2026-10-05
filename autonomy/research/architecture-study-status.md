# Architecture study execution status

Study authorized2026-10-02; [spec](../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md) and [plan](../../../docs/superpowers/plans/2026-10-02-perception-architecture-study.md). Tickets28–32 are part of existing goals.

First cohort: deepPFN,contextPFN,residualBEV plus64pointretention. All use originalGN-backbone reference recipe and fullnativeGT. Contract REDmissingmodule→GREEN passes;64pointcache independently admitted with native targets byte-identical. Serial GPU training and separateCPU loss/native scoring audits in progress. No quality/adoption result is claimed until separate11checkpoint geometry/export/native metric replay and GPU checkpoint replay complete.

Later gates: masked-baseline attribution control for contextual pooling; ragged packing and fixedheadspacing grid sweep; windowattention/computecontrol; rangefusion/localpointattention; signassignment/support investigation,fullclassTier1,fixed16,multiseed and officialsegmentheldout evidence. Written exact interfaces are required before unspecified follow-up modules. Original program goals remain open.

Execution extension: maskedPFN,windowattention/equalparameter coarseMLP and evidence-driven allpillars control are now specified and executing. Independent review found no critical model masking/attention defect; provenance/sharedweight/storage guards strengthened, corruption/overflow fixtures livepassed, strict checkpoint receipts replace historical weaker ones. Originalcontext timing is excluded; exact exclusive replay admitted. Finalresult requires all8candidate score/checkpoint/loss audits plus resource/hash reconciliation.

All8treatments trained. Completed strictcheckpoint replay for each8 and independent native scoring audits for7; allpillars finalaudit pending. ResidualCNN finalmeanAPH.907812 versusGNreference.878552; maskedpooling.886386. DeeperPFN.848343,contextPFN.857262,retain64.848249,windowattention.878419,equalparametercoarseMLP.878573,allpillars.830791. None passes signperclass≥.8; no cyclists. No adoption/closure until broader gates. Retained scientific storage liveaudited9,095,758,634bytes under15GiB; eachrun under768MiB.

Final admission: all8candidates/all88checkpoint audits complete; strictcheckpoint readmissions pass;1529artifact hashes reconciled. See [final comparison](architecture-first-cohort-results.md). Firstcohort complete; later study stages and program goals remain open.
