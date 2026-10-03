#include <iostream>
#include <cstdint>
int main(){uint64_t h=14695981039346656037ull;char buffer[65536];while(std::cin){std::cin.read(buffer,sizeof(buffer));for(std::streamsize i=0;i<std::cin.gcount();i++){h^=(unsigned char)buffer[i];h*=1099511628211ull;}}if(!std::cin.eof())return 1;std::cout<<h<<"\n";}
