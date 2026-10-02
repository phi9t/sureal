"""Distinct annotation catalogs and measurement support; no pixel-level claims."""


def summarize_frame_support(camera_observations, lidar_label_frames, camera_label_frames):
    def catalog(values):
        if not isinstance(values,list) or any(type(v) is not int or v<0 for v in values):
            raise ValueError('explicit nonnegative integer frame catalog required')
        if len(values)!=len(set(values)):raise ValueError('duplicate frame catalog entry')
        return set(values)
    observations=catalog(camera_observations)
    point_targets=catalog(lidar_label_frames)
    camera_targets=catalog(camera_label_frames)
    return {'point_semantic_eval_frames':sorted(point_targets),
            'camera_conditioned_point_frames':sorted(point_targets & observations),
            'point_labels_missing_camera_measurements':sorted(point_targets-observations),
            'camera_mask_eval_frames':sorted(camera_targets & observations),
            'camera_labels_missing_measurements':sorted(camera_targets-observations),
            'joint_annotation_frames':sorted(point_targets & camera_targets),
            'scope':'annotation-row frame catalogs only; per-camera validity, observed point support and spatial label overlap require native payload checks'}
