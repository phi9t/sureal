"""Null C++ toolchain for pure-Python Bazel targets in the CPU rootfs."""

load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/toolchains:cc_toolchain_config_info.bzl", "CcToolchainConfigInfo")

def _null_cc_toolchain_config_impl(ctx):
    return [cc_common.create_cc_toolchain_config_info(
        ctx = ctx,
        toolchain_identifier = "sureal_null_cc",
        host_system_name = "local",
        target_system_name = "local",
        target_cpu = "k8",
        target_libc = "local",
        compiler = "null",
        abi_version = "local",
        abi_libc_version = "local",
        cxx_builtin_include_directories = [],
    )]

null_cc_toolchain_config = rule(
    implementation = _null_cc_toolchain_config_impl,
    provides = [CcToolchainConfigInfo],
)
