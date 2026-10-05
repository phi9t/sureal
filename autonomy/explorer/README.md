# Selected-scene explorer

Closeout status: the preview and joint-render workers have source-bound live
receipts. The builder, payload assembly, template and orchestration remain local
candidates pending their own source-bound generation/provenance gate; they are
listed in the comprehensive closeout inventory. Embedded sensor-image previews
remain outside Git. The command below describes the preserved local candidate,
and is not yet available in a clean mainline checkout.

Candidate refresh has no clean-mainline command yet. The admitted explorer
workers are `autonomy/explorer/camera_preview.py` and
`autonomy/explorer/joint_render.py`; retained receipts own their invocation and
source-bound artifact checks.

The explorer includes 16 selected training frames from 13 scenes, native FRONT-camera previews, eligible upright boxes in vehicle coordinates, class coverage, and positive-anchor coverage. It preserves uncovered ground truth. This is selected-frame inspection, not full-scene playback, calibrated camera/LiDAR projection, or a model-quality claim.

Camera originals were compared byte-for-byte against generation-pinned native Parquet sources by separate producer/reference executions in live CPU Insula. Thumbnails are presentation derivatives; their dimensions and format are checked. The builder verifies recorded artifact hashes before embedding previews and labels.

Historical inspection reported three payload contract tests and browser
interactions (scene selection, uncovered filter, class toggle) at 736px and
360px with zero browser exceptions. These observations do not close the pending
source-bound generator admission. Native preview/renderer receipts retain their
separate, narrower scope.
