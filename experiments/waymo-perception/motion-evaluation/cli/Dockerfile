FROM sha256:84fb83dd874d0cfff8e9ee3df0759d89f9ad85e9538c0071c9eb606a13d8c233
COPY CMakeLists.txt motion_metrics_main.cc /motion-cli-recipe/
RUN cmake -S /motion-cli-recipe -B /motion-cli-build && cmake --build /motion-cli-build --parallel 4
