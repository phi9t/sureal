#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 4 ]]; then
    printf 'usage: run-rgbd.sh DATASET ASSOCIATIONS GROUND_TRUTH OUTPUT\n' >&2
    exit 2
fi

dataset="$1"
associations="$2"
ground_truth="$3"
output="$4"
mkdir -p "${output}"
cp /etc/surflo-pathway-insula "${output}/insula-manifest.txt"
printf '%s\n' '4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4' > "${output}/source-commit.txt"
export LD_LIBRARY_PATH="/opt/ORB_SLAM3/lib:/opt/ORB_SLAM3/Thirdparty/DBoW2/lib:/opt/ORB_SLAM3/Thirdparty/g2o/lib:${LD_LIBRARY_PATH:-}"
/usr/bin/time -v -o "${output}/resource-summary.txt" \
    /opt/ORB_SLAM3/bin/surflo_rgbd \
    /opt/ORB_SLAM3/Vocabulary/ORBvoc.txt \
    /opt/ORB_SLAM3/Examples/RGB-D/TUM1.yaml \
    "${dataset}" "${associations}" "${ground_truth}" "${output}"
