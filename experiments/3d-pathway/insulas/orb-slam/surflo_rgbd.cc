#include <System.h>
#include <Map.h>
#include <MapPoint.h>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/calib3d.hpp>

#include <Eigen/Core>
#include <Eigen/Geometry>

#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <tuple>
#include <vector>

namespace {

struct FrameRecord {
    double timestamp;
    std::string rgb;
    std::string depth;
};

struct PoseRecord {
    double timestamp;
    Eigen::Vector3f translation;
    Eigen::Quaternionf rotation;
};

struct RunStats {
    int frames = 0;
    int tracked = 0;
    bool lost_during_perturbation = false;
    bool tracking_resumed = false;
    bool same_map_relocalized = false;
    long map_id_before_perturbation = -1;
    long map_id_after_resume = -1;
};

long dominant_map_id(const std::vector<ORB_SLAM3::MapPoint*>& points) {
    std::map<unsigned long, int> counts;
    for (auto* point : points) {
        if (point == nullptr || point->isBad()) continue;
        ORB_SLAM3::Map* map = point->GetMap();
        if (map == nullptr || map->IsBad()) continue;
        counts[map->GetId()] += 1;
    }
    int best_count = 0;
    long best_id = -1;
    for (const auto& item : counts) {
        if (item.second > best_count) {
            best_count = item.second;
            best_id = static_cast<long>(item.first);
        }
    }
    return best_id;
}

std::vector<FrameRecord> load_associations(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) throw std::runtime_error("cannot open associations: " + path);
    std::vector<FrameRecord> records;
    std::string line;
    while (std::getline(stream, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream values(line);
        double depth_timestamp = 0.0;
        FrameRecord record;
        if (!(values >> record.timestamp >> record.rgb >> depth_timestamp >> record.depth)) {
            throw std::runtime_error("malformed association record");
        }
        records.push_back(record);
    }
    if (records.empty()) throw std::runtime_error("empty association file");
    return records;
}

std::vector<PoseRecord> load_poses(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) throw std::runtime_error("cannot open ground truth: " + path);
    std::vector<PoseRecord> records;
    std::string line;
    while (std::getline(stream, line)) {
        if (line.empty() || line[0] == '#') continue;
        PoseRecord record;
        float tx, ty, tz, qx, qy, qz, qw;
        std::istringstream values(line);
        if (!(values >> record.timestamp >> tx >> ty >> tz >> qx >> qy >> qz >> qw)) {
            throw std::runtime_error("malformed ground-truth record");
        }
        record.translation = Eigen::Vector3f(tx, ty, tz);
        record.rotation = Eigen::Quaternionf(qw, qx, qy, qz).normalized();
        records.push_back(record);
    }
    if (records.empty()) throw std::runtime_error("empty ground truth");
    return records;
}

void write_ply(const std::string& path, const std::vector<Eigen::Vector3f>& points) {
    if (points.empty()) throw std::runtime_error("refusing to write an empty point cloud");
    std::ofstream stream(path);
    if (!stream) throw std::runtime_error("cannot write PLY: " + path);
    stream << "ply\nformat ascii 1.0\nelement vertex " << points.size()
           << "\nproperty float x\nproperty float y\nproperty float z\nend_header\n";
    stream << std::setprecision(9);
    for (const auto& point : points) stream << point.x() << ' ' << point.y() << ' ' << point.z() << '\n';
}

std::vector<Eigen::Vector3f> truth_cloud(
    const std::string& dataset,
    const std::vector<FrameRecord>& frames,
    const std::vector<PoseRecord>& poses) {
    const float fx = 517.306408f;
    const float fy = 516.469215f;
    const float cx = 318.643040f;
    const float cy = 255.313989f;
    const float voxel = 0.05f;
    std::vector<cv::Point> sample_pixels;
    std::vector<cv::Point2f> distorted_pixels;
    for (int v = 0; v < 480; v += 12) {
        for (int u = 0; u < 640; u += 12) {
            sample_pixels.emplace_back(u, v);
            distorted_pixels.emplace_back(static_cast<float>(u), static_cast<float>(v));
        }
    }
    const cv::Mat camera = (cv::Mat_<double>(3, 3) << fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0);
    const cv::Mat distortion = (cv::Mat_<double>(1, 5)
        << 0.262383, -0.953104, -0.005358, 0.002628, 1.163314);
    std::vector<cv::Point2f> normalized_pixels;
    cv::undistortPoints(distorted_pixels, normalized_pixels, camera, distortion);
    std::map<std::tuple<int, int, int>, Eigen::Vector3f> voxels;
    const size_t frame_stride = std::max<size_t>(1, frames.size() / 80);
    for (size_t index = 0; index < frames.size(); index += frame_stride) {
        cv::Mat depth = cv::imread(dataset + "/" + frames[index].depth, cv::IMREAD_UNCHANGED);
        if (depth.empty() || depth.type() != CV_16UC1) throw std::runtime_error("invalid TUM depth image");
        const PoseRecord& pose = poses.at(index);
        for (size_t pixel_index = 0; pixel_index < sample_pixels.size(); ++pixel_index) {
            const cv::Point pixel = sample_pixels[pixel_index];
            const uint16_t raw = depth.at<uint16_t>(pixel.y, pixel.x);
            if (raw == 0) continue;
            const float z = static_cast<float>(raw) / 5000.0f;
            if (z < 0.2f || z > 6.0f) continue;
            const cv::Point2f ray = normalized_pixels[pixel_index];
            const Eigen::Vector3f camera_point(ray.x * z, ray.y * z, z);
            const Eigen::Vector3f world = pose.rotation * camera_point + pose.translation;
            const auto key = std::make_tuple(
                static_cast<int>(std::floor(world.x() / voxel)),
                static_cast<int>(std::floor(world.y() / voxel)),
                static_cast<int>(std::floor(world.z() / voxel)));
            voxels.emplace(key, world);
        }
    }
    std::vector<Eigen::Vector3f> all;
    all.reserve(voxels.size());
    for (const auto& item : voxels) all.push_back(item.second);
    const size_t limit = 8192;
    if (all.size() <= limit) return all;
    std::vector<Eigen::Vector3f> sampled;
    sampled.reserve(limit);
    for (size_t index = 0; index < limit; ++index) sampled.push_back(all[index * all.size() / limit]);
    return sampled;
}

void perturb(cv::Mat& rgb, cv::Mat& depth, const std::string& mode, size_t index, size_t count) {
    const size_t begin = count * 35 / 100;
    const size_t end = count * 50 / 100;
    if (index < begin || index >= end) return;
    if (mode == "occlusion") {
        rgb.setTo(cv::Scalar::all(0));
        depth.setTo(cv::Scalar::all(0));
    } else if (mode == "dynamic-object") {
        const int width = std::min(180, rgb.cols / 3);
        const int height = std::min(140, rgb.rows / 3);
        const int x = static_cast<int>((index * 17) % std::max(1, rgb.cols - width));
        const int y = (rgb.rows - height) / 2;
        const cv::Rect box(x, y, width, height);
        cv::rectangle(rgb, box, cv::Scalar(20, 220, 20), cv::FILLED);
        for (int row = y; row < y + height; row += 16) {
            cv::line(rgb, cv::Point(x, row), cv::Point(x + width - 1, row), cv::Scalar(240, 20, 240), 3);
        }
        depth(box).setTo(cv::Scalar::all(750));
    }
}

RunStats run_sequence(
    const std::string& vocabulary,
    const std::string& settings,
    const std::string& dataset,
    const std::vector<FrameRecord>& frames,
    const std::string& mode,
    const std::string& output) {
    ORB_SLAM3::System slam(vocabulary, settings, ORB_SLAM3::System::RGBD, false);
    std::ofstream tracking;
    std::ofstream variant_trajectory;
    if (mode == "baseline") {
        tracking.open(output + "/tracking.csv");
        tracking << "timestamp,state,tracked_map_points,runtime_seconds\n";
    } else {
        const std::string path = mode == "occlusion"
            ? output + "/CameraTrajectory-occlusion.txt"
            : output + "/CameraTrajectory-dynamic-object.txt";
        variant_trajectory.open(path);
        variant_trajectory << std::fixed;
    }
    std::map<unsigned long, ORB_SLAM3::MapPoint*> landmarks;
    RunStats stats;
    for (size_t index = 0; index < frames.size(); ++index) {
        cv::Mat rgb = cv::imread(dataset + "/" + frames[index].rgb, cv::IMREAD_UNCHANGED);
        cv::Mat depth = cv::imread(dataset + "/" + frames[index].depth, cv::IMREAD_UNCHANGED);
        if (rgb.empty() || depth.empty()) throw std::runtime_error("failed to load TUM RGB-D frame");
        perturb(rgb, depth, mode, index, frames.size());
        const auto start = std::chrono::steady_clock::now();
        const Sophus::SE3f Tcw = slam.TrackRGBD(rgb, depth, frames[index].timestamp);
        const double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        const int state = slam.GetTrackingState();
        const auto points = slam.GetTrackedMapPoints();
        stats.frames += 1;
        const bool tracked = state == 2 || state == 5;
        if (tracked) stats.tracked += 1;
        if (mode != "baseline" && tracked) {
            const Sophus::SE3f Twc = Tcw.inverse();
            const Eigen::Vector3f translation = Twc.translation();
            const Eigen::Quaternionf rotation = Twc.unit_quaternion();
            variant_trajectory << std::setprecision(6) << frames[index].timestamp << ' '
                               << std::setprecision(9) << translation.x() << ' ' << translation.y() << ' '
                               << translation.z() << ' ' << rotation.x() << ' ' << rotation.y() << ' '
                               << rotation.z() << ' ' << rotation.w() << '\n';
        }
        const size_t disturbance_begin = frames.size() * 35 / 100;
        const size_t disturbance_end = frames.size() * 50 / 100;
        const long map_id = dominant_map_id(points);
        if (index < disturbance_begin && map_id >= 0) {
            stats.map_id_before_perturbation = map_id;
        }
        if (index >= disturbance_begin && index < disturbance_end && !tracked) {
            stats.lost_during_perturbation = true;
        }
        if (
            index >= disturbance_end && stats.lost_during_perturbation && tracked
            && !stats.tracking_resumed) {
            stats.tracking_resumed = true;
            stats.map_id_after_resume = map_id;
            stats.same_map_relocalized = map_id >= 0 && map_id == stats.map_id_before_perturbation;
        }
        if (mode == "baseline") {
            tracking << std::setprecision(17) << frames[index].timestamp << ',' << state << ','
                     << points.size() << ',' << elapsed << '\n';
            for (auto* point : points) {
                if (point == nullptr || point->isBad() || point->Observations() < 2) continue;
                while (point->GetReplaced() != nullptr) point = point->GetReplaced();
                if (!point->isBad()) landmarks[point->mnId] = point;
            }
        }
        const double interval = index + 1 < frames.size()
            ? frames[index + 1].timestamp - frames[index].timestamp
            : (index > 0 ? frames[index].timestamp - frames[index - 1].timestamp : 0.0);
        if (elapsed < interval) std::this_thread::sleep_for(std::chrono::duration<double>(interval - elapsed));
    }
    variant_trajectory.close();
    slam.Shutdown();
    if (mode == "baseline") {
        slam.SaveTrajectoryTUM(output + "/CameraTrajectory.txt");
        slam.SaveKeyFrameTrajectoryTUM(output + "/KeyFrameTrajectory.txt");
        std::map<unsigned long, Eigen::Vector3f> final_landmarks;
        for (const auto& item : landmarks) {
            ORB_SLAM3::MapPoint* point = item.second;
            while (point != nullptr && point->GetReplaced() != nullptr) point = point->GetReplaced();
            if (point == nullptr || point->isBad() || point->Observations() < 2) continue;
            const Eigen::Vector3f position = point->GetWorldPos();
            if (position.allFinite()) final_landmarks[point->mnId] = position;
        }
        std::map<std::tuple<int, int, int>, Eigen::Vector3f> voxels;
        for (const auto& item : final_landmarks) {
            const Eigen::Vector3f& point = item.second;
            const auto key = std::make_tuple(
                static_cast<int>(std::floor(point.x() / 0.02f)),
                static_cast<int>(std::floor(point.y() / 0.02f)),
                static_cast<int>(std::floor(point.z() / 0.02f)));
            voxels.emplace(key, point);
        }
        std::vector<Eigen::Vector3f> points;
        for (const auto& item : voxels) points.push_back(item.second);
        write_ply(output + "/map.ply", points);
    }
    return stats;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 7) {
            std::cerr << "usage: surflo_rgbd VOCAB SETTINGS DATASET ASSOCIATIONS GROUND_TRUTH OUTPUT\n";
            return 2;
        }
        const std::string dataset = argv[3];
        const std::string output = argv[6];
        const auto frames = load_associations(argv[4]);
        const auto poses = load_poses(argv[5]);
        if (poses.size() != frames.size()) throw std::runtime_error("ground-truth/frame count mismatch");
        write_ply(output + "/ground-truth-map.ply", truth_cloud(dataset, frames, poses));
        run_sequence(argv[1], argv[2], dataset, frames, "baseline", output);
        const RunStats occlusion = run_sequence(argv[1], argv[2], dataset, frames, "occlusion", output);
        const RunStats dynamic = run_sequence(argv[1], argv[2], dataset, frames, "dynamic-object", output);
        std::ofstream sweep(output + "/failure-sweep.json");
        sweep << std::boolalpha << std::setprecision(17)
              << "{\"variants\":["
              << "{\"id\":\"occlusion\",\"tracking_coverage\":"
              << static_cast<double>(occlusion.tracked) / occlusion.frames
              << ",\"lost_during_perturbation\":" << occlusion.lost_during_perturbation
              << ",\"tracking_resumed\":" << occlusion.tracking_resumed
              << ",\"same_map_relocalized\":" << occlusion.same_map_relocalized
              << ",\"map_id_before_perturbation\":" << occlusion.map_id_before_perturbation
              << ",\"map_id_after_resume\":" << occlusion.map_id_after_resume << "},"
              << "{\"id\":\"dynamic-object\",\"tracking_coverage\":"
              << static_cast<double>(dynamic.tracked) / dynamic.frames
              << ",\"lost_during_perturbation\":" << dynamic.lost_during_perturbation
              << ",\"tracking_resumed\":" << dynamic.tracking_resumed
              << ",\"same_map_relocalized\":" << dynamic.same_map_relocalized
              << ",\"map_id_before_perturbation\":" << dynamic.map_id_before_perturbation
              << ",\"map_id_after_resume\":" << dynamic.map_id_after_resume << "}]}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "surflo_rgbd: " << error.what() << '\n';
        return 1;
    }
}
