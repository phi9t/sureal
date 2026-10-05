cmake_minimum_required(VERSION 3.16)
project(waymo_native_metrics LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(Protobuf REQUIRED)
find_package(absl REQUIRED)
find_package(glog REQUIRED)
find_package(GTest REQUIRED)
file(GLOB_RECURSE PROTO_CC /generated/*.pb.cc)
add_library(wod_proto ${PROTO_CC})
target_include_directories(wod_proto PUBLIC /generated /upstream/src)
target_link_libraries(wod_proto PUBLIC protobuf::libprotobuf)
set(WOD /upstream/src/waymo_open_dataset)
add_library(wod_metrics
 ${WOD}/metrics/breakdown_generator.cc ${WOD}/metrics/config_util.cc
 ${WOD}/metrics/hungarian.cc ${WOD}/metrics/iou.cc ${WOD}/metrics/matcher.cc
 ${WOD}/metrics/metrics_utils.cc ${WOD}/metrics/detection_metrics.cc
 ${WOD}/metrics/segmentation_metrics.cc ${WOD}/metrics/test_utils.cc
 ${WOD}/common/status.cc ${WOD}/math/box2d.cc ${WOD}/math/polygon2d.cc
 ${WOD}/math/segment2d.cc)
target_link_libraries(wod_metrics PUBLIC wod_proto glog::glog absl::strings absl::str_format absl::flat_hash_map absl::status)
foreach(metric detection segmentation)
 add_executable(${metric}_metrics_test ${WOD}/metrics/${metric}_metrics_test.cc)
 target_link_libraries(${metric}_metrics_test PRIVATE wod_metrics GTest::gtest_main)
 add_executable(compute_${metric}_metrics ${WOD}/metrics/tools/compute_${metric}_metrics_main.cc)
 target_link_libraries(compute_${metric}_metrics PRIVATE wod_metrics z)
endforeach()
