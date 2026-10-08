"""Image passthrough and camera-colour sampling for LiDAR points."""
import io

import numpy as np
from PIL import Image


def decode_jpeg_half(data):
    """Decode a JPEG at half resolution (DCT scaling) as an (h/2, w/2, 3) uint8 array."""
    im = Image.open(io.BytesIO(data))
    w, h = im.size
    im.draft("RGB", (w // 2, h // 2))
    im = im.convert("RGB")
    return np.asarray(im), (w, h)


def image_size(data):
    return Image.open(io.BytesIO(data)).size


def png_mode(data):
    return Image.open(io.BytesIO(data)).mode


def first_projection(proj, rows, cols):
    """Select the first valid (camera, u, v) projection per point from a (H, W, 6) table."""
    p = np.asarray(proj, dtype=np.float64)[rows, cols]
    cam = p[:, 0].astype(np.int64)
    u = p[:, 1]
    v = p[:, 2]
    use_second = cam <= 0
    cam = np.where(use_second, p[:, 3].astype(np.int64), cam)
    u = np.where(use_second, p[:, 4], u)
    v = np.where(use_second, p[:, 5], v)
    return cam, u, v


def sample_rgb(cam, u, v, images):
    """images: {camera_name: (half_res_rgb, (full_w, full_h))}. Returns (rgb uint8, has_proj bool)."""
    n = cam.shape[0]
    rgb = np.zeros((n, 3), dtype=np.uint8)
    has = np.zeros(n, dtype=bool)
    for name, (arr, (w, h)) in images.items():
        sel = (cam == name) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
        if not sel.any():
            continue
        x = np.clip((u[sel] * 0.5).astype(np.int64), 0, arr.shape[1] - 1)
        y = np.clip((v[sel] * 0.5).astype(np.int64), 0, arr.shape[0] - 1)
        rgb[sel] = arr[y, x]
        has[sel] = True
    return rgb, has
