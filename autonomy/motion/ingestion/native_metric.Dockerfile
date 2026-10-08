FROM sha256:c0018cf57e482c6a9e6623ea32f29c6039f22f5dafb0f3311bad6d411a7bb135
COPY CMakeLists.txt /motion-build-recipe/CMakeLists.txt
RUN cmake -S /motion-build-recipe -B /motion-build && cmake --build /motion-build --parallel 4
