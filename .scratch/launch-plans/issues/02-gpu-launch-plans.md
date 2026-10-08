# 02: GPU launch plans

**What to build:** A researcher requests a GPU by index on a launch plan and gets that device, the control and UVM devices, the driver libraries and the GPU environment, from the same code the Bazel launcher uses. The GPU live verifiers use it instead of copying device handling or taking a lock from an old receipt.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A plan takes an optional GPU index. The module adds the device, control and UVM devices, driver libraries under `/driver` and the GPU environment, honours `SUREAL_BAZEL_GPU_DEVICES`, and never picks a GPU itself
- [ ] The Bazel launcher's GPU configuration and the launch-plan module share one implementation
- [ ] The receipt record names the GPU by requested index and device UUID, not device paths
- [ ] `insula/verify_gpu_live.py` and `insula/verify_gpu_isolation.py` use GPU launch plans and the module's lock loading. Neither copies device handling nor reads a runtime lock out of an old receipt
- [ ] Offline tests cover the GPU additions using a fake device list. A `requires_gpu` test runs a trivial CUDA query through a GPU plan on GPU 1 and records its pass
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
