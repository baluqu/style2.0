from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pygltflib import Animation, Material, PbrMetallicRoughness, Sampler, Texture, TextureInfo

from build_runway_assets import (
    ARRAY_BUFFER,
    FLOAT,
    GLBBuilder,
    GeometryPayload,
    IMAGES_DIR,
    MODELS_DIR,
    PI2,
    SCALAR,
    VEC3,
    VEC4,
    quaternion_from_euler,
)


MODEL_PATH = MODELS_DIR / "formal-olive-look.glb"
POSTER_PATH = IMAGES_DIR / "formal-olive-poster.jpg"
METADATA_PATH = MODELS_DIR / "formal-olive-look.json"
REFERENCE_PATH = IMAGES_DIR / "formal-olive-reference.jpg"
CUTOUT_PATH = IMAGES_DIR / "formal-olive-cutout.png"
SEGMENTS_DIR = IMAGES_DIR / "formal-rig"
POSTER_SIZE = (1600, 1000)
TARGET_HEIGHT = 2.82
CLAMP_TO_EDGE = 33071
LINEAR = 9729

SILHOUETTE_POINTS = [
    (0.36, 0.0),
    (0.64, 0.0),
    (0.79, 0.06),
    (0.89, 0.14),
    (0.94, 0.27),
    (0.93, 0.45),
    (0.89, 0.61),
    (0.84, 0.76),
    (0.89, 0.92),
    (0.96, 0.985),
    (0.78, 1.0),
    (0.67, 0.91),
    (0.62, 0.76),
    (0.62, 0.58),
    (0.57, 0.33),
    (0.5, 0.21),
    (0.43, 0.33),
    (0.38, 0.58),
    (0.38, 0.76),
    (0.33, 0.91),
    (0.22, 1.0),
    (0.04, 0.985),
    (0.11, 0.92),
    (0.16, 0.76),
    (0.11, 0.61),
    (0.07, 0.45),
    (0.06, 0.27),
    (0.11, 0.14),
    (0.21, 0.06),
]


SEGMENT_SPECS = {
    "Head": {"xr": (0.29, 0.71), "yr": (0.0, 0.16), "z": 0.018},
    "Torso": {"xr": (0.2, 0.8), "yr": (0.10, 0.44), "z": 0.012},
    "Hip": {"xr": (0.18, 0.82), "yr": (0.42, 0.60), "z": 0.015},
    "LeftArm": {"xr": (0.03, 0.32), "yr": (0.14, 0.66), "z": 0.022},
    "RightArm": {"xr": (0.68, 0.97), "yr": (0.14, 0.66), "z": 0.022},
    "LeftUpperLeg": {"xr": (0.18, 0.5), "yr": (0.55, 0.78), "z": 0.007},
    "RightUpperLeg": {"xr": (0.5, 0.82), "yr": (0.55, 0.78), "z": 0.007},
    "LeftLowerLeg": {"xr": (0.14, 0.45), "yr": (0.77, 0.96), "z": 0.006},
    "RightLowerLeg": {"xr": (0.55, 0.86), "yr": (0.77, 0.96), "z": 0.006},
    "LeftFoot": {"xr": (0.03, 0.43), "yr": (0.93, 1.0), "z": 0.014},
    "RightFoot": {"xr": (0.57, 0.97), "yr": (0.93, 1.0), "z": 0.014},
}


def load_reference_image() -> tuple[Image.Image, str]:
    if REFERENCE_PATH.exists():
        return Image.open(REFERENCE_PATH).convert("RGB"), REFERENCE_PATH.name

    downloads_dir = Path.home() / "Downloads"
    matches = sorted(downloads_dir.glob("Premium men*formal outfit*jpg"))
    if matches:
        source = Image.open(matches[0]).convert("RGB")
        REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        source.save(REFERENCE_PATH, quality=94, optimize=True, progressive=True)
        return source, matches[0].name

    fallback = Image.new("RGB", (736, 1104), "#687159")
    return fallback, ""


def average_background_color(rgb: np.ndarray) -> np.ndarray:
    patch = 24
    corners = np.concatenate(
        [
            rgb[:patch, :patch].reshape(-1, 3),
            rgb[:patch, -patch:].reshape(-1, 3),
            rgb[-patch:, :patch].reshape(-1, 3),
            rgb[-patch:, -patch:].reshape(-1, 3),
        ],
        axis=0,
    )
    return corners.mean(axis=0)


def extract_subject_rgba(image: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    bg = average_background_color(rgb)
    distance = np.linalg.norm(rgb - bg, axis=2)
    mask = distance > 18.0
    mask_image = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    mask_image = mask_image.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.25))
    alpha = np.asarray(mask_image, dtype=np.uint8)
    alpha = np.where(alpha > 48, 255, 0).astype(np.uint8)

    rows = np.where(alpha.max(axis=1) > 0)[0]
    cols = np.where(alpha.max(axis=0) > 0)[0]
    if not len(rows) or not len(cols):
        bbox = (0, 0, image.size[0], image.size[1])
    else:
        pad = 10
        bbox = (
            max(0, int(cols[0]) - pad),
            max(0, int(rows[0]) - pad),
            min(image.size[0], int(cols[-1]) + pad + 1),
            min(image.size[1], int(rows[-1]) + pad + 1),
        )

    rgba = image.convert("RGBA")
    rgba.putalpha(Image.fromarray(alpha, mode="L"))
    cropped = rgba.crop(bbox)
    return cropped, bbox


def build_reference_poster(subject_rgba: Image.Image, reference_rgb: Image.Image) -> None:
    background = reference_rgb.resize(POSTER_SIZE, Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(28))
    canvas = background.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", POSTER_SIZE, (8, 12, 15, 104)))

    figure = subject_rgba.copy()
    figure.thumbnail((640, 880), Image.Resampling.LANCZOS)
    x = (POSTER_SIZE[0] - figure.width) // 2
    y = (POSTER_SIZE[1] - figure.height) // 2 + 16

    shadow = Image.new("RGBA", POSTER_SIZE, (0, 0, 0, 0))
    silhouette = Image.new("RGBA", figure.size, (0, 0, 0, 132))
    shadow.alpha_composite(silhouette, dest=(x + 14, y + 22))
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(20)))
    canvas.alpha_composite(figure, dest=(x, y))

    POSTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(POSTER_PATH, quality=92, optimize=True, progressive=True)


def create_cutout_image(subject_rgba: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    width, height = subject_rgba.size
    points = [(int(width * x), int(height * y)) for x, y in SILHOUETTE_POINTS]
    mask = Image.new("L", subject_rgba.size, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(2.0))
    alpha = np.asarray(mask, dtype=np.uint8)
    alpha = np.where(alpha > 18, 255, 0).astype(np.uint8)

    rows = np.where(alpha.max(axis=1) > 0)[0]
    cols = np.where(alpha.max(axis=0) > 0)[0]
    bbox = (
        max(0, int(cols[0]) - 4),
        max(0, int(rows[0]) - 4),
        min(width, int(cols[-1]) + 5),
        min(height, int(rows[-1]) + 5),
    )

    cutout = subject_rgba.copy()
    cutout.putalpha(Image.fromarray(alpha, mode="L"))
    return cutout.crop(bbox), bbox


def crop_segment(subject_rgba: Image.Image, spec: dict[str, tuple[float, float] | float]) -> tuple[Image.Image, tuple[int, int, int, int]]:
    width, height = subject_rgba.size
    x0 = int(width * float(spec["xr"][0]))
    x1 = int(width * float(spec["xr"][1]))
    y0 = int(height * float(spec["yr"][0]))
    y1 = int(height * float(spec["yr"][1]))

    region = subject_rgba.crop((x0, y0, x1, y1))
    alpha = np.asarray(region.getchannel("A"))
    rows = np.where(alpha.max(axis=1) > 0)[0]
    cols = np.where(alpha.max(axis=0) > 0)[0]
    if not len(rows) or not len(cols):
        return region, (x0, y0, x1, y1)

    pad = 8
    cropped_bbox = (
        max(0, int(cols[0]) - pad),
        max(0, int(rows[0]) - pad),
        min(region.size[0], int(cols[-1]) + pad + 1),
        min(region.size[1], int(rows[-1]) + pad + 1),
    )
    cropped = region.crop(cropped_bbox)
    absolute_bbox = (x0 + cropped_bbox[0], y0 + cropped_bbox[1], x0 + cropped_bbox[2], y0 + cropped_bbox[3])
    return cropped, absolute_bbox


def plane_payload(width: float, height: float) -> GeometryPayload:
    positions = np.asarray(
        [
            [-width / 2.0, -height / 2.0, 0.0],
            [width / 2.0, -height / 2.0, 0.0],
            [-width / 2.0, height / 2.0, 0.0],
            [width / 2.0, height / 2.0, 0.0],
        ],
        dtype=np.float32,
    )
    indices = np.asarray([0, 1, 2, 1, 3, 2], dtype=np.uint32)
    normals = np.tile(np.array([[0.0, 0.0, 1.0]], dtype=np.float32), (4, 1))
    uvs = np.asarray([[0.0, 1.0], [1.0, 1.0], [0.0, 0.0], [1.0, 0.0]], dtype=np.float32)
    return GeometryPayload(positions=positions, indices=indices, normals=normals, uvs=uvs)


def segment_transform(bbox: tuple[int, int, int, int], subject_size: tuple[int, int], z: float) -> tuple[float, float, float, float, float]:
    subject_width, subject_height = subject_size
    x0, y0, x1, y1 = bbox
    width_px = max(1, x1 - x0)
    height_px = max(1, y1 - y0)

    plane_height = TARGET_HEIGHT * (height_px / subject_height)
    plane_width = TARGET_HEIGHT * (width_px / subject_height)

    subject_world_width = TARGET_HEIGHT * (subject_width / subject_height)
    center_x = ((x0 + x1) / 2.0) / subject_width
    center_y = ((y0 + y1) / 2.0) / subject_height

    x_world = (center_x - 0.5) * subject_world_width
    y_world = (0.5 - center_y) * TARGET_HEIGHT
    return plane_width, plane_height, x_world, y_world, z


def add_segment(
    builder: GLBBuilder,
    segment_name: str,
    segment_image: Image.Image,
    bbox: tuple[int, int, int, int],
    subject_size: tuple[int, int],
    z_offset: float,
) -> tuple[int, list[float]]:
    plane_width, plane_height, x_world, y_world, z_world = segment_transform(bbox, subject_size, z_offset)
    geometry = plane_payload(plane_width, plane_height)
    image_index = builder.add_image(segment_image, "image/png", f"{segment_name}Image")
    if not hasattr(builder, "formal_sampler_index"):
        builder.gltf.samplers.append(
            Sampler(magFilter=LINEAR, minFilter=LINEAR, wrapS=CLAMP_TO_EDGE, wrapT=CLAMP_TO_EDGE)
        )
        builder.formal_sampler_index = len(builder.gltf.samplers) - 1
    builder.gltf.textures.append(
        Texture(name=f"{segment_name}Texture", sampler=builder.formal_sampler_index, source=image_index)
    )
    texture_index = len(builder.gltf.textures) - 1
    material_index = builder.add_material(
        Material(
            name=f"{segment_name}Material",
            alphaMode="MASK",
            alphaCutoff=0.38,
            doubleSided=True,
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorFactor=[1.0, 1.0, 1.0, 1.0],
                metallicFactor=0.0,
                roughnessFactor=0.9,
                baseColorTexture=TextureInfo(index=texture_index),
            ),
        )
    )
    mesh_index = builder.add_mesh(f"Formal_{segment_name}", geometry, material_index)
    return mesh_index, [x_world, y_world, z_world]


def build_formal_walk_animation(builder: GLBBuilder, nodes: dict[str, int]) -> None:
    frame_count = 49
    duration = 10.0
    times = np.linspace(0.0, duration, frame_count, dtype=np.float32).reshape(-1, 1)
    input_accessor = builder.add_accessor(times, FLOAT, SCALAR, ARRAY_BUFFER)
    animation = Animation(name="FormalLookWalk")

    def rotations(values: list[tuple[float, float, float]]) -> int:
        quats = np.asarray([quaternion_from_euler(*angles) for angles in values], dtype=np.float32)
        return builder.add_accessor(quats, FLOAT, VEC4, ARRAY_BUFFER, include_min_max=False)

    def translations(values: list[tuple[float, float, float]]) -> int:
        vectors = np.asarray(values, dtype=np.float32)
        return builder.add_accessor(vectors, FLOAT, VEC3, ARRAY_BUFFER, include_min_max=False)

    normalized = np.linspace(0.0, 1.0, frame_count, dtype=np.float32)
    hips_rot, hips_pos, torso_rot, hip_rot, head_rot = [], [], [], [], []
    left_arm_rot, right_arm_rot = [], []
    left_upper_leg_rot, right_upper_leg_rot = [], []
    left_lower_leg_rot, right_lower_leg_rot = [], []
    left_foot_rot, right_foot_rot = [], []

    for t in normalized:
        phase = PI2 * t
        stride = math.sin(phase)
        opposing = math.sin(phase + math.pi)
        bounce = math.sin(phase * 2.0)
        settle = math.sin(phase + math.pi / 3.0)

        hips_rot.append((0.008 * bounce, 0.02 * math.sin(phase + math.pi / 2.0), 0.012 * bounce))
        hips_pos.append((0.0, 0.02 * abs(bounce), 0.0))
        torso_rot.append((-0.008 * bounce, -0.01 * math.sin(phase + math.pi / 2.0), -0.006 * settle))
        hip_rot.append((0.006 * bounce, 0.0, -0.01 * settle))
        head_rot.append((0.004 * bounce, 0.009 * math.sin(phase + math.pi), -0.004 * bounce))
        left_arm_rot.append((-0.045 * opposing, 0.0, 0.012 * settle))
        right_arm_rot.append((-0.045 * stride, 0.0, -0.012 * settle))
        left_upper_leg_rot.append((0.05 * stride, 0.0, 0.008 * settle))
        right_upper_leg_rot.append((0.05 * opposing, 0.0, -0.008 * settle))
        left_lower_leg_rot.append((-0.03 * max(0.0, opposing), 0.0, 0.0))
        right_lower_leg_rot.append((-0.03 * max(0.0, stride), 0.0, 0.0))
        left_foot_rot.append((-0.022 * max(0.0, stride), 0.0, 0.0))
        right_foot_rot.append((-0.022 * max(0.0, opposing), 0.0, 0.0))

    channels = [
        ("Hips", "rotation", rotations(hips_rot)),
        ("Hips", "translation", translations(hips_pos)),
        ("Torso", "rotation", rotations(torso_rot)),
        ("Hip", "rotation", rotations(hip_rot)),
        ("Head", "rotation", rotations(head_rot)),
        ("LeftArm", "rotation", rotations(left_arm_rot)),
        ("RightArm", "rotation", rotations(right_arm_rot)),
        ("LeftUpperLeg", "rotation", rotations(left_upper_leg_rot)),
        ("RightUpperLeg", "rotation", rotations(right_upper_leg_rot)),
        ("LeftLowerLeg", "rotation", rotations(left_lower_leg_rot)),
        ("RightLowerLeg", "rotation", rotations(right_lower_leg_rot)),
        ("LeftFoot", "rotation", rotations(left_foot_rot)),
        ("RightFoot", "rotation", rotations(right_foot_rot)),
    ]

    for node_name, path, output_accessor in channels:
        builder.add_animation_channel(animation, input_accessor, output_accessor, nodes[node_name], path)

    builder.gltf.animations.append(animation)


def build_asset() -> dict[str, int | float | str]:
    reference_rgb, reference_name = load_reference_image()
    subject_rgba, _ = extract_subject_rgba(reference_rgb)
    build_reference_poster(subject_rgba, reference_rgb)
    cutout_image, cutout_bbox = create_cutout_image(subject_rgba)
    cutout_image.save(CUTOUT_PATH, optimize=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    builder = GLBBuilder()
    mesh_indices: dict[str, int] = {}
    positions: dict[str, list[float]] = {}
    segment_records: list[dict[str, object]] = []

    for segment_name, spec in SEGMENT_SPECS.items():
        segment_image, segment_bbox = crop_segment(subject_rgba, spec)
        segment_path = SEGMENTS_DIR / f"{segment_name}.png"
        segment_image.save(segment_path, optimize=True)
        plane_width, plane_height, x_world, y_world, z_world = segment_transform(segment_bbox, subject_rgba.size, float(spec["z"]))
        mesh_index, node_position = add_segment(builder, segment_name, segment_image, segment_bbox, subject_rgba.size, float(spec["z"]))
        mesh_indices[segment_name] = mesh_index
        positions[segment_name] = node_position
        segment_records.append(
            {
                "name": segment_name,
                "image": f"formal-rig/{segment_name}.png",
                "bbox": [int(value) for value in segment_bbox],
                "plane_width": round(plane_width, 4),
                "plane_height": round(plane_height, 4),
                "position": [round(x_world, 4), round(y_world, 4), round(z_world, 4)],
            }
        )

    nodes: dict[str, int] = {}
    nodes["Head"] = builder.add_node("Head", mesh_indices["Head"], translation=positions["Head"])
    nodes["Torso"] = builder.add_node("Torso", mesh_indices["Torso"], translation=positions["Torso"])
    nodes["Hip"] = builder.add_node("Hip", mesh_indices["Hip"], translation=positions["Hip"])
    nodes["LeftArm"] = builder.add_node("LeftArm", mesh_indices["LeftArm"], translation=positions["LeftArm"])
    nodes["RightArm"] = builder.add_node("RightArm", mesh_indices["RightArm"], translation=positions["RightArm"])
    nodes["LeftUpperLeg"] = builder.add_node("LeftUpperLeg", mesh_indices["LeftUpperLeg"], translation=positions["LeftUpperLeg"])
    nodes["RightUpperLeg"] = builder.add_node("RightUpperLeg", mesh_indices["RightUpperLeg"], translation=positions["RightUpperLeg"])
    nodes["LeftLowerLeg"] = builder.add_node("LeftLowerLeg", mesh_indices["LeftLowerLeg"], translation=positions["LeftLowerLeg"])
    nodes["RightLowerLeg"] = builder.add_node("RightLowerLeg", mesh_indices["RightLowerLeg"], translation=positions["RightLowerLeg"])
    nodes["LeftFoot"] = builder.add_node("LeftFoot", mesh_indices["LeftFoot"], translation=positions["LeftFoot"])
    nodes["RightFoot"] = builder.add_node("RightFoot", mesh_indices["RightFoot"], translation=positions["RightFoot"])
    nodes["Hips"] = builder.add_node(
        "Hips",
        None,
        children=[
            nodes["Torso"],
            nodes["Hip"],
            nodes["Head"],
            nodes["LeftArm"],
            nodes["RightArm"],
            nodes["LeftUpperLeg"],
            nodes["RightUpperLeg"],
            nodes["LeftLowerLeg"],
            nodes["RightLowerLeg"],
            nodes["LeftFoot"],
            nodes["RightFoot"],
        ],
    )
    root = builder.add_node("FormalImageLook", None, children=[nodes["Hips"]])

    build_formal_walk_animation(builder, nodes)
    builder.finalize([root], MODEL_PATH)

    total_triangles = len(SEGMENT_SPECS) * 2
    glb_size = MODEL_PATH.stat().st_size
    cutout_width, cutout_height = cutout_image.size
    metadata = {
        "inspiration": "premium men's formal outfit",
        "reference_image": reference_name,
        "segments": len(SEGMENT_SPECS),
        "total_scene_triangles": int(total_triangles),
        "meshes": len(builder.gltf.meshes),
        "nodes": len(builder.gltf.nodes),
        "animations": len(builder.gltf.animations),
        "duration_seconds": 10.0,
        "render_style": "layered image rig derived from uploaded reference",
        "asset_mode": "rig",
        "cutout_image": CUTOUT_PATH.name,
        "cutout_bbox": [int(value) for value in cutout_bbox],
        "cutout_width": int(cutout_width),
        "cutout_height": int(cutout_height),
        "cutout_plane_width": round(TARGET_HEIGHT * (cutout_width / max(cutout_height, 1)), 4),
        "cutout_plane_height": round(TARGET_HEIGHT, 4),
        "segments_data": segment_records,
        "size_bytes": int(glb_size),
        "size_mb": round(glb_size / (1024 * 1024), 4),
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    metadata = build_asset()
    print(json.dumps({"model": str(MODEL_PATH), "poster": str(POSTER_PATH), "metadata": metadata}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
