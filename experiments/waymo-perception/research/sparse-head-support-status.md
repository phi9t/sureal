# Sparse transformer local support diagnostic

[Live Insula evidence](sparse-head-support-live-verified.json) uses the exact admitted all-class observation and target payloads, pinned sparse-backbone/model sources and locked Torch runtime with no GPU device binding. It checks actual transpose-convolution kernel/stride topology and three pooling levels. Dense multiscale support expansion agrees with a separate direct coarse-cell membership computation. All original positive assignments and object indices are retained.

| Class | Positive anchors | Outside local support | Objects with no supported positive anchor |
|---|---:|---:|---:|
| Vehicle |338|30|1 /36|
| Pedestrian |30|0|0 /18|
| Sign |16|0|0 /14|
| Cyclist |6|0|0 /5|

The sparse hierarchy scatters only occupied tokens and the largest upsample support covers a4×4 head-cell tile. Of65,536 head cells,46,432 have no local occupied-token support. Normalization statistics can still couple distant cells; this report does not claim zero dependence on the scene.

**Decision: needs more evidence.** One unsupported vehicle cannot explain the entire observed vehicle APH gap. The current treatment continues to its approved sustained-overfit gate or finite update cap. Matched densification/local-position treatments require separately specified architecture and live gates; no treatment is changed during this sweep. The diagnostic is neither held-out evidence nor a causal attribution of prediction errors.

Two initial invocations failed before diagnostic admission: the NumPy-only root lacked Torch, then the Torch root required its absolute virtual-environment interpreter. Their logs remain under `insula/sparse-head-support-20261003{a,b}`. Invocationc passed. Replay the recorded bubblewrap command with retained source/input bindings and a fresh output directory; the executed diagnostic is `analysis/sparse-head-support.py`.

Successful live execution took1.689s with91,620KiB child peakRSS; no optimizer step or GPU allocation was performed.
