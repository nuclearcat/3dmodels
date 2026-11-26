"""Fit a pinhole camera to each gallery view and compare the exported GLB.
Optionally pass a directory of gallery photos to generate local comparison sheets.
"""

import argparse
import json
import subprocess
import tempfile
import struct
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SIZE = (1254, 836)
# Photo coordinates measured at half resolution. Boxes include the tyres.
# Frontal widths use the fenders, omitting the separately checked mirrors.
VIEWS = {
    "side": dict(
        file="09.webp",
        box=[61, 236, 1187, 599],
        yaw=0,
        hubs=[[286, 523], [944, 520]],
        marks={
            "front handle": (619, 386),
            "rear handle": (856, 379),
            "B pillar foot": (653, 347),
            "front wheel arch": (287, 424),
            "rear wheel arch": (944, 419),
            "side glass tail": (978, 297),
            "mirror cap": (449, 322),
        },
    ),
    "front": dict(
        file="03.jpg",
        box=[308, 175, 946, 665],
        yaw=-90,
        marks={
            "windscreen foot": (627, 312),
            "bonnet leading edge": (627, 420),
            "bottom of grille": (375, 547),
            "plate centre": (627, 539),
            "mirror outside": (955, 306),
        },
    ),
    "rear": dict(
        file="10.jpg",
        box=[307, 163, 947, 676],
        yaw=90,
        marks={
            "rear glass foot": (627, 255),
            "deck lip": (627, 286),
            "tail light bar": (627, 338),
            "plate centre": (625, 504),
            "reflector": (440, 530),
        },
    ),
    "quarter": dict(
        file="00.jpg",
        box=[154, 201, 1106, 631],
        yaw=-48,
        steer=-29,
        hubs=[[642, 541], [1033, 518]],
        marks={
            "plate centre": (282, 511),
            "mirror cap": (779, 303),
            "front handle": (864, 375),
            "rear handle": (991, 368),
        },
    ),
    "rear_quarter": dict(
        file="07.jpg",
        box=[153, 197, 1103, 643],
        yaw=55,
        steer=24,
        hubs=[[227, 519], [551, 545]],
        marks={
            "plate centre": (948, 489),
            "tail lamp tip": (653, 357),
            "mirror cap": (278, 305),
            "front handle": (370, 378),
            "rear handle": (499, 369),
        },
    ),
    "right_rear_quarter": dict(
        file="11.jpg",
        box=[154, 189, 1106, 643],
        yaw=120,
        steer=-25,
        hubs=[[1034, 522], [717, 547]],
        marks={
            "plate centre": (309, 489),
            "mirror cap": (979, 303),
            "front handle": (891, 373),
            "rear handle": (768, 365),
            "tail lamp tip": (624, 354),
        },
    ),
}

GALLERY_FILES = {
    "right_rear_quarter": "3b64e65a56a09816ea69a1a665dc8b812508x0.jpg",
    "side": "e01f10c7e91c977905c8f66dc79815c52508x0.webp",
    "front": "bc29db0365504994c4b978c5825e43e82508x0.jpg",
    "rear": "d2e6aa1ee547b6d4b9a927a90bde36512508x0.jpg",
    "quarter": "e13c6b8cdec3110a288bde30ab0726262508x0.jpg",
    "rear_quarter": "fea7b89b4cde73da63f3ff7d76e0fefc2508x0.jpg",
}
# Visible upper silhouette, manually sampled at fixed image columns in the profile.
# The background van overlaps the bonnet between x=275 and 350.
SIDE_OUTLINE = [
    (100, 401),
    (150, 378),
    (200, 365),
    (250, 356),
    (400, 319),
    (450, 293),
    (500, 270),
    (550, 253),
    (600, 245),
    (650, 238),
    (700, 236),
    (750, 237),
    (800, 240),
    (850, 245),
    (900, 255),
    (950, 267),
    (1000, 280),
    (1050, 297),
    (1100, 312),
    (1150, 324),
]


def read_model():
    with (ROOT / "Destroyer_05.glb").open("rb") as f:
        magic, version, total, jlen, jtype = struct.unpack("<4sIIII", f.read(20))
        assert magic == b"glTF" and version == 2 and total == (ROOT / "Destroyer_05.glb").stat().st_size
        doc = json.loads(f.read(jlen))
        size, tag = struct.unpack("<I4s", f.read(8))
        blob = f.read()
        assert size == len(blob) and tag == b"BIN\0"

    def arr(idx):
        a = doc["accessors"][idx]
        v = doc["bufferViews"][a["bufferView"]]
        data = np.frombuffer(
            blob[v["byteOffset"] : v["byteOffset"] + v["byteLength"]],
            dtype="<u4" if a["componentType"] == 5125 else "<f4",
        )
        return data.reshape(-1, 3) if a["type"] == "VEC3" else data

    parts = {}
    # This exporter groups the wheels at their hubs so they can be steered in a viewer.
    origins = {
        n["mesh"]: np.array(group.get("translation", [0, 0, 0]))
        for group in doc["nodes"]
        if "children" in group
        for child in group["children"]
        for n in [doc["nodes"][child]]
    }
    owners = {
        doc["nodes"][child]["mesh"]: group["name"]
        for group in doc["nodes"]
        if "children" in group
        for child in group["children"]
    }
    for index, mesh in enumerate(doc["meshes"]):
        p = mesh["primitives"][0]
        att = p["attributes"]
        xyz = (arr(att["POSITION"]) + origins[index])[:, [0, 2, 1]] * [1000, -1000, 1000]
        normals = arr(att["NORMAL"])[:, [0, 2, 1]] * [1, -1, 1]
        parts[mesh["name"]] = (xyz, normals, arr(p["indices"]), p["material"], owners[index])
    return parts, doc["materials"]


def basis(params):
    yaw, pitch, roll, dist, scale, dx, dy = params
    y, p, r = np.radians([yaw, pitch, roll])
    right = np.array([np.cos(y), np.sin(y), 0.0])
    back = np.array([np.sin(y) * np.cos(p), -np.cos(y) * np.cos(p), np.sin(p)])
    up = np.cross(back, right)
    right, up = right * np.cos(r) + up * np.sin(r), up * np.cos(r) - right * np.sin(r)
    eye = np.array([1360.0, 0, 750]) + dist * back
    return right, up, back, eye


def project(xyz, params):
    right, up, back, eye = basis(params)
    rel = xyz - eye
    d = rel @ (-back)
    focal = params[3] * params[4]
    return np.column_stack(
        [627 + params[5] + focal * (rel @ right) / d, 418 + params[6] - focal * (rel @ up) / d]
    )


def steer_points(xyz, side, angle):
    q = np.radians(angle)
    cs, sn = np.cos(q), np.sin(q)
    pivot = np.array([0, side * 790, 321])
    return (xyz - pivot) @ np.array([[cs, sn, 0], [-sn, cs, 0], [0, 0, 1]]) + pivot


def bounds(parts, angle=0):
    # Convex hulls retain the exact projected extrema with far fewer vertices.
    from scipy.spatial import ConvexHull

    def hull(names):
        groups = []
        for k, p in parts.items():
            if not names(k):
                continue
            xyz = p[0]
            if angle and p[4].startswith("Wheel assembly 0 "):
                xyz = steer_points(xyz, int(p[4].split()[-1]), angle)
            groups.append(xyz)
        xyz = np.concatenate(groups)
        return xyz[ConvexHull(xyz).vertices]

    return hull(lambda k: True), hull(lambda k: "mirror" not in k.lower())


def fit(view, env, bare):
    yaw = view["yaw"]
    headon = abs(yaw) == 90
    initial = [yaw, 1.0, 0.0, 16000.0, 0.30 if headon else 0.24, 0.0, 0.0]
    photo = np.array(view["box"])
    side = 1 if yaw > 90 else -1
    hubs = np.array([[0, side * 890.0, 321], [2718, side * 895.0, 321]])
    hubs[0] = steer_points(hubs[0], side, view.get("steer", 0))

    def residual(par):
        outline = project(bare if headon else env, par)
        a = outline.min(0)
        b = outline.max(0)
        errors = list(np.r_[a, b] - photo)
        if "hubs" in view:
            errors.extend((project(hubs, par) - view["hubs"]).ravel())
        # Low camera in the dealership gallery. The plates are level left to right.
        errors.extend([(par[3] - 16000) / 6000, par[1] / 2, par[2] / 0.7])
        if "steer" in view:
            # The rim diameters distinguish lens distance from a change in yaw.
            for axle, wheel_y, diameter in [
                (0, side * 890, 139 if yaw < 0 else 115),
                (2718, side * 895, 116 if yaw < 0 else 137),
            ]:
                rim = project(np.array([[axle, wheel_y, 321 - 226], [axle, wheel_y, 321 + 226]]), par)
                errors.append(abs(rim[1, 1] - rim[0, 1]) - diameter)
        if "steer" in view:
            mount = [3783, 0, 505] if yaw > 0 else [-982.65, 0, 388]
            plate = project(np.array([mount]), par)[0]
            errors.extend((plate - view["marks"]["plate centre"]) * 0.9)
        if yaw == 90:
            contact = project(np.array([[2718, -795, 0], [2718, 795, 0]]), par)
            errors.extend(((contact - np.array([[355, 674], [897, 673]])) * 0.55).ravel())
            plate_edges = project(np.array([[3783, -220, 505], [3783, 220, 505]]), par)
            errors.extend(((plate_edges - np.array([[542, 504], [705, 503]])) * 1.1).ravel())
            # The distant mirror tips constrain focal distance separately from the near body envelope.
            tips = project(np.array([[680, -997, 1065], [680, 997, 1065]]), par)
            errors.extend((tips[:, 0] - [320, 928]) * 0.65)
        if headon:
            errors.extend([(par[0] - yaw) / 0.15, par[1] / 0.7])
        return errors

    lim = 1.7 if headon else 20
    result = least_squares(
        residual,
        initial,
        bounds=([yaw - lim, -7, -3, 6500, 0.12, -210, -170], [yaw + lim, 9, 3, 65000, 0.65, 210, 170]),
        x_scale="jac",
    )
    return result.x


def center(parts, name):
    pts = parts[name][0]
    return (pts.min(0) + pts.max(0)) / 2


def landmark_points(parts, label):
    def pick(name, dim, value):
        xyz = parts[name][0]
        return xyz[np.argmin(abs(xyz[:, dim] - value))]

    s = 1 if label == "right_rear_quarter" else -1
    mirror = parts[f"Painted mirror cap {s}"][0]
    arch = lambda c: pick("Rolled arch " + str((c, -1)), 0, c)
    plate = lambda f: center(parts, "Registration plate " + str(f))
    if label in ("side", "quarter", "rear_quarter", "right_rear_quarter"):
        marks = {
            "front handle": center(parts, f"Pull handle (1380, {s})"),
            "rear handle": center(parts, f"Pull handle (2352, {s})"),
            "B pillar foot": center(parts, "B pillar -1"),
            "tail lamp tip": pick(f"Tail lens return {s}", 0, 3279),
            "front wheel arch": arch(0),
            "rear wheel arch": arch(2718),
            "side glass tail": parts["Side glass -1"][0][-1],
            "mirror cap": mirror[np.argmax(mirror[:, 2])],
            "plate centre": plate("rear" not in label),
        }
        p = parts["B pillar -1"][0]
        marks["B pillar foot"] = (p[0] + p[1]) / 2
        return marks

    def edge(name, x):
        xyz = parts[name][0]
        near = xyz[abs(xyz[:, 1]) < 4]
        return near[np.argmin(near[:, 0]) if x == "min" else np.argmax(near[:, 0])]

    if label == "front":
        lower = parts["Offset silver blade (4, 1)"][0]
        return {
            "windscreen foot": edge("Windscreen", "min"),
            "bonnet leading edge": edge("Chrome bonnet leading edge", "min"),
            "bottom of grille": lower[np.argmax(lower[:, 1])],
            "plate centre": plate(True),
            "mirror outside": mirror[np.argmin(mirror[:, 1])],
        }
    return {
        "rear glass foot": edge("Rear screen", "max"),
        "deck lip": parts["Rear bumper"][0][np.argmax(parts["Rear bumper"][0][:, 2])],
        "tail light bar": edge("Tail guide highlight", "max"),
        "plate centre": plate(False),
        "reflector": center(parts, "Rear reflector -1"),
    }


DETAIL_FILES = {
    "grille_detail": ("658147ab1c148e3776f259d89ca7ecbf2508x0.jpg", "06.jpg"),
    "lamp_detail": ("3d2842e7bbbc9ba1bf9276619561ed9b2508x0.webp", "05.webp"),
}


def front_features(parts):
    """Named physical ends of the silver strips, cover, optics and calibration targets."""
    points = {}
    plate = parts["Registration plate True"][0]
    for name, axis, op in [
        ("plate left", 1, max),
        ("plate right", 1, min),
        ("plate top", 2, max),
        ("plate bottom", 2, min),
    ]:
        boundary = op(plate[:, axis])
        points[name] = plate[np.isclose(plate[:, axis], boundary, atol=0.01)].mean(0)
    windshield = parts["Windscreen"][0]
    middle = windshield[np.abs(windshield[:, 1]) < 4]
    points["windscreen foot"] = middle[middle[:, 0].argmin()]
    for side, label in [(-1, "right"), (1, "left")]:
        shell = parts[f"Headlamp recessed black mask {side}"][0]
        points[label + " inner top"] = shell[8]
        points[label + " inner bottom"] = shell[0]
        points[label + " wing tip"] = shell[-1]
        guide = parts[f"Swept daytime running light {side}"][0]
        points[label + " diffuser start"] = guide[:9].mean(0)
        points[label + " diffuser tip"] = guide[-9:].mean(0)
        for name, key in [
            ("reflector", "Inboard faceted reflector"),
            ("projector", "Outboard projector"),
        ]:
            points[f"{label} {name}"] = center(parts, f"{key} {side} optical face")
        for i in range(5):
            for kind, key in [("main", "Main silver blade"), ("offset", "Offset silver blade")]:
                xyz = parts[f"{key} {(i,side)}"][0]
                # The last cross-section is the outboard end; vertices 2/3 form its silver face.
                points[f"{label} {kind} {i+1}"] = xyz[-4:-2].mean(0)
                points[f"{label} {kind} {i+1} start"] = xyz[2:4].mean(0)
    return points


def fit_front_details(parts):
    features = front_features(parts)
    # Fit each close-up to the surrounding trim. Keep the optical centres and most
    # louvre tips out of the calibration so their residuals check the new geometry.
    controls = {
        "grille_detail": {
            "plate left": (438, 579),
            "plate right": (826, 579),
            "plate top": (632, 517),
            "plate bottom": (632, 640),
            "windscreen foot": (627, 68),
            "left inner top": (202, 286),
            "right inner top": (1058, 285),
        },
        "lamp_detail": {
            "right inner top": (427, 355),
            "right inner bottom": (351, 510),
            "right diffuser tip": (849, 269),
            "right main 1": (379, 578),
            "right offset 1": (616, 593),
            "right offset 3": (662, 739),
            "right offset 1 start": (199, 617),
        },
    }
    checks = {
        "grille_detail": {},
        "lamp_detail": {
            "right reflector": (551, 396),
            "right projector": (729, 353),
            "right diffuser start": (392, 480),
            "right main 2": (380, 662),
            "right main 3": (409, 744),
            "right offset 2": (638, 667),
        },
    }
    # Traced at 1,254 x 836 pixels. The plate hides the inboard ends of the lower two rows.
    for label, main, offset, starts in [
        (
            "left",
            [(216, 408), (214, 454), (200, 499), (185, 546), (174, 589)],
            [(94, 419), (81, 463), (69, 505), (56, 547), (47, 590)],
            [(305, 430), (293, 474), (277, 518), (264, 562), (252, 606)],
        ),
        (
            "right",
            [(1044, 406), (1047, 452), (1060, 498), (1074, 544), (1087, 588)],
            [(1167, 416), (1180, 459), (1194, 502), (1206, 545), (1214, 587)],
            [(953, 427), (969, 471), (983, 516), (999, 560), (1011, 605)],
        ),
    ]:
        for i in range(5):
            checks["grille_detail"][f"{label} main {i+1}"] = main[i]
            checks["grille_detail"][f"{label} offset {i+1}"] = offset[i]
            checks["grille_detail"][f"{label} offset {i+1} start"] = starts[i]
    cameras = {}
    measurements = {}
    for label, marks in controls.items():
        xyz = np.array([features[key] for key in marks])
        target = np.array(list(marks.values()))
        is_lamp = label == "lamp_detail"
        start = [
            -74 if is_lamp else -90,
            7 if is_lamp else 3,
            0,
            11500,
            1.35 if is_lamp else 0.7,
            -630 if is_lamp else 0,
            -20,
        ]

        def residual(par):
            errors = (project(xyz, par) - target).ravel()
            return np.r_[errors, (par[3] - 11500) / 3000, par[2] / 1.5]

        sol = least_squares(
            residual,
            start,
            x_scale="jac",
            bounds=(
                [-110, -12, -6, 2950 if is_lamp else 4400, 0.25, -3600, -1500],
                [-42, 24, 6, 50000, 3.4, 1500, 1500],
            ),
        )
        cameras[label] = sol.x.tolist()
        measured = {}
        for key, pt in checks[label].items():
            xy = project(features[key][None, :], sol.x)[0]
            measured[key] = dict(
                photo=list(pt),
                model=xy.round(1).tolist(),
                error_px=round(float(np.linalg.norm(xy - pt)), 1),
            )
        measurements[label] = dict(camera=cameras[label], controls=marks, landmarks=measured)
    return cameras, measurements


def load_photo(path):
    im = Image.open(path)
    return im.convert("RGB").resize(SIZE, Image.Resampling.LANCZOS)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "photos", nargs="?", type=Path, help="optional local gallery photos for comparison sheets"
    )
    ap.add_argument("--blender", default="blender")
    ap.add_argument("--samples", type=int, default=256)
    args = ap.parse_args()
    parts, _ = read_model()
    envelopes = {k: bounds(parts, v.get("steer", 0)) for k, v in VIEWS.items()}
    cameras = {key: fit(view, *envelopes[key]).tolist() for key, view in VIEWS.items()}
    detail_cameras, detail_metrics = fit_front_details(parts)
    cameras = detail_cameras | cameras
    cameras["hero"] = [-44, 7.3, 0, 12800, 0.253, 9, -6]
    scratch = tempfile.TemporaryDirectory()
    photo_paths = {}
    comparison_dir = ROOT.parent / ".local" / ROOT.name
    if args.photos:
        reference_names = {label: (GALLERY_FILES[label], view["file"]) for label, view in VIEWS.items()}
        for label, (original, alias) in (reference_names | DETAIL_FILES).items():
            reference = args.photos / original
            if not reference.is_file():
                reference = args.photos / alias
            if not reference.is_file():
                ap.error(f"Missing reference photograph: {original}")
            photo_paths[label] = reference
        comparison_dir.mkdir(parents=True, exist_ok=True)
    job = Path(scratch.name) / "cameras.json"
    job.write_text(
        json.dumps(
            dict(
                views=cameras,
                save_scene=True,
                steering={k: v.get("steer", 0) for k, v in VIEWS.items()},
                out=scratch.name,
                samples=args.samples,
            )
        )
    )
    subprocess.run(
        [args.blender, "-b", "--python-exit-code", "1", "-P", str(ROOT / "render.py"), "--", str(job)],
        check=True,
    )

    out = ROOT / "checks"
    out.mkdir(exist_ok=True)
    nonmirror = [p[0] for k, p in parts.items() if "mirror" not in k.lower()]
    overall = [p[0] for p in parts.values()]
    body_size = np.ptp(np.concatenate(nonmirror), axis=0)
    all_size = np.ptp(np.concatenate(overall), axis=0)
    hubs = [center(parts, "Wheel centre " + str((x, -1))) for x in (0, 2718)]
    wheelbase = hubs[1][0] - hubs[0][0]
    assert np.allclose(body_size, [4780, 1837, 1495], atol=0.05)
    assert abs(wheelbase - 2718) < 0.05
    results = {
        "dimensions_mm": dict(
            length=round(body_size[0], 3),
            width=round(body_size[1], 3),
            height=round(body_size[2], 3),
            width_with_mirrors=round(all_size[1], 3),
            wheelbase=round(wheelbase, 3),
        ),
        "photo_resolution": SIZE,
        "views": {},
    }

    for label, view in VIEWS.items():
        camera = np.array(cameras[label])
        rgba = Image.open(Path(scratch.name) / (label + ".png")).convert("RGBA")
        mask = (np.array(rgba.getchannel("A")) > 75).astype(np.uint8) * 255
        render = Image.new("RGB", SIZE, "#e4e5e2")
        render.paste(rgba, mask=rgba.getchannel("A"))
        pts = landmark_points(parts, label)
        measured = {}
        for k, observed in view["marks"].items():
            xy = project(pts[k][None, :], camera)[0]
            measured[k] = {
                "photo": list(observed),
                "model": np.round(xy, 1).tolist(),
                "error_px": round(float(np.linalg.norm(xy - observed)), 1),
            }
        env, bare = envelopes[label]
        cloud = project(bare if label in ("front", "rear") else env, camera)
        box = np.r_[cloud.min(0), cloud.max(0)]
        results["views"][label] = dict(
            photo_file=GALLERY_FILES[label],
            camera=camera.round(5).tolist(),
            steering_degrees=view.get("steer", 0),
            photo_box=view["box"],
            render_box=box.round(1).tolist(),
            landmarks=measured,
        )
        if label == "side":
            samples = []
            for x, y in SIDE_OUTLINE:
                row = int(np.flatnonzero(mask[:, x])[0])
                samples.append(dict(x=x, photo_y=y, render_y=row, error_px=row - y))
            results["views"][label]["upper_outline"] = samples
        sheet_path = comparison_dir / ("fit_" + label + ".jpg")
        if label == "rear":
            hidden = Image.open(Path(scratch.name) / "rear_without_mirrors.png").convert("RGBA")
            bare = (np.array(hidden.getchannel("A")) > 75).astype(np.uint8) * 255
            trace = rear_body_edges(bare)
            results["views"][label]["body_edges_without_mirrors"] = trace
            if photo_paths:
                rear_sheet(sheet_path, load_photo(photo_paths[label]), render, mask, hidden, bare, trace)
        elif photo_paths:
            write_sheet(sheet_path, label, load_photo(photo_paths[label]), render, mask, view, measured)
        print(
            label,
            "bbox",
            np.round(box - view["box"], 1),
            "marks",
            [(k, m["error_px"]) for k, m in measured.items()],
        )
    for label, detail in detail_metrics.items():
        detail["photo_file"] = DETAIL_FILES[label][0]
        errors = [p["error_px"] for p in detail["landmarks"].values()]
        detail["mean_error_px"] = round(float(np.mean(errors)), 1)
        detail["max_error_px"] = max(errors)
    results["front_outline"], paths = measure_nose(parts, cameras)
    render_paths = {view: Path(scratch.name) / (view + ".png") for view in paths}
    nose_outline_sheet(out / "front_outline.jpg", render_paths, paths)
    if photo_paths:
        nose_outline_sheet(comparison_dir / "fit_front_outline.jpg", photo_paths, paths)
        front_detail_sheet(comparison_dir / "fit_front_details.jpg", photo_paths, Path(scratch.name))
    results["front_details"] = detail_metrics
    (out / "measurements.json").write_text(json.dumps(results, indent=2) + "\n")
    hero = Image.open(Path(scratch.name) / "hero.png").convert("RGB")
    hero.crop((21, 156, 1233, 718)).save(ROOT / "Destroyer_05.jpg", quality=95)


def front_detail_sheet(path, photo_paths, scratch):
    tiles = [
        ("lamp_detail", "Headlamp", (277, 170, 961, 551)),
        ("grille_detail", "Grille", (3, 316, 1251, 651)),
    ]
    width = 760
    margin = 16
    sizes = [(width, round(width * (box[3] - box[1]) / (box[2] - box[0]))) for _, _, box in tiles]
    sheet = Image.new(
        "RGB", (2 * width + 3 * margin, 104 + sum(h + 41 for _, h in sizes) + 35), "#f5f5f1"
    )
    draw = ImageDraw.Draw(sheet)
    font = lambda size: ImageFont.truetype("DejaVuSans.ttf", size)
    draw.text((margin, 13), "BYD Destroyer 05", font=font(27), fill="#172325")
    for x, text in [(margin, "Original photograph"), (width + 2 * margin, "Model at the fitted camera")]:
        draw.text((x, 59), text, font=font(20), fill="#425153")
    y = 97
    for (label, title, box), size in zip(tiles, sizes):
        draw.text((margin, y), title, font=font(17), fill="#172325")
        y += 30
        photo = load_photo(photo_paths[label])
        rgba = Image.open(scratch / (label + ".png")).convert("RGBA")
        render = Image.new("RGB", SIZE, "#e4e5e2")
        render.paste(rgba, mask=rgba.getchannel("A"))
        for x, im in [(margin, photo), (2 * margin + width, render)]:
            sheet.paste(im.crop(box).resize(size, Image.Resampling.LANCZOS), (x, y))
        y += size[1] + 11
    draw.text(
        (margin, y + 5),
        "Reference photography from the Destroyer 05 gallery at importbyd.com.",
        font=font(14),
        fill="#425153",
    )
    sheet.save(path, quality=94, optimize=True)


# Pixel traces from the three gallery photos. Each pair is (column, row).
# The far tyre occludes part of the three-quarter chin. Keep the two exposed runs separate.
front_fenders = [
    (355, 343, 911),
    (365, 337, 917),
    (375, 332, 922),
    (385, 329, 928),
    (395, 321, 935),
    (405, 314, 939),
    (415, 311, 942),
    (425, 310, 944),
    (440, 309, 945),
    (460, 309, 945),
    (480, 309, 945),
    (500, 309, 944),
    (520, 310, 943),
    (540, 311, 941),
    (560, 314, 939),
    (580, 315, 939),
]
NOSE_TRACES = {
    "front": {
        "left body edge": ("left", [(l, y) for y, l, r in front_fenders]),
        "right body edge": ("right", [(r, y) for y, l, r in front_fenders]),
        "lower bright lip": (
            "lip",
            [
                (365, 594),
                (400, 596),
                (460, 598),
                (520, 598),
                (600, 598),
                (680, 598),
                (750, 597),
                (810, 596),
                (860, 593),
                (890, 591),
            ],
        ),
    },
    "quarter": {
        "bonnet outline": (
            "top",
            [
                (180, 387),
                (190, 381),
                (200, 373),
                (210, 367),
                (220, 362),
                (230, 357),
                (240, 354),
                (250, 351),
            ],
        ),
        "bumper leading edge": (
            "left",
            [
                (x, y)
                for y, x in [
                    (390, 181),
                    (400, 174),
                    (410, 167),
                    (420, 165),
                    (430, 162),
                    (440, 156),
                    (450, 154),
                    (460, 155),
                    (470, 157),
                    (480, 158),
                    (490, 160),
                    (500, 161),
                    (510, 163),
                    (520, 162),
                    (530, 158),
                    (540, 155),
                    (550, 155),
                    (560, 160),
                ]
            ],
        ),
        "far chin": ("bottom", [(168, 568), (178, 569), (188, 570)]),
        "near chin": (
            "bottom",
            [
                (368, 584),
                (388, 585),
                (408, 586),
                (428, 586),
                (448, 587),
                (468, 589),
                (488, 589),
                (508, 588),
                (528, 588),
            ],
        ),
    },
    "side": {
        "bonnet outline": (
            "top",
            [
                (80, 412),
                (95, 402),
                (110, 394),
                (125, 387),
                (140, 381),
                (155, 377),
                (170, 373),
                (185, 369),
                (200, 365),
                (215, 362),
                (230, 360),
                (245, 357),
            ],
        ),
        "bumper leading edge": (
            "left",
            [
                (x, y)
                for y, x in [
                    (422, 72),
                    (430, 70),
                    (438, 69),
                    (446, 67),
                    (454, 66),
                    (462, 67),
                    (470, 68),
                    (478, 60),
                    (486, 61),
                    (494, 62),
                    (502, 62),
                    (510, 63),
                    (518, 70),
                    (526, 74),
                    (534, 66),
                ]
            ],
        ),
        "lower bumper": (
            "bottom",
            [(75, 540), (95, 545), (115, 550), (135, 554), (155, 557), (175, 558), (195, 558)],
        ),
    },
}


def nose_masks(parts, camera):
    """Supersample the projected front panels, wheel arch lips and fascia fittings."""
    import cv2

    scale = 2
    shell = np.zeros((SIZE[1] * scale, SIZE[0] * scale), np.uint8)
    lip = np.zeros_like(shell)
    for name, (vertices, _, indices, _, group) in parts.items():
        if group not in ("Body shell", "Fascias and lamps") or vertices[:, 0].min() > 0:
            continue
        if name.startswith(("Inner wheelhouses", "Wheelhouse return", "Dark undertray")):
            continue
        triangles = indices.reshape(-1, 3)
        # Cut well behind the arch crown. The three cropped views measure only the nose.
        triangles = triangles[np.min(vertices[triangles, 0], axis=1) < 350]
        xy = np.rint(project(vertices, camera) * scale).astype(np.int32)
        for tri in xy[triangles]:
            cv2.fillConvexPoly(shell, tri, 255)
            if name == "Lower bumper bright lip":
                cv2.fillConvexPoly(lip, tri, 255)
    return shell, lip, scale


def measure_nose(parts, cameras):
    measurements = {}
    paths = {}
    for view, traces in NOSE_TRACES.items():
        shell, lip, scale = nose_masks(parts, cameras[view])
        measurements[view] = {}
        paths[view] = {}
        for name, (edge, observed) in traces.items():
            horizontal = edge in ("left", "right")
            samples = lip if edge == "lip" else shell
            scan_axis = int(horizontal)
            stations = [pt[scan_axis] for pt in observed]
            curve = {}
            for station in range(stations[0], stations[-1] + 1):
                scan = samples[station * scale, :] if horizontal else samples[:, station * scale]
                pixels = np.flatnonzero(scan)
                if not pixels.size:
                    raise ValueError(f"No mesh intersection in {view} at {name}, {station}")
                if edge == "lip":
                    coordinate = (int(pixels[0]) + int(pixels[-1])) / (2 * scale)
                else:
                    coordinate = int(pixels[0 if edge in ("left", "top") else -1]) / scale
                curve[station] = (coordinate, station) if horizontal else (station, coordinate)
            values = [curve[key] for key in stations]
            errors = [v[1 - scan_axis] - o[1 - scan_axis] for v, o in zip(values, observed)]
            measurements[view][name] = dict(
                photo_xy=observed,
                model_xy=values,
                error_px=errors,
                mean_abs_px=round(float(np.mean(np.abs(errors))), 2),
                max_abs_px=float(np.max(np.abs(errors))),
            )
            paths[view][name] = list(curve.values())
    return measurements, paths


def nose_outline_sheet(path, image_paths, paths):
    # Every line uses the original photo pixel coordinates, prior to cropping or enlarging.
    boxes = {"front": (287, 325, 966, 631), "quarter": (139, 337, 546, 600), "side": (49, 339, 253, 572)}
    widths = {"front": 970, "quarter": 608, "side": 334}
    panels = {}
    cyan = "#00eddf"
    amber = "#ffad30"
    for view, box in boxes.items():
        with Image.open(image_paths[view]) as source:
            panel = source.convert("RGBA").resize(SIZE, Image.Resampling.LANCZOS).crop(box)
        base = Image.new("RGB", panel.size, "#e4e5e2")
        base.paste(panel, mask=panel.getchannel("A"))
        ratio = widths[view] / base.width
        im = base.resize((widths[view], round(base.height * ratio)), Image.Resampling.LANCZOS)
        d = ImageDraw.Draw(im)

        def coords(points):
            return [((x - box[0]) * ratio, (y - box[1]) * ratio) for x, y in points]

        for name, curve in paths[view].items():
            line = coords(curve)
            d.line(line, fill="#163639", width=4)
            d.line(line, fill=cyan, width=2)
            for x, y in coords(NOSE_TRACES[view][name][1]):
                d.ellipse((x - 2.7, y - 2.7, x + 2.7, y + 2.7), fill=amber, outline="#503300", width=1)
        panels[view] = im
    h = panels["front"].height
    sheet = Image.new(
        "RGB", (1002, 154 + h + max(panels["side"].height, panels["quarter"].height) + 39), "#f5f5f1"
    )
    d = ImageDraw.Draw(sheet)
    font = lambda size: ImageFont.truetype("DejaVuSans.ttf", size)
    d.text((16, 10), "BYD Destroyer 05  ·  Front outline", fill="#172325", font=font(25))
    d.line((20, 58, 47, 58), fill="#009f97", width=3)
    d.text((57, 47), "Projected mesh edge", fill="#253039", font=font(17))
    d.ellipse((307, 54, 315, 62), fill=amber, outline="#503300")
    d.text((326, 47), "Edge sampled on the photograph", fill="#253039", font=font(17))
    for label, title, x, y in [
        ("front", "Front elevation", 16, 84),
        ("quarter", "Front three-quarter", 16, 124 + h),
        ("side", "Side profile", 652, 124 + h),
    ]:
        d.text((x, y), title, font=font(17), fill="#172325")
        sheet.paste(panels[label], (x, y + 25))
    d.text(
        (16, sheet.height - 27),
        "Measured points from the Destroyer 05 gallery at importbyd.com.",
        font=font(13),
        fill="#425153",
    )
    sheet.save(path, quality=94, optimize=True)


# Rear body boundaries read from the photo in the original 1,254 x 836 camera.
# Rows through the mirror housings are deliberately left out of the edge sample.
REAR_BODY_ROWS = [
    (340, 328, 927),
    (350, 326, 929),
    (370, 321, 933),
    (395, 315, 939),
    (420, 309, 944),
    (450, 308, 945),
    (480, 308, 945),
    (510, 309, 943),
    (540, 312, 941),
    (560, 313, 939),
]


def rear_body_edges(bare):
    trace = []
    for y, left, right in REAR_BODY_ROWS:
        xs = np.flatnonzero(bare[y])
        xl, xr = int(xs[0]), int(xs[-1])
        trace.append(
            dict(y=y, photo_x=[left, right], render_x=[xl, xr], error_px=[xl - left, xr - right])
        )
    return trace


def rear_sheet(path, photo, render, mask, bare_rgba, bare, trace):
    import cv2

    no_mirrors = Image.new("RGB", SIZE, "#e4e5e2")
    no_mirrors.paste(bare_rgba, mask=bare_rgba.getchannel("A"))
    overlay = np.array(photo)

    def contour(layer, color):
        edges, _ = cv2.findContours(layer, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, edges, -1, color, 2, cv2.LINE_AA)

    contour(bare, (0, 235, 205))
    projecting_mirrors = cv2.bitwise_and(mask, cv2.bitwise_not(bare))
    # Limit stochastic alpha differences to the two known mirror regions.
    region = np.zeros_like(mask)
    region[268:338, 284:395] = 255
    region[268:338, 855:961] = 255
    contour(cv2.bitwise_and(projecting_mirrors, region), (246, 70, 168))
    for point in trace:
        y = point["y"]
        for x in point["photo_x"]:
            cv2.circle(overlay, (x, y), 3, (255, 184, 65), -1, cv2.LINE_AA)
    crop = (270, 145, 980, 697)
    w, h = crop[2] - crop[0], crop[3] - crop[1]
    sheet = Image.new("RGB", (w * 2, 78 + (h + 33) * 2 + 55), "#f5f5f1")
    draw = ImageDraw.Draw(sheet)
    font = lambda size: ImageFont.truetype("DejaVuSans.ttf", size)
    draw.text((14, 10), "BYD Destroyer 05", font=font(26), fill="#172325")
    draw.text(
        (15, 45), "Rear elevation   /   Boot, fenders and door mirrors", font=font(16), fill="#425153"
    )
    for i, (title, img) in enumerate(
        [
            ("Original photograph", photo),
            ("Complete model", render),
            ("Same camera, door mirrors hidden", no_mirrors),
            ("Body and visible mirror outlines on the original", Image.fromarray(overlay)),
        ]
    ):
        x, y = (i % 2) * w, 78 + (i // 2) * (h + 33)
        draw.text((x + 12, y + 6), title, font=font(16), fill="#172325")
        sheet.paste(img.crop(crop), (x, y + 33))
    y = sheet.height - 45
    draw.text((15, y), "Cyan   body with mirrors hidden", font=font(15), fill="#007b6d")
    draw.text((310, y), "Pink   door mirrors extending beyond the body", font=font(15), fill="#ab2066")
    draw.text((753, y), "Amber   measured body edges", font=font(15), fill="#9a5911")
    draw.text(
        (15, y + 24),
        "Reference photography from the Destroyer 05 gallery at importbyd.com.",
        font=font(12),
        fill="#425153",
    )
    sheet.save(path, quality=93, optimize=True)


def write_sheet(file, label, photo, render, mask, view, measured):
    import cv2

    region = view["box"]
    l, t, r, b = region
    dx = 54 if label in ("front", "rear") else 20
    crop = (max(0, l - dx), max(0, t - 22), min(SIZE[0], r + dx), min(SIZE[1], b + 24))
    overlay = photo.copy()
    outline, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    data = np.array(overlay)
    cv2.drawContours(data, outline, -1, (16, 255, 215), 2, cv2.LINE_AA)
    overlay = Image.fromarray(data)
    d = ImageDraw.Draw(overlay)
    # Corner ticks show the rectangle used for scale and translation.
    left, top, right, bottom = view["box"]
    for x, ex in [(left, 1), (right, -1)]:
        for y, ey in [(top, 1), (bottom, -1)]:
            d.line([(x + ex * 14, y), (x, y), (x, y + ey * 11)], fill="#fff5ce", width=2)
    for m in measured.values():
        a = m["photo"]
        b = m["model"]
        d.line((tuple(a), tuple(b)), fill="#fff5ce", width=2)
        d.ellipse((a[0] - 4, a[1] - 4, a[0] + 4, a[1] + 4), fill="#fdaa38", outline="black")
        d.line((b[0] - 5, b[1], b[0] + 5, b[1]), fill="#00ffe2", width=2)
        d.line((b[0], b[1] - 5, b[0], b[1] + 5), fill="#00ffe2", width=2)
    width = crop[2] - crop[0]
    height = crop[3] - crop[1]
    # Two end elevations are tall, side elevations benefit from a vertical stack.
    horizontal = label in ("front", "rear")
    header = 64
    bar = 33
    sheet = Image.new(
        "RGB",
        (
            (width * 3 if horizontal else width),
            header + ((height + bar) if horizontal else 3 * (height + bar)) + 49,
        ),
        "#f5f5f1",
    )
    draw = ImageDraw.Draw(sheet)
    font = lambda size: ImageFont.truetype("DejaVuSans.ttf", size)
    draw.text((12, 9), "BYD Destroyer 05", font=font(25), fill="#172325")
    draw.text(
        (13, 41),
        {
            "quarter": "Front three-quarter",
            "rear_quarter": "Left rear three-quarter",
            "right_rear_quarter": "Right rear three-quarter",
            "side": "Side elevation",
            "front": "Front elevation",
            "rear": "Rear elevation",
        }[label]
        + "   /   Camera registration",
        font=font(14),
        fill="#425153",
    )
    for i, (title, im) in enumerate(
        [
            ("Reference photograph", photo),
            ("Model at the fitted camera", render),
            ("Model outline and landmarks over photograph", overlay),
        ]
    ):
        x = i * width if horizontal else 0
        y = header if horizontal else header + i * (height + bar)
        draw.text((x + 10, y + 7), title, font=font(15), fill="#172325")
        sheet.paste(im.crop(crop), (x, y + bar))
    draw.text(
        (10, sheet.height - 42),
        "Amber dot   measured on photograph     /     Cyan cross   projected from mesh",
        font=font(14),
        fill="#425153",
    )
    draw.text(
        (10, sheet.height - 21),
        "Reference photography reproduced from the Destroyer 05 gallery at importbyd.com.",
        font=font(12),
        fill="#425153",
    )
    sheet.save(file, quality=91, optimize=True)


if __name__ == "__main__":
    main()
