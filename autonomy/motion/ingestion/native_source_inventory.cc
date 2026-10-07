#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <set>
#include <regex>
#include <cstdint>
#include <google/protobuf/message.h>
#include <google/protobuf/unknown_field_set.h>
#include "waymo_open_dataset/protos/scenario.pb.h"
uint32_t crc(const std::string& s){uint32_t v=~0u;for(unsigned char c:s){v^=c;for(int j=0;j<8;j++)v=(v>>1)^((v&1)?0x82f63b78u:0u);}return ~v;}
uint32_t mask(uint32_t c){return ((c>>15)|(c<<17))+0xa282ead8u;}
uint64_t le(const std::string& s){uint64_t v=0;for(size_t i=0;i<s.size();i++)v|=uint64_t((unsigned char)s[i])<<(8*i);return v;}
std::string read(std::ifstream& f,size_t n){std::string s(n,'\0');if(!f.read(s.data(),n))throw std::runtime_error("truncated frame");return s;}
void known(const google::protobuf::Message& m){auto r=m.GetReflection();if(r->GetUnknownFields(m).field_count())throw std::runtime_error("unknown pinned field");std::vector<const google::protobuf::FieldDescriptor*> fs;r->ListFields(m,&fs);for(auto x:fs)if(x->cpp_type()==google::protobuf::FieldDescriptor::CPPTYPE_MESSAGE){if(x->is_repeated())for(int i=0;i<r->FieldSize(m,x);i++)known(r->GetRepeatedMessage(m,x,i));else known(r->GetMessage(m,x));}}
int main(int argc,char**argv){try{if(argc!=4)throw std::runtime_error("arguments");std::ifstream f(argv[1],std::ios::binary);std::ofstream inv(argv[2]);if(!f||!inv)throw std::runtime_error("files");std::set<std::string> ids;std::string selected,bytes;uint64_t offset=0;size_t index=0;inv<<"index\toffset\tpayload_bytes\tscenario_id\tcurrent_index\ttimestamps\ttracks\ttargets\tlidar_frames\tcamera_frames\n";
while(f.peek()!=EOF){auto len=read(f,8);if(le(read(f,4))!=mask(crc(len)))throw std::runtime_error("length CRC");uint64_t n=le(len);if(n==0||n>64*1024*1024)throw std::runtime_error("length cap");auto payload=read(f,n);if(le(read(f,4))!=mask(crc(payload)))throw std::runtime_error("payload CRC");waymo::open_dataset::Scenario s;if(!s.ParseFromString(payload))throw std::runtime_error("protobuf");known(s);if(!std::regex_match(s.scenario_id(),std::regex("[A-Za-z0-9_-]{1,128}"))||!ids.insert(s.scenario_id()).second)throw std::runtime_error("duplicate/invalid ID");if(!s.has_current_time_index()||s.current_time_index()<0||s.current_time_index()>=s.timestamps_seconds_size())throw std::runtime_error("clock");std::set<int> tracks;for(auto&t:s.tracks())if(!t.has_id()||!tracks.insert(t.id()).second||t.states_size()!=s.timestamps_seconds_size())throw std::runtime_error("track timeline");for(auto&t:s.tracks_to_predict())if(t.track_index()<0||t.track_index()>=s.tracks_size())throw std::runtime_error("target");inv<<index<<'\t'<<offset<<'\t'<<n<<'\t'<<s.scenario_id()<<'\t'<<s.current_time_index()<<'\t'<<s.timestamps_seconds_size()<<'\t'<<s.tracks_size()<<'\t'<<s.tracks_to_predict_size()<<'\t'<<s.compressed_frame_laser_data_size()<<'\t'<<s.frame_camera_tokens_size()<<'\n';if(selected.empty()||s.scenario_id()<selected){selected=s.scenario_id();bytes=payload;}offset+=n+16;index++;}
if(!index)throw std::runtime_error("empty");std::ofstream out(argv[3],std::ios::binary);out.write(bytes.data(),bytes.size());if(!out||!inv)throw std::runtime_error("write");std::cout<<"INVENTORIED "<<index<<" "<<offset<<" SELECTED "<<selected<<"\n";return 0;}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
