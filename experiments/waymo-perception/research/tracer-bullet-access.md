# Real-data tracer bullet: acquisition preflight

Date: 2026-09-29.
Status: acquisition pending; no Waymo files downloaded and no processing run.

## Requested execution order

Obtain the bounded all-modality local slice first, then investigate the full
source-to-output path against its actual schemas. Use approximately two complete
scenes, retain every available component/sensor/frame in local raw storage, and
distinguish modality acquisition coverage from interpretation coverage. Keep
the complete dataset in HDFS and defer storage/materialization policy to
`~/workspace/waystone`. No TensorFlow, including reference execution.

## Observed access evidence

- Waystone's built wrapper resolves the shared prefix to
  `hdfs://harunava/user/tiger/waystone/` in this environment.
- An environment-only authentication attempt failed because no supported token
  environment variable was set. The normal Waystone authentication path then
  successfully listed HDFS. Do not characterize HDFS access as unavailable.
- The shared prefix contained only `fineweb-edu-live-tests` at the check time.
- No Waymo-named entry was found in the shallow listing of `/user/tiger/`;
  `/user/tiger/datasets/` was empty.
- `/user/philip.yang/dataset/` contained FineWeb;
  `/user/philip.yang/datasets/` contained FineWeb, a Qwen demo, and `reged`.
- `/user/jay.yang/datasets/` and its `open-source/` child had no identified Waymo
  entry. These are bounded directory checks, not proof that the cluster has no
  Waymo data elsewhere.
- Filename discovery across the local workspace found design/planning artifacts
  but no Waymo shard or slice receipt.
- No `gcloud` executable or `~/.config/gcloud` directory was found. No
  Google/Waymo credential configuration was supplied for this task.
- An anonymous HTTP request to the official v2 bucket inventory endpoint
  returned `401`:
  `https://storage.googleapis.com/storage/v1/b/waymo_open_dataset_v_2_0_1/o?maxResults=1`.
  The [official download page](https://waymo.com/open/download/) redirected to
  Google login in the browser check. This does not determine whether the user
  already accepted terms on another machine.
- Waystone's Python environment contains PyArrow `25.0.1`; Torch, JAX,
  TensorFlow, `google-auth` and `google-cloud-storage` were absent. No packages
  were installed during this preflight.

No credential contents were printed or copied. Waystone files were read only;
its existing uncommitted changes were left intact.

## Next executable boundary

Supply an authorized existing HDFS/local source path or the path to an existing
Google credential configuration authorized for Waymo, without sending credential
contents. If terms acceptance or browser sign-in is still required, those remain
human actions. Continue with measured source inventory and Waystone-derived
storage policy before a bounded transfer.

Once access exists, inventory component coverage, select the small context
cohort, verify byte-preserving staging and source lineage, then run the offline
investigation: actual Parquet schemas and native-key uniqueness, calibration and
pose provenance, camera/image inspection, range-return statistics, labels and
available auxiliary modality inspection, deterministic manifest emission,
semantic/hash validation, immutable output promotion and a repeat-run content
comparison. Record unavailable/unsupported components and processing failures
explicitly. Do not substitute synthetic success for the requested real-data
end-to-end result.
