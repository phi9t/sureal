// Bounded offline adapter to the unmodified Waymo camera core.
// World points are explicitly treated as static landmarks; no object GT enters.
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include "google/protobuf/text_format.h"
#include "waymo_open_dataset/wdl_limited/camera/camera_model.h"
namespace fs=std::filesystem;
using namespace waymo::open_dataset;
void Require(bool condition,const char* message){if(!condition)throw std::runtime_error(message);}
template<class P> P Read(const char* path){
 Require(fs::is_regular_file(path)&&fs::file_size(path)<=1024*1024,"bounded regular metadata required");
 std::ifstream file(path);std::string text((std::istreambuf_iterator<char>(file)),{});P value;
 Require(google::protobuf::TextFormat::ParseFromString(text,&value),"invalid metadata proto");return value;
}
void ValidateTransform(const Transform& value){
 Require(value.transform_size()==16,"sixteen transform elements required");Eigen::Matrix4d matrix;
 for(int r=0;r<4;++r)for(int c=0;c<4;++c){double x=value.transform(4*r+c);Require(std::isfinite(x),"finite transform required");matrix(r,c)=x;}
 Require((matrix.row(3)-Eigen::RowVector4d(0,0,0,1)).norm()<=1e-6,"homogeneous transform required");
 Eigen::Matrix3d rotation=matrix.topLeftCorner<3,3>();
 Require((rotation.transpose()*rotation-Eigen::Matrix3d::Identity()).norm()<=1e-6&&std::abs(rotation.determinant()-1)<=1e-6,"proper rigid rotation required");
}
int main(int argc,char** argv){try{
 Require(argc==5,"usage: project_camera calibration image world_xyz output_csv");
 Require(!fs::exists(argv[4])&&!fs::is_symlink(argv[4]),"new output required");
 auto calibration=Read<CameraCalibration>(argv[1]);auto image=Read<CameraImage>(argv[2]);
 Require(calibration.name()>0&&calibration.name()<=5&&calibration.name()==image.name(),"camera identity differs");
 Require(calibration.intrinsic_size()==9&&calibration.intrinsic(0)>0&&calibration.intrinsic(1)>0&&calibration.width()>0&&calibration.height()>0,"native intrinsics and image dimensions required");
 for(double x:calibration.intrinsic())Require(std::isfinite(x),"finite intrinsics required");
 Require(calibration.rolling_shutter_direction()>=1&&calibration.rolling_shutter_direction()<=5,"explicit shutter direction required");
 ValidateTransform(calibration.extrinsic());ValidateTransform(image.pose());
 Require(image.has_pose_timestamp()&&image.has_shutter()&&image.has_camera_trigger_time()&&image.has_camera_readout_done_time()&&image.has_velocity(),"native timing/velocity presence required");
 for(double x:{image.pose_timestamp(),image.shutter(),image.camera_trigger_time(),image.camera_readout_done_time(),double(image.velocity().v_x()),double(image.velocity().v_y()),double(image.velocity().v_z()),image.velocity().w_x(),image.velocity().w_y(),image.velocity().w_z()})Require(std::isfinite(x),"finite timing/velocity required");
 Require(image.shutter()>=0&&image.camera_readout_done_time()-image.camera_trigger_time()>=image.shutter(),"invalid exposure duration");
 Require(fs::is_regular_file(argv[3])&&fs::file_size(argv[3])<=32*1024*1024,"bounded world point source required");
 CameraModel model(calibration);model.PrepareProjection(image);std::ifstream points(argv[3]);std::ostringstream output;output<<std::setprecision(17);std::string line;size_t index=0;
 while(std::getline(points,line)){
  Require(line.size()<=512&&index<200000,"point row/cap exceeded");std::istringstream row(line);double x,y,z;std::string extra;
  Require(bool(row>>x>>y>>z)&&!(row>>extra)&&std::isfinite(x)&&std::isfinite(y)&&std::isfinite(z),"finite exact world XYZ row required");
  double u=-1,v=-1,depth=-1;bool valid=model.WorldToImageWithDepth(x,y,z,false,&u,&v,&depth);
  if(!std::isfinite(u)||!std::isfinite(v)||!std::isfinite(depth)){valid=false;u=v=depth=-1;}
  output<<index++<<','<<int(valid)<<','<<u<<','<<v<<','<<depth<<'\n';
 }
 Require(points.eof()&&index>0,"complete nonempty world point source required");std::ofstream file(argv[4]);file<<output.str();Require(bool(file),"output write failed");
 std::cout<<"PASS static-world camera projection rows "<<index<<'\n';return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
