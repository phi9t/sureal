# Waymo Perception viewer

A web-based 3D viewer for Waymo Open Dataset Perception v2.0.1 scenes: fused
multi-LiDAR point clouds, 3D and 2D labels, calibrated camera frusta with the
real images, panoptic and LiDAR segmentation, human keypoints, the ego
trajectory, and temporal accumulation, rendered with Three.js from bundles
exported by a small PyArrow/NumPy pipeline. No TensorFlow and no Waymo SDK.

Radar is not part of the Perception release, so the viewer has no radar layer.

A hosted copy of the viewer and a landing page live at
<https://phi9t.github.io/sureal/> (branch `gh-pages`, assembled with
`run.sh pages`). It carries no data: run `run.sh serve` locally and paste the
bundle URL it prints into the hosted splash.

## License note

Waymo Open Dataset data is licensed for non-commercial use and may not be
redistributed. Bundles are derived data under the same terms: they are written
outside git under `$WAYMO_VIEWER_CACHE`, are never committed, and should only
be served on localhost or a trusted network. `tests/test_repo_hygiene.py`
fails if any image, point file or Parquet payload becomes tracked here.

## Quick start

```bash
V=autonomy/viewer/run.sh
S=~/.cache/waystone/waymo-perception/slices/validation-two-scenes-20260929
$V setup                                                # uv venv + npm ci
$V test                                                 # exporter unit tests
$V export "$S" 5847910688643719375_180_000_200_000      # ~40 s, ~955 MB
$V verify "$S" 5847910688643719375_180_000_200_000      # independent checks
$V dev                                                  # http://127.0.0.1:5173/
```

`run.sh build` then `run.sh serve [PORT]` serves the production build plus the
bundle cache with the standard-library server in `export/serve.py`.
Environment: `WAYMO_VIEWER_CACHE` (default
`~/.cache/waystone/waymo-perception/viewer`), `WAYMO_VIEWER_VENV` (default
`./.venv`). Requirements: `uv`, Python 3.12 (downloaded by `uv` if absent),
Node 20+, a WebGL2 browser.

## Layout

```
run.sh            setup | test | export | verify | dev | build | serve
export/           exporter package (numpy, pyarrow, pillow)
  range_image.py  range image -> vehicle-frame points (pinned upstream equations)
  quantize.py     int16 xyz, u8 intensity/elongation, flag bits
  wpc.py          WPC1 planar point container writer/reader
  images.py       JPEG/PNG passthrough, camera colour baked per point
  export.py       CLI: slice -> bundle (staging dir, atomic rename)
  verify.py       CLI: scalar re-derivation, box-count agreement, hashes
  serve.py        static server for web/dist + bundles
tests/            stdlib unittest, synthetic data only
web/              Vite + TypeScript + Three.js app
```

## Bundle format (`waymo-viewer-bundle/1`)

```
bundles/{slice_id}/{context}/
  scene.json        calibrations, per-frame poses and image poses, stats, palettes,
                    lineage (slice id, release, split, source Parquet SHA-256s),
                    quantization, and SHA-256 of every output file
  tracks.json       lidar_box rows grouped by laser_object_id (whole scene)
  frames/NNNN.wpc   all LiDARs and both returns for one frame
  frames/NNNN.json  camera boxes, projected boxes, synced boxes, associations, keypoints
  images/NNNN_k.jpg camera JPEG bytes copied verbatim
  panoptic/NNNN_k.png 16-bit panoptic PNG copied verbatim (frames where labelled)
```

`.wpc` is a little-endian planar container: a 32-byte header, a 32-byte
section table entry per (sensor, return, kind), then 4-byte-aligned payloads.
Per point: `xyz` int16 at 5 mm in the **vehicle frame** of that frame,
`intensity` u8 (`255·log1p(min(I,cap))/log1p(cap)`, cap 32768 for TOP and 16
for the short-range LiDARs), `elongation` u8, `flags` u8 (bit 0 no-label zone,
bit 1 second return, bits 2-4 sensor id, bit 5 has camera projection), `rgb`
u8×3 baked from the frame's JPEG through `lidar_camera_projection`, optional
`proj_cam/u/v`, and `semantic`/`instance` on the TOP frames that carry
`lidar_segmentation`. Point order is row-major over valid range pixels, which
the verifier relies on. World coordinates are re-centred on the frame-0
vehicle origin (`frames_declaration.world_origin_waymo`).

## Geometry and conventions

- Range image to points follows the upstream `range_image_utils` recipe at
  commit `99a4cb3`: half-pixel inclination sampling, row 0 is the top beam,
  azimuth from the column index corrected by the extrinsic yaw, and
  `Rz(yaw)·Ry(pitch)·Rx(roll)` per-pixel motion compensation for the TOP
  LiDAR, then the inverse frame pose.
- Waymo frames: vehicle `+x` forward, `+y` left, `+z` up; camera `+x` out of the
  lens, `+y` left, `+z` up. The app keeps all data in Waymo coordinates under
  one root whose matrix is `three = [[0,-1,0],[0,0,1],[-1,0,0]] · waymo`.
- The camera-POV rig builds an exact off-centre pinhole frustum from
  `f_u, f_v, c_u, c_v`; lens distortion is ignored for rendering. The baked
  point colours use Waymo's own projections and are therefore distortion-aware.
- The 3D box `speed` field is empirically in the **world** frame (the verifier
  reports this) and speed arrows are drawn accordingly.

## Verification

`run.sh verify` re-derives sampled points with scalar math independent of the
exporter (tolerance: half a quantization step, 2.5 mm), counts exported points
inside every `lidar_box` and requires Pearson r ≥ 0.999 against
`num_lidar_points_in_box` with a median ratio in [0.93, 1.02] (Waymo's own
count is a few percent higher on large boxes), and re-hashes every output.
Measured on the two-scene validation slice: max scalar error 0.0025 m,
r = 0.99998, median ratio 0.97.

In the browser, the camera-POV projection of the 3D boxes matches Waymo's
`projected_lidar_box` rectangles with a median residual under 1 px on the
front cameras and about 3 px on the side cameras.

## Controls

Space play · ← → step (Shift ×10) · Home/End · , . rate · 1-7 colour modes ·
a accumulate · [ ] window · b boxes · l labels · t trails · k keypoints ·
f frusta · i image planes · s panoptic overlay · e ego · g additive glow ·
c cycle view · Shift+1..5 camera POV · h hide UI · p screenshot · Esc deselect.
Click a box to select its track (shows its full trail); click an image panel
to open it at full resolution.

## Known limitations

- Image planes and frusta ignore lens distortion (a few pixels at the edges).
- LiDAR segmentation exists only every ~0.5 s (timeline ticks); panoptic
  labels every 0.2 s.
- Playback drops frames rather than stalling when the cache is behind; the
  cache holds about 700 MB of decoded frames.
