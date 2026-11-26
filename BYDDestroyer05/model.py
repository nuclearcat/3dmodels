"""Build the BYD Destroyer 05 exterior. Run with Python, NumPy and SciPy.
Coordinates in mm: front axle origin, +X towards boot, +Y passenger side, +Z up.
The GLB uses metres and Y up. See README.md for references and camera checks.
"""

# SPDX-License-Identifier: CC-BY-NC-4.0
import json
import struct
from pathlib import Path
from math import sin, cos, pi, sqrt
import numpy as np
from scipy.interpolate import PchipInterpolator

OUT = Path(__file__).resolve().parent
# sRGB, metallic, roughness
MATERIALS = {
    "Ocean graphite": ("394650", 0.65, 0.24),
    "Smoked glazing": ("405660", 0.13, 0.095),
    "Ceramic frit": ("111820", 0.28, 0.19),
    "Satin black": ("1d2126", 0.16, 0.36),
    "Panel shutline": ("181e23", 0.1, 0.45),
    "Machined alloy": ("c4c9cd", 0.83, 0.21),
    "Brightwork": ("cdd1d3", 0.89, 0.155),
    "Tyre": ("191a1c", 0.01, 0.68),
    "Wheel graphite": ("313740", 0.66, 0.29),
    "Brake rotor": ("666967", 0.70, 0.41),
    "Lens polycarbonate": ("b2cad5", 0.05, 0.09),
    "Optic bezel": ("10151a", 0.14, 0.25),
    "Lamp housing": ("080b0e", 0.05, 0.30),
    "Optical reflector": ("d9dfe4", 0.94, 0.11),
    "Projector glass": ("37475b", 0.48, 0.115),
    "Lens glint": ("d8dde3", 0.64, 0.19),
    "LED diffuser": ("f7f8ec", 0.08, 0.26),
    "Brushed light trim": ("dbe0df", 0.67, 0.25),
    "Grille silver": ("d7dcd9", 0.68, 0.25),
    "Intake shadow": ("090c10", 0.02, 0.74),
    "Louvre graphite": ("24282c", 0.26, 0.29),
    "Headlamp": ("3e4a59", 0.53, 0.16),
    "Light guide": ("f2f4eb", 0.28, 0.18),
    "Tail lens": ("631827", 0.4, 0.18),
    "Red guide": ("c32b3b", 0.29, 0.19),
    "Plate": ("e3b727", 0.07, 0.34),
    "Upholstery": ("4c4745", 0.01, 0.75),
    "Interior charcoal": ("2b2d30", 0.04, 0.56),
}


def profile(xs, values):
    return PchipInterpolator(xs, values)


def unit(vector):
    return vector / np.maximum(np.linalg.norm(vector, axis=-1, keepdims=True), 1e-12)


# Half-section corrections from the mirror-free rear elevation. The belt, lamp
# returns and quarter glass share the same cross-section as their supporting panels.
rear_shoulder_inset = profile(
    [0, 600, 685, 750, 820, 900, 980, 1040, 1100, 1200, 1320, 1495],
    [0, 0, 0, 4, 17, 37, 53, 73, 76, 54, 25, 0],
)


def rear_section(vertices):
    x, y, z = vertices.T
    run = np.clip((x - 1450) / 950, 0, 1)
    run = run * run * (3 - 2 * run)
    wing = np.clip((np.abs(y) - 560) / 310, 0, 1)
    wing = wing * wing * (3 - 2 * wing)
    inset = run * wing * rear_shoulder_inset(np.clip(z, 0, 1495))
    # The shoulders turn inward in plan ahead of the light bar. The lamp nose
    # was triangulated in the side and both rear three-quarter photographs.
    inset += 59 * np.exp(-(((x - 3290) / 245) ** 2) - ((z - 978) / 142) ** 2) * wing
    # Maximum width is on the lower haunch. The rear lamps tuck in above it.
    swell = (
        np.clip((x - 2670) / 570, 0, 1)
        * np.interp(z, [260, 340, 420, 500, 570, 650, 730], [0, 0, 0.20, 0.76, 1, 0.65, 0])
        * wing
    )
    outset = np.minimum(25 * swell, np.maximum(0, 918.49 - np.abs(y)))
    return np.column_stack([x, np.sign(y) * (np.abs(y) - inset + outset), z])


def nose_section(vertices):
    """The bumper corners and bonnet shoulders sweep back around the lamp assemblies."""
    x, y, z = vertices.T
    high = np.clip((z - 670) / 110, 0, 1)
    fade_end = -385 + 250 * high
    run = np.clip((fade_end - x) / (fade_end + 670), 0, 1)
    outer = np.minimum(abs(y) / 835, 1)
    sweep = (167 + 46 * high) * outer**2.55 * run
    shoulder = np.clip((abs(y) - 560) / 290, 0, 1) ** 2
    inset = 36 * shoulder * np.clip((z - 620) / 155, 0, 1) * np.clip((-70 - x) / 380, 0, 1)
    # Keep the lower bumper lip forward. Above it, the lamp face turns in
    # toward the bonnet while its long bright tip continues along the wing.
    tuck = np.clip((abs(y) - 715) / 110, 0, 1) * np.clip((625 - z) / 200, 0, 1)
    sweep *= 1 - 0.62 * tuck
    lamp_zone = np.clip((abs(y) - 665) / 145, 0, 1) * np.clip((-145 - x) / 290, 0, 1)
    inset += 32 * lamp_zone * np.clip((z - 607) / 80, 0, 1)
    drop = 10 * run * np.clip((z - 597) / 105, 0, 1)
    # Raise the outer brow toward the wing while retaining the lower guide line.
    lift_weight = np.clip((z - 675) / 112, 0, 1)
    lift_weight = lift_weight**2 * (3 - 2 * lift_weight)
    lift = 27 * np.exp(-(((abs(y) - 790) / 148) ** 2)) * lift_weight * np.exp(-(((x + 620) / 265) ** 4))
    return np.column_stack((x + sweep, np.sign(y) * (abs(y) - inset), z - drop + lift))


# Cross-sections traced from the front elevation and the two views of the nose.
# Grid coordinates are original panel heights in mm before the section is rolled inward.
fender_roll = profile(
    [700, 740, 770, 805, 840, 880, 920, 970, 1030, 1100, 1210], [0, 2, 16, 49, 75, 82, 76, 56, 34, 11, 0]
)
valance_drop = profile([185, 252, 286, 313, 345, 365], [91, 98, 64, 29, 6, 0])
valance_return = profile(
    [180, 245, 254, 268, 286, 296, 314, 330, 345, 365], [207, 207, 203, 120, 26, 7, 39, 15, 0, 0]
)
corner_return = profile(
    [238, 278, 312, 350, 412, 470, 525, 575, 625, 665, 700],
    [-30, -8, 44, 34, 9, -23, -58, -66, -34, 0, 0],
)


def smooth_step(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def front_panel_section(vertices, fitting, station_x):
    x, y, z = vertices.T
    lateral = np.abs(y)
    wing = smooth_step((lateral - 570) / 270)
    roll = fender_roll(np.clip(z, 700, 1210)) * smooth_step((1550 - x) / 950) * wing
    roll *= smooth_step((x + 410) / 350)
    # Carry the mirror plinth inward with the door skin, fading along the mounting arm.
    if fitting.startswith("Mirror"):
        roll *= smooth_step((902 - lateral) / 64)
    half_width = lateral - roll
    if "mirror" not in fitting.lower():
        arch_lip = 7.5 * np.exp(-(((x - 78) / 140) ** 2) - ((z - 712) / 48) ** 2) * wing
        half_width = np.minimum(918.5, half_width + arch_lip)
    # Shape the skirt from the local sill height before the corner is swept back.
    # This joins its underside continuously to the floor behind the bumper.
    floor_height = rocker(np.clip(station_x, -670, -275))
    clearance = 156 + 15 * smooth_step((station_x + 670) / 220)
    skirt = np.clip((floor_height - clearance) / 98, 0, 1) * smooth_step((-275 - station_x) / 95)
    z_out = z - skirt * valance_drop(np.clip(z, 185, 365))
    z_out -= 12 * skirt * smooth_step((lateral - 330) / 360) * np.exp(-(((z - 292) / 21) ** 2))
    x_out = x + skirt * valance_return(np.clip(z, 180, 365)) * (
        1 - 0.71 * smooth_step((lateral - 550) / 285)
    )
    corner = smooth_step((lateral - 602) / 196) * smooth_step((-335 - x) / 200)
    x_out += corner_return(np.clip(z, 238, 700)) * corner
    # The lower front fender returns under the wheel opening toward the tyre.
    x_out += (
        68
        * np.exp(-(((x + 377) / 93) ** 2))
        * smooth_step((360 - z) / 165)
        * smooth_step((lateral - 655) / 138)
    )
    # Round the central leading edge of the bonnet into the upright face.
    bonnet = np.maximum(
        np.exp(-(((x + 830) / 190) ** 4)),
        0.76 * smooth_step((x + 800) / 140) * smooth_step((160 - x) / 270),
    )
    z_out += 29 * smooth_step((z - 646) / 97) * bonnet * (1 - smooth_step((lateral - 268) / 209))
    x_out -= (
        13
        * smooth_step((z - 547) / 125)
        * np.exp(-(((x + 917) / 103) ** 4))
        * (1 - smooth_step((lateral - 285) / 190))
    )
    # The rolled lower corners run wider and slightly lower than the centre of the chin.
    lip_corner = (
        smooth_step((210 - z_out) / 53)
        * smooth_step((-445 - x_out) / 122)
        * smooth_step((half_width - 410) / 280)
    )
    return np.column_stack(
        (x_out + 14 * lip_corner, np.sign(y) * (half_width + 8 * lip_corner), z_out - 12 * lip_corner)
    )


class Model:
    def __init__(self):
        self.parts = []
        self.group = "Bodywork"
        self.groups = {}

    def mesh(self, name, material, vertices, faces):
        v = np.asarray(vertices, dtype=float).reshape(-1, 3)
        if not self.group.startswith("Wheel assembly"):
            station_x = v[:, 0]
            v = rear_section(v)
            if v[:, 0].min() < -70 and not name.startswith("Registration plate"):
                v = nose_section(v)
            if v[:, 0].min() < 1550 and not name.startswith(
                ("Registration plate", "Painted mirror cap")
            ):
                v = front_panel_section(v, name, station_x)
            if v[:, 0].min() < -915:
                # The plate and its supporting face lean back together below the top edge.
                x, y, z = v.T
                rake = (
                    0.105
                    * np.clip(458 - z, 0, 152)
                    * smooth_step((-915 - x) / 65)
                    * smooth_step((365 - np.abs(y)) / 130)
                )
                v[:, 0] += rake
        f = np.asarray(faces, dtype=int).reshape(-1, 3)
        n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
        valid = np.linalg.norm(n, axis=1) > 1e-8
        f, n = f[valid], n[valid]
        used, remap = np.unique(f, return_inverse=True)
        v = v[used]
        f = remap.reshape(-1, 3)
        normals = np.zeros_like(v)
        for i in range(3):
            np.add.at(normals, f[:, i], n)
        self.groups[name] = self.group
        self.parts.append((name, material, v, f, unit(normals)))

    def grid(self, name, material, rows, reverse=False):
        a = np.asarray(rows)
        m, n = a.shape[:2]
        corners = (np.arange(m - 1)[:, None] * n + np.arange(n - 1)).ravel()
        faces = np.concatenate(
            [
                np.stack([corners, corners + n, corners + n + 1], 1),
                np.stack([corners, corners + n + 1, corners + 1], 1),
            ]
        )
        self.mesh(name, material, a, faces[:, ::-1] if reverse else faces)

    def tube(self, name, material, points, radius, sides=8):
        pts = np.asarray(points, dtype=float)
        tangent = unit(np.gradient(pts, axis=0))
        # Parallel transport prevents sudden twists on nearly vertical sections.
        axes = []
        axis = np.eye(3)[np.argmin(abs(tangent[0]))]
        for t in tangent:
            axis = unit(axis - np.dot(t, axis) * t)
            axes.append(axis)
        b = np.cross(tangent, axes)
        angles = np.linspace(0, 2 * pi, sides + 1)
        rings = pts[:, None, :] + radius * (
            np.cos(angles)[None, :, None] * np.array(axes)[:, None, :]
            + np.sin(angles)[None, :, None] * b[:, None, :]
        )
        self.grid(name, material, rings, True)

    def ellipsoid(self, name, mat, center, scale):
        a, b = np.meshgrid(np.linspace(0, 2 * pi, 49), np.linspace(-pi / 2, pi / 2, 25))
        xyz = np.stack([np.cos(a) * np.cos(b), np.sin(a) * np.cos(b), np.sin(b)], -1)
        self.grid(name, mat, xyz * scale + center, True)

    def save(self):
        binary = bytearray()
        views, access, meshes, nodes, materials = [], [], [], [], []
        for name, (rgb, metallic, roughness) in MATERIALS.items():
            c = np.array([int(rgb[i : i + 2], 16) / 255 for i in (0, 2, 4)])
            linear = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
            materials.append(
                dict(
                    name=name,
                    doubleSided=True,
                    pbrMetallicRoughness=dict(
                        baseColorFactor=[*linear, 1], metallicFactor=metallic, roughnessFactor=roughness
                    ),
                )
            )

        materials[0]["extensions"] = {
            "KHR_materials_clearcoat": {"clearcoatFactor": 0.76, "clearcoatRoughnessFactor": 0.19}
        }
        glazing = materials[list(MATERIALS).index("Smoked glazing")]
        glazing["alphaMode"] = "BLEND"
        glazing["pbrMetallicRoughness"]["baseColorFactor"][3] = 0.32

        lens = materials[list(MATERIALS).index("Lens polycarbonate")]
        lens["alphaMode"] = "BLEND"
        lens["pbrMetallicRoughness"]["baseColorFactor"][3] = 0.047
        lens["extensions"] = {
            "KHR_materials_clearcoat": {"clearcoatFactor": 1, "clearcoatRoughnessFactor": 0.09}
        }
        for name, factor in [("Intake shadow", 0.12), ("Lamp housing", 0.19), ("Louvre graphite", 0.45)]:
            materials[list(MATERIALS).index(name)]["extensions"] = {
                "KHR_materials_specular": {"specularFactor": factor}
            }
        materials[list(MATERIALS).index("LED diffuser")]["emissiveFactor"] = [0.55, 0.58, 0.53]

        def buffer(data, indices=False):
            data = np.ascontiguousarray(data, dtype="<u4" if indices else "<f4")
            views.append(
                dict(
                    buffer=0,
                    byteOffset=len(binary),
                    byteLength=data.nbytes,
                    target=34963 if indices else 34962,
                )
            )
            binary.extend(data.tobytes())
            access.append(
                dict(
                    bufferView=len(views) - 1,
                    componentType=5125 if indices else 5126,
                    count=len(data),
                    type="SCALAR" if indices else "VEC3",
                    min=np.atleast_1d(data.min(0)).tolist(),
                    max=np.atleast_1d(data.max(0)).tolist(),
                )
            )
            return len(access) - 1

        roots = []
        groups = {}
        for name, material, verts, faces, normals in self.parts:
            group = self.groups[name]
            pivot = np.zeros(3)
            if group.startswith("Wheel assembly"):
                axle, side = map(int, group.split()[-2:])
                pivot = np.array([axle, side * (790 if axle == 0 else 795), 321])
            if group not in groups:
                groups[group] = len(nodes)
                roots.append(len(nodes))
                nodes.append(
                    dict(
                        name=group,
                        children=[],
                        translation=(pivot[[0, 2, 1]] * [0.001, 0.001, -0.001]).tolist(),
                    )
                )
            nodes[groups[group]]["children"].append(len(nodes))

            # Right-handed Z-up -> right-handed glTF Y-up.
            def rotate(a):
                return a[:, [0, 2, 1]] * [1, 1, -1]

            primitive = dict(
                attributes=dict(
                    POSITION=buffer(rotate(verts - pivot) / 1000), NORMAL=buffer(rotate(normals))
                ),
                indices=buffer(faces.ravel(), True),
                material=list(MATERIALS).index(material),
            )
            nodes.append(dict(name=name, mesh=len(meshes)))
            meshes.append(dict(name=name, primitives=[primitive]))
        gltf = dict(
            asset=dict(
                version="2.0", generator="BYD Destroyer 05 parametric exterior", copyright="CC BY-NC 4.0"
            ),
            scene=0,
            scenes=[dict(nodes=roots)],
            nodes=nodes,
            meshes=meshes,
            materials=materials,
            extensionsUsed=["KHR_materials_clearcoat", "KHR_materials_specular"],
            buffers=[dict(byteLength=len(binary))],
            bufferViews=views,
            accessors=access,
        )
        meta = json.dumps(gltf, separators=(",", ":")).encode()
        meta += b" " * (-len(meta) % 4)
        with (OUT / "Destroyer_05.glb").open("wb") as f:
            f.write(
                struct.pack("<4sIIII", b"glTF", 2, 28 + len(meta) + len(binary), len(meta), 0x4E4F534A)
            )
            f.write(meta)
            f.write(struct.pack("<I4s", len(binary), b"BIN\0") + binary)


body = Model()
paint, dark, seam = "Ocean graphite", "Satin black", "Panel shutline"
chrome, glass, frit = "Brightwork", "Smoked glazing", "Ceramic frit"
# Actual side stations. The centre of each end projects beyond its side corner.
stations = [-670, -530, -340, 0, 260, 465, 800, 1350, 1880, 2350, 2718, 2960, 3200, 3420, 3535]
width = profile(
    stations, [835, 882, 905, 918.5, 905, 892, 890, 888, 893, 906, 918.5, 914, 905, 887, 841]
)
shoulder = profile(
    stations, [790, 821, 850, 900, 944, 984, 997, 1010, 1030, 1051, 1071, 1080, 1090, 1083, 1070]
)
crown = profile(
    stations, [715, 848, 930, 985, 1015, 1025, 1032, 1042, 1062, 1090, 1110, 1110, 1121, 1119, 1108]
)
rocker = profile(stations, [254, 197, 180, 176, 174, 178, 183, 188, 194, 204, 220, 258, 298, 343, 350])


def gauge(x):
    return max(0.0, 1 - (x + 670) / 830) ** 2, max(0.0, 1 - (3535 - x) / 660) ** 2


def section_x(x, t):
    front, rear = gauge(x)
    return x + (-268 * front + 212 * rear) * (1 - abs(t) ** 3.4)


def hood(x, t):
    """Crowned hood and deck with two shallow pressed character lines."""
    u = abs(t)
    w = float(width(x)) - 33
    pressing = (
        np.exp(-(((u - 0.66) / 0.078) ** 2))
        * 21
        * np.clip((x + 670) / 250, 0, 1)
        * np.clip((500 - x) / 490, 0, 1)
    )
    z = float(crown(x)) + (float(shoulder(x)) - float(crown(x))) * u**2.6 + pressing
    return [section_x(x, t), w * t, z]


def arch(x):
    floor = float(rocker(x))
    for center in (0, 2718):
        d = abs(x - center)
        if d < 380:
            # Almost vertical lower fender returns, then a circular crown.
            if d < 367:
                floor = max(floor, 321 + sqrt(max(0, 374**2 - d * d)) * (1.08 if center else 1.025))
            else:
                floor = max(floor, np.interp(d, [367, 375, 380], [393, 285, float(rocker(x))]))
    return floor


flank_inset = profile(
    [0, 0.055, 0.12, 0.20, 0.36, 0.62, 0.79, 0.88, 0.94, 1], [42, 28, 21, 30, 32, 13, 5, 0, 3, 33]
)


def flank(x, z, s):
    high, low = float(shoulder(x)), arch(x)
    bottom = float(rocker(x))
    # Doors carry a shallow hollow above the sill and a sharp upper shoulder.
    h = np.clip((z - bottom) / (high - bottom), 0, 1)
    inset = float(flank_inset(h))
    fender = max(np.exp(-(((x - c) / 500) ** 4)) for c in (0, 2718))
    inset *= 1 - 0.73 * fender * np.sin(pi * h)
    if 280 < x < 2520:
        run = (x - 280) / 2240
        swell = sin(pi * run) ** 1.2
        # Stamped lower-door scallop rises toward the rear haunch.
        inset += swell * 29 * np.exp(-(((h - (0.19 + 0.115 * run)) / 0.095) ** 2))
        inset += swell * 9 * np.exp(-(((h - 0.72) / 0.09) ** 2))
    # Recessed handle bowls lie within the outer fender width.
    inset += 17 * np.exp(-(((x - 2352) / 126) ** 4) - ((h - 0.82) / 0.063) ** 2)
    if low > bottom + 10:
        inset += 9 * max(0, 1 - (z - low) / 20)
        inset += 14 * np.exp(-(((z - low - 90) / 54) ** 2)) * np.clip((1 - h) * 8, 0, 1)
    crown_flare = 4.5 * np.exp(-(((x - 10) / 225) ** 2) - ((z - 855) / 75) ** 2)
    return [x, s * min(918.5, float(width(x)) - inset + crown_flare), z]


# Front and rear fascia geometry shares its boundary samples with the body.
def end(front, t, k, offset=0):
    x = stations[0] if front else stations[-1]
    z0 = float(rocker(x)) + (0 if front else -10) * (1 - abs(t))
    z1 = hood(x, t)[2]
    z = z0 + (z1 - z0) * k
    y = abs(flank(x, z, 1)[1]) * t
    if front:
        blend = np.clip((k - 0.80) / 0.20, 0, 1)
        # The flange must meet both the bonnet above and the side panel at t = ±1.
        side_z = z0 + (shoulder(x) - z0) * k
        side_delta = hood(x, 1)[1] - flank(x, side_z, 1)[1]
        y += (hood(x, t)[1] - y - np.sign(t) * abs(t) ** 7 * side_delta) * blend**2
    edge = hood(x, t)[0]
    curve = (
        np.interp(k, [0, 0.09, 0.19, 0.36, 0.55, 0.75, 1], [-16, -47, -36, -43, -33, -18, 0])
        if front
        else np.interp(
            k,
            [0, 0.16, 0.29, 0.36, 0.43, 0.485, 0.53, 0.60, 0.69, 0.765, 0.819, 0.91, 1],
            [-65, -28, 28, 43, 41, 22, -15, -29, -13, 8, 12, 10, 0],
        )
    )
    xx = edge + curve * (1 - abs(t) ** 3) + (-offset if front else offset)
    if front:
        # The sculpted cheeks fold inward behind the outboard air curtains.
        xx += (
            26
            * (1 - smooth_step((abs(t) - 0.93) / 0.07))
            * np.exp(-(((abs(t) - 0.923) / 0.070) ** 4) - ((k - 0.43) / 0.29) ** 4)
        )
    else:
        lower = max(0, 1 - k / 0.21)
        z -= lower**2 * 61 * (1 - abs(t) ** 4)
        xx -= lower**2 * 118 * (1 - abs(t) ** 3)
    return [xx, y, z]


def side_stations():
    sections = list(np.arange(-670, 3535, 23)) + stations + [230, 420, 3200, 3400, 3535]
    for c in (0, 2718):
        sections += [c + d for d in (-381, -380, -378, -375, -371, -367, 367, 371, 375, 378, 380, 381)]
        sections += list(c + 374 * np.cos(np.linspace(0, pi, 60)))
    return sorted(set(round(x, 4) for x in sections))


def hull():
    xs = side_stations()
    ts = np.linspace(-1, 1, 65)
    for s in (-1, 1):
        top = []
        for x in xs:
            aperture = np.interp(x, [230, 420, 3200, 3400], [0, 0.88, 0.88, 0])
            top.append([hood(x, s * t) for t in np.linspace(aperture, 1, 39)])
        body.grid("Bonnet and deck " + str(s), paint, top, s == -1)
    for s in (-1, 1):
        rows = []
        lips = []
        liners = []
        for x in xs:
            a, b = arch(x), float(shoulder(x))
            heights = np.linspace(a, b, 41)
            rows.append([flank(x, z, s) for z in heights])
            p = np.array(flank(x, a, s))
            lips.append([p, p - [0, s * 18, 0]])
            liners.append([p - [0, s * 18, 0], [x, s * 630, a - 6]])
        body.grid("Pressed bodyside " + str(s), paint, rows, s == 1)
        body.grid("Folded wheel opening and sill " + str(s), paint, lips, s == 1)
        body.grid("Wheelhouse return " + str(s), dark, liners, s == 1)
        body.grid(
            "Inner wheelhouses " + str(s),
            dark,
            [[row[1], [x, s * 630, float(rocker(x)) - 7]] for x, row in zip(xs, liners)],
            s == -1,
        )
        for c in (0, 2718):
            pts = []
            for x in xs:
                if abs(x - c) <= 380:
                    z = arch(x) + 17
                    p = flank(x, z, s)
                    p[1] += s
                    pts.append(p)
            # The edge catches light along the rolled steel lip.
            body.tube("Rolled arch " + str((c, s)), paint, pts, 2.4)
    for front in (True, False):
        body.grid(
            "Front bumper" if front else "Rear bumper",
            paint,
            [
                [end(front, t, k) for t in ts]
                for k in np.unique(np.r_[np.linspace(0, 1, 41), 0.09, 0.36])
            ],
            not front,
        )
    valance_floor = []
    for t in ts:
        leading = np.array(end(True, t, 0))
        trailing = np.array([stations[0], leading[1], rocker(stations[0])])
        valance_floor.append([leading * (1 - u) + trailing * u for u in np.linspace(0, 1, 15)])
    body.grid("Front valance underside", dark, valance_floor)
    for side in (-1, 1):
        rows = []
        for x in xs:
            if x >= -380:
                break
            z = float(rocker(x))
            y = abs(flank(x, z, side)[1])
            rows.append([[x, side * w, z] for w in np.linspace(635, y, 13)])
        body.grid("Front lower fender return " + str(side), dark, rows, side == 1)
    body.grid(
        "Dark undertray",
        dark,
        [[[x, y, float(rocker(x))] for y in np.linspace(-635, 635, 31)] for x in xs],
        True,
    )


# Side stations of the greenhouse. The front and rear screens bow in plan.
cab_x = [330, 445, 580, 770, 990, 1200, 1450, 1710, 1920, 2150, 2370, 2600, 2840, 3070, 3270, 3430]
roof_z = profile(
    cab_x,
    [1007, 1071, 1157, 1260, 1361, 1434, 1478, 1494, 1495, 1488, 1463, 1408, 1331, 1243, 1176, 1115],
)
cant_z = profile(
    cab_x,
    [992, 1016, 1124, 1223, 1325, 1383, 1421, 1436, 1437, 1429, 1401, 1361, 1301, 1222, 1160, 1108],
)
cant_y = profile(cab_x, [772, 791, 760, 706, 650, 610, 587, 584, 585, 591, 605, 630, 654, 680, 713, 748])
waist_y = profile(
    cab_x, [778, 809, 820, 827, 831, 833, 832, 832, 831, 828, 825, 823, 818, 809, 792, 764]
)


def canopy(x, t):
    u = abs(t)
    # Windscreen rakes farther forward at its centre than at the A pillars.
    shift = np.interp(
        x, cab_x, [-105, -125, -114, -105, -101, -85, -36, 0, 0, 0, 18, 45, 75, 115, 100, 45]
    )
    return [x + shift * (1 - u * u), cant_y(x) * t, roof_z(x) + (cant_z(x) - roof_z(x)) * u**3.8]


def cabin_side(x, h, s, offset=0):
    low = hood(x, waist_y(x) / (float(width(x)) - 33))[2] - 2
    y = waist_y(x) * (1 - h) + cant_y(x) * h + 9 * np.sin(h * pi)
    return [x, s * (y + offset), low + (cant_z(x) - low) * h]


def glass_bounds(u):
    # Tapered end radii at the A and sail pillars.
    x = 486 + (2865 - 486) * u
    cap = np.clip(min(u / 0.105, (1 - u) / 0.055), 0, 1)
    return x, 0.018 + (1 - cap) ** 2 * 0.715, 0.944 - (1 - cap) ** 2 * 0.211


def cabin():
    # Separate panels share their boundary coordinates, leaving open glazing apertures.
    def screen_edge(x, t, edge):
        return x + edge * 26 * max(0, (abs(t) - 0.83) / 0.17) ** 2

    limits = [(330, 0), (343, 1), (1210, -1), (2370, 1), (3238, -1), (3430, 0)]
    for i, ((start, start_sign), (finish, end_sign)) in enumerate(zip(limits, limits[1:])):
        is_screen = i in (1, 3)
        lanes = [(-1, -0.957), (-0.957, 0.957), (0.957, 1)] if is_screen else [(-1, 1)]
        for tl, tr in lanes:
            ts = np.linspace(tl, tr, 51 if tr - tl > 1 else 5)
            for low, high in ([(0, 0.041), (0.041, 0.958), (0.958, 1)] if is_screen else [(0, 1)]):
                rows = []
                for v in np.linspace(low, high, 41 if high - low > 0.5 else 5):
                    rows.append(
                        [
                            canopy(
                                (1 - v) * screen_edge(start, t, start_sign)
                                + v * screen_edge(finish, t, end_sign),
                                t,
                            )
                            for t in ts
                        ]
                    )
                mat = paint
                name = "Roof panel"
                if is_screen:
                    name = "Windscreen" if i == 1 else "Rear screen"
                    mat = paint if tl == -1 or tr == 1 else (glass if low == 0.041 else frit)
                if mat != glass:
                    name += f" {i} {tl} {low}"
                body.grid(name, mat, rows)
    for s in (-1, 1):
        us = np.linspace(0, 1, 121)
        rows = []
        top = []
        sill = []
        frame_top = []
        frame_low = []
        for u in us:
            x, lo, hi = glass_bounds(u)
            rows.append([cabin_side(x, h, s) for h in np.linspace(lo, hi, 17)])
            top.append(cabin_side(x, hi, s, 1))
            sill.append(cabin_side(x, lo, s, 1))
            frame_top.append([cabin_side(x, h, s) for h in np.linspace(hi, 1, 5)])
            frame_low.append([cabin_side(x, h, s) for h in np.linspace(0, lo, 5)])
        for i, (a, b) in enumerate([(cab_x[0], glass_bounds(0)[0]), (glass_bounds(1)[0], cab_x[-1])]):
            body.grid(
                "Pillar " + str((s, i)),
                paint,
                [[cabin_side(x, h, s) for h in np.linspace(0, 1, 13)] for x in np.linspace(a, b, 37)],
                s == 1,
            )
        body.grid("Upper door frame " + str(s), paint, frame_top, s == 1)
        body.grid("Window sill " + str(s), paint, frame_low, s == 1)
        body.grid("Side glass " + str(s), glass, rows, s == 1)
        perimeter = top + sill[::-1] + top[:1]
        body.tube("Side window bright surround " + str(s), chrome, perimeter, 6)
        for name, lower, upper, w in [
            ("B pillar", 1517, 1592, 95),
            ("Rear quarter division", 2563, 2380, 48),
        ]:
            rows = []
            for h in np.linspace(0, 1, 21):
                x = lower * (1 - h) + upper * h
                rows.append([cabin_side(x + dx, 0.026 + 0.903 * h, s, 4) for dx in [-w / 2, w / 2]])
            body.grid(name + " " + str(s), frit, rows, s == -1)
    for s in (-1, 1):
        pts = [canopy(x, 0.93 * s) for x in np.linspace(1230, 2355, 50)]
        body.tube("Roof ditch moulding " + str(s), seam, pts, 3.5)


# End trim follows the curved bumper surface. Coordinates are fractional
# half-width and fractional height between valance and deck.
def band(name, mat, front, ts, bottom, top, offset):
    rows = []
    for t in ts:
        a = bottom(t) if callable(bottom) else bottom
        b = top(t) if callable(top) else top
        rows.append([end(front, t, k, offset) for k in np.linspace(a, b, 6)])
    body.grid(name, mat, rows, front)


def stripe(name, mat, front, a, b, base, height, offset):
    ts = np.linspace(a, b, max(7, int((b - a) * 55) + 1))
    band(name, mat, front, ts, base, lambda t: base(t) + height, offset)


# Perimeter coordinate 0..1 follows the front cap. Beyond the corner it advances
# along the wing by 600 mm per unit. Both halves meet on the actual panel boundary.
lamp_depth = profile(
    [0.53, 0.60, 0.76, 0.94, 1.04, 1.15, 1.30, 1.40, 1.48, 1.55, 1.79],
    [99, 99, 99, 101, 101, 97, 72, 39, 24, 15, 1],
)
lamp_start, lamp_tip = 0.546, 1.79


def lamp_point(q, height, side, relief=0):
    if q <= 1:
        z_top = hood(-670, q)[2]
        z = z_top - (1 - height) * lamp_depth(q)
        p = np.asarray(end(True, side * q, (z - 254) / (z_top - 254)))
    else:
        x = -670 + 600 * (q - 1)
        z = shoulder(x) - (1 - height) * lamp_depth(q)
        p = np.asarray(flank(x, z, side))
    # Offset normal to the nose, turning with the cover over the front corner.
    angle = (pi / 2) * np.clip((q - 0.30) / 0.83, 0, 1) ** 1.3
    return p + np.array([-cos(angle), side * sin(angle), 0]) * relief


def lens_patch(name, material, side, start, stop, bottom, top, relief, steps=53):
    rows = []
    for u in np.linspace(0, 1, steps):
        row = []
        for v in np.linspace(0, 1, 9):
            a = start(v) if callable(start) else start
            b = stop(v) if callable(stop) else stop
            q = a + (b - a) * u
            h = bottom(q) + (top(q) - bottom(q)) * v
            d = relief(q, h) if callable(relief) else relief
            row.append(lamp_point(q, h, side, d))
        rows.append(row)
    body.grid(name + " " + str(side), material, rows, side == -1)


def rectangular_optic(side, name, q, half_width, height, half_height, projector):
    # A rounded rectangular pocket, a recessed optical cup and a convex inner lens.
    # The two modules have different sizes and internal reflector geometry.
    def ring(w, h, depth, roundness):
        pts = []
        for a in np.linspace(0, 2 * pi, 49):
            du = np.sign(cos(a)) * abs(cos(a)) ** roundness
            dv = np.sign(sin(a)) * abs(sin(a)) ** roundness
            pts.append(lamp_point(q + w * du, height + h * dv, side, depth))
        return pts

    suffix = name + " " + str(side)
    rings = [
        ring(half_width * scale, half_height * scale, d, 0.40)
        for scale, d in [(1, 3), (0.98, 10), (0.82, 11), (0.74, 4.8)]
    ]
    body.grid(suffix + " bezel", "Optic bezel", rings[:3], side == 1)
    body.grid(suffix + " reflector walls", "Optical reflector", rings[2:], side == 1)
    if projector:
        rings = [
            ring(half_width * w, half_height * h, d, 0.45)
            for w, h, d in [(0.76, 0.74, 5), (0.64, 0.63, 9), (0.37, 0.38, 13), (0.01, 0.01, 14)]
        ]
        body.grid(suffix + " optical face", "Projector glass", rings, side == 1)
    else:
        # Folded reflector facets fan outward from the central emitter. Each facet
        # has its own normal, so the silver cup catches distinct studio highlights.
        vertices = []
        faces = []
        angles = np.linspace(0, 2 * pi, 23)
        for inner, outer in zip([0.04, 0.36, 0.68], [0.36, 0.68, 1]):
            for a, b in zip(angles, angles[1:]):
                first = len(vertices)
                for r, t, crease in [(inner, a, 0), (outer, a, 1.4), (outer, b, 0), (inner, b, 0.7)]:
                    u = np.sign(cos(t)) * abs(cos(t)) ** 0.54
                    v = np.sign(sin(t)) * abs(sin(t)) ** 0.54
                    depth = 3.1 + 9 * r * r + crease
                    vertices.append(
                        lamp_point(
                            q + half_width * 0.73 * u * r,
                            height + half_height * 0.74 * v * r,
                            side,
                            depth,
                        )
                    )
                faces.extend([[first, first + 1, first + 2], [first, first + 2, first + 3]])
        body.mesh(suffix + " optical face", "Optical reflector", vertices, faces)
        for h, w in [(height - 0.045, 0.0065), (height - 0.003, 0.0032)]:
            body.tube(
                suffix + " emitter " + str(h),
                "Lens glint",
                [lamp_point(q + u, h, side, 11) for u in [-w, 0, w]],
                1.65,
                8,
            )


def headlamps():
    edge = lambda v: lamp_start + 0.066 * v
    zero = lambda q: 0
    one = lambda q: 1
    brow_width = profile([lamp_start, 1.02, 1.19, 1.39, 1.55, lamp_tip], [19, 19, 15, 5, 3, 0.8])
    brow_bottom = lambda q: 1 - min(0.94, brow_width(q) / lamp_depth(q))
    for side in (-1, 1):
        lens_patch("Headlamp recessed black mask", "Lamp housing", side, edge, lamp_tip, zero, one, 1.8)
        # Only the outer section of the upper blade continues rearwards over the wing.
        lens_patch(
            "Headlamp satin brow",
            "Brushed light trim",
            side,
            0.612,
            lamp_tip,
            brow_bottom,
            one,
            lambda q, h: 5.4 + 10 * np.clip((q - 0.612) / 0.04, 0, 1) * np.clip((1.52 - q) / 0.13, 0, 1),
        )
        rectangular_optic(side, "Inboard faceted reflector", 0.686, 0.058, 0.65, 0.22, False)
        rectangular_optic(side, "Outboard projector", 0.867, 0.058, 0.70, 0.19, True)
        # Fluted end of the black grille bridge just inside the first reflector.
        for i in range(5):
            h = 0.24 + i * 0.089
            lens_patch(
                "Inner mask flute " + str(i),
                "Headlamp",
                side,
                0.579 + 0.013 * i,
                0.634,
                lambda q, h=h: h,
                lambda q, h=h: h + 0.018,
                4.8,
                9,
            )
        guide_q = [0.575, 0.69, 0.84, 0.96, 1.04, 1.13, 1.22, 1.34, 1.385]
        guide_h = profile(guide_q, [0.115, 0.115, 0.118, 0.13, 0.145, 0.19, 0.36, 0.64, 0.75])
        guide_low = lambda q: float(guide_h(q))
        guide_high = lambda q: min(brow_bottom(q) - 0.01, guide_low(q) + min(0.14, 7.3 / lamp_depth(q)))
        lens_patch(
            "Daytime running light carrier",
            "Headlamp",
            side,
            guide_q[0] - 0.001,
            guide_q[-1],
            lambda q: guide_low(q) - 0.030,
            lambda q: guide_high(q) + 0.030,
            8,
        )
        lens_patch(
            "Swept daytime running light",
            "LED diffuser",
            side,
            guide_q[0],
            guide_q[-1],
            guide_low,
            guide_high,
            10.5,
        )
        # Narrow black seal and a single clear outer cover spanning both modules.
        lens_patch(
            "Clear headlamp cover",
            "Lens polycarbonate",
            side,
            edge,
            1.48,
            zero,
            brow_bottom,
            lambda q, h: 16 + 1.7 * sin(pi * h),
        )
        body.tube(
            "Lamp lower weather seal " + str(side),
            "Optic bezel",
            [lamp_point(q, 0, side, 4) for q in np.linspace(lamp_start, 1.48, 55)],
            2.2,
        )
    band("Gloss grille bridge", frit, True, np.linspace(-0.613, 0.613, 77), 0.808, 1, 2)
    band(
        "Chrome bonnet leading edge",
        "Brushed light trim",
        True,
        np.linspace(-0.612, 0.612, 103),
        lambda t: 1 - 19 / (hood(-670, t)[2] - 254),
        1,
        5.3,
    )
    stripe(
        "Upper bridge lower moulding", "Machined alloy", True, -0.546, 0.546, lambda t: 0.814, 0.009, 4
    )
    for i in range(7):
        k = 0.831 + i * 0.016
        for side in (-1, 1):
            a, b = sorted([side * 0.18, side * (0.545 + 0.006 * i)])
            stripe(
                "Badge bridge flute " + str((i, side)),
                "Satin black",
                True,
                a,
                b,
                lambda t, k=k: k,
                0.003,
                4.2,
            )


def grille_surface(y, z, relief):
    """A horizontal section through the bumper, in body millimetres."""
    half_width = flank(-670, z, 1)[1]
    t = y / half_width
    k = (z - 254) / (hood(-670, t)[2] - 254)
    return end(True, t, k, relief)


def grille():
    # Five central blades and five pairs of lower, overlapping outboard inlays.
    # Rows run top to bottom. Dimensions are half-spans measured from the badge centre.
    centres = [582, 530, 478, 426, 375]
    inner_ends = [474, 477, 493, 509, 523]
    outer_starts = [370, 383, 402, 417, 433]
    outer_ends = [619, 635, 651, 666, 680]

    def opening_edge(z):
        return np.interp(z, [345, 354, 575, 603, 617], [669, 687, 625, 618, 570])

    rows = []
    for z in np.linspace(345, 617, 43):
        w = opening_edge(z)
        rows.append([grille_surface(y, z, 1.4) for y in np.linspace(-w, w, 131)])
    body.grid("Recessed trapezoid grille", "Intake shadow", rows)
    # Each moulded cell has a sloping surround and flat black inset, visible
    # between the silver blades at the outer corners. The upper bank rises under the lamps.
    walls = []
    wall_faces = []
    for side in (-1, 1):
        for row in range(13):
            z = 357 + row * 23.4
            outer = opening_edge(z) if z < 610 else 627 + (z - 610) * 0.95
            for column in range(3):
                y = side * (outer - 25 - column * 44)
                ring = [(-20, -7), (16, -7), (21, -3), (19, 6), (-16, 6), (-21, 3)]
                loops = []
                for scale, d in [(1, 2.3), (0.95, 5), (0.76, 4.8), (0.69, 2.8)]:
                    loops.append(
                        [
                            grille_surface(y + side * (a + b * 0.25) * scale, z + b * scale, d)
                            for a, b in ring
                        ]
                    )
                first = len(walls)
                walls.extend(pt for loop in loops for pt in loop)
                for j in range(3):
                    for i in range(6):
                        a = first + j * 6 + i
                        b = first + j * 6 + (i + 1) % 6
                        tri = [[a, b, b + 6], [a, b + 6, a + 6]]
                        wall_faces.extend(tri if side == 1 else [f[::-1] for f in tri])
    body.mesh("Outboard grille cell surrounds", "Louvre graphite", walls, wall_faces)

    def blade(name, start, stop, z_at, bright, backing="Louvre graphite"):
        # A sloped metallic face over a deeper black louvre gives the bar a crisp lower shadow.
        coords = (
            [(-4, 3), (-3.4, 7), (-3.1, 10), (2.8, 10.5), (3.5, 7), (4, 3)]
            if bright
            else [(-6.7, 2), (-5.3, 6), (4.5, 6.3), (6.9, 2)]
        )
        rows = []
        for u in np.linspace(0, 1, max(6, int(abs(stop - start) / 14))):
            y = start + (stop - start) * u
            taper = min(1, 0.70 + min(u, 1 - u) * 15)
            z = z_at(abs(y))
            rows.append([grille_surface(y, z + h * taper, d) for h, d in coords])
        body.grid(name, "Grille silver" if bright else backing, rows, stop > start)

    for i, z in enumerate(centres):
        for side in (-1, 1):
            end_y = inner_ends[i]
            start_y = 18 if i == 0 else 88 if i in (1, 2) else 218
            line = lambda y, z=z: z + 3.5 * (y / 530) ** 2
            blade("Central louvre " + str((i, side)), side * 3, side * (end_y + 4), line, False)
            blade("Main silver blade " + str((i, side)), side * start_y, side * end_y, line, True)
            outside = (
                lambda y, z=z, i=i: z
                - 19
                + (14 + 2.2 * i) * ((y - outer_starts[i]) / (outer_ends[i] - outer_starts[i])) ** 2
            )
            blade(
                "Outer louvre " + str((i, side)),
                side * (outer_starts[i] - 2),
                side * (outer_ends[i] + 3),
                outside,
                False,
            )
            blade(
                "Offset silver blade " + str((i, side)),
                side * outer_starts[i],
                side * outer_ends[i],
                outside,
                True,
            )
        if i in (1, 2):
            insert = [
                [grille_surface(y, z + h, 6.8) for h in (-6, 4, 12 + (1 - abs(y) / 86) * 2)]
                for y in np.linspace(-86, 86, 29)
            ]
            body.grid("Centre strip socket " + str(i), "Panel shutline", insert, True)
            blade("Centre blade join " + str(i), -83, 83, lambda y, z=z: z - 0.8, True)
        if i < 4:
            for j in range(2):
                blade(
                    "Intake fin " + str((i, j)),
                    -inner_ends[i],
                    inner_ends[i],
                    lambda y, z=z, j=j: z - 14 - j * 13 + 5 * (y / 530) ** 2,
                    False,
                    "Intake shadow",
                )


def face_trim():
    ts = np.linspace(-1, 1, 121)
    headlamps()
    grille()
    for s in (-1, 1):
        # Rounded triangular pocket with a recessed-looking surround and vertical throat.
        for name, mat, margin, off in [
            ("Bumper duct surround", "Wheel graphite", 0.009, 3),
            ("Outer bumper duct", frit, 0, 5),
        ]:
            rows = []
            for v in np.linspace(0, 1, 43):
                rad = min(1, sqrt(max(0, 1 - ((v - 0.5) / 0.5) ** 8)))
                mid = 0.928 + 0.022 * (1 - v)
                half = (0.028 + 0.018 * v) * rad + margin
                rows.append(
                    [
                        end(True, s * t, 0.08 + 0.65 * v, off)
                        for t in np.linspace(mid - half, mid + half, 9)
                    ]
                )
            body.grid(name + " " + str(s), mat, rows, s == -1)
        for j in range(5):
            c = 0.29 + 0.069 * j
            stripe(
                "Duct louvre " + str((j, s)),
                "Wheel graphite",
                True,
                min(s * 0.925, s * 0.955),
                max(s * 0.925, s * 0.955),
                lambda t, c=c: c,
                0.027,
                8,
            )
    band(
        "Lower intake",
        frit,
        True,
        np.linspace(-0.83, 0.83, 79),
        0.075,
        lambda t: 0.198 - 0.093 * (abs(t) / 0.83) ** 4,
        3,
    )
    band(
        "Lower valance facing",
        dark,
        True,
        np.linspace(-0.955, 0.955, 109),
        0,
        lambda t: 0.071 * (1 - smooth_step((abs(t) - 0.87) / 0.085)),
        1.3,
    )
    stripe(
        "Lower bumper bright lip", chrome, True, -0.94, 0.94, lambda t: 0.072 + 0.009 * t * t, 0.006, 2
    )
    # Full-width rear lamp with parallel light pipes and stacked corner elements.
    band(
        "Full width smoked tail panel",
        frit,
        False,
        ts,
        lambda t: 0.753 - 0.047 * np.clip((abs(t) - 0.40) / 0.16, 0, 1) + 0.018 * abs(t) ** 3,
        lambda t: 0.829 + 0.048 * abs(t) ** 3,
        3,
    )
    stripe(
        "Tail light ribbon", "Tail lens", False, -1, 1, lambda t: 0.789 + 0.044 * abs(t) ** 3, 0.026, 5
    )
    stripe(
        "Tail guide highlight",
        "Red guide",
        False,
        -1,
        1,
        lambda t: 0.811 + 0.044 * abs(t) ** 3,
        0.006,
        5.5,
    )
    for s in (-1, 1):
        for j in range(3):
            for i in (0, 1):
                a = (0.53 + 0.25 * i) * s
                b = (0.72 + 0.22 * i) * s
                stripe(
                    "Tail lamp segment " + str((s, j, i)),
                    "Machined alloy",
                    False,
                    min(a, b),
                    max(a, b),
                    lambda t, j=j: 0.716 + j * 0.017 + 0.016 * abs(t) ** 2,
                    0.008,
                    5,
                )
        rows = []
        for v in np.linspace(0, 1, 57):
            x = 3535 - 256 * v
            top = end(False, s, 0.877)[2] * (1 - v) + 960 * v + 11 * sin(pi * v)
            thickness = (end(False, s, 0.877)[2] - end(False, s, 0.724)[2]) * min(
                1, (1 - v) / 0.40
            ) ** 0.78
            pts = [flank(x, z, s) for z in np.linspace(top - thickness, top, 9)]
            for p in pts:
                p[1] += s * 3.5
            rows.append(pts)
        body.grid("Tail lens return " + str(s), frit, rows, s == -1)
        body.tube("Tail wrap guide " + str(s), "Tail lens", [r[-2] for r in rows], 3)
        for line in (2, 4, 6):
            body.tube(
                "Quarter lamp reflector " + str((s, line)),
                "Headlamp",
                [r[line] for r in rows[2:38]],
                2.8,
            )
    band("Rear valance", dark, False, ts, 0, lambda t: 0.098 - 0.036 * t * t, 2)
    band(
        "Rear lower bumper insert",
        frit,
        False,
        np.linspace(-0.88, 0.88, 81),
        0.098,
        lambda t: 0.34 - 0.24 * (abs(t) / 0.88) ** 6,
        3,
    )
    stripe(
        "Rear lower bright strip", chrome, False, -0.94, 0.94, lambda t: 0.093 - 0.037 * t * t, 0.008, 4
    )
    for s in (-1, 1):
        a, b = sorted([s * 0.46, s * 0.795])
        stripe(
            "Rear reflector " + str(s),
            "Red guide",
            False,
            a,
            b,
            lambda t: 0.102 - 0.02 * t * t,
            0.024,
            5,
        )
    # Rectangular dealer plates sit on flat plinths across the curved bumpers.
    for front, z in [(True, 388), (False, 505)]:
        sign = -1 if front else 1
        face = -990 if front else 3783
        for name, mat, hw, hh, r, depth in [
            ("Registration plate mount", dark, 231, 81, 8, 2),
            ("Registration plate", "Plate", 220, 70, 5, 0),
        ]:
            ring = []
            for sy, sz, start in [(1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)]:
                for a in np.radians(np.linspace(start, start + 90, 7)):
                    ring.append([sy * (hw - r) + r * cos(a), z + sz * (hh - r) + r * sin(a)])
            xx = face - sign * depth
            front_ring = [[xx, y, h] for y, h in ring]
            inner_ring = [[xx - sign * (3 if mat == "Plate" else 14), y, h] for y, h in ring]
            rows = [[a, b] for a, b in zip(front_ring + [front_ring[0]], inner_ring + [inner_ring[0]])]
            body.grid(name + " edge " + str(front), mat, rows, front)
            triangles = [[0, i + 1, ((i + 1) % len(ring)) + 1] for i in range(len(ring))]
            body.mesh(
                name + " " + str(front),
                mat,
                [[xx, 0, z]] + front_ring,
                np.array(triangles)[:, ::-1] if front else triangles,
            )
    for s in (-1, 1):
        for j in range(6):
            inner = 0.43 + 0.004 * j
            outer = 0.82 - 0.023 * j
            stripe(
                "Rear bumper fin " + str((s, j)),
                "Wheel graphite",
                False,
                min(s * inner, s * outer),
                max(s * inner, s * outer),
                lambda t, j=j: 0.139 + 0.026 * j,
                0.008,
                5.2,
            )
        stripe(
            "Reflector reverse insert " + str(s),
            "Light guide",
            False,
            min(s * 0.575, s * 0.642),
            max(s * 0.575, s * 0.642),
            lambda t: 0.104 - 0.02 * t * t,
            0.020,
            6.5,
        )


def side_detail():
    door_paths = [
        [(485, 0.997), (444, 0.89), (434, 0.73), (431, 0.44), (440, 0.22), (467, 0.104), (492, 0.086)],
        [(1555, 0.995), (1532, 0.85), (1520, 0.67), (1530, 0.47), (1532, 0.28), (1526, 0.097)],
        [
            (2552, 0.998),
            (2593, 0.92),
            (2602, 0.84),
            (2556, 0.74),
            (2441, 0.59),
            (2289, 0.40),
            (2132, 0.20),
            (2055, 0.105),
        ],
    ]
    for s in (-1, 1):

        def side_pt(x, h, off=1):
            p = flank(x, float(rocker(x)) + (float(shoulder(x)) - float(rocker(x))) * h, s)
            p[1] = s * min(915.5, abs(p[1]) + off)
            return p

        for i, path in enumerate(door_paths):
            x, h = np.array(path).T
            u = np.arange(len(x))
            pts = [
                side_pt(float(profile(u, x)(v)), float(profile(u, h)(v)))
                for v in np.linspace(0, u[-1], 61)
            ]
            body.tube("Door shut " + str((s, i)), seam, pts, 2.8)
        pts = [side_pt(x, 0.089 + 0.017 * ((x - 1250) / 850) ** 2) for x in np.linspace(490, 2059, 60)]
        body.tube("Door lower shut " + str(s), seam, pts, 2.7)
        # The projecting sill and lower crease track the wheel openings.
        rows = []
        for x in np.linspace(388, 2334, 81):
            taper = max(0, min((x - 388) / 110, (2334 - x) / 160, 1))
            rows.append(
                [side_pt(x, 0.026, 0), side_pt(x, 0.039, 8 * taper), side_pt(x, 0.081, 5 * taper)]
            )
        body.grid("Rocker blade " + str(s), paint, rows, s == 1)
        for x, h in [(1380, 0.82), (2352, 0.821)]:
            p = np.array(side_pt(x, h))
            body.ellipsoid("Handle pocket " + str((x, s)), seam, p, [76, 8, 30])
            body.ellipsoid("Pull handle " + str((x, s)), paint, p + [0, s * 12, 11], [101, 17, 17])
        # Fuel-filler door on the driver side. Opposite flank has the charging flap.
        x = 2916 if s == -1 else 2950
        pts = []
        for a in np.linspace(0, 2 * pi, 73):
            exponent = 1 if s == -1 else 0.55
            xx = x + (99 if s == -1 else 109) * np.sign(cos(a)) * abs(cos(a)) ** exponent
            z = 902 + 99 * np.sign(sin(a)) * abs(sin(a)) ** exponent
            p = flank(xx, z, s)
            p[1] = s * min(916.1, abs(p[1]) + 1.5)
            pts.append(p)
        body.tube("Service flap " + str(s), seam, pts, 2.3)
        pts = [hood(x, s * (0.68 + 0.21 * (x + 670) / 1105)) for x in np.linspace(-670, 430, 75)]
        body.tube("Bonnet shut " + str(s), seam, pts, 2.8)
        pts = [hood(x, s * (0.74 + 0.045 * (x - 3190) / 345)) for x in np.linspace(3220, 3535, 35)]
        pts.extend(
            end(False, s * t, k, 2)
            for t, k in [
                (0.785, 1),
                (0.785, 0.92),
                (0.785, 0.82),
                (0.782, 0.7),
                (0.76, 0.63),
                (0.707, 0.55),
                (0.66, 0.49),
                (0.622, 0.478),
            ]
        )
        body.tube("Boot lid shut " + str(s), seam, pts, 3)
    stripe("Boot lid lower shut", seam, False, -0.623, 0.623, lambda t: 0.474, 0.008, 2.8)


# Turn a radial tyre/rim cross-section about the axle, retaining the shoulder round.
def wheel():
    for c, track in [(0, 1580), (2718, 1590)]:
        for s in [-1, 1]:
            body.group = f"Wheel assembly {c} {s}"
            suffix = " " + str((c, s))
            cy = s * track / 2
            rz = 321

            def revolve(name, mat, section):
                rows = []
                for a in np.linspace(0, 2 * pi, 121):
                    rows.append(
                        [[c + r * cos(a), cy + s * y, max(0, rz + r * sin(a))] for r, y in section]
                    )
                body.grid(name + suffix, mat, rows, s == 1)

            revolve(
                "Tyre casing",
                "Tyre",
                [
                    (217, -75),
                    (219, -94),
                    (254, -104),
                    (290, -107),
                    (310, -102),
                    (327, -90),
                    (333, -72),
                    (334, -53),
                    (334, 53),
                    (333, 72),
                    (327, 90),
                    (310, 102),
                    (290, 107.5),
                    (255, 105),
                    (224, 97),
                    (217, 84),
                ],
            )
            for r in [255, 292]:
                revolve("Sidewall bead " + str(r), "Tyre", [(r - 1, 106), (r, 107.9), (r + 1, 106)])
            revolve(
                "Alloy barrel",
                "Wheel graphite",
                [
                    (0, -65),
                    (216, -65),
                    (228, -35),
                    (231, 84),
                    (228, 98),
                    (221, 99),
                    (214, 87),
                    (208, -39),
                    (0, -39),
                ],
            )
            revolve("Diamond cut rim", "Machined alloy", [(216, 87), (219, 99), (225, 100), (229, 96)])
            revolve(
                "Brake disc",
                "Brake rotor",
                [(0, 34), (153, 34), (158, 36), (158, 42), (150, 44), (0, 44)],
            )
            body.ellipsoid(
                "Brake caliper" + suffix, "Wheel graphite", [c + 133, cy + s * 53, rz + 38], [27, 18, 57]
            )

            def blade(name, mat, a, shape, depth):
                pts = []
                for r, da in shape:
                    ang = a + da * pi / 180
                    pts.append([c + r * cos(ang), cy + s * (depth + (r / 229) * 8), rz + r * sin(ang)])
                # Quads with tapered tips, triangulated in ordered radial strips.
                body.mesh(name + suffix, mat, pts, [[0, 1, 2], [0, 2, 5], [5, 2, 3], [5, 3, 4]])

            for i in range(5):
                a = (i * 72 + 16) * pi / 180
                for off, spread in [(0, 8), (34, 3.8)]:
                    shape = [
                        (34, off - 12),
                        (108, off - spread),
                        (223, off - spread),
                        (226, off + spread),
                        (105, off + spread),
                        (36, off + 12),
                    ]
                    blade("Cast spoke " + str((i, off)), "Wheel graphite", a, shape, 88)
                blade(
                    "Forged blade " + str(i),
                    "Machined alloy",
                    a,
                    [(43, 1), (105, 2.8), (221, 1.8), (227, 15), (202, 8), (44, 5)],
                    93,
                )
                blade(
                    "Slim spoke edge " + str(i),
                    "Machined alloy",
                    a,
                    [(45, -5), (120, -3), (220, -3), (226, -6), (128, -5), (45, -8)],
                    93,
                )
                body.ellipsoid(
                    "Lug " + str(i) + suffix,
                    "Machined alloy",
                    [c + 34 * cos(a), cy + s * 93, rz + 34 * sin(a)],
                    [7, 5, 7],
                )
            revolve("Wheel centre", "Wheel graphite", [(0, 88), (34, 88), (34, 97), (28, 101), (0, 101)])
            revolve("Hub bright ring", "Machined alloy", [(25, 101), (26, 103), (28, 102)])


def cabin_furniture():
    # Shapes visible through the glazing establish scale in the daylight opening.
    trim, cloth = "Interior charcoal", "Upholstery"

    def padded(name, mat, section):
        rows = []
        for z, x, y, rx, ry in section:
            row = []
            for a in np.linspace(0, 2 * pi, 57):
                ca, sa = cos(a), sin(a)
                row.append(
                    [x + rx * np.sign(ca) * abs(ca) ** 0.57, y + ry * np.sign(sa) * abs(sa) ** 0.57, z]
                )
            rows.append(row)
        body.grid(name, mat, rows, True)

    padded(
        "Dashboard top pad",
        trim,
        [
            (790, 540, 0, 260, 688),
            (903, 538, 0, 267, 752),
            (960, 529, 0, 258, 745),
            (975, 526, 0, 220, 695),
            (985, 520, 0, 1, 1),
        ],
    )
    padded(
        "Parcel shelf",
        trim,
        [
            (901, 3017, 0, 361, 684),
            (1015, 3016, 0, 373, 707),
            (1055, 3038, 0, 310, 665),
            (1065, 3040, 0, 1, 1),
        ],
    )
    for s in (-1, 1):
        rows = []
        for x in np.linspace(340, 3350, 65):
            y = s * (waist_y(x) - 12)
            z = cabin_side(x, 0, s)[2]
            rows.append(
                [[x, y, z - 2], [x, y - s * 39, z - 10], [x, y - s * 52, z - 65], [x, y - s * 35, 375]]
            )
        body.grid("Cabin door card " + str(s), trim, rows, s == -1)
    body.grid("Cabin carpet", trim, [[[x, -792, 374], [x, 792, 374]] for x in [315, 3360]])
    for name, x, y, h in [
        ("Driver", 1330, -410, 0),
        ("Passenger", 1330, 410, 0),
        ("Rear left", 2500, -420, -33),
        ("Rear centre", 2500, 0, -60),
        ("Rear right", 2500, 420, -33),
    ]:
        padded(
            name + " cushion",
            cloth,
            [
                (466, x - 90, y, 188, 160),
                (498, x - 96, y, 230, 199),
                (578, x - 96, y, 226, 195),
                (594, x - 91, y, 160, 137),
                (602, x - 91, y, 1, 1),
            ],
        )
        padded(
            name + " backrest",
            cloth,
            [
                (560, x + 12, y, 82, 200),
                (651, x + 17, y, 86, 222),
                (895 + h, x + 74, y, 67, 211),
                (1008 + h, x + 106, y, 61, 174),
                (1040 + h, x + 109, y, 42, 117),
                (1043 + h, x + 109, y, 1, 1),
            ],
        )
        for sign in (-1, 1):
            body.tube(
                name + " headrest post " + str(sign),
                "Machined alloy",
                [[x + 111, y + sign * 54, 1025 + h], [x + 116, y + sign * 54, 1090 + h]],
                5,
            )
        padded(
            name + " head restraint",
            cloth,
            [
                (1061 + h, x + 120, y, 36, 92),
                (1074 + h, x + 120, y, 47, 110),
                (1174 + h, x + 136, y, 49, 109),
                (1204 + h, x + 142, y, 35, 89),
                (1210 + h, x + 142, y, 1, 1),
            ],
        )
    # Left-hand steering wheel, hub, spokes, infotainment display and interior mirror.
    ring = []
    for a in np.linspace(0, 2 * pi, 91):
        ring.append([895 + 42 * sin(a), -408 + 173 * cos(a), 883 + 158 * sin(a)])
    body.tube("Steering rim", trim, ring, 14, 12)
    body.ellipsoid("Airbag pad", trim, [903, -408, 883], [31, 72, 53])
    for a in (0, pi, 1.5 * pi):
        body.tube("Steering spoke " + str(a), trim, [[902, -408, 885], ring[int(a / (2 * pi) * 90)]], 13)
    body.ellipsoid("Display frame", trim, [731, 0, 976], [19, 128, 73])
    body.ellipsoid("Interior mirror", trim, [847, 0, 1285], [24, 94, 30])
    body.tube("Interior mirror stem", trim, [[823, 0, 1315], [849, 0, 1287]], 8)
    for s in (-1, 1):
        pts = [
            canopy(368 + 13 * t * t, t)
            for t in np.linspace(-0.86 if s < 0 else -0.04, -0.035 if s < 0 else 0.80, 25)
        ]
        body.tube("Parked wiper " + str(s), trim, [[x, y, z + 3] for x, y, z in pts], 4)


def mirrors():
    # A split housing with a flatter, rear-facing glass surface.
    for s in (-1, 1):
        body.ellipsoid("Mirror plinth " + str(s), dark, [638, s * 824, 1005], [83, 34, 26])
        body.tube(
            "Mirror neck " + str(s),
            dark,
            [[643, s * 831, 999], [659, s * 854, 1008], [675, s * 897, 1053]],
            23,
            16,
        )

        def shell(a, v):
            w = cos(a)
            side = sin(a)
            f = max(0.001, cos(v * pi / 2))
            return [
                680 + 97 * (np.sign(w) * abs(w) ** 0.78) * f,
                s * (908 + 89 * (np.sign(side) * abs(side) ** 0.78) * f),
                1065 + 66 * sin(v * pi / 2) - 6 * side * f + 5 * w * f,
            ]

        for name, mat, lo, hi in [
            ("Mirror lower housing", dark, -1, -0.23),
            ("Painted mirror cap", paint, -0.23, 1),
        ]:
            body.grid(
                name + " " + str(s),
                mat,
                [[shell(a, v) for a in np.linspace(0, 2 * pi, 57)] for v in np.linspace(lo, hi, 17)],
                s == 1,
            )
        body.ellipsoid("Mirror glass " + str(s), "Headlamp", [749, s * 907, 1063], [26, 76, 43])
        body.tube(
            "Mirror repeater " + str(s),
            "Light guide",
            [shell(a, -0.18) for a in np.linspace(0.43 * pi, 0.91 * pi, 23)],
            2.2,
        )


def emblems():
    # Monoline paths of the wide BYD nose badge and spaced deck lettering.
    lettering = {
        "B": [
            [(0, 1), (0.78, 1), (1, 0.85), (0.98, 0.64), (0.73, 0.52), (0, 0.52)],
            [(0.73, 0.52), (1, 0.38), (1, 0.18), (0.79, 0), (0, 0)],
        ],
        "Y": [
            [(0, 1), (0, 0.67), (0.17, 0.52), (0.82, 0.52), (1, 0.67), (1, 1)],
            [(0.5, 0.52), (0.5, 0)],
        ],
        "D": [[(0, 1), (0.63, 1), (0.9, 0.83), (1, 0.57), (1, 0.38), (0.81, 0.12), (0.62, 0), (0, 0)]],
        "U": [[(0, 1), (0, 0.23), (0.18, 0), (0.82, 0), (1, 0.23), (1, 1)]],
        "I": [[(0.5, 1), (0.5, 0)]],
        "L": [[(0, 1), (0, 0), (1, 0)]],
        "O": [
            [(0.2, 1), (0.8, 1), (1, 0.78), (1, 0.2), (0.8, 0), (0.2, 0), (0, 0.2), (0, 0.8), (0.2, 1)]
        ],
        "R": [
            [(0, 0), (0, 1), (0.8, 1), (1, 0.82), (1, 0.65), (0.8, 0.48), (0, 0.48)],
            [(0.5, 0.48), (1, 0)],
        ],
        "E": [[(1, 1), (0, 1), (0, 0), (1, 0)], [(0, 0.5), (0.85, 0.5)]],
        "A": [[(0, 0), (0.47, 1), (0.55, 1), (1, 0)], [(0.25, 0.47), (0.78, 0.47)]],
        "M": [[(0, 0), (0, 1), (0.5, 0.46), (1, 1), (1, 0)]],
        "S": [
            [(1, 0.95), (0.2, 1), (0, 0.8), (0.1, 0.58), (0.89, 0.43), (1, 0.2), (0.83, 0), (0, 0.05)]
        ],
    }

    # Small raised deck badges. Stroke coordinates run left-to-right on an 8-unit grid.
    badge_strokes = {
        "比": ["17 11 32", "14 34", "57 51 71 72", "54 76"],
        "亚": ["17 77", "37 31", "57 51", "15 23", "75 63", "01 81"],
        "迪": ["06 15", "04 14 12 01 21 70", "37 36", "26 76 71 21 26", "24 74", "58 51"],
        "驱": ["08 38 25", "16 15 35 31 20", "04 24", "78 48 41 71", "56 75 62 51", "76 53"],
        "逐": ["07 16", "04 14 12 01 21 80", "28 78", "56 35", "46 65 63 51", "55 32", "55 75", "64 81"],
        "舰": ["28 16 11 01", "16 46 41 31", "24 34", "55 57 77 74", "66 64 52 41", "65 61 81 82"],
        "0": ["27 67 76 72 61 21 12 16 27"],
        "5": ["77 27 25 64 73 72 61 11"],
        "-": ["24 64"],
        "i": ["54 51", "56 57"],
    }
    for char, strokes in badge_strokes.items():
        lettering[char] = [
            [(int(p[0]) / 8, int(p[1]) / 8) for p in stroke.split()] for stroke in strokes
        ]

    def word(front, phrase, w, h, k, r, mat, off, centre=0):
        pitch = w / len(phrase)
        for index, c in enumerate(phrase):
            for j, stroke in enumerate(lettering.get(c, [])):
                pts = []
                for u, v in stroke:
                    # Viewer right points toward -Y from front and +Y from rear.
                    y = (-1 if front else 1) * (centre - w / 2 + pitch * (index + 0.07 + 0.85 * u))
                    pts.append(
                        end(
                            front,
                            y / float(width(stations[0] if front else stations[-1])),
                            k + h * v,
                            off,
                        )
                    )
                body.tube(phrase + f" {front} {k} " + str((index, j)), mat, pts, r)

    word(True, "BYD", 244, 0.066, 0.857, 2.7, chrome, 6)
    word(False, "BUILD YOUR DREAMS", 566, 0.018, 0.85, 1.4, chrome, 4)
    word(False, "比亚迪", 100, 0.030, 0.556, 1.55, chrome, 4, -464)
    word(False, "DM-i", 82, 0.019, 0.521, 1.25, chrome, 4, -467)
    word(False, "驱逐舰05", 146, 0.028, 0.556, 1.55, chrome, 4, 465)


if __name__ == "__main__":
    body.group = "Body shell"
    hull()
    body.group = "Roof and glazing"
    cabin()
    body.group = "Cabin furniture"
    cabin_furniture()
    body.group = "Exterior mirrors"
    mirrors()
    body.group = "Exterior fittings"
    side_detail()
    body.group = "Fascias and lamps"
    face_trim()
    emblems()
    wheel()
    body.save()
    print(len(body.parts), "parts;", sum(len(p[3]) for p in body.parts), "triangles")
