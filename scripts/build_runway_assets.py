from __future__ import annotations

import io
import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFilter
from pygltflib import (
    Accessor,
    Animation,
    AnimationChannel,
    AnimationChannelTarget,
    AnimationSampler,
    ARRAY_BUFFER,
    Asset,
    Attributes,
    Buffer,
    BufferView,
    ELEMENT_ARRAY_BUFFER,
    FLOAT,
    GLTF2,
    Image as GLTFImage,
    Material,
    Mesh,
    Node,
    NormalMaterialTexture,
    PbrMetallicRoughness,
    Primitive,
    Sampler,
    Scene,
    SCALAR,
    Texture,
    TextureInfo,
    UNSIGNED_INT,
    UNSIGNED_SHORT,
    VEC2,
    VEC3,
    VEC4,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "app" / "static"
MODELS_DIR = STATIC_ROOT / "models"
IMAGES_DIR = STATIC_ROOT / "images"

MODEL_PATH = MODELS_DIR / "satin-slip-dress.glb"
POSTER_PATH = IMAGES_DIR / "satin-slip-poster.jpg"
METADATA_PATH = MODELS_DIR / "satin-slip-dress.json"

TEXTURE_SIZE = 1024
POSTER_SIZE = (1600, 1000)
PI2 = math.pi * 2.0

logging.getLogger("trimesh").setLevel(logging.ERROR)


@dataclass
class GeometryPayload:
    positions: np.ndarray
    indices: np.ndarray
    normals: np.ndarray | None = None
    uvs: np.ndarray | None = None
    morph_positions: dict[str, np.ndarray] = field(default_factory=dict)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = clamp((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def gaussian(value: float, center: float, width: float) -> float:
    if width == 0:
        return 0.0
    return math.exp(-((value - center) ** 2) / (2.0 * width * width))


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
    lengths[lengths == 0] = 1.0
    return vectors / lengths


def compute_vertex_normals(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    normals = np.zeros_like(positions, dtype=np.float32)
    triangles = positions[indices.reshape(-1, 3)]
    face_normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    for tri_index, face in enumerate(indices.reshape(-1, 3)):
        normals[face] += face_normals[tri_index]
    return normalize_vectors(normals.astype(np.float32))


def quaternion_from_euler(x: float, y: float, z: float) -> np.ndarray:
    cx, cy, cz = math.cos(x / 2.0), math.cos(y / 2.0), math.cos(z / 2.0)
    sx, sy, sz = math.sin(x / 2.0), math.sin(y / 2.0), math.sin(z / 2.0)
    return np.array(
        [
            sx * cy * cz + cx * sy * sz,
            cx * sy * cz - sx * cy * sz,
            cx * cy * sz + sx * sy * cz,
            cx * cy * cz - sx * sy * sz,
        ],
        dtype=np.float32,
    )


def make_grid_indices(columns: int, rows: int, reverse: bool = False) -> np.ndarray:
    faces: list[list[int]] = []
    stride = columns + 1
    for row in range(rows):
        for col in range(columns):
            a = row * stride + col
            b = a + 1
            c = a + stride
            d = c + 1
            if reverse:
                faces.append([a, c, b])
                faces.append([b, c, d])
            else:
                faces.append([a, b, c])
                faces.append([b, d, c])
    return np.asarray(faces, dtype=np.uint32).reshape(-1)


def size_factor(size_key: str) -> float:
    return {"size2": -1.0, "size6": 0.0, "size10": 1.0}[size_key]


def bodice_top(theta: float) -> float:
    u = ((theta / PI2) + 0.5) % 1.0
    front = math.exp(-((u - 0.5) / 0.18) ** 2)
    strap_left = math.exp(-((u - 0.39) / 0.045) ** 2)
    strap_right = math.exp(-((u - 0.61) / 0.045) ** 2)
    back = max(math.exp(-(u / 0.14) ** 2), math.exp(-((u - 1.0) / 0.14) ** 2))
    top = 1.28 + 0.16 * back + 0.14 * max(strap_left, strap_right) - 0.04 * front
    return clamp(top, 1.22, 1.48)


def bodice_position(theta: float, vertical: float, size_key: str) -> np.ndarray:
    top = bodice_top(theta)
    waist = 1.01
    y = top * (1.0 - vertical) + waist * vertical

    bust = gaussian(y, 1.24, 0.12)
    waist_tuck = gaussian(y, 1.02, 0.08)
    underbust = gaussian(y, 1.11, 0.05)
    fit = size_factor(size_key)

    rx = 0.148 + 0.042 * bust - 0.028 * waist_tuck
    rz = 0.116 + 0.058 * bust - 0.021 * waist_tuck + 0.006 * underbust
    fit_x = 1.0 + fit * (0.04 * bust + 0.054 * waist_tuck)
    fit_z = 1.0 + fit * (0.046 * bust + 0.044 * waist_tuck)

    x = rx * fit_x * math.sin(theta)
    z = rz * fit_z * math.cos(theta)
    bias_pull = 0.012 * (1.0 - vertical) * math.sin(theta * 2.1 + 0.7)
    x += bias_pull * math.cos(theta)
    z += bias_pull * math.sin(theta)
    return np.array([x, y, z], dtype=np.float32)


def skirt_position(theta: float, vertical: float, size_key: str) -> np.ndarray:
    waist = 1.01
    hem = 0.18
    y = waist * (1.0 - vertical) + hem * vertical

    hip = gaussian(y, 0.86, 0.16)
    thigh = gaussian(y, 0.64, 0.18)
    flare = smoothstep(waist, hem, y)
    fit = size_factor(size_key)

    rx = 0.148 + 0.056 * hip + 0.156 * (flare ** 1.28)
    rz = 0.124 + 0.086 * hip + 0.212 * (flare ** 1.22)
    fit_x = 1.0 + fit * (0.036 + 0.036 * hip + 0.024 * thigh)
    fit_z = 1.0 + fit * (0.042 + 0.046 * hip + 0.028 * thigh)

    theta_warp = theta + 0.12 * (flare ** 1.35) * math.sin(theta + 0.45)
    radial_noise = 0.016 * flare * math.sin(theta * 2.0 + 0.55) + 0.008 * flare * math.sin(theta * 5.0 - 0.2)
    x = (rx * fit_x + radial_noise) * math.sin(theta_warp)
    z = (rz * fit_z - radial_noise * 0.65) * math.cos(theta_warp)
    y += 0.013 * flare * math.sin(theta * 3.1 + 0.8)
    return np.array([x, y, z], dtype=np.float32)


def build_dress_surface(
    theta_start: float,
    theta_end: float,
    theta_segments: int,
    vertical_segments: int,
    position_fn,
    uv_v_start: float,
    uv_v_end: float,
    thickness: float = 0.008,
) -> GeometryPayload:
    size_keys = ("size2", "size6", "size10")
    theta_values = np.linspace(theta_start, theta_end, theta_segments + 1, dtype=np.float32)
    vertical_values = np.linspace(0.0, 1.0, vertical_segments + 1, dtype=np.float32)

    variant_positions: dict[str, list[np.ndarray]] = {key: [] for key in size_keys}
    uvs: list[list[float]] = []

    for vertical in vertical_values:
        for theta in theta_values:
            global_u = (((float(theta) / PI2) + 0.5) % 1.0)
            uv_v = uv_v_start + (uv_v_end - uv_v_start) * float(vertical)
            uvs.append([global_u, uv_v])
            for size_key in size_keys:
                variant_positions[size_key].append(position_fn(float(theta), float(vertical), size_key))

    base_outer = np.asarray(variant_positions["size6"], dtype=np.float32)
    inner_variants: dict[str, list[np.ndarray]] = {key: [] for key in size_keys}
    for size_key in size_keys:
        for position in variant_positions[size_key]:
            horizontal = np.array([position[0], 0.0, position[2]], dtype=np.float32)
            inward = normalize_vectors(horizontal.reshape(1, 3))[0]
            inner_variants[size_key].append(position - inward * thickness)

    texcoords = np.vstack([np.asarray(uvs, dtype=np.float32), np.asarray(uvs, dtype=np.float32)])
    base_positions = np.vstack([base_outer, np.asarray(inner_variants["size6"], dtype=np.float32)])
    size2_positions = np.vstack([np.asarray(variant_positions["size2"], dtype=np.float32), np.asarray(inner_variants["size2"], dtype=np.float32)])
    size10_positions = np.vstack([np.asarray(variant_positions["size10"], dtype=np.float32), np.asarray(inner_variants["size10"], dtype=np.float32)])

    outer_indices = make_grid_indices(theta_segments, vertical_segments)
    inner_indices = make_grid_indices(theta_segments, vertical_segments, reverse=True) + len(base_outer)
    indices = np.concatenate([outer_indices, inner_indices]).astype(np.uint32)

    return GeometryPayload(
        positions=base_positions,
        indices=indices,
        normals=compute_vertex_normals(base_positions, indices),
        uvs=texcoords,
        morph_positions={
            "size2": size2_positions - base_positions,
            "size10": size10_positions - base_positions,
        },
    )


def transform_payload_to_local(payload: GeometryPayload, pivot: np.ndarray) -> GeometryPayload:
    return GeometryPayload(
        positions=payload.positions - pivot,
        indices=payload.indices.copy(),
        normals=None if payload.normals is None else payload.normals.copy(),
        uvs=None if payload.uvs is None else payload.uvs.copy(),
        morph_positions={key: value.copy() for key, value in payload.morph_positions.items()},
    )


def mesh_payload_from_trimesh(mesh: trimesh.Trimesh) -> GeometryPayload:
    return GeometryPayload(
        positions=np.asarray(mesh.vertices, dtype=np.float32),
        indices=np.asarray(mesh.faces.reshape(-1), dtype=np.uint32),
        normals=np.asarray(mesh.vertex_normals, dtype=np.float32),
    )


def make_capsule(radius: float, height: float, sections: int = 18, count: list[int] | None = None) -> trimesh.Trimesh:
    count = count or [sections, sections]
    return trimesh.creation.capsule(radius=radius, height=height, count=count)


def make_sphere(radius: float, count: list[int] | None = None) -> trimesh.Trimesh:
    count = count or [20, 20]
    return trimesh.creation.uv_sphere(radius=radius, count=count)


def make_cylinder(radius: float, start: np.ndarray, end: np.ndarray, sections: int = 18) -> trimesh.Trimesh:
    return trimesh.creation.cylinder(radius=radius, segment=[start.tolist(), end.tolist()], sections=sections)


def component_type_for_indices(indices: np.ndarray) -> int:
    return UNSIGNED_SHORT if int(indices.max()) < 65535 else UNSIGNED_INT


def create_satin_base_texture(size: int) -> Image.Image:
    rng = np.random.default_rng(20260331)
    u = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    diagonal = 0.5 + 0.5 * np.sin((uu * 1.45 + vv * 5.8) * PI2)
    ripple = 0.5 + 0.5 * np.sin((uu * 12.0 - vv * 17.0) * PI2)
    weave = 0.5 + 0.5 * np.sin((uu * 34.0 + vv * 8.0) * PI2)
    noise = rng.normal(0.0, 0.12, (size, size)).astype(np.float32)
    highlight = np.exp(-(((uu - 0.5) / 0.16) ** 2 + ((vv - 0.53) / 0.34) ** 2))
    sidelights = np.exp(-(((uu - 0.21) / 0.06) ** 2 + ((vv - 0.68) / 0.2) ** 2)) + np.exp(-(((uu - 0.79) / 0.06) ** 2 + ((vv - 0.65) / 0.2) ** 2))

    luminance = 0.45 + 0.18 * diagonal + 0.1 * ripple + 0.05 * weave + 0.11 * highlight + 0.04 * sidelights + noise * 0.02
    luminance -= vv * 0.12
    luminance = np.clip(luminance, 0.18, 0.98)

    alpha = np.ones_like(luminance, dtype=np.float32)
    bodice = vv < 0.36
    front_dist = np.abs(uu - 0.5)
    neckline = 0.1 + 0.14 * np.clip(1.0 - front_dist / 0.16, 0.0, 1.0) ** 1.35
    front_body = bodice & (uu > 0.24) & (uu < 0.76) & (vv >= neckline)
    side_body = bodice & (vv > 0.18) & (uu > 0.18) & (uu < 0.82)
    back_body = bodice & ((uu < 0.14) | (uu > 0.86)) & (vv > 0.02)
    straps = bodice & (vv < 0.12) & ((np.abs(uu - 0.39) < 0.024) | (np.abs(uu - 0.61) < 0.024))
    alpha[bodice] = 0.0
    alpha[front_body | side_body | back_body | straps] = 1.0

    alpha_image = Image.fromarray((alpha * 255.0).astype(np.uint8), mode="L").filter(ImageFilter.GaussianBlur(1.5))
    alpha = np.asarray(alpha_image, dtype=np.float32) / 255.0
    alpha = (alpha > 0.35).astype(np.float32)

    rgb = np.stack(
        [
            np.clip(luminance * 0.86 + 0.08, 0.0, 1.0),
            np.clip(luminance * 0.94 + 0.05, 0.0, 1.0),
            np.clip(luminance * 0.82 + 0.06, 0.0, 1.0),
        ],
        axis=-1,
    )
    rgba = np.concatenate([rgb, alpha[..., None]], axis=-1)
    return Image.fromarray((rgba * 255.0).astype(np.uint8), mode="RGBA")


def create_metallic_roughness_texture(size: int) -> Image.Image:
    u = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    wrinkle = 0.5 + 0.5 * np.sin((uu * 7.0 + vv * 5.0) * PI2)
    bias = 0.5 + 0.5 * np.sin((uu * 16.0 - vv * 23.0) * PI2)
    highlight = np.exp(-(((uu - 0.5) / 0.18) ** 2 + ((vv - 0.5) / 0.36) ** 2))

    roughness = 0.1 + 0.16 * wrinkle + 0.08 * bias + 0.06 * vv - 0.1 * highlight
    roughness = np.clip(roughness, 0.035, 0.62)
    metallic = 0.04 + 0.03 * highlight + 0.02 * (1.0 - roughness)
    metallic = np.clip(metallic, 0.02, 0.12)

    packed = np.zeros((size, size, 3), dtype=np.uint8)
    packed[..., 0] = 255
    packed[..., 1] = (roughness * 255.0).astype(np.uint8)
    packed[..., 2] = (metallic * 255.0).astype(np.uint8)
    return Image.fromarray(packed, mode="RGB")


def create_normal_texture(size: int) -> Image.Image:
    u = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, size, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    height = (
        0.3 * np.sin((uu * 11.0 + vv * 5.5) * PI2)
        + 0.22 * np.sin((uu * 24.0 - vv * 13.0) * PI2)
        + 0.18 * np.sin((uu * 40.0 + vv * 6.0) * PI2)
        + 0.34 * np.exp(-(((uu - 0.48) / 0.2) ** 2 + ((vv - 0.6) / 0.32) ** 2))
    ).astype(np.float32)

    dx = np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)
    dy = np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)
    normals = np.dstack([-dx * 7.5, -dy * 7.5, np.ones_like(dx, dtype=np.float32)]).reshape(-1, 3)
    normals = normalize_vectors(normals).reshape(size, size, 3)
    encoded = ((normals * 0.5 + 0.5) * 255.0).astype(np.uint8)
    return Image.fromarray(encoded, mode="RGB")


def build_poster(base_texture: Image.Image) -> None:
    width, height = POSTER_SIZE
    background = Image.new("RGB", POSTER_SIZE, "#030811")
    pixels = background.load()
    top = (6, 17, 33)
    mid = (8, 28, 43)
    bottom = (1, 5, 13)
    for y in range(height):
        t = y / max(1, height - 1)
        if t < 0.46:
            mix = t / 0.46
            row = tuple(int(top[index] + (mid[index] - top[index]) * mix) for index in range(3))
        else:
            mix = (t - 0.46) / 0.54
            row = tuple(int(mid[index] + (bottom[index] - mid[index]) * mix) for index in range(3))
        for x in range(width):
            pixels[x, y] = row

    composition = background.convert("RGBA")
    glow = Image.new("RGBA", POSTER_SIZE, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((220, 80, 1380, 700), fill=(16, 196, 160, 62))
    glow_draw.ellipse((1020, 40, 1540, 620), fill=(255, 220, 174, 36))
    glow_draw.ellipse((110, 160, 640, 740), fill=(45, 126, 204, 26))
    composition = Image.alpha_composite(composition, glow.filter(ImageFilter.GaussianBlur(88)))

    runway = Image.new("RGBA", POSTER_SIZE, (0, 0, 0, 0))
    runway_draw = ImageDraw.Draw(runway)
    runway_draw.polygon([(510, height), (676, 562), (934, 562), (1094, height)], fill=(8, 22, 39, 220))
    runway_draw.rounded_rectangle((610, 786, 990, 844), radius=112, outline=(99, 242, 208, 160), width=6)
    for stripe in range(0, 280, 34):
        inset = int(stripe * 0.24)
        runway_draw.line([(676 - inset, 562 + stripe), (934 + inset, 562 + stripe)], fill=(88, 224, 193, max(20, 112 - stripe // 3)), width=2)
    composition = Image.alpha_composite(composition, runway.filter(ImageFilter.GaussianBlur(2)))

    silhouette = Image.new("RGBA", POSTER_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(silhouette)
    draw.ellipse((760, 108, 842, 188), fill=(27, 24, 26, 160))
    draw.rounded_rectangle((786, 184, 814, 238), radius=12, fill=(34, 28, 30, 142))
    draw.line([(734, 196), (670, 352)], fill=(44, 42, 45, 110), width=22)
    draw.line([(866, 196), (934, 366)], fill=(44, 42, 45, 110), width=22)
    composition = Image.alpha_composite(composition, silhouette.filter(ImageFilter.GaussianBlur(4)))

    dress_texture = base_texture.resize((520, 860), Image.Resampling.LANCZOS)
    dress_mask = dress_texture.getchannel("A").resize((520, 860), Image.Resampling.LANCZOS)
    emerald = Image.new("RGBA", dress_texture.size, (18, 127, 104, 255))
    pearl = Image.new("RGBA", dress_texture.size, (214, 194, 158, 255))
    dress = Image.blend(emerald, pearl, 0.14)
    dress = Image.composite(dress, Image.new("RGBA", dress_texture.size, (0, 0, 0, 0)), dress_mask)
    sheen = dress_texture.convert("L").filter(ImageFilter.GaussianBlur(4))
    dress = Image.blend(dress, Image.merge("RGBA", (sheen, sheen, sheen, dress_mask)), 0.28)
    composition.alpha_composite(dress, dest=(540, 150))

    reflection = dress.crop((58, 380, 468, 852)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).resize((402, 178), Image.Resampling.LANCZOS)
    reflection.putalpha(reflection.getchannel("A").point(lambda value: int(value * 0.22)))
    composition.alpha_composite(reflection.filter(ImageFilter.GaussianBlur(10)), dest=(598, 738))

    rings = Image.new("RGBA", POSTER_SIZE, (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(rings)
    ring_draw.ellipse((506, 796, 1094, 882), outline=(94, 238, 204, 108), width=10)
    ring_draw.ellipse((468, 766, 1134, 904), outline=(255, 247, 220, 24), width=5)
    composition = Image.alpha_composite(composition, rings.filter(ImageFilter.GaussianBlur(8)))

    POSTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    composition.convert("RGB").save(POSTER_PATH, quality=92, optimize=True, progressive=True)


class GLBBuilder:
    def __init__(self) -> None:
        self.gltf = GLTF2(asset=Asset(generator="StyleBridge procedural runway builder", version="2.0"))
        self.gltf.buffers = [Buffer(byteLength=0)]
        self.binary_blob = bytearray()
        self.default_sampler = self._add_sampler()

    def _align(self) -> None:
        while len(self.binary_blob) % 4:
            self.binary_blob.append(0)

    def _add_sampler(self) -> int:
        self.gltf.samplers.append(Sampler(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497))
        return len(self.gltf.samplers) - 1

    def add_blob(self, blob: bytes, target: int | None = None) -> int:
        self._align()
        offset = len(self.binary_blob)
        self.binary_blob.extend(blob)
        self.gltf.bufferViews.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(blob), target=target))
        return len(self.gltf.bufferViews) - 1

    def add_accessor(
        self,
        array: np.ndarray,
        component_type: int,
        accessor_type: str,
        target: int | None = None,
        include_min_max: bool = True,
    ) -> int:
        contiguous = np.ascontiguousarray(array)
        view_index = self.add_blob(contiguous.tobytes(), target)
        accessor = Accessor(bufferView=view_index, componentType=component_type, count=int(contiguous.shape[0]), type=accessor_type)
        if include_min_max and contiguous.size:
            reshaped = contiguous.reshape(contiguous.shape[0], -1)
            accessor.min = reshaped.min(axis=0).astype(float).tolist()
            accessor.max = reshaped.max(axis=0).astype(float).tolist()
        self.gltf.accessors.append(accessor)
        return len(self.gltf.accessors) - 1

    def add_image(self, image: Image.Image, mime_type: str, name: str) -> int:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG" if mime_type == "image/png" else "JPEG", optimize=True, quality=92)
        view_index = self.add_blob(buffer.getvalue())
        self.gltf.images.append(GLTFImage(bufferView=view_index, mimeType=mime_type, name=name))
        return len(self.gltf.images) - 1

    def add_texture(self, image_index: int, name: str) -> int:
        self.gltf.textures.append(Texture(name=name, sampler=self.default_sampler, source=image_index))
        return len(self.gltf.textures) - 1

    def add_material(self, material: Material) -> int:
        self.gltf.materials.append(material)
        return len(self.gltf.materials) - 1

    def add_mesh(self, name: str, geometry: GeometryPayload, material_index: int, target_names: list[str] | None = None) -> int:
        attributes = Attributes(
            POSITION=self.add_accessor(geometry.positions.astype(np.float32), FLOAT, VEC3, ARRAY_BUFFER),
            NORMAL=self.add_accessor(geometry.normals.astype(np.float32), FLOAT, VEC3, ARRAY_BUFFER) if geometry.normals is not None else None,
            TEXCOORD_0=self.add_accessor(geometry.uvs.astype(np.float32), FLOAT, VEC2, ARRAY_BUFFER) if geometry.uvs is not None else None,
        )
        index_type = component_type_for_indices(geometry.indices)
        index_array = geometry.indices.astype(np.uint16 if index_type == UNSIGNED_SHORT else np.uint32).reshape(-1, 1)
        primitive = Primitive(
            attributes=attributes,
            indices=self.add_accessor(index_array, index_type, SCALAR, ELEMENT_ARRAY_BUFFER),
            material=material_index,
        )
        if geometry.morph_positions:
            primitive.targets = [
                Attributes(POSITION=self.add_accessor(geometry.morph_positions["size2"].astype(np.float32), FLOAT, VEC3, ARRAY_BUFFER, include_min_max=False)),
                Attributes(POSITION=self.add_accessor(geometry.morph_positions["size10"].astype(np.float32), FLOAT, VEC3, ARRAY_BUFFER, include_min_max=False)),
            ]
        mesh = Mesh(name=name, primitives=[primitive], weights=[0.0, 0.0] if geometry.morph_positions else [])
        if target_names:
            mesh.extras = {"targetNames": target_names}
        self.gltf.meshes.append(mesh)
        return len(self.gltf.meshes) - 1

    def add_node(
        self,
        name: str,
        mesh_index: int | None = None,
        translation: list[float] | None = None,
        rotation: list[float] | None = None,
        children: list[int] | None = None,
    ) -> int:
        node = Node(name=name, mesh=mesh_index)
        if translation is not None:
            node.translation = translation
        if rotation is not None:
            node.rotation = rotation
        if children:
            node.children = children
        self.gltf.nodes.append(node)
        return len(self.gltf.nodes) - 1

    def add_animation_channel(self, animation: Animation, input_accessor: int, output_accessor: int, node_index: int, path: str) -> None:
        sampler_index = len(animation.samplers)
        animation.samplers.append(AnimationSampler(input=input_accessor, output=output_accessor, interpolation="LINEAR"))
        animation.channels.append(AnimationChannel(sampler=sampler_index, target=AnimationChannelTarget(node=node_index, path=path)))

    def finalize(self, scene_nodes: list[int], output_path: Path) -> None:
        self.gltf.scene = 0
        self.gltf.scenes = [Scene(nodes=scene_nodes)]
        self.gltf.buffers[0].byteLength = len(self.binary_blob)
        self.gltf.set_binary_blob(bytes(self.binary_blob))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.gltf.save_binary(output_path)


def create_avatar_geometry() -> dict[str, GeometryPayload]:
    avatar: dict[str, GeometryPayload] = {}
    chest_pivot = np.array([0.0, 1.17, 0.0], dtype=np.float32)
    head_pivot = np.array([0.0, 1.44, 0.0], dtype=np.float32)

    chest = make_capsule(0.118, 0.22, count=[18, 20])
    chest.apply_scale([1.04, 1.12, 0.88])
    chest.apply_translation([0.0, 1.305, 0.0])
    avatar["Avatar_Chest"] = transform_payload_to_local(mesh_payload_from_trimesh(chest), chest_pivot)

    neck = make_cylinder(0.045, np.array([0.0, 1.37, 0.0]), np.array([0.0, 1.47, 0.0]), sections=18)
    avatar["Avatar_Neck"] = transform_payload_to_local(mesh_payload_from_trimesh(neck), chest_pivot)

    head = make_sphere(0.098, count=[18, 20])
    head.apply_scale([1.0, 1.1, 0.96])
    head.apply_translation([0.0, 1.60, 0.0])
    avatar["Avatar_Head"] = transform_payload_to_local(mesh_payload_from_trimesh(head), head_pivot)

    upper_arm = make_cylinder(0.048, np.array([0.0, 0.0, 0.0]), np.array([0.0, -0.24, 0.0]), sections=16)
    avatar["Avatar_LeftUpperArm"] = mesh_payload_from_trimesh(upper_arm)
    avatar["Avatar_RightUpperArm"] = mesh_payload_from_trimesh(upper_arm.copy())

    lower_arm = make_cylinder(0.038, np.array([0.0, 0.0, 0.0]), np.array([0.0, -0.24, 0.0]), sections=16)
    avatar["Avatar_LeftLowerArm"] = mesh_payload_from_trimesh(lower_arm)
    avatar["Avatar_RightLowerArm"] = mesh_payload_from_trimesh(lower_arm.copy())

    upper_leg = make_cylinder(0.072, np.array([0.0, 0.0, 0.0]), np.array([0.0, -0.4, 0.0]), sections=18)
    upper_leg.apply_scale([0.92, 1.0, 1.0])
    avatar["Avatar_LeftUpperLeg"] = mesh_payload_from_trimesh(upper_leg)
    avatar["Avatar_RightUpperLeg"] = mesh_payload_from_trimesh(upper_leg.copy())

    lower_leg = make_cylinder(0.056, np.array([0.0, 0.0, 0.0]), np.array([0.0, -0.43, 0.0]), sections=18)
    lower_leg.apply_scale([0.85, 1.0, 0.92])
    avatar["Avatar_LeftLowerLeg"] = mesh_payload_from_trimesh(lower_leg)
    avatar["Avatar_RightLowerLeg"] = mesh_payload_from_trimesh(lower_leg.copy())

    foot = trimesh.creation.box(extents=[0.085, 0.03, 0.22])
    foot.apply_translation([0.0, -0.015, 0.07])
    avatar["Avatar_LeftFoot"] = mesh_payload_from_trimesh(foot)
    avatar["Avatar_RightFoot"] = mesh_payload_from_trimesh(foot.copy())
    return avatar


def create_strap_geometry(side: str) -> GeometryPayload:
    direction = -1.0 if side == "left" else 1.0
    front = np.array([0.092 * direction, 1.44, 0.116], dtype=np.float32)
    back = np.array([0.135 * direction, 1.405, -0.092], dtype=np.float32)
    strap = make_cylinder(0.009, front, back, sections=18)
    payload = mesh_payload_from_trimesh(strap)
    positions = payload.positions
    bounds_min = positions.min(axis=0)
    bounds_max = positions.max(axis=0)
    span_y = max(bounds_max[1] - bounds_min[1], 1e-4)
    u = np.full((len(positions),), 0.18 if side == "left" else 0.82, dtype=np.float32)
    v = 0.76 + 0.18 * ((positions[:, 1] - bounds_min[1]) / span_y)
    payload.uvs = np.column_stack([u, v]).astype(np.float32)
    return payload


def build_runway_walk_animation(builder: GLBBuilder, nodes: dict[str, int]) -> None:
    frame_count = 41
    duration = 10.0
    times = np.linspace(0.0, duration, frame_count, dtype=np.float32).reshape(-1, 1)
    input_accessor = builder.add_accessor(times, FLOAT, SCALAR, ARRAY_BUFFER)
    animation = Animation(name="RunwayWalkLoop")

    def rotations_from_eulers(values: list[tuple[float, float, float]]) -> int:
        quaternions = np.asarray([quaternion_from_euler(*angles) for angles in values], dtype=np.float32)
        return builder.add_accessor(quaternions, FLOAT, VEC4, ARRAY_BUFFER, include_min_max=False)

    def translations_from_vectors(values: list[tuple[float, float, float]]) -> int:
        return builder.add_accessor(np.asarray(values, dtype=np.float32), FLOAT, VEC3, ARRAY_BUFFER, include_min_max=False)

    normalized = np.linspace(0.0, 1.0, frame_count, dtype=np.float32)
    hips_rot, hips_pos, chest_rot, head_rot = [], [], [], []
    left_upper_arm, right_upper_arm, left_lower_arm, right_lower_arm = [], [], [], []
    left_upper_leg, right_upper_leg, left_lower_leg, right_lower_leg = [], [], [], []
    left_foot, right_foot = [], []
    skirt_front, skirt_right, skirt_back, skirt_left = [], [], [], []

    for t in normalized:
        phase = PI2 * t
        stride = math.sin(phase)
        opposing = math.sin(phase + math.pi)
        bounce = math.sin(phase * 2.0)
        settle = math.sin(phase * 2.0 + math.pi / 3.0)

        hips_rot.append((0.015 * bounce, 0.05 * math.sin(phase + math.pi / 2.0), 0.032 * bounce))
        hips_pos.append((0.0, 1.03 + 0.018 * abs(bounce), 0.0))
        chest_rot.append((-0.028 * bounce, -0.04 * math.sin(phase + math.pi / 2.0), -0.015 * bounce))
        head_rot.append((0.012 * bounce, 0.014 * math.sin(phase + math.pi), -0.012 * bounce))

        left_upper_arm.append((0.24 * opposing, 0.04, 0.08))
        right_upper_arm.append((0.24 * stride, -0.04, -0.08))
        left_lower_arm.append((0.09 + 0.1 * max(0.0, -opposing), 0.0, 0.0))
        right_lower_arm.append((0.09 + 0.1 * max(0.0, -stride), 0.0, 0.0))
        left_upper_leg.append((0.48 * stride, 0.04 * math.sin(phase + math.pi / 2.0), 0.02))
        right_upper_leg.append((0.48 * opposing, -0.04 * math.sin(phase + math.pi / 2.0), -0.02))
        left_lower_leg.append((0.18 + 0.42 * max(0.0, -stride), 0.0, 0.0))
        right_lower_leg.append((0.18 + 0.42 * max(0.0, -opposing), 0.0, 0.0))
        left_foot.append((-0.08 * max(0.0, stride), 0.0, 0.0))
        right_foot.append((-0.08 * max(0.0, opposing), 0.0, 0.0))

        skirt_front.append((0.04 * stride, 0.02 * math.sin(phase + 0.4), 0.02 * settle))
        skirt_right.append((0.03 * settle, -0.04 - 0.03 * stride, 0.015 * bounce))
        skirt_back.append((-0.028 * bounce, -0.018 * math.sin(phase + 0.8), -0.018 * settle))
        skirt_left.append((0.03 * settle, 0.04 + 0.03 * opposing, -0.015 * bounce))

    channels = [
        ("Hips", "rotation", rotations_from_eulers(hips_rot)),
        ("Hips", "translation", translations_from_vectors(hips_pos)),
        ("Chest", "rotation", rotations_from_eulers(chest_rot)),
        ("Head", "rotation", rotations_from_eulers(head_rot)),
        ("LeftUpperArm", "rotation", rotations_from_eulers(left_upper_arm)),
        ("RightUpperArm", "rotation", rotations_from_eulers(right_upper_arm)),
        ("LeftLowerArm", "rotation", rotations_from_eulers(left_lower_arm)),
        ("RightLowerArm", "rotation", rotations_from_eulers(right_lower_arm)),
        ("LeftUpperLeg", "rotation", rotations_from_eulers(left_upper_leg)),
        ("RightUpperLeg", "rotation", rotations_from_eulers(right_upper_leg)),
        ("LeftLowerLeg", "rotation", rotations_from_eulers(left_lower_leg)),
        ("RightLowerLeg", "rotation", rotations_from_eulers(right_lower_leg)),
        ("LeftFoot", "rotation", rotations_from_eulers(left_foot)),
        ("RightFoot", "rotation", rotations_from_eulers(right_foot)),
        ("DressFront", "rotation", rotations_from_eulers(skirt_front)),
        ("DressRight", "rotation", rotations_from_eulers(skirt_right)),
        ("DressBack", "rotation", rotations_from_eulers(skirt_back)),
        ("DressLeft", "rotation", rotations_from_eulers(skirt_left)),
    ]

    for node_name, path, output_accessor in channels:
        builder.add_animation_channel(animation, input_accessor, output_accessor, nodes[node_name], path)

    builder.gltf.animations.append(animation)


def build_asset() -> dict[str, int | float | list[str] | dict[str, str]]:
    base_texture = create_satin_base_texture(TEXTURE_SIZE)
    metallic_roughness_texture = create_metallic_roughness_texture(TEXTURE_SIZE)
    normal_texture = create_normal_texture(TEXTURE_SIZE)
    build_poster(base_texture)
    compressed_base_texture = base_texture.quantize(colors=192, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)

    builder = GLBBuilder()

    base_color_image = builder.add_image(compressed_base_texture, "image/png", "DressBaseColor")
    metallic_roughness_image = builder.add_image(metallic_roughness_texture, "image/png", "DressMetallicRoughness")
    normal_image = builder.add_image(normal_texture, "image/jpeg", "DressNormal")

    base_color_texture = builder.add_texture(base_color_image, "DressBaseColor")
    metallic_roughness_texture_index = builder.add_texture(metallic_roughness_image, "DressMetallicRoughness")
    normal_texture_index = builder.add_texture(normal_image, "DressNormal")

    dress_material = builder.add_material(
        Material(
            name="EmeraldLiquidSatin",
            alphaMode="MASK",
            alphaCutoff=0.52,
            doubleSided=True,
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorFactor=[0.094, 0.463, 0.376, 1.0],
                metallicFactor=0.06,
                roughnessFactor=0.14,
                baseColorTexture=TextureInfo(index=base_color_texture),
                metallicRoughnessTexture=TextureInfo(index=metallic_roughness_texture_index),
            ),
            normalTexture=NormalMaterialTexture(index=normal_texture_index, scale=0.85),
        )
    )
    strap_material = builder.add_material(
        Material(
            name="EmeraldStraps",
            alphaMode="OPAQUE",
            doubleSided=True,
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorFactor=[0.094, 0.463, 0.376, 1.0],
                metallicFactor=0.04,
                roughnessFactor=0.14,
                baseColorTexture=TextureInfo(index=base_color_texture),
                metallicRoughnessTexture=TextureInfo(index=metallic_roughness_texture_index),
            ),
            normalTexture=NormalMaterialTexture(index=normal_texture_index, scale=0.6),
        )
    )
    skin_material = builder.add_material(
        Material(
            name="AvatarMannequin",
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorFactor=[0.15, 0.16, 0.18, 1.0],
                metallicFactor=0.05,
                roughnessFactor=0.92,
            ),
        )
    )
    shoe_material = builder.add_material(
        Material(
            name="AvatarShoes",
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorFactor=[0.08, 0.09, 0.11, 1.0],
                metallicFactor=0.12,
                roughnessFactor=0.48,
            ),
        )
    )

    pivots = {
        "bodice": np.array([0.0, 1.30, 0.0], dtype=np.float32),
        "skirt": np.array([0.0, 1.03, 0.0], dtype=np.float32),
    }

    bodice = transform_payload_to_local(build_dress_surface(-math.pi, math.pi, 96, 48, bodice_position, 0.0, 0.36, thickness=0.0075), pivots["bodice"])
    skirt_front = transform_payload_to_local(build_dress_surface(-math.pi / 4.0, math.pi / 4.0, 24, 72, skirt_position, 0.34, 1.0, thickness=0.0085), pivots["skirt"])
    skirt_right = transform_payload_to_local(build_dress_surface(math.pi / 4.0, 3.0 * math.pi / 4.0, 24, 72, skirt_position, 0.34, 1.0, thickness=0.0085), pivots["skirt"])
    skirt_back = transform_payload_to_local(build_dress_surface(3.0 * math.pi / 4.0, 5.0 * math.pi / 4.0, 24, 72, skirt_position, 0.34, 1.0, thickness=0.0085), pivots["skirt"])
    skirt_left = transform_payload_to_local(build_dress_surface(5.0 * math.pi / 4.0, 7.0 * math.pi / 4.0, 24, 72, skirt_position, 0.34, 1.0, thickness=0.0085), pivots["skirt"])
    strap_left = transform_payload_to_local(create_strap_geometry("left"), pivots["bodice"])
    strap_right = transform_payload_to_local(create_strap_geometry("right"), pivots["bodice"])
    avatar = create_avatar_geometry()

    mesh_indices = {
        "Avatar_Chest": builder.add_mesh("Avatar_Chest", avatar["Avatar_Chest"], skin_material),
        "Avatar_Neck": builder.add_mesh("Avatar_Neck", avatar["Avatar_Neck"], skin_material),
        "Avatar_Head": builder.add_mesh("Avatar_Head", avatar["Avatar_Head"], skin_material),
        "Avatar_LeftUpperArm": builder.add_mesh("Avatar_LeftUpperArm", avatar["Avatar_LeftUpperArm"], skin_material),
        "Avatar_RightUpperArm": builder.add_mesh("Avatar_RightUpperArm", avatar["Avatar_RightUpperArm"], skin_material),
        "Avatar_LeftLowerArm": builder.add_mesh("Avatar_LeftLowerArm", avatar["Avatar_LeftLowerArm"], skin_material),
        "Avatar_RightLowerArm": builder.add_mesh("Avatar_RightLowerArm", avatar["Avatar_RightLowerArm"], skin_material),
        "Avatar_LeftUpperLeg": builder.add_mesh("Avatar_LeftUpperLeg", avatar["Avatar_LeftUpperLeg"], skin_material),
        "Avatar_RightUpperLeg": builder.add_mesh("Avatar_RightUpperLeg", avatar["Avatar_RightUpperLeg"], skin_material),
        "Avatar_LeftLowerLeg": builder.add_mesh("Avatar_LeftLowerLeg", avatar["Avatar_LeftLowerLeg"], skin_material),
        "Avatar_RightLowerLeg": builder.add_mesh("Avatar_RightLowerLeg", avatar["Avatar_RightLowerLeg"], skin_material),
        "Avatar_LeftFoot": builder.add_mesh("Avatar_LeftFoot", avatar["Avatar_LeftFoot"], shoe_material),
        "Avatar_RightFoot": builder.add_mesh("Avatar_RightFoot", avatar["Avatar_RightFoot"], shoe_material),
        "Dress_Bodice": builder.add_mesh("Dress_Bodice", bodice, dress_material, ["size2", "size10"]),
        "Dress_FrontPanel": builder.add_mesh("Dress_FrontPanel", skirt_front, dress_material, ["size2", "size10"]),
        "Dress_RightPanel": builder.add_mesh("Dress_RightPanel", skirt_right, dress_material, ["size2", "size10"]),
        "Dress_BackPanel": builder.add_mesh("Dress_BackPanel", skirt_back, dress_material, ["size2", "size10"]),
        "Dress_LeftPanel": builder.add_mesh("Dress_LeftPanel", skirt_left, dress_material, ["size2", "size10"]),
        "Dress_LeftStrap": builder.add_mesh("Dress_LeftStrap", strap_left, strap_material),
        "Dress_RightStrap": builder.add_mesh("Dress_RightStrap", strap_right, strap_material),
    }

    nodes: dict[str, int] = {}
    nodes["Head"] = builder.add_node("Head", mesh_indices["Avatar_Head"], translation=[0.0, 0.23, 0.0])
    nodes["LeftLowerArm"] = builder.add_node("LeftLowerArm", mesh_indices["Avatar_LeftLowerArm"], translation=[0.0, -0.24, 0.0])
    nodes["RightLowerArm"] = builder.add_node("RightLowerArm", mesh_indices["Avatar_RightLowerArm"], translation=[0.0, -0.24, 0.0])
    nodes["LeftUpperArm"] = builder.add_node("LeftUpperArm", mesh_indices["Avatar_LeftUpperArm"], translation=[-0.19, 0.1, -0.03], rotation=quaternion_from_euler(0.02, 0.12, 0.24).tolist(), children=[nodes["LeftLowerArm"]])
    nodes["RightUpperArm"] = builder.add_node("RightUpperArm", mesh_indices["Avatar_RightUpperArm"], translation=[0.19, 0.1, -0.03], rotation=quaternion_from_euler(0.02, -0.12, -0.24).tolist(), children=[nodes["RightLowerArm"]])
    nodes["Chest"] = builder.add_node(
        "Chest",
        mesh_indices["Avatar_Chest"],
        translation=[0.0, 0.14, 0.0],
        children=[
            nodes["Head"],
            builder.add_node("DressBodice", mesh_indices["Dress_Bodice"]),
            builder.add_node("DressLeftStrap", mesh_indices["Dress_LeftStrap"]),
            builder.add_node("DressRightStrap", mesh_indices["Dress_RightStrap"]),
            builder.add_node("AvatarNeck", mesh_indices["Avatar_Neck"]),
            nodes["LeftUpperArm"],
            nodes["RightUpperArm"],
        ],
    )
    nodes["LeftFoot"] = builder.add_node("LeftFoot", mesh_indices["Avatar_LeftFoot"], translation=[0.0, -0.43, 0.04])
    nodes["RightFoot"] = builder.add_node("RightFoot", mesh_indices["Avatar_RightFoot"], translation=[0.0, -0.43, 0.04])
    nodes["LeftLowerLeg"] = builder.add_node("LeftLowerLeg", mesh_indices["Avatar_LeftLowerLeg"], translation=[0.0, -0.4, 0.0], children=[nodes["LeftFoot"]])
    nodes["RightLowerLeg"] = builder.add_node("RightLowerLeg", mesh_indices["Avatar_RightLowerLeg"], translation=[0.0, -0.4, 0.0], children=[nodes["RightFoot"]])
    nodes["LeftUpperLeg"] = builder.add_node("LeftUpperLeg", mesh_indices["Avatar_LeftUpperLeg"], translation=[-0.08, -0.03, 0.0], children=[nodes["LeftLowerLeg"]])
    nodes["RightUpperLeg"] = builder.add_node("RightUpperLeg", mesh_indices["Avatar_RightUpperLeg"], translation=[0.08, -0.03, 0.0], children=[nodes["RightLowerLeg"]])
    nodes["DressFront"] = builder.add_node("DressFront", mesh_indices["Dress_FrontPanel"])
    nodes["DressRight"] = builder.add_node("DressRight", mesh_indices["Dress_RightPanel"])
    nodes["DressBack"] = builder.add_node("DressBack", mesh_indices["Dress_BackPanel"])
    nodes["DressLeft"] = builder.add_node("DressLeft", mesh_indices["Dress_LeftPanel"])
    nodes["Hips"] = builder.add_node(
        "Hips",
        None,
        translation=[0.0, 1.03, 0.0],
        children=[
            nodes["Chest"],
            nodes["LeftUpperLeg"],
            nodes["RightUpperLeg"],
            nodes["DressFront"],
            nodes["DressRight"],
            nodes["DressBack"],
            nodes["DressLeft"],
        ],
    )

    root = builder.add_node("RunwayModel", None, children=[nodes["Hips"]])
    build_runway_walk_animation(builder, nodes)
    builder.finalize([root], MODEL_PATH)

    dress_triangles = sum(len(payload.indices) // 3 for payload in [bodice, skirt_front, skirt_right, skirt_back, skirt_left, strap_left, strap_right])
    total_triangles = dress_triangles + sum(len(payload.indices) // 3 for payload in avatar.values())
    glb_size = MODEL_PATH.stat().st_size

    metadata = {
        "dress_triangles": int(dress_triangles),
        "total_scene_triangles": int(total_triangles),
        "meshes": len(builder.gltf.meshes),
        "nodes": len(builder.gltf.nodes),
        "animations": len(builder.gltf.animations),
        "duration_seconds": 10.0,
        "morph_targets": ["size2", "size10"],
        "textures": {
            "base_color": f"{TEXTURE_SIZE}x{TEXTURE_SIZE}",
            "metallic_roughness": f"{TEXTURE_SIZE}x{TEXTURE_SIZE}",
            "normal": f"{TEXTURE_SIZE}x{TEXTURE_SIZE}",
        },
        "size_bytes": int(glb_size),
        "size_mb": round(glb_size / (1024 * 1024), 4),
        "default_color": "deep emerald",
        "variants": ["liquid satin", "matte silk", "pearl champagne"],
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
