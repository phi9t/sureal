# 06: Incremental SfM with bundle adjustment; module 05 goes real

**What to build:** All orbit views are registered by our incremental SfM and refined by our Levenberg–Marquardt bundle adjustment. Curriculum module 05 reports measured results, compared with the COLMAP SfM baseline on the same images.

**Blocked by:** 05, 11

**Status:** done

- [x] **Code.**
  - `sfm/tracks.py`: the track graph.
  - `sfm/initialize.py`: picks the best pair.
  - `sfm/incremental.py`: PnP registration, triangulation and periodic bundle adjustment.
  - `sfm/bundle_adjust.py`: LM with a Schur complement on scipy sparse matrices.
  - `sfm/reconstruction.py`: the data model.
- [x] **Tests.**
  - Bundle adjustment reduces reprojection RMSE from a perturbed start, and recovers poses within tolerance on noise-free data.
  - Incremental SfM registers every view of the smoke orbit scene.
- [x] **Module 05 goes real.** The module routes to `sfm/`, its metrics come from `evaluation/`, and its status is `real+baseline`. The report includes the `baselines/colmap_sfm` result on the same images when the container gate is available.
- [x] **No ground-truth priors in estimation.** Matching, registration and bundle adjustment read no pose or azimuth metadata. Ground truth is used only for scoring. A test hides ground-truth fields and checks the estimate is unchanged, as in ticket 11. Use symmetric or coarse-to-fine match bounds, or matching guided by the current pose estimate, not the orbit-tuned `-4..+9` px window.
- [x] **General rotation.** Add elevation variation, or a second orbit ring, to the scene (see the ticket 04 review), so that SfM is not tested on single-axis rotation only.
- [ ] **Live check.** `run.sh run --module 05 --profile smoke` and `--profile full` run inside the Insula. Record:
  - ATE;
  - rotation error;
  - initial and final reprojection RMSE;
  - the number of registered views;
  - runtime;
  - the COLMAP comparison, if it can run.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...`.

## Comments

### 2026-10-10

- Implemented the repo-owned incremental SfM path under `parallax/sfm/`: feature tracks, initial-pair selection, PnP registration, triangulation, sparse Schur-complement LM bundle adjustment and the shared reconstruction model. Module 05 now routes through `sfm.incremental.run_orbit_sfm_profile`, reports measured geometry metrics as `computed_real`, and is marked `real+baseline`.
- Added tests for bundle adjustment recovery, smoke-scene incremental registration, no-ground-truth estimation, elevated orbit camera motion, and the symmetric local matching assumptions used by the two-view bootstrap.
- Live smoke command:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/live-smoke-final.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //parallax:run -- run --module 05 --profile smoke --run-id ticket06-sfm-smoke-final`
  Result: passed, wrote `.bazel-cache/home/.cache/surflo/3d-pathway/runs/ticket06-sfm-smoke-final/05`.
- Live smoke validation command:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/live-validate-final.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //parallax:run -- validate --module 05 --run-id ticket06-sfm-smoke-final`
  Result: passed with `valid: ticket06-sfm-smoke-final/05`.
- Live smoke metrics/counts: `ate_m=0.4187896664686187`, `mean_rotation_error_deg=11.867497954671503`, `max_rotation_error_deg=14.890331919891127`, `ba_initial_reprojection_rmse_px=0.604316778038311`, `ba_final_reprojection_rmse_px=0.16768051131139247`, `registered_view_count=3`, `sparse_point_count=256`, `track_observation_count=564`, `runtime_seconds=37.25716975796968`, module artifact count `22`, nested SfM artifact count `20`.
- Live smoke digests: `result.json=60633d882a949b898b9bec1ffedf61b2302f6eee7102731a65b8f6c74025091f`, `report.md=f6dfb09447f32771de32e93d21c25fb7a983fbce0f60c351de2b392682a711c1`, `artifacts/incremental-sfm/reconstruction.json=c26a27742510aa4603180190b7ae5396a621bed490de196a85179aabcb4e5a4a`, `artifacts/failure_sweep.csv=343f90501b58e96f22b56004322720b7561f2a5c94c6add6e388e6c8b1fed35b`, nested SfM artifact tree `c9789271a39ffc7f714d5456f5dd878cf29138d5e51d973175fa8f76eaa513fe`.
- Live full command:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/live-full-final.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //parallax:run -- run --module 05 --profile full --run-id ticket06-sfm-full-final`
  Result: failed before module-05 metrics because the validated Blender controlled suite is unavailable in this sandbox: `error: bwrap is required on the host`; `error: validated Blender controlled suite is unavailable; run \`run.sh build\`, \`run.sh fetch --asset controlled-suite\`, then retry the full profile: offline Blender render failed with exit code 1`.
- COLMAP comparison: not run here because the full/container-backed gate is unavailable under the same `bwrap` blocker.
- Gates:
  - `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/final-repo.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test //:repo_gate` passed, 23/23 tests.
  - `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/autonomy-final.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 191/191 tests.
  - `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/parallax-final.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 29/29 tests.
  - CUDA gate intentionally skipped because this sandbox has no GPU devices and the coordinator owns CUDA.
- Remaining human/environment item: rerun module 05 `--profile full` and the COLMAP same-image comparison where the host has `bwrap` and the validated controlled-suite/container gate available.

### 2026-10-10 rework

- Safety checkpoint: committed the pre-existing WIP as `429892b`, then committed the current rework state as `607bac1`.
- Diagnosis from the focused full-profile accuracy target: the original about-8 degree rotation error was introduced in the initial pair. Adding subpixel refinement to the incremental initializer reduced the seed pair from about `8.25 deg` to `0.5459647909595645 deg`, matching the ticket 11 two-view behavior much more closely. The next error source is registration growth: image-order neighbor registration avoids the previous far-reference jump, and keeping epipolar inliers for track growth avoids starving the final neighbor registration, but `frame-005 -> frame-006` still enters with `7.712664175882735 deg` before final BA and remains `4.050577235469223 deg` after final BA.
- The neighbor-only registration rule uses capture sequence order only. It does not read pose, azimuth, elevation, depth or surface ground-truth fields; the hidden-ground-truth test strips `elevation_degrees` as well as the other score-only fields.
- Focused full-profile accuracy command:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/full-accuracy-once.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_incremental_sfm --test_filter=IncrementalSfmTest.test_full_orbit_profile_meets_accuracy_targets`
  Result: failed after `459.795s` test runtime. The Python unittest target still ran the smoke and hidden-ground-truth cases (`.F.`), and those passed; the full accuracy case failed without loosening thresholds.
- Full-profile stage trace from that run:
  - `initial_pair frame-001 -> frame-002`: mean/max relative rotation error `0.5459647909595645 deg`.
  - `pnp_registration frame-003 from frame-002`: mean `0.5852231803753638 deg`, max `0.624481569791163 deg`.
  - `pnp_registration frame-004 from frame-003`: mean `0.7673620126489912 deg`, max `1.131639677196246 deg`.
  - `periodic_bundle_adjustment` after frames 1-4: mean `0.73173676060566 deg`, max `0.8391613428501825 deg`.
  - `pnp_registration frame-005 from frame-004`: mean `0.7557409395033994 deg`, max `0.8391613428501825 deg`.
  - `pnp_registration frame-000 from frame-001`: `frame-000 -> frame-001` jumps to `3.821877469170118 deg`; mean `1.3689682454367431 deg`.
  - `periodic_bundle_adjustment` after frames 0-5: mean `0.6420721949663644 deg`, max `0.8581015032998348 deg`.
  - `pnp_registration frame-006 from frame-005`: `frame-005 -> frame-006` jumps to `7.712664175882735 deg`; mean `1.8205041917857594 deg`.
  - `before_final_bundle_adjustment`: mean `1.8205041917857594 deg`, max `7.712664175882735 deg`.
  - `after_final_bundle_adjustment`: mean `1.5778872955298324 deg`, max `4.050577235469223 deg`.
- Current full-profile status: all 7 views register, but the required accuracy targets are not met. Observed final rotation metrics are `mean_rotation_error_deg=1.5778872955298324` and `max_rotation_error_deg=4.050577235469223`; the required targets remain `mean < 1.0 deg`, `max < 2.0 deg`, `Sim3 ATE < 0.05 m`. ATE was not printed by the failed assertion output, so it is not claimed here.
- What changed in the rework before stopping: removed the hard-coded `[3, 0]` coarse-center diagnostic, added subpixel right-point refinement to `sfm/initialize.py`, limited incremental registration to already-registered image-sequence neighbors, preserved full epipolar inlier sets for track growth instead of replacing them with PnP-known inliers, and anchored each BA call to the first currently registered camera. These are committed, but the full-profile accuracy acceptance remains incomplete.
- Not rerun after the target miss, per stop instruction: smoke live metrics, ticket 11 two-view accuracy, `//:repo_gate`, `//parallax/...`, `//autonomy/...`, and `//:pinned_sources_test`. The live full profile and COLMAP comparison remain blocked on the same sandbox asset/`bwrap` environment noted above.

### 2026-10-10 rework follow-up

- Commit `647b8f3` added the requested PnP refinement and refined-pose inlier reselection. The PnP observations use the subpixel-refined `PairMatch.right_points` from `sfm.initialize`, not integer patch centers.
- Focused full-profile command for the PnP step:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/full-pnp-reselect.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_incremental_sfm --test_filter=IncrementalSfmTest.test_full_orbit_profile_meets_accuracy_targets`
  Result: failed after `463.260s` test runtime. It improved `frame-000 -> frame-001` to `0.9268551173999094 deg` after final BA, but `frame-005 -> frame-006` remained `2.9569215771420287 deg`; final mean rotation was `1.1540254700700243 deg`, above the `1.0 deg` target.
- Commit `c67785d` added Huber-weighted bundle adjustment, post-BA pruning for observations above `2 px`, track pruning for fewer than two observations or triangulation angle below about `1 deg`, retriangulation after track growth, and per-registration support diagnostics.
- Focused full-profile command for robust BA/pruning:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/full-robust-prune.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_incremental_sfm --test_filter=IncrementalSfmTest.test_full_orbit_profile_meets_accuracy_targets`
  Result: failed after `543.754s` test runtime. It kept interior views below about `0.84 deg`, but `frame-005 -> frame-006` still entered at `13.39497437941721 deg` on PnP and ended at `4.632667956791188 deg` after final BA; final mean rotation was `1.447073817743241 deg`.
- Commit `521df58` added a guided PnP candidate seeded from the adjacent two-view relative pose and copied PnP correspondence counts, inlier counts and median triangulation angle into the stage trace.
- Focused full-profile command for guided PnP diagnostics:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/full-guided-pnp.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_incremental_sfm --test_filter=IncrementalSfmTest.test_full_orbit_profile_meets_accuracy_targets`
  Result: failed after `539.041s` test runtime. All 7 views registered, but final rotation metrics were still `mean_rotation_error_deg=1.447073817743241`, `max_rotation_error_deg=4.632667956791188`; ATE was not printed by the failed assertion output, so it is not claimed.
- Endpoint diagnostics from the guided PnP run:
  - `frame-000` registered from `frame-001` with `pnp_correspondence_count=200`, `pnp_inlier_count=199`, `pnp_rmse_px=0.20275396641423185`, `median_triangulation_angle_deg=15.140982616142935`. Its relative rotation was `0.8138306811520646 deg` on registration and `0.6881174485724296 deg` after final BA.
  - `frame-006` registered from `frame-005` with `pnp_correspondence_count=73`, `pnp_inlier_count=54`, `pnp_rmse_px=0.5587069945264591`, `median_triangulation_angle_deg=8.137543452049346`. Its relative rotation was `13.39497437941721 deg` on registration and `4.632667956791188 deg` after final BA.
- Current diagnosis: the seed pair and interior sequence are now sub-degree after subpixel matching, PnP refinement, sequence-neighbor registration and anchored BA. The remaining failure is localized to sparse/contaminated 2D-3D support when closing the high end of the 7-view full profile: `frame-006` has far fewer 2D-3D correspondences and inliers than the interior registrations, despite a usable median triangulation angle. The full-profile accuracy test remains intentionally red; thresholds were not loosened.
- Not run after the remaining miss, per instruction to stop after the third full-profile attempt: smoke live metrics, ticket 11 two-view accuracy, `//:repo_gate`, `//parallax/...`, `//autonomy/...`, and `//:pinned_sources_test`. The live full profile and COLMAP comparison remain blocked on the sandbox asset/`bwrap` environment noted above.

### 2026-10-10 rework endpoint diagnostics

- Commit `3fe20ce` added same-view conflict rejection in `sfm.tracks.TrackGraph` plus `//parallax:test_sfm_tracks`. The regression builds a match graph that would merge two keypoints from the same view into one track; `add_match` now rejects that edge and increments `conflict_count` instead of conflating the observations.
- Track-conflict test command:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/tracks-conflict.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_sfm_tracks`
  Result: passed. This was run after a red check where the conflict was incorrectly accepted.
- Commit `59f1a39` added a focused two-view endpoint diagnostic for the full orbit profile. With the then-current default two-view bounds, `frame-005 -> frame-006` measured `rotation_error_deg=9.191159696781003`; with the historical `9f11aaa` defaults it improved to `2.3328122401031637` but regressed the smoke ground-truth fundamental-matrix inlier ratio to `0.8845470692717584` against the existing `0.95` test target. The branch therefore restored the current symmetric defaults (`min_delta_x_px=-5.0`, `max_delta_x_px=5.0`, `max_abs_delta_y_px=6.0`, `match_ratio=0.8`) and keeps the endpoint diagnostic on explicit focused bounds.
- Endpoint pair sanity command:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/twoview-56-subdegree.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=all //parallax:test_two_view_orbit --test_filter=TwoViewOrbitTest.test_full_profile_endpoint_pair_recovers_subdegree_rotation`
  Result: passed. The unittest filter still executed the 4 tests in that target; the focused diagnostic printed `full_endpoint_5_6_rotation_error_deg=0.1745023865063678`. This shows the endpoint pair is not inherently hard when the matching window captures the correct displacement.
- Commit `7ccb16a` drops candidate 2D-3D support before PnP when any already-registered observation of the candidate point reprojection exceeds `2 px`; commit `8ccdfab` forwards the support-source diagnostics into the stage trace.
- Full-profile diagnostic command, first allowed run this session:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/full-track-filter.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_incremental_sfm --test_filter=IncrementalSfmTest.test_full_orbit_profile_meets_accuracy_targets`
  Result: failed after `549.504s`. All 7 views registered, but final metrics remained `mean_rotation_error_deg=1.447073817743241`, `max_rotation_error_deg=4.632667956791188`, above the unchanged targets `mean < 1.0 deg`, `max < 2.0 deg`. The run reported `track_conflict_count=0`, so union-find same-view conflation was not the current endpoint failure.
- Full-profile diagnostic command, second allowed run this session:
  `TMPDIR=$(mktemp -d ~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/para06-incremental-sfm-20261011T031930Z/tmp/full-support-diag.XXXXXX) SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_incremental_sfm --test_filter=IncrementalSfmTest.test_full_orbit_profile_meets_accuracy_targets`
  Result: failed after `551.455s`. All 7 views registered, but final metrics again remained `mean_rotation_error_deg=1.447073817743241`, `max_rotation_error_deg=4.632667956791188`; no full-profile artifact digests were produced by this filtered failing test.
- `frame-006` PnP support in the second run: `pnp_correspondence_count=73`, `pnp_inlier_count=54`, `pnp_rmse_px=0.5587069945264591`, `median_triangulation_angle_deg=8.137543452049346`. Track source pairs were `frame-000->frame-005: 6`, `frame-002->frame-005: 5`, `frame-003->frame-005: 5`, `frame-004->frame-005: 57`.
- `frame-006` pre-PnP stale-support filtering rejected `0` candidate points. Existing registered-view reprojection errors for the same 73 support points were low: overall max `0.30805297856316105 px`, median `0.05108551244166803 px`, p95 `0.24346736838054245 px`; for `frame-004`, count `73`, max `0.30805297856316105 px`, median `0.050830466030918946 px`, p95 `0.20202912236871554 px`; for `frame-005`, count `73`, max `0.2543217369015762 px`, median `0.04815601563342589 px`, p95 `0.16557387297728549 px`.
- Current diagnosis after the two allowed full-profile runs: the remaining endpoint miss is not explained by same-view track conflation, stale high-error prior-view support, or an inherently hard `frame-005 -> frame-006` two-view geometry. The bad `frame-006` pose is low-RMSE against an internally consistent support set, so the remaining defect is still in endpoint correspondence/support selection, most likely the incremental `frame-005 -> frame-006` match window or track-growth path that selects wrong but self-consistent 2D-3D points.
- Current status remains `ready-for-human`. The full-profile accuracy acceptance is still incomplete, the live full profile and COLMAP comparison remain blocked on the sandbox `bwrap`/controlled-suite environment, and the final `//:repo_gate` plus `//parallax/...` closeout gates were not rerun after this miss per the instruction to stop instead of spending a third full-profile attempt.

### 2026-10-11 coordinator review and landing

- Landed as 2f5fde1 (squash of the worker branch) plus 66d4c67 (numeric tolerance on the new exact full-orbit two-view test: 1.7e-6 deg on the landing host vs a 1e-6 bound, now 1e-4).
- Root causes found across the reworks: integer-pixel seed correspondences (fixed by subpixel refinement); far-reference registration; PnP inliers replacing epipolar inliers in track growth; no BA gauge anchor; and a fixed +-5 px match window that aliases on the repeated-texture orbit scene at frame-005 -> frame-006. Registration growth now uses constant-velocity pose prediction from estimated poses and capture order, with 2D-3D matching around projected tracks; no ground-truth field is read outside scoring.
- `//parallax:test_incremental_sfm` (6 tests) passes, including the full 7-view orbit targets: mean relative rotation error < 1 deg, max < 2 deg, Sim3 ATE < 0.05 m. The smoke profile is a registration and plumbing test only.
- Gates on the landing tree: `//:repo_gate` 23/23, `//autonomy/...` 191/191, CUDA 31/31 on GPU 1, `//parallax/...` 30/30.
- Deferred with the Parallax asset refetch: the Blender `--profile full` live check and the COLMAP same-image comparison. The unadopted two-pass guided matcher experiment is kept on the worker repo branch `wip/para06-guided-matcher-experiment`.
- Follow-up: `sfm/incremental.py` is about 2,100 lines and should be split (prediction, registration, growth, scoring) when ticket 09 touches it.
