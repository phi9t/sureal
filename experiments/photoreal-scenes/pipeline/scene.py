#!/usr/bin/env python3
"""Repository-owned Blender/Cycles scene family and annotation extractor."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
import shutil
from typing import Any, Sequence

import numpy as np

from contracts import PROFILES, validate_device
from geometry import (
    blender_matrix_from_opencv,
    look_at_opencv,
    sample_triangle_surface,
    visibility_from_views,
)

try:  # Import safety lets contract tests run in the Surflo Insula.
    import bpy  # type: ignore
    from mathutils import Matrix  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised by import-safety test
    bpy = None
    Matrix = None


@dataclass(frozen=True)
class CameraSpec:
    eye: tuple[float, float, float]
    target: tuple[float, float, float]
    width: int
    height: int
    fov_degrees: float = 52.0

    def matrices(self) -> tuple[np.ndarray, np.ndarray]:
        return look_at_opencv(
            eye=np.asarray(self.eye),
            target=np.asarray(self.target),
            width=self.width,
            height=self.height,
            fov_degrees=self.fov_degrees,
        )


@dataclass(frozen=True)
class ObjectSpec:
    name: str
    semantic_class: str
    object_id: int
    role: str
    asset_id: str
    material_asset_id: str | None
    location: tuple[float, float, float]
    rotation_degrees: tuple[float, float, float]
    target_size: tuple[float, float, float]
    geometry_kind: str
    supported_by: tuple[str, ...] = ()
    supports: tuple[str, ...] = ()
    occludes: tuple[str, ...] = ()


_COMMON_OBJECTS = (
    ObjectSpec(
        "floor_front", "floor", 1, "common", "procedural", "wood_floor",
        (0.0, -2.5, -0.06), (0.0, 0.0, 0.0), (8.0, 5.0, 0.12), "box",
        supports=("table", "chair_left", "chair_right"),
    ),
    ObjectSpec(
        "floor_rear", "floor", 2, "common", "procedural", "wood_floor",
        (-0.75, 2.0, -0.06), (0.0, 0.0, 0.0), (6.5, 4.0, 0.12), "box",
        supports=("hidden_sofa", "hidden_shelf"),
    ),
    ObjectSpec(
        "partition", "wall", 3, "common", "procedural", "white_plaster_02",
        (-1.4, 0.0, 1.5), (0.0, 0.0, 0.0), (5.2, 0.22, 3.0), "box",
        occludes=("hidden_sofa", "hidden_shelf"),
    ),
    ObjectSpec(
        "wall_left", "wall", 4, "common", "procedural", "white_plaster_02",
        (-4.0, -0.5, 1.5), (0.0, 0.0, 0.0), (0.20, 9.0, 3.0), "box",
    ),
    ObjectSpec(
        "wall_front_right", "wall", 5, "common", "procedural", "white_plaster_02",
        (4.0, -2.5, 1.5), (0.0, 0.0, 0.0), (0.20, 5.0, 3.0), "box",
    ),
    ObjectSpec(
        "wall_rear_right", "wall", 6, "common", "procedural", "white_plaster_02",
        (2.5, 2.0, 1.5), (0.0, 0.0, 0.0), (0.20, 4.0, 3.0), "box",
    ),
    ObjectSpec(
        "wall_back", "wall", 7, "common", "procedural", "white_plaster_02",
        (-0.75, 4.0, 1.5), (0.0, 0.0, 0.0), (6.5, 0.20, 3.0), "box",
    ),
    ObjectSpec(
        "ceiling_front", "ceiling", 8, "common", "procedural", "white_plaster_02",
        (0.0, -2.5, 3.06), (0.0, 0.0, 0.0), (8.0, 5.0, 0.12), "box",
    ),
    ObjectSpec(
        "ceiling_rear", "ceiling", 9, "common", "procedural", "white_plaster_02",
        (-0.75, 2.0, 3.06), (0.0, 0.0, 0.0), (6.5, 4.0, 0.12), "box",
    ),
    ObjectSpec(
        "table", "table", 20, "common", "WoodenTable_01", None,
        (-0.9, -1.85, 0.0), (0.0, 0.0, 8.0), (1.45, 0.85, 0.78), "asset",
        supported_by=("floor_front",),
    ),
    ObjectSpec(
        "chair_left", "chair", 21, "common", "WoodenChair_01", None,
        (-2.0, -1.75, 0.0), (0.0, 0.0, -78.0), (0.62, 0.62, 1.0), "asset",
        supported_by=("floor_front",),
    ),
    ObjectSpec(
        "chair_right", "chair", 22, "common", "WoodenChair_01", None,
        (0.15, -1.72, 0.0), (0.0, 0.0, 92.0), (0.62, 0.62, 1.0), "asset",
        supported_by=("floor_front",),
    ),
)

_HIDDEN = {
    "scene_a": ObjectSpec(
        "hidden_sofa", "sofa", 101, "hidden", "Sofa_01", None,
        (-1.1, 1.55, 0.0), (0.0, 0.0, 180.0), (2.25, 1.05, 0.92), "asset",
        supported_by=("floor_rear",),
    ),
    "scene_b": ObjectSpec(
        "hidden_shelf", "shelf", 102, "hidden", "Shelf_01", None,
        (-1.35, 1.95, 0.0), (0.0, 0.0, 180.0), (1.55, 0.50, 2.35), "asset",
        supported_by=("floor_rear",),
    ),
}


def object_specs(scene_name: str) -> tuple[ObjectSpec, ...]:
    if scene_name not in _HIDDEN:
        raise ValueError(f"unknown complete hypothesis: {scene_name}")
    return (*_COMMON_OBJECTS, _HIDDEN[scene_name])


def object_table(scene_name: str) -> list[dict[str, object]]:
    specs = object_specs(scene_name)
    names = {spec.name for spec in specs}
    table = []
    for spec in specs:
        record = asdict(spec)
        record["transform"] = {
            "translation_metres": list(spec.location),
            "rotation_degrees_xyz": list(spec.rotation_degrees),
            "target_size_metres": list(spec.target_size),
        }
        record["asset_provenance"] = {
            "provider": "procedural" if spec.asset_id == "procedural" else "Poly Haven",
            "asset_id": spec.asset_id,
            "material_asset_id": spec.material_asset_id,
            "resolution": "2k" if spec.asset_id != "procedural" or spec.material_asset_id else None,
            "license": "CC0-1.0",
            "lockfile": "assets.lock.json" if spec.asset_id != "procedural" or spec.material_asset_id else None,
        }
        record["relations"] = {
            "supported_by": [name for name in spec.supported_by if name in names],
            "supports": [name for name in spec.supports if name in names],
            "occludes": [name for name in spec.occludes if name in names],
        }
        for key in (
            "location", "rotation_degrees", "target_size", "supported_by",
            "supports", "occludes",
        ):
            record.pop(key)
        table.append(record)
    return table


def camera_specs(*, width: int, height: int) -> tuple[tuple[CameraSpec, ...], tuple[CameraSpec, ...]]:
    context: list[CameraSpec] = []
    for index, x in enumerate(np.linspace(-2.35, -0.45, 16)):
        phase = index / 15.0
        context.append(
            CameraSpec(
                eye=(float(x), -4.25, float(1.30 + 0.10 * math.sin(math.pi * phase))),
                target=(-0.90, -1.35, 0.78),
                width=width,
                height=height,
                fov_degrees=58.0,
            )
        )
    target_eyes = (
        (1.95, -0.30, 1.35),
        (2.12, 0.35, 1.42),
        (2.18, 0.95, 1.32),
        (2.05, 1.55, 1.38),
        (1.72, 2.25, 1.30),
        (1.15, 2.85, 1.40),
        (0.35, 3.25, 1.34),
        (-0.55, 3.38, 1.44),
    )
    target = tuple(
        CameraSpec(
            eye=eye,
            target=(-1.10, 1.85, 1.05),
            width=width,
            height=height,
            fov_degrees=58.0,
        )
        for eye in target_eyes
    )
    return tuple(context), target


def _require_bpy() -> None:
    if bpy is None:
        raise RuntimeError("this operation must run under Blender's Python")


def _clear_scene() -> None:
    _require_bpy()
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _augment_material_aovs(material: Any) -> None:
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    if nodes.get("SurfloAOV.Validity") is not None:
        return
    geometry = nodes.new("ShaderNodeNewGeometry")
    geometry.name = "SurfloAOV.Geometry"
    camera = nodes.new("ShaderNodeCameraData")
    camera.name = "SurfloAOV.Camera"
    object_info = nodes.new("ShaderNodeObjectInfo")
    object_info.name = "SurfloAOV.ObjectInfo"
    validity = nodes.new("ShaderNodeMath")
    validity.name = "SurfloAOV.Validity"
    validity.operation = "GREATER_THAN"
    validity.inputs[1].default_value = 0.0
    links.new(object_info.outputs["Object Index"], validity.inputs[0])

    def value_aov(name: str, socket: Any) -> None:
        node = nodes.new("ShaderNodeOutputAOV")
        node.name = f"SurfloAOV.{name}"
        node.aov_name = name
        links.new(socket, node.inputs["Value"])

    def color_aov(name: str, socket: Any) -> None:
        node = nodes.new("ShaderNodeOutputAOV")
        node.name = f"SurfloAOV.{name}"
        node.aov_name = name
        links.new(socket, node.inputs["Color"])

    # Keep both quantities on shader AOVs so Cycles evaluates them from the
    # same surface sample.  The built-in Z pass uses different edge sampling
    # and cannot be paired pixel-for-pixel with a shader AOV.
    value_aov("CameraDepth", camera.outputs["View Z Depth"])
    value_aov("RayDistance", camera.outputs["View Distance"])
    value_aov("Validity", validity.outputs[0])
    color_aov("GeomNormal", geometry.outputs["True Normal"])
    color_aov("ShadeNormal", geometry.outputs["Normal"])
    principled = next((node for node in nodes if node.type == "BSDF_PRINCIPLED"), None)
    if principled is None:
        rgb = nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
        albedo_socket = rgb.outputs[0]
    else:
        base = principled.inputs["Base Color"]
        albedo_socket = base.links[0].from_socket if base.is_linked else base
    color_aov("DiffuseAlbedo", albedo_socket)


def _load_material_asset(asset_root: Path, asset_id: str) -> Any:
    path = asset_root / asset_id / f"{asset_id}_2k.gltf"
    if not path.is_file():
        raise FileNotFoundError(f"locked material asset is missing: {path}")
    existing_objects = set(bpy.data.objects)
    existing_materials = set(bpy.data.materials)
    bpy.ops.import_scene.gltf(filepath=str(path))
    created_objects = [obj for obj in bpy.data.objects if obj not in existing_objects]
    created_materials = [mat for mat in bpy.data.materials if mat not in existing_materials]
    if not created_materials:
        raise RuntimeError(f"asset did not import a material: {path}")
    material = created_materials[0].copy()
    material.name = f"material.{asset_id}"
    material.use_fake_user = True
    for obj in created_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    _augment_material_aovs(material)
    return material


def _make_box(spec: ObjectSpec, material: Any) -> list[Any]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=spec.location)
    obj = bpy.context.object
    obj.name = spec.name
    obj.dimensions = spec.target_size
    obj.rotation_euler = tuple(math.radians(value) for value in spec.rotation_degrees)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = obj.modifiers.new(name="architectural_bevel", type="BEVEL")
    bevel.width = 0.025
    bevel.segments = 3
    obj.data.materials.append(material)
    _tag_object(obj, spec)
    return [obj]


def _world_bounds(objects: Sequence[Any]) -> tuple[np.ndarray, np.ndarray]:
    corners = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        local = np.asarray(obj.bound_box, dtype=np.float64)
        homogeneous = np.concatenate(
            [local, np.ones((len(local), 1), dtype=np.float64)], axis=1
        )
        world = np.asarray(obj.matrix_world, dtype=np.float64)
        corners.extend((homogeneous @ world.T)[:, :3])
    if not corners:
        raise RuntimeError("imported asset contains no mesh bounds")
    stacked = np.stack(corners)
    return stacked.min(axis=0), stacked.max(axis=0)


def _tag_object(obj: Any, spec: ObjectSpec) -> None:
    obj.pass_index = spec.object_id
    obj["benchmark_object_id"] = spec.object_id
    obj["benchmark_object_name"] = spec.name
    obj["benchmark_role"] = spec.role
    obj["benchmark_semantic_class"] = spec.semantic_class
    obj["benchmark_asset_id"] = spec.asset_id


def _import_model_asset(asset_root: Path, spec: ObjectSpec) -> list[Any]:
    path = asset_root / spec.asset_id / f"{spec.asset_id}_2k.gltf"
    if not path.is_file():
        raise FileNotFoundError(f"locked model asset is missing: {path}")
    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = [obj for obj in bpy.data.objects if obj not in existing and obj.type == "MESH"]
    if not imported:
        raise RuntimeError(f"asset did not import mesh geometry: {path}")
    parent = bpy.data.objects.new(f"{spec.name}.transform", None)
    bpy.context.scene.collection.objects.link(parent)
    for index, obj in enumerate(imported):
        world = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_world = world
        obj.name = f"{spec.name}.part{index:02d}"
        _tag_object(obj, spec)
        for material in obj.data.materials:
            if material is not None:
                _augment_material_aovs(material)
    lower, upper = _world_bounds(imported)
    dimensions = upper - lower
    valid_ratios = [
        target / actual
        for target, actual in zip(spec.target_size, dimensions, strict=True)
        if actual > 1e-9 and target > 0.0
    ]
    scale = min(valid_ratios)
    parent.scale = (scale, scale, scale)
    parent.rotation_euler = tuple(math.radians(value) for value in spec.rotation_degrees)
    bpy.context.view_layer.update()
    lower, upper = _world_bounds(imported)
    desired_center = np.asarray(
        [spec.location[0], spec.location[1], spec.location[2] + 0.5 * (upper[2] - lower[2])]
    )
    actual_center = 0.5 * (lower + upper)
    actual_center[2] = lower[2]
    desired_center[2] = spec.location[2]
    parent.location = tuple(np.asarray(parent.location) + desired_center - actual_center)
    bpy.context.view_layer.update()
    return imported


def _configure_world(asset_root: Path) -> None:
    world = bpy.data.worlds.new("kloofendal_overcast_puresky")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld")
    background = nodes.new("ShaderNodeBackground")
    background.inputs["Strength"].default_value = 0.65
    environment = nodes.new("ShaderNodeTexEnvironment")
    hdri = asset_root / "kloofendal_overcast_puresky" / "kloofendal_overcast_puresky_2k.exr"
    if not hdri.is_file():
        raise FileNotFoundError(f"locked HDRI is missing: {hdri}")
    environment.image = bpy.data.images.load(str(hdri), check_existing=True)
    world.node_tree.links.new(environment.outputs["Color"], background.inputs["Color"])
    world.node_tree.links.new(background.outputs["Background"], output.inputs["Surface"])


def _configure_lighting() -> None:
    """Add deterministic interior fill while retaining the HDRI environment."""
    for name, location, energy, size in (
        ("fill.front", (-0.65, -1.65, 2.72), 650.0, 3.2),
        ("fill.rear", (-0.70, 2.10, 2.72), 800.0, 3.0),
    ):
        data = bpy.data.lights.new(name=f"{name}.data", type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        data.color = (1.0, 0.96, 0.90)
        light = bpy.data.objects.new(name, data)
        light.location = location
        light.rotation_euler = (0.0, 0.0, 0.0)  # area lights emit along local -Z
        bpy.context.scene.collection.objects.link(light)


def _configure_device(scene: Any, device: str) -> list[str]:
    preferences = bpy.context.preferences.addons["cycles"].preferences
    if device == "CPU":
        scene.cycles.device = "CPU"
        return ["CPU"]
    preferences.compute_device_type = "OPTIX"
    preferences.get_devices()
    selected = []
    for candidate in preferences.devices:
        candidate.use = candidate.type == "OPTIX"
        if candidate.use:
            selected.append(candidate.name)
    if not selected:
        raise RuntimeError("OptiX was requested but Blender found no OptiX device")
    scene.cycles.device = "GPU"
    return selected


def configure_cycles(profile: str, device: str, seed: int) -> dict[str, object]:
    _require_bpy()
    device = validate_device(profile, device)
    settings = PROFILES[profile]
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if False else "CYCLES"
    scene.render.resolution_x = int(settings["width"])
    scene.render.resolution_y = int(settings["height"])
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.use_motion_blur = False
    scene.cycles.samples = int(settings["samples"])
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.seed = int(seed)
    scene.cycles.use_denoising = True
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.camera.data.dof.use_dof = False
    view_layer = bpy.context.view_layer
    view_layer.use_pass_z = True
    view_layer.use_pass_normal = True
    view_layer.use_pass_object_index = True
    view_layer.use_pass_diffuse_color = True
    view_layer.cycles.use_denoising = True
    for name, aov_type in (
        ("CameraDepth", "VALUE"),
        ("RayDistance", "VALUE"),
        ("Validity", "VALUE"),
        ("GeomNormal", "COLOR"),
        ("ShadeNormal", "COLOR"),
        ("DiffuseAlbedo", "COLOR"),
    ):
        if view_layer.aovs.get(name) is None:
            aov = view_layer.aovs.add()
            aov.name = name
            aov.type = aov_type
    devices = _configure_device(scene, device)
    return {"device": device, "devices": devices}


def build_blender_scene(
    scene_name: str,
    *,
    asset_root: Path,
    profile: str,
    device: str,
    seed: int,
    include_hidden: bool = True,
) -> dict[str, object]:
    """Build the metric L-room; context builds omit the hidden hypothesis."""
    _require_bpy()
    if scene_name not in _HIDDEN:
        raise ValueError(f"unknown scene: {scene_name}")
    _clear_scene()
    asset_root = Path(asset_root)
    floor_material = _load_material_asset(asset_root, "wood_floor")
    plaster_material = _load_material_asset(asset_root, "white_plaster_02")
    created: list[Any] = []
    specs = object_specs(scene_name)
    for spec in specs:
        if spec.role == "hidden" and not include_hidden:
            continue
        if spec.geometry_kind == "box":
            material = floor_material if spec.material_asset_id == "wood_floor" else plaster_material
            created.extend(_make_box(spec, material))
        else:
            created.extend(_import_model_asset(asset_root, spec))
    _configure_world(asset_root)
    _configure_lighting()
    camera_data = bpy.data.cameras.new("benchmark_camera")
    camera_object = bpy.data.objects.new("benchmark_camera", camera_data)
    bpy.context.scene.collection.objects.link(camera_object)
    bpy.context.scene.camera = camera_object
    renderer = configure_cycles(profile, device, seed)
    return {
        "scene_name": scene_name,
        "include_hidden": include_hidden,
        "mesh_objects": len([obj for obj in created if obj.type == "MESH"]),
        "renderer": renderer,
    }


def set_camera(camera: CameraSpec) -> None:
    _require_bpy()
    intrinsics, extrinsics = camera.matrices()
    camera_object = bpy.context.scene.camera
    camera_object.data.type = "PERSP"
    camera_object.data.sensor_fit = "HORIZONTAL"
    camera_object.data.sensor_width = 36.0
    camera_object.data.lens = 0.5 * camera_object.data.sensor_width / math.tan(
        math.radians(camera.fov_degrees) / 2.0
    )
    camera_object.matrix_world = Matrix(blender_matrix_from_opencv(extrinsics).tolist())
    bpy.context.scene.render.resolution_x = camera.width
    bpy.context.scene.render.resolution_y = camera.height
    camera_object["intrinsics"] = [float(value) for value in intrinsics.reshape(-1)]


def _setup_compositor_sidecars(base_path: Path) -> dict[str, Path]:
    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    render_layers = tree.nodes.new("CompositorNodeRLayers")
    outputs = {
        "depth": "CameraDepth",
        "ray_distance": "RayDistance",
        "geometric_normal": "GeomNormal",
        "shading_normal": "ShadeNormal",
        # IndexOB is categorical and deliberately unfiltered. A shader-valued
        # object-ID AOV is anti-aliased and creates nonexistent interpolated IDs.
        "object_id": "IndexOB",
        "albedo": "DiffuseAlbedo",
        "validity": "Validity",
    }
    paths = {}
    for label, socket_name in outputs.items():
        output = tree.nodes.new("CompositorNodeOutputFile")
        output.base_path = str(base_path)
        output.file_slots[0].path = f"{label}_"
        output.format.file_format = "OPEN_EXR"
        output.format.color_depth = "32"
        output.format.color_mode = "RGB" if "normal" in label or label == "albedo" else "BW"
        tree.links.new(render_layers.outputs[socket_name], output.inputs[0])
        paths[label] = base_path / f"{label}_0001.exr"
    return paths


def _read_exr(path: Path, *, color: bool) -> np.ndarray:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        width, height = image.size
        pixels = np.asarray(image.pixels[:], dtype=np.float32).reshape(height, width, 4)
        pixels = np.flipud(pixels)
        return pixels[:, :, :3].copy() if color else pixels[:, :, 0].copy()
    finally:
        bpy.data.images.remove(image)


def normalize_valid_vectors(vectors: np.ndarray, validity: np.ndarray) -> np.ndarray:
    """Normalize vector AOVs after Cycles' edge anti-aliasing."""
    vectors = np.asarray(vectors, dtype=np.float32).copy()
    validity = np.asarray(validity, dtype=bool)
    lengths = np.linalg.norm(vectors, axis=-1)
    usable = validity & (lengths > 1e-12)
    vectors[usable] /= lengths[usable, None]
    vectors[~usable] = 0.0
    return vectors


def derive_validity(depth: np.ndarray, object_ids: np.ndarray) -> np.ndarray:
    """Canonical mask shared by metric depth and stable instance IDs."""
    return (np.asarray(depth) > 0.0) & (np.asarray(object_ids) > 0)


def camera_depth_to_ray_distance(
    depth: np.ndarray, intrinsics: np.ndarray
) -> np.ndarray:
    """Convert +z camera depth to nominal pixel-center Euclidean distance."""
    depth = np.asarray(depth, dtype=np.float32)
    intrinsics = np.asarray(intrinsics, dtype=np.float64)
    height, width = depth.shape
    xs, ys = np.meshgrid(np.arange(width), np.arange(height))
    factor = np.sqrt(
        1.0
        + ((xs - intrinsics[0, 2]) / intrinsics[0, 0]) ** 2
        + ((ys - intrinsics[1, 2]) / intrinsics[1, 1]) ** 2
    )
    return (depth * factor).astype(np.float32)


def render_views(
    output_root: Path,
    cameras: Sequence[CameraSpec],
    *,
    relative_to: Path,
) -> list[dict[str, object]]:
    """Render beauty, multilayer EXR, and lossless numeric supervision."""
    _require_bpy()
    output_root = Path(output_root)
    for layer in (
        "rgb", "exr", "depth", "ray_distance", "geometric_normal",
        "shading_normal", "object_id", "albedo", "validity",
    ):
        (output_root / layer).mkdir(parents=True, exist_ok=True)
    records = []
    scene = bpy.context.scene
    for index, camera in enumerate(cameras):
        set_camera(camera)
        intrinsics, extrinsics = camera.matrices()
        scratch = output_root / f".passes-{index:04d}"
        scratch.mkdir()
        sidecars = _setup_compositor_sidecars(scratch)
        exr_path = output_root / "exr" / f"{index:04d}.exr"
        png_path = output_root / "rgb" / f"{index:04d}.png"
        scene.frame_set(1)
        scene.render.filepath = str(exr_path)
        scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
        scene.render.image_settings.color_depth = "32"
        scene.render.image_settings.exr_codec = "ZIP"
        bpy.ops.render.render(write_still=True)
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.render.image_settings.color_depth = "8"
        bpy.data.images["Render Result"].save_render(str(png_path), scene=scene)
        arrays = {}
        for label, sidecar in sidecars.items():
            color = label in {"geometric_normal", "shading_normal", "albedo"}
            array = _read_exr(sidecar, color=color)
            if label == "object_id":
                array = np.rint(array).astype(np.int32)
            elif label == "validity":
                array = array > 0.5
            arrays[label] = array
        arrays["ray_distance"] = camera_depth_to_ray_distance(
            arrays["depth"], intrinsics
        )
        arrays["validity"] = derive_validity(arrays["depth"], arrays["object_id"])
        for label in ("geometric_normal", "shading_normal"):
            arrays[label] = normalize_valid_vectors(arrays[label], arrays["validity"])
        data_paths = {}
        for label, array in arrays.items():
            npy_path = output_root / label / f"{index:04d}.npy"
            np.save(npy_path, array)
            data_paths[label] = str(npy_path.relative_to(relative_to))
        shutil.rmtree(scratch)
        records.append(
            {
                "index": index,
                "rgb": str(png_path.relative_to(relative_to)),
                "exr": str(exr_path.relative_to(relative_to)),
                **data_paths,
                "intrinsics": intrinsics.tolist(),
                "world_to_camera": extrinsics.tolist(),
            }
        )
    return records


def hardlink_render_tree(source: Path, destination: Path) -> None:
    source = Path(source)
    destination = Path(destination)
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(path, target)


def evaluated_geometry_and_surface(
    scene_name: str,
    *,
    seed: int,
    total_samples: int = 250_000,
    minimum_per_object: int = 2_048,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    _require_bpy()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    vertices_parts: list[np.ndarray] = []
    triangle_parts: list[np.ndarray] = []
    id_parts: list[np.ndarray] = []
    vertex_offset = 0
    role_by_id = {spec.object_id: spec.role for spec in object_specs(scene_name)}
    for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name):
        if obj.type != "MESH" or "benchmark_object_id" not in obj:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
        try:
            mesh.calc_loop_triangles()
            world = np.asarray(evaluated.matrix_world, dtype=np.float64)
            local_vertices = np.asarray([vertex.co[:] for vertex in mesh.vertices], dtype=np.float64)
            homogeneous = np.concatenate(
                [local_vertices, np.ones((len(local_vertices), 1), dtype=np.float64)], axis=1
            )
            world_vertices = (homogeneous @ world.T)[:, :3]
            triangles = np.asarray(
                [triangle.vertices[:] for triangle in mesh.loop_triangles], dtype=np.int64
            )
            if triangles.size == 0:
                continue
            vertices_parts.append(world_vertices)
            triangle_parts.append(triangles + vertex_offset)
            object_id = int(obj["benchmark_object_id"])
            id_parts.append(np.full(len(triangles), object_id, dtype=np.int32))
            vertex_offset += len(world_vertices)
        finally:
            evaluated.to_mesh_clear()
    if not triangle_parts:
        raise RuntimeError("scene contains no evaluated triangles")
    vertices = np.concatenate(vertices_parts).astype(np.float32)
    triangles = np.concatenate(triangle_parts).astype(np.int32)
    triangle_object_ids = np.concatenate(id_parts)
    points, normals, object_ids = sample_triangle_surface(
        vertices,
        triangles,
        triangle_object_ids,
        total=total_samples,
        minimum=minimum_per_object,
        seed=seed,
    )
    hidden = np.asarray([role_by_id[int(value)] == "hidden" for value in object_ids])
    geometry = {
        "vertices": vertices,
        "triangles": triangles,
        "triangle_object_ids": triangle_object_ids,
    }
    surface = {
        "points": points,
        "normals": normals,
        "object_ids": object_ids,
        "roles": hidden.astype(np.uint8),
        "hidden_hypothesis": hidden,
    }
    return geometry, surface


def label_surface_visibility(
    surface: dict[str, np.ndarray],
    *,
    context_root: Path,
    target_root: Path,
    context_cameras: Sequence[CameraSpec],
    target_cameras: Sequence[CameraSpec],
) -> dict[str, float]:
    points = surface["points"]
    object_ids = surface["object_ids"]
    scene_scale = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))

    def buffers(root: Path, cameras: Sequence[CameraSpec]):
        for index, camera in enumerate(cameras):
            intrinsics, extrinsics = camera.matrices()
            yield (
                intrinsics,
                extrinsics,
                np.load(root / "depth" / f"{index:04d}.npy"),
                np.load(root / "object_id" / f"{index:04d}.npy"),
            )

    context_visible = visibility_from_views(
        points,
        object_ids,
        buffers(Path(context_root), context_cameras),
        scene_scale=scene_scale,
    )
    target_visible = visibility_from_views(
        points,
        object_ids,
        buffers(Path(target_root), target_cameras),
        scene_scale=scene_scale,
    )
    target_only = target_visible & ~context_visible
    hidden = surface["hidden_hypothesis"].astype(bool)
    surface["context_visible"] = context_visible
    surface["target_visible"] = target_visible
    surface["target_only_visible"] = target_only
    surface["new_in_target"] = target_only  # v1 probe compatibility alias
    hidden_count = max(int(hidden.sum()), 1)
    target_count = max(int(target_visible.sum()), 1)
    return {
        "hidden_object_context_fraction": float((hidden & context_visible).sum() / hidden_count),
        "hidden_object_target_fraction": float((hidden & target_visible).sum() / hidden_count),
        "target_new_surface_fraction": float(target_only.sum() / target_count),
        "target_only_surface_fraction": float((hidden & target_only).sum() / hidden_count),
    }
