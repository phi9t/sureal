#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <google/protobuf/text_format.h>
#include <google/protobuf/util/json_util.h>
#include "waymo_open_dataset/metrics/motion_metrics.h"
namespace wod = waymo::open_dataset;
void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
template<class T> T read(const char* name) {
  const auto bytes = std::filesystem::file_size(name);
  require(bytes > 0 && bytes <= 64*1024*1024, "bounded nonempty input required");
  std::ifstream stream(name); require(stream.good(), "cannot read input");
  std::string text((std::istreambuf_iterator<char>(stream)), {}); T result;
  require(google::protobuf::TextFormat::ParseFromString(text, &result), "malformed textproto");
  return result;
}
int main(int argc, char** argv) {
 try {
  require(argc == 5, "usage: compute_motion_metrics SCENARIO PREDICTIONS CONFIG OUTPUT");
  require(!std::filesystem::exists(argv[4]), "existing output refused");
  auto scene=read<wod::Scenario>(argv[1]); auto predictions=read<wod::ScenarioPredictions>(argv[2]); auto config=read<wod::MotionMetricsConfig>(argv[3]);
  require(!scene.scenario_id().empty() && scene.scenario_id()==predictions.scenario_id(), "scenario identity differs");
  const int track_rate=config.track_steps_per_second(), pred_rate=config.prediction_steps_per_second();
  require(track_rate>0 && pred_rate>0 && track_rate%pred_rate==0, "invalid sampling rates");
  require(config.track_history_samples()>=0 && config.track_future_samples()>0 && config.track_future_samples()%(track_rate/pred_rate)==0, "invalid sample counts");
  const int length=config.track_future_samples()/(track_rate/pred_rate);
  require(scene.current_time_index()==config.track_history_samples(), "current index differs from configured history");
  require(config.max_predictions()>0 && config.step_configurations_size()>0, "positive K and horizons required");
  std::set<int> horizons;
  for (const auto& step:config.step_configurations()) {
    require(step.measurement_step()>=0 && step.measurement_step()<length && horizons.insert(step.measurement_step()).second, "invalid or repeated endpoint");
    require(std::isfinite(step.lateral_miss_threshold()) && step.lateral_miss_threshold()>0 && std::isfinite(step.longitudinal_miss_threshold()) && step.longitudinal_miss_threshold()>0, "invalid miss threshold");
  }
  std::set<int> ids;
  const int states=config.track_history_samples()+config.track_future_samples()+1;
  require(scene.timestamps_seconds_size()==states && scene.tracks_size()>0, "native state catalog differs");
  for (const auto& track:scene.tracks()) {
    require(ids.insert(track.id()).second && track.states_size()==states, "duplicate track or wrong state length");
    for (const auto& state:track.states()) if (state.valid()) require(std::isfinite(state.center_x()) && std::isfinite(state.center_y()) && std::isfinite(state.heading()) && std::isfinite(state.velocity_x()) && std::isfinite(state.velocity_y()) && std::isfinite(state.length()) && std::isfinite(state.width()), "nonfinite valid state");
  }
  require(predictions.multi_modal_predictions_size()>0, "predictions required");
  for (const auto& group:predictions.multi_modal_predictions()) {
    require(group.joint_predictions_size()>0, "modes required");
    for (const auto& mode:group.joint_predictions()) {
      require(std::isfinite(mode.confidence()) && mode.confidence()>=0 && mode.trajectories_size()>0, "invalid mode confidence or group");
      for (const auto& trajectory:mode.trajectories()) {
        require(ids.count(trajectory.object_id()) && trajectory.center_x_size()==length && trajectory.center_y_size()==length, "invalid target or prediction length");
        for (int i=0;i<length;++i) require(std::isfinite(trajectory.center_x(i)) && std::isfinite(trajectory.center_y(i)), "nonfinite prediction");
      }
    }
  }
  wod::BucketedMetricsStats stats; auto status=wod::ComputeMetricsStats(config,predictions,scene,&stats);
  require(status.ok(),status.message().c_str());
  auto metrics=wod::ComputeMotionMetrics(&stats);std::string native_json;
  google::protobuf::util::JsonPrintOptions options;options.always_print_primitive_fields=true;
  require(google::protobuf::util::MessageToJsonString(metrics,&native_json,options).ok(), "metric serialization failed");
  std::ostringstream result;result<<"{\"metrics\":"<<native_json<<",\"counts\":[";bool first=true;
  for (const auto& type:stats.stats) for (const auto& step:type.second) {
    if (!first) result<<",";first=false;const auto& s=step.second;
    result<<"{\"object_type\":"<<type.first<<",\"measurement_step\":"<<step.first<<",\"min_ade\":"<<s.min_average_displacement.num_measurements<<",\"min_fde\":"<<s.min_final_displacement.num_measurements<<",\"miss_rate\":"<<s.miss_rate.num_measurements<<",\"overlap_rate\":"<<s.overlap_rate.num_measurements<<"}";
  }
  result<<"]}\n";std::ofstream output(argv[4]);require(output.good(), "cannot open output");output<<result.str();output.close();require(output.good(), "output write failed");return 0;
 } catch (const std::exception& e) {std::cerr<<e.what()<<"\n";return 1;}
}
