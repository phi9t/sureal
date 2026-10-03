# Motion current-reference geometry checkpoint

Live Insula extracted native calibration and historical frame poses, then reconstructed every positive LiDAR return in both engineering pilots into the vehicle reference at current index 10. Both returns and all five lasers are retained, without ROI or point caps. TOP uses first-return pixel poses for both returns; physical features contain range, intensity and elongation, excluding annotation-coverage NLZ. Camera tokens remain separate.

The producer receipts pin the executed source snapshots and output hashes. `current_geometry_fixture.py` matches the executed producer exactly; `native_geometry_metadata_fixture.cc` relocates its inventory include to the checked-in filename.

**Gate remains open:** an independent native scalar ray/transform, pixel-key and physical-feature audit must pass before geometry is accepted for forecasting. This checkpoint does not establish forecasting quality, close ticket 19, or promote a scientific cohort.
