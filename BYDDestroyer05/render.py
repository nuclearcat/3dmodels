"""Render the exported GLB with Blender in background mode (called by check_views.py)."""

import json
import sys
from pathlib import Path
from math import sin, cos, radians
import bpy
from mathutils import Matrix, Vector

root = Path(__file__).resolve().parent
job = json.loads(Path(sys.argv[-1]).read_text())
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=str(root / "Destroyer_05.glb"))
scene.render.engine = "CYCLES"
scene.cycles.samples = job.get("samples", 192)
scene.cycles.adaptive_threshold = 0.035
scene.cycles.use_denoising = True
scene.cycles.transparent_max_bounces = 8
scene.render.resolution_x, scene.render.resolution_y = 1254, 836
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "AgX"
scene.world = bpy.data.worlds.new("Soft studio")
scene.world.use_nodes = True
background = scene.world.node_tree.nodes["Background"]
background.inputs["Color"].default_value = (0.62, 0.68, 0.75, 1)
background.inputs["Strength"].default_value = 0.32
studio = bpy.data.collections.new("Studio and cameras")
scene.collection.children.link(studio)


def softbox(name, pos, target, power, length, width):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "RECTANGLE"
    data.energy = power
    data.size = length
    data.size_y = width
    obj = bpy.data.objects.new(name, data)
    studio.objects.link(obj)
    obj.location = pos
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


softbox("Roof strip", (1.1, 0.4, 5.4), (1.2, 0, 0), 750, 6, 1.3)
softbox("Driver side strip", (1.8, -4.3, 2.8), (1.4, 0, 0.7), 320, 5.2, 0.62)
softbox("Passenger side strip", (2.8, 4.2, 2.9), (1.4, 0, 0.7), 450, 5, 1.2)
softbox("Nose softbox", (-4, -1.1, 3.3), (0, 0, 0.5), 260, 3, 2.4)

bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.0015))
floor = bpy.context.object
floor.name = "Studio floor"
for collection in list(floor.users_collection):
    collection.objects.unlink(floor)
studio.objects.link(floor)
mat = bpy.data.materials.new("Studio floor")
mat.diffuse_color = (0.48, 0.52, 0.54, 1)
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.48, 0.52, 0.54, 1)
bsdf.inputs["Roughness"].default_value = 0.82
floor.data.materials.append(mat)
labels = {
    "hero": "Studio perspective",
    "lamp_detail": "Headlamp detail",
    "grille_detail": "Grille detail",
    "side": "Side elevation",
    "front": "Front elevation",
    "rear": "Rear elevation",
    "quarter": "Front three-quarter",
    "rear_quarter": "Left rear three-quarter",
    "right_rear_quarter": "Right rear three-quarter",
}
frames = [
    "hero",
    "side",
    "front",
    "rear",
    "quarter",
    "rear_quarter",
    "right_rear_quarter",
    "grille_detail",
    "lamp_detail",
]
# A dedicated collection toggles the mirrors together while editing the rear body.
mirrors_collection = bpy.data.collections.new("Door mirrors")
scene.collection.children.link(mirrors_collection)
mirror_root = bpy.data.objects["Exterior mirrors"]
for obj in [mirror_root, *mirror_root.children]:
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    mirrors_collection.objects.link(obj)
for name, params in job["views"].items():
    data = bpy.data.cameras.new(labels[name])
    cam = bpy.data.objects.new(labels[name], data)
    studio.objects.link(cam)
    scene.camera = cam
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = 36
    cam.data.clip_end = 250
    frame = frames.index(name) + 1
    scene.frame_set(frame)
    for s in (-1, 1):
        wheel = bpy.data.objects[f"Wheel assembly 0 {s}"]
        wheel.rotation_euler.z = radians(job.get("steering", {}).get(name, 0))
        wheel.keyframe_insert(data_path="rotation_euler", frame=frame)
    yaw, pitch, roll, dist, scale, dx, dy = params
    y, p, r = map(radians, [yaw, pitch, roll])
    right = Vector((cos(y), sin(y), 0))
    back = Vector((sin(y) * cos(p), -cos(y) * cos(p), sin(p)))
    up = back.cross(right)
    right, up = right * cos(r) + up * sin(r), up * cos(r) - right * sin(r)
    cam.rotation_euler = Matrix([right, up, back]).transposed().to_euler()
    cam.location = Vector((1.360, 0, 0.750)) + back * dist / 1000
    cam.data.lens = dist * scale * 36 / 1254
    cam.data.shift_x = -dx / 1254
    cam.data.shift_y = dy / 1254
    # The camera-matched plates use alpha for the exact object outline. The
    # presentation camera includes the studio floor and its contact shadow.
    marker = scene.timeline_markers.new(labels[name], frame=frame)
    marker.camera = cam
    scene.camera = cam
    is_hero = name == "hero"
    floor.visible_camera = is_hero
    scene.render.film_transparent = not is_hero
    scene.render.filepath = str(Path(job["out"]) / (name + ".png"))
    bpy.ops.render.render(write_still=True)
    if name == "rear":
        mirrors_collection.hide_render = True
        scene.render.filepath = str(Path(job["out"]) / "rear_without_mirrors.png")
        bpy.ops.render.render(write_still=True)
        mirrors_collection.hide_render = False

if job.get("save_scene"):
    scene.frame_start = 1
    scene.frame_end = len(frames)
    scene.frame_set(1)
    scene.camera = bpy.data.objects[labels["hero"]]
    scene.render.film_transparent = False
    floor.visible_camera = True
    scene.render.filepath = "//Destroyer_05_render.png"
    scene.render.image_settings.color_mode = "RGB"
    # Open on the studio view with the car centred for both camera and orbit navigation.
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.region_3d.view_perspective = "CAMERA"
                space.region_3d.view_distance = 6.2
                space.region_3d.view_location = (1.36, 0, 0.75)
                space.region_3d.view_rotation = scene.camera.rotation_euler.to_quaternion()
                space.overlay.show_overlays = False
                space.shading.color_type = "MATERIAL"
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = None
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "Destroyer_05.blend"), compress=True)
