#!/usr/bin/env python3
"""Shared, Blender-independent contracts for the photoreal benchmark."""

from __future__ import annotations


PROFILES = {
    "draft": {
        "width": 128,
        "height": 96,
        "samples": 32,
        "denoise_beauty": True,
        "required_device": None,
    },
    "benchmark": {
        "width": 512,
        "height": 384,
        "samples": 256,
        "denoise_beauty": True,
        "required_device": "OPTIX",
    },
}


def validate_device(profile: str, device: str) -> str:
    """Return a normalized device or reject implicit/unsupported fallback."""
    if profile not in PROFILES:
        raise ValueError(f"unknown render profile: {profile}")
    normalized = device.strip().upper()
    if normalized not in {"CPU", "OPTIX"}:
        raise ValueError("render device must be explicit: CPU or OPTIX")
    if profile == "benchmark" and normalized != "OPTIX":
        raise ValueError("benchmark renders require OptiX; CPU is draft-only")
    return normalized
