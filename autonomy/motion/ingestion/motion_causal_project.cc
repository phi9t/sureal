// Explicit native history/current projection; full truth never becomes inputs.
#include <cmath>
#include <fstream>
#include <iostream>
#include <set>
#include <string>
#include <filesystem>
#include <google/protobuf/message.h>
#include <google/protobuf/unknown_field_set.h>
void reject_unknown(const google::protobuf::Message& message) {
 const auto* reflection=message.GetReflection();
 if(reflection->GetUnknownFields(message).field_count()) throw std::runtime_error("unknown native field outside pinned schema");
 std::vector<const google::protobuf::FieldDescriptor*> fields;reflection->ListFields(message,&fields);
 for(const auto* field:fields) if(field->cpp_type()==google::protobuf::FieldDescriptor::CPPTYPE_MESSAGE) {
  if(field->is_repeated()) for(int i=0;i<reflection->FieldSize(message,field);++i) reject_unknown(reflection->GetRepeatedMessage(message,field,i));
  else reject_unknown(reflection->GetMessage(message,field));
 }
}
#include "waymo_open_dataset/protos/scenario.pb.h"
int main(int argc,char** argv) {
 try {
  if(argc!=3) throw std::runtime_error("input and output required");
  if(std::filesystem::exists(argv[2])) throw std::runtime_error("output exists");
  const auto bytes=std::filesystem::file_size(argv[1]);
  if(bytes==0 || bytes>64*1024*1024) throw std::runtime_error("bounded nonempty source required");
  std::ifstream f(argv[1],std::ios::binary); std::string data(bytes,'\0');
  if(!f.read(data.data(),bytes)) throw std::runtime_error("source read failed");
  waymo::open_dataset::Scenario truth,out;
  if(!truth.ParseFromString(data)) throw std::runtime_error("invalid native Scenario");
  reject_unknown(truth);
  const int total=truth.timestamps_seconds_size();
  const int64_t n=static_cast<int64_t>(truth.current_time_index())+1;
  if(truth.scenario_id().empty() || !truth.has_current_time_index() || n<=0 || n>total || truth.tracks_size()==0 || !truth.has_sdc_track_index() || truth.sdc_track_index()<0 || truth.sdc_track_index()>=truth.tracks_size()) throw std::runtime_error("invalid native identity/current/ego");
  for(int i=0;i<total;++i) if(!std::isfinite(truth.timestamps_seconds(i)) || (i && truth.timestamps_seconds(i)<=truth.timestamps_seconds(i-1))) throw std::runtime_error("invalid native timeline");
  if(truth.dynamic_map_states_size()!=total) throw std::runtime_error("dynamic timeline mismatch");
  for(int count:{truth.compressed_frame_laser_data_size(),truth.frame_camera_tokens_size()}) if(count!=0 && count!=n) throw std::runtime_error("sensor coverage must be history/current only");
  out.set_scenario_id(truth.scenario_id());out.set_current_time_index(n-1);out.set_sdc_track_index(truth.sdc_track_index());
  for(int i=0;i<n;++i) {out.add_timestamps_seconds(truth.timestamps_seconds(i));*out.add_dynamic_map_states()=truth.dynamic_map_states(i);}
  std::set<int> ids;
  for(const auto& track:truth.tracks()) {
   if(!track.has_id() || !ids.insert(track.id()).second || track.states_size()!=total) throw std::runtime_error("track identity/timeline mismatch");
   auto* t=out.add_tracks();t->set_id(track.id());t->set_object_type(track.object_type());
   for(int i=0;i<n;++i)*t->add_states()=track.states(i);
  }
  for(const auto& x:truth.map_features())*out.add_map_features()=x;
  for(const auto& x:truth.compressed_frame_laser_data())*out.add_compressed_frame_laser_data()=x;
  for(const auto& x:truth.frame_camera_tokens())*out.add_frame_camera_tokens()=x;
  // Explicit construction excludes required-target difficulty, interaction
  // annotations, unknown future fields and all states/signals after current.
  std::string encoded;if(!out.SerializeToString(&encoded)) throw std::runtime_error("serialize failed");
  std::ofstream target(argv[2],std::ios::binary);target.write(encoded.data(),encoded.size());if(!target)throw std::runtime_error("write failed");
  std::cout<<"PASS native causal projection "<<n<<" timesteps\n";return 0;
 } catch(const std::exception& e) {std::cerr<<e.what()<<"\n";return 1;}
}
