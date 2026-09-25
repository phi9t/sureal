"""Test-only Blender entrypoint that constructs a complete draft scene."""

from pathlib import Path
import sys


PIPELINE = Path(__file__).resolve().parents[1] / "pipeline"
sys.path.insert(0, str(PIPELINE))

from scene import build_blender_scene  # noqa: E402
import bpy  # noqa: E402


asset_root = Path(sys.argv[sys.argv.index("--") + 1])
sofa = asset_root / "Sofa_01" / "Sofa_01_2k.gltf"
assert sofa.is_file()
build_blender_scene(
    "scene_a",
    asset_root=asset_root,
    profile="draft",
    device="CPU",
    seed=20260925,
    include_hidden=False,
)
assert sofa.is_file(), "scene reset removed the external asset cache"
result = build_blender_scene(
    "scene_a",
    asset_root=asset_root,
    profile="draft",
    device="CPU",
    seed=20260925,
    include_hidden=True,
)
area_lights = sorted(
    (obj for obj in bpy.context.scene.objects if obj.type == "LIGHT"),
    key=lambda obj: obj.name,
)
assert [light.name for light in area_lights] == ["fill.front", "fill.rear"]
assert all(light.data.type == "AREA" and light.data.energy > 0 for light in area_lights)
view_layer = bpy.context.view_layer
assert view_layer.aovs.get("CameraDepth") is not None
for material in bpy.data.materials:
    if material.use_nodes and material.node_tree.nodes.get("SurfloAOV.Validity") is not None:
        assert material.node_tree.nodes.get("SurfloAOV.CameraDepth") is not None
print(f"SCENE_SMOKE_OK mesh_objects={result['mesh_objects']}")
