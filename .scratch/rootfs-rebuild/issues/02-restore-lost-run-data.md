# 02: Restore lost run data from HDFS publications

**What to do:** Inventory local run data lost with `~/.cache/waystone`,
restore only absent paths that are covered by retained HDFS publications, and
record unrecoverable paths without regenerating them.

**Status:** ready-for-human

- [x] Inventory missing retained sweep, Motion foundation, lp03 cohort and
  Parallax paths.
- [x] Check whether HDFS publications cover each missing path.
- [ ] Restore every HDFS-covered path.
- [x] Leave unrecoverable paths unmodified and record the reason.
- [x] Re-run the retained sweep and Motion foundation replay command.
- [x] Re-run `//:repo_gate` before commit.

## Restore Summary

No cache target was promoted in this worker run.

Two small Motion extension source TFRecords are covered by HDFS and were
verified by temporary readback, but promotion into `~/.cache/waystone` was
blocked by the managed worker filesystem before staging beside the target:
`mkdir: cannot create directory '~/.cache/waystone/waymo-perception/motion-pilot':
Read-only file system`.

The temp-only readback verified the HDFS bytes:

| Local path | HDFS publication covers it? | HDFS key | Expected digest | Size | Result |
| --- | --- | --- | --- | --- | --- |
| `~/.cache/waystone/waymo-perception/motion-pilot/training-extension-3ac2217db574457eb1835e7647e4aed3/source.tfrecord` | Yes | `datasets/waymo-motion/v1.2.1/pilot/training/1706642338741149-9da4602bee5c46d70ddae1e60b62c0c048252c1d4322c259b88a822f92a76832.tfrecord` | `9da4602bee5c46d70ddae1e60b62c0c048252c1d4322c259b88a822f92a76832` | 5081750 | Temp readback verified; not promoted because cache write was denied |
| `~/.cache/waystone/waymo-perception/motion-pilot/validation-extension-a047963e2ccb4cc8877051b841c01f71/source.tfrecord` | Yes | `datasets/waymo-motion/v1.2.1/pilot/validation/1706641287836292-a33485f7936b39596a9948ad18d7bac17e594101a43cce88180450c79b653c6c.tfrecord` | `a33485f7936b39596a9948ad18d7bac17e594101a43cce88180450c79b653c6c` | 4810884 | Temp readback verified; not promoted because cache write was denied |

Disk floor check before the attempted restore showed 311157260288 bytes free on
`/data02`, above the 200 GB floor. No existing cache file was overwritten or
deleted.

## Retained Sweep Inventory

The default retained sweep needs the retained balanced16 case directory named
by `autonomy/research/balanced16-sustained-bs1220261009T154234Z-progress.json`.
The records are marked `released: false`, and no HDFS publication was found for
this run id. Checked HDFS namespaces included `checkpoints/`,
`runs/perception-sustained-checkpoints`, and
`runs/perception-resource-closures`; the visible checkpoint/resource closure
entries are for other run ids such as
`balanced16-sustained-admission-native20261003a` and
`balanced16-sustained-baseline-controller20261003a`.

| Local path | HDFS publication covers it? | HDFS key | Expected digest | Size | Result |
| --- | --- | --- | --- | --- | --- |
| `~/.cache/waystone/waymo-perception/insula/balanced16-sustained-baseline-bs1220261009T154234Z/` | No | none | case manifest `fd1825fb7c9e9ab8e0dbc8ce76178249b7efada6ced8bfa733b7e0478c5898d2` | not recorded | Unrecoverable from published HDFS state |
| `~/.cache/waystone/waymo-perception/scientific-processing/balanced16-sustained-baseline-bs1220261009T154234Z/update-00` | No | none | checkpoint `921a5e34971454003d7828a87d19eea6024c83e9b6a4e8e9f01493f85e586688` | not recorded | Unrecoverable; source record is unreleased |
| `~/.cache/waystone/waymo-perception/insula/balanced16-sustained-baseline-bs1220261009T154234Z/checkpoint-00-admitted.json` | No | none | `6a1850e676ead55d368d35329802efab85e96abd8c09a93aa8c3fa199f6f5826` | not recorded | Unrecoverable; source record is unreleased |
| `~/.cache/waystone/waymo-perception/insula/balanced16-sustained-baseline-bs1220261009T154234Z/resource-layer/checkpoints/checkpoint-00.json` | No | none | `48b5c579721dc8e5b5610728fc76b6207549081b6d6a3b90f47b84872bdc6d65` | not recorded | Unrecoverable; source record is unreleased |
| `~/.cache/waystone/waymo-perception/scientific-processing/balanced16-sustained-baseline-bs1220261009T154234Z/update-1000` | No | none | checkpoint `c31098e8f3eabab1e52874b03f004093c63d51eddeab3bea8896481a6446efb9` | not recorded | Unrecoverable; source record is unreleased |
| `~/.cache/waystone/waymo-perception/insula/balanced16-sustained-baseline-bs1220261009T154234Z/checkpoint-1000-admitted.json` | No | none | `4110dfad0fd536bc5a1921eb26f30a003c5ed0623ed3203b0c7c3b1e1f1b0c64` | not recorded | Unrecoverable; source record is unreleased |
| `~/.cache/waystone/waymo-perception/insula/balanced16-sustained-baseline-bs1220261009T154234Z/resource-layer/checkpoints/checkpoint-1000.json` | No | none | `5bf46f996b7c31f2dfc008c894c26ea4536fb071443481fadb97719857b7a6b7` | not recorded | Unrecoverable; source record is unreleased |

Regeneration would require re-running the retained balanced16 sustained
baseline commands represented in the progress file. I did not run training or
long jobs.

## Motion Foundation Inventory

`autonomy/motion/replay_motion_foundation.py` asserts all artifacts recorded in
the parent native-link receipts before it links the two `merged.pb` files into
the replay input directory. The source TFRecords above are HDFS-covered, but
the native-link output artifacts below are not covered by the visible HDFS
Motion publications. The checked Motion HDFS publication manifests do not name
`merged.pb`, `observations.pb`, `training.pb`, or `validation.pb`.

| Local path | HDFS publication covers it? | HDFS key | Expected digest | Size | Result |
| --- | --- | --- | --- | --- | --- |
| `~/.cache/waystone/waymo-perception/insula/motion-native-link-v5/output/merged.pb` | No | none | `36cb0f5f23eeb558ab95babe1eaf9f6475c7668970269d68faed8a6bbea8163a` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-native-link-v5/output/wrong-key.log` | No | none | `7bc07886a424784a95a7e437b50d3ff9a9f821585fbe45bd671d532eed491a7b` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-native-link-v5/output/future-rejection.log` | No | none | `818f28029a5635b86d011c58cc42a9641415e9f0e1486c1f294693b0e91c7535` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-native-link-v5/output/live.log` | No | none | `d331fd94fa4a1bf762a3c79be38c41e107429f14b9076e5d4da7b527fe60031c` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-native-link-v5/output/duplicate.log` | No | none | `911c709de89c4459ba6fd125d665f8c2725205d4ec1e4f141aebd1c5856e2e6c` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-native-link-v5/output/link` | No | none | `772bfcac457bf0c24cdd3e9a3ee8e0b7655d2e9c63a0d41d1829c1e0ee67794d` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-native-link-v5/output/observations.pb` | No | none | `0d2e7305baf337692dfaaf11d3de89ba54d285d68eb181d59a99249fe1280c62` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-native-link-v5/output/future.pb` | No | none | `168c632ba11349b9bbc14eadc8f471fdc47c4e9c9be7c5e10ba30747f4566a5d` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-validation-native-link-v1/output/merged.pb` | No | none | `7a36ac3fddf2d0b21516e9b1eb3381b288e7409543708415b625efaa7fa4dddf` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-validation-native-link-v1/output/wrong-key.log` | No | none | `ded64540256cd681d6a063ac2a14a2df31efda7139664e73f64c7bd5e48042de` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-validation-native-link-v1/output/future-rejection.log` | No | none | `818f28029a5635b86d011c58cc42a9641415e9f0e1486c1f294693b0e91c7535` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-validation-native-link-v1/output/live.log` | No | none | `79397b412e637066a99bc6367157e4103d698e868e289527a826f7d34abf4289` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-validation-native-link-v1/output/duplicate.log` | No | none | `844dd7bcefd5d9ec9679c64acac74ccc6b1f71e078ed2c9a42e3a1af5fba479c` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-validation-native-link-v1/output/link` | No | none | `772bfcac457bf0c24cdd3e9a3ee8e0b7655d2e9c63a0d41d1829c1e0ee67794d` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-validation-native-link-v1/output/observations.pb` | No | none | `85365af948859d081f8758e283fd7d1c1a8e680c0c20bafcd17ab11b1965985d` | not recorded | Unrecoverable from HDFS publication |
| `~/.cache/waystone/waymo-perception/insula/motion-validation-native-link-v1/output/future.pb` | No | none | `c603ecfc9f68452db782459e9ad3b4c69b339d29ac6795fb6422ac91dae07dea` | not recorded | Unrecoverable from HDFS publication |

Regeneration would require re-running the native-link commands recorded in
`autonomy/research/motion-training-native-link-verified.json` and
`autonomy/research/motion-validation-native-link-verified.json`; I did not run
them.

## lp03 Cohort Inventory

The live cohort driver needs source-audit JSON records under
`~/.cache/waystone/waymo-perception/scientific-source-audit`. The local
directory is absent. HDFS has the legacy raw source Parquet files at
`waymo/perception/v2.0.1/raw/<split>/<component>/<scene>.parquet` for all 51
records below, but no HDFS publication was found for the audit JSON records
themselves. The audit JSON sizes are therefore not recorded.

For every row in this table: HDFS publication covering the local audit JSON is
`No`, the HDFS key for the missing audit JSON is `none`, and the size is `not
recorded`.

| Local source-audit record | Expected digest |
| --- | --- |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-camera_box-6183008573786657189_5414_000_5434_000.json` | `1b220303337b94d1a1e223c7c9002d436e7641fc6009ffc27898674d0ddf71a0` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-camera_calibration-6183008573786657189_5414_000_5434_000.json` | `68157addb17b8b2030bbf6194735c9638614fd1cdd8b096a0df029adb691c28e` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-camera_hkp-6183008573786657189_5414_000_5434_000.json` | `b91e7439e04ec86be852252dee85bcbdf6a804943c6c285e8ac89845fdaa093e` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-camera_image-6183008573786657189_5414_000_5434_000.json` | `ab3decfa7054bae6e59b370044d70ba0abc37f30d04e1709264e1cb8dd92dea9` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-camera_segmentation-6183008573786657189_5414_000_5434_000.json` | `2a2b8a1842355160d7be4b776ed68f72c3da4cc9fe477245ebe29b972e60a791` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-camera_to_lidar_box_association-6183008573786657189_5414_000_5434_000.json` | `ee8e3df69fa60f04e70663fd5bbbff24362cf4cae13e2208c153c83484709f4e` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-lidar-6183008573786657189_5414_000_5434_000.json` | `7072539cf074d76f208621200ddcad8f7cb84c0c4f029b4e8a07664ba83fe8d3` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-lidar_box-6183008573786657189_5414_000_5434_000.json` | `6db6fc54334c421a3c256361aacfb023d75f41ceb7cbe8ba521ed679294e804e` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-lidar_calibration-6183008573786657189_5414_000_5434_000.json` | `74f9134cd1f9768bbaab5bfb07d7371061b3a9a1dce18d6306ddd226ebb95c79` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-lidar_camera_projection-6183008573786657189_5414_000_5434_000.json` | `9f0251b1f5c9d50df73d137f31740c80b70d4eed8c8cf8b60c7cd815802e8f93` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-lidar_camera_synced_box-6183008573786657189_5414_000_5434_000.json` | `6ed20b1f161169a7e6a8126fedcc7e576967a65c7494e7d844949f81b8392d32` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-lidar_hkp-6183008573786657189_5414_000_5434_000.json` | `71a8f1c1f5f694fdd5cf4f671c550c52ffabf3111b4f04c237d85fb36274b97c` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-lidar_pose-6183008573786657189_5414_000_5434_000.json` | `78222bd01e35bb526025141095a7a1bbc5ef4903dcc26ed7b776e5a967bf0a10` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-lidar_segmentation-6183008573786657189_5414_000_5434_000.json` | `f65d63a3088eac972beb6d87d9cf52710c0dfbcf9661221f73b68f9b5a4c2a88` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-projected_lidar_box-6183008573786657189_5414_000_5434_000.json` | `f7344373ec62b91caa5e271bd093b19371727614fef3d76031ea8bee9d6ed4e1` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-stats-6183008573786657189_5414_000_5434_000.json` | `3e96673faaf52497866357b332aa49459bfb1a927ca504da54d81d699b9ee6f3` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/validation-vehicle_pose-6183008573786657189_5414_000_5434_000.json` | `9a0c0a037cd335c9446140b2f04f84d7fb615730d745e5a8b6ce277ae01b3346` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_box-1357883579772440606_2365_000_2385_000.json` | `06b13948b45f31c7f688a02a9c8fa9952a3579096754991374e395aa7b557abe` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_calibration-1357883579772440606_2365_000_2385_000.json` | `2e484d52e8b92dabb681d1759dd9eb685aeafb8fe715c6b24d5148378c147456` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_hkp-1357883579772440606_2365_000_2385_000.json` | `0dc5eaa1bed048b58e0894ad8dcda350fe3c022fc30b7cbf1a028be5b1d661eb` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_image-1357883579772440606_2365_000_2385_000.json` | `3d4e27b3ad82488695843dc2222602eff83de7ee92a86c9ccb58d81dd028bcdd` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_segmentation-1357883579772440606_2365_000_2385_000.json` | `768817a0d1ea19e6b0435c821c428ef1a784459586f5c5a55794ea4ef4e23a05` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_to_lidar_box_association-1357883579772440606_2365_000_2385_000.json` | `779f5ded0835b829174eb08951ba7308b840a4c570515272a89cdc62da7635c5` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar-1357883579772440606_2365_000_2385_000.json` | `44e883cc6ef3fef43137996054dd77dee6ef33ec46914a47f305abeca63ee956` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_box-1357883579772440606_2365_000_2385_000.json` | `592a36656cd5997c46aa3a3bbdaa19042c7c86ad0de62c52b5ad75e2c99269a0` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_calibration-1357883579772440606_2365_000_2385_000.json` | `9a6a698eb1008d21edc3e81b4c0c18000e2bdbb88c295c826c4bfcee42889a06` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_camera_projection-1357883579772440606_2365_000_2385_000.json` | `2d3146d7cc2e4d7dfe18485715045e31f5161e8c385b25a98846fc7874e80d9a` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_camera_synced_box-1357883579772440606_2365_000_2385_000.json` | `455daeed6311ee42a03d80f2309123baf93feafe43f4999b9e9086d009388914` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_hkp-1357883579772440606_2365_000_2385_000.json` | `14340b59fff59ed52f178197ff4dea5d29588844d9399e3f0b604e6bbe1b4235` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_pose-1357883579772440606_2365_000_2385_000.json` | `0b13319ddad220decf5468650e862f31f8b338a2908107533cb881ec5a5c6281` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_segmentation-1357883579772440606_2365_000_2385_000.json` | `9f0d3fd892e3e47c677fadcb3d8282ce4499638504c42cce7aa87f205e6e577e` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-projected_lidar_box-1357883579772440606_2365_000_2385_000.json` | `2c79d284f63478e57a67dc864e6d03d617523aedc30309cab82be449607aa8f5` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-stats-1357883579772440606_2365_000_2385_000.json` | `307f0ed9d941b4b84ac3c67a1a7300e84e5e8aba6dd0f0934ff7ba80366e682e` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-vehicle_pose-1357883579772440606_2365_000_2385_000.json` | `1384b3fc49abb830bf3acba12873e9b072d7d722ed36c280f1d7238eafdddc43` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_box-5468483805452515080_4540_000_4560_000.json` | `03a02595f9854ab4f44d7690e5e34c44631d4e5cc45d2fc4ff7bb4fd2a47dd3a` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_calibration-5468483805452515080_4540_000_4560_000.json` | `66878fb16a1cdb875682d055d89c17ca483df992cf4415fb63a9de6808d3bd36` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_hkp-5468483805452515080_4540_000_4560_000.json` | `ac9802a698c15772364d1195f8cc1d1522429295cea06d4cd8ed25197a3d4261` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_image-5468483805452515080_4540_000_4560_000.json` | `03bf6c8a20591f460501a4f93463fd31734006095d4d055bd8ec47f05ab5b044` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_segmentation-5468483805452515080_4540_000_4560_000.json` | `31d30e01e3fbde7b9a1eaf6fb8f6ac0cba86f90782fef833170dba84005f739f` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-camera_to_lidar_box_association-5468483805452515080_4540_000_4560_000.json` | `ccafb61d1a27f518dac528224fe6d463834be8188a293915792a6f40f5676e09` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar-5468483805452515080_4540_000_4560_000.json` | `41bb69cfaea57806220e851ec62f670dd856bf3bd8cd60d99474dcec8f6fc956` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_box-5468483805452515080_4540_000_4560_000.json` | `40517cbab5a1e0536df918e1efde601a0f6fb96d32a5a73996b5730b702a022b` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_calibration-5468483805452515080_4540_000_4560_000.json` | `2a5ea5c0912f25e9beee9d92bf76bb6815ee7b6a54bdd70be2ecdd3672f8a53b` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_camera_projection-5468483805452515080_4540_000_4560_000.json` | `5886b000f410db479595f0357054702e33b4e3c435ca622ab039d3012719261d` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_camera_synced_box-5468483805452515080_4540_000_4560_000.json` | `a9c40ab6884e4a79bedf0efaf0185e8dfddf0a62c94fba162cff8dec5a5d7ca2` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_hkp-5468483805452515080_4540_000_4560_000.json` | `31d3e77baaaa8d6cc4e510f8830d5aa54b79e96e3c574690a4dc7cf6e648c8e5` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_pose-5468483805452515080_4540_000_4560_000.json` | `f0afc0ed5645235601797823dd4291ae70057adeeb1805ed3f896c44e6325914` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-lidar_segmentation-5468483805452515080_4540_000_4560_000.json` | `4ea6354d48c6ef6d11de50e8a25ad6af5c6f1c164b4c1160c9f0dcccd758fe17` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-projected_lidar_box-5468483805452515080_4540_000_4560_000.json` | `a33808cb14d407b567b5455c96580a5a1cdb9db4598201928902ad5017559ce5` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-stats-5468483805452515080_4540_000_4560_000.json` | `6ec5948d5d43aa96a2b0b890065693b57d372fb5401a58efc11d5e2b08389524` |
| `~/.cache/waystone/waymo-perception/scientific-source-audit/training-vehicle_pose-5468483805452515080_4540_000_4560_000.json` | `898ed43867a8044f9c273134a102538e4de772674ea8a7528a0c5d2db21c17b3` |

Regeneration would require rebuilding the source-audit records from the
admission path, for example:

```bash
HADOOP_CONF_DIR=/opt/tiger/yarn_deploy/hadoop/conf PYTHONPATH=autonomy \
python3 autonomy/dataset/acquire-scientific-cohort.py
```

I did not run it because it is a broad acquisition job and can perform HDFS
writes through the blob store.

Related lp03 publication outputs are present on HDFS for the two attempted
scenes, but they are not the missing local source-audit inputs:

| Scene | HDFS key | Digest | Size |
| --- | --- | --- | --- |
| `6183008573786657189_5414_000_5434_000` | `datasets/scene-records-v1/6183008573786657189_5414_000_5434_000/scientific/archive.tar` | `b0fda5dcf4f1d3f6bb29ee4792cf9bdc705171f9ed6f4d2fca7af03d71687523` | 2612971520 |
| `6183008573786657189_5414_000_5434_000` | `datasets/scene-records-v1/6183008573786657189_5414_000_5434_000/scientific/publication.json` | `3f9c0243c2a6c5696092598054639bf3126bd8de185962f79aa88ffa7064a2ee` | 8983 |
| `6183008573786657189_5414_000_5434_000` | `datasets/component-bundles-v1/6183008573786657189_5414_000_5434_000/scientific/archive.tar` | `8a942ac7ef64ba5ffb91aaaf98885132492e775ff767783273212f0e57441edb` | 7143526400 |
| `6183008573786657189_5414_000_5434_000` | `datasets/component-bundles-v1/6183008573786657189_5414_000_5434_000/scientific/publication.json` | `0f6be61068e42e991d3977a30222c7166178e97d74fb4a14781f0919cfc4bc67` | 3645 |
| `1357883579772440606_2365_000_2385_000` | `datasets/scene-records-v1/1357883579772440606_2365_000_2385_000/scientific/archive.tar` | `b3bad587624bdd8a188901f61c04636742af4b4421076dfee860f6653de50b8c` | 3057008640 |
| `1357883579772440606_2365_000_2385_000` | `datasets/scene-records-v1/1357883579772440606_2365_000_2385_000/scientific/publication.json` | `2d0b4c8849f2a0635c4a7f2e4d4107e3ca458b00afca975a4a71e5bcacaadd4e` | 8908 |
| `1357883579772440606_2365_000_2385_000` | `datasets/component-bundles-v1/1357883579772440606_2365_000_2385_000/scientific/archive.tar` | `b9274d2a9c324000455660e95ec7a013141a8fcf013135470bc00b545f801945` | 7074037760 |
| `1357883579772440606_2365_000_2385_000` | `datasets/component-bundles-v1/1357883579772440606_2365_000_2385_000/scientific/publication.json` | `27310b47de896d6397866bd604812e7a43087e08674a5bd57deac942987cb3a4` | 3630 |
| `5468483805452515080_4540_000_4560_000` | none | none | not recorded |

## Parallax Inventory

The Parallax reusable cache defaults to `~/.cache/surflo/3d-pathway`, which is
outside this worker's allowed outside-repository write roots. These assets are
locked by `parallax/assets.lock.json`; they are not Sureal HDFS publications.

| Local path | HDFS publication covers it? | HDFS key | Expected digest | Size | Result |
| --- | --- | --- | --- | --- | --- |
| `~/.cache/surflo/3d-pathway/assets/controlled-suite` | No | none | `9b73b5c0b1b498879209530512c93756de6f0c1130a63d81959965cf6993cd32` | 444 artifacts | Unrecoverable by this HDFS restore |
| `~/.cache/surflo/3d-pathway/assets/middlebury-mvs.archive` | No | none | `b4684adcfda53b47b0964355b4142c53cb28940bbb448e0e974f92748e428de9` | 4004383 | Unrecoverable by this HDFS restore |
| `~/.cache/surflo/3d-pathway/assets/tum-rgbd.archive` | No | none | `a0236d97b8c30cd93b653656d2b6c293ff7c982a4130ef2a1a8beecdb124ef98` | not recorded | Unrecoverable by this HDFS restore |
| `~/.cache/surflo/3d-pathway/assets/depth-anything-v2-metric-hypersim-small.archive` | No | none | `b782898d8a3e8be1f639de33837ed85e9b4b73e40f8f5e5cd99067588d722545` | 99222290 | Unrecoverable by this HDFS restore |
| `~/.cache/surflo/3d-pathway/assets/nerfstudio-lpips-alexnet.archive` | No | none | `7be5be791159472b1fbf3c69796f7cb30dca7ad8466c2df70058c37116cdee02` | 244408911 | Unrecoverable by this HDFS restore |
| `~/.cache/surflo/3d-pathway/assets/foundation-geometry-models` | No | none | `fb7bf9bfcfb7ff5136297dd9183355ec9c7b7461d9c4ecbafb77e2d6bd2a3cf1` | not recorded | Unrecoverable by this HDFS restore |
| `~/.cache/surflo/3d-pathway/assets/nerf-synthetic.archive` | No | none | `ce4e94e031c099a19ef04cfb6c71f1e47225d97d365be610b476e379a386c25f` | 370385516 | Unrecoverable by this HDFS restore |
| `~/.cache/surflo/3d-pathway/assets/surflo-paired-scenes` | No | none | `1d4b82e749781aceaab51e0c127aac2363d6931c738be459b68529de546f818c` | not recorded | Unrecoverable by this HDFS restore |
| `~/.cache/surflo/3d-pathway/assets/surflo-visible-scout` | No | none | `48be64c4d647e5d48545068fe9fb19e06ea73b034bea5382697c0aac228d1ac1` | not recorded | Unrecoverable by this HDFS restore |

Regeneration/refetch would use the Parallax fetch path, for example
`parallax/run.sh fetch --asset <asset>`, but I did not run it because the
target cache root is outside this worker's permitted write roots and the assets
are not Sureal HDFS publications.

## Reruns

Retained sweep command:

```bash
TMPDIR=~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/cache-restore-20261010T173423Z/tmp/retained-sweep-final.FOxvlg \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy \
python3 autonomy/retained_receipt_sweep.py --require-host-data
```

Result, compared with the baseline `2279/14/14/2/9`, all 0 failures and 0
skips:

| Verifier | Baseline passed | Rerun passed | Rerun failed | Rerun skipped |
| --- | ---: | ---: | ---: | ---: |
| `launch_plan_receipt_readers` | 2279 | 2101 | 0 | 0 |
| `balanced16_stage_check` | 14 | 0 | 0 | 1 |
| `resource_stage_proof_validation` | 14 | 0 | 0 | 1 |
| `resource_checkpoint_validation` | 2 | 0 | 0 | 1 |
| `legacy_resource_publication_validation` | 9 | 0 | 0 | 1 |

Skip reasons:

- `~/.cache/waystone/waymo-perception/insula/balanced16-sustained-baseline-bs1220261009T154234Z`:
  retained case directory not present.
- Same case directory: no retained resource proofs found.
- No retained legacy resource publication receipts found.

Required Motion foundation replay command:

```bash
TMPDIR=~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/cache-restore-20261010T173423Z/tmp/foundation-replay-final.LHAcvj \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy \
python3 autonomy/motion/replay_motion_foundation.py \
  --run-id foundation-restore2 \
  --output-root ~/devx/tmp/sureal-refactor-20261007/pa-live/restore-20261010T173249Z
```

Result: failed before staging inputs because the managed filesystem made the
requested `pa-live` output root read-only:

```text
OSError: [Errno 30] Read-only file system:
'~/devx/tmp/sureal-refactor-20261007/pa-live/restore-20261010T173249Z/foundation-restore2'
```

Control replay under the declared worker temp root, with the output parent
created first, reproduced the cache-loss blocker:

```text
ValueError: regular non-symlinked file required:
~/.cache/waystone/waymo-perception/insula/motion-native-link-v5/output/merged.pb
```

## Notes

- HDFS reads used `HADOOP_CONF_DIR=/opt/tiger/yarn_deploy/hadoop/conf` and
  `CPP_HDFS_LOG_DIR` under this worker's declared temp directory.
- No HDFS write command was run.
- `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //:repo_gate` passed with 17 of
  17 tests passing.
- No repository tooling was added.
- No existing cache file, retained receipt, source snapshot, rootfs or lock was
  modified or deleted.
