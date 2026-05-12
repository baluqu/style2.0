from __future__ import annotations

import re
from collections import defaultdict


STYLE_WORLD_OPTIONS = [
    {
        "slug": "neo-minimal",
        "title": "Neo Minimal",
        "mood": "Architectural calm with clean restraint and precision balance.",
        "lighting": "High-key studio diffusion with cool highlights",
        "motion": "Slow orbital drift and minimal parallax",
        "typography": "Space Grotesk + Manrope",
        "palette": ["#e8edf2", "#9fb3c8", "#1c2733", "#0f141b"],
        "supports_androgynous": True,
        "semantic_keywords": {"minimal", "tailored", "clean", "precise", "structured", "sharp"},
        "style_tags": {"Minimalist", "Formal", "Casual"},
        "silhouettes": {"structured", "balanced", "slim"},
        "fits": {"tailored", "balanced"},
        "textures": {"cotton", "wool", "crepe", "smooth", "poplin", "knit"},
        "materials": {"matte", "polished", "natural"},
        "aesthetic_categories": {"minimalist", "tailoring", "quiet-luxury"},
        "eras": {"contemporary", "90s"},
        "formality_range": (0.55, 0.95),
        "aggression_range": (0.05, 0.35),
        "layering_range": (0.35, 0.75),
        "color_families": {"monochrome", "neutral", "cool"},
    },
    {
        "slug": "dark-academia",
        "title": "Dark Academia",
        "mood": "Intellectual romanticism with heritage tailoring and darker tones.",
        "lighting": "Low-key amber pools and shadow-heavy edges",
        "motion": "Candle-flicker fade and gentle film-grain drift",
        "typography": "Playfair Display + Source Serif 4",
        "palette": ["#c5b79a", "#6f5943", "#2a2220", "#161214"],
        "supports_androgynous": False,
        "semantic_keywords": {"tweed", "oxford", "heritage", "scholar", "wool", "coat", "vintage"},
        "style_tags": {"Vintage", "Formal", "Minimalist"},
        "silhouettes": {"structured", "draped", "balanced"},
        "fits": {"tailored", "balanced"},
        "textures": {"wool", "tweed", "corduroy", "leather", "knit"},
        "materials": {"natural", "matte", "distressed"},
        "aesthetic_categories": {"heritage", "vintage", "tailoring"},
        "eras": {"70s", "80s", "90s", "heritage"},
        "formality_range": (0.55, 0.95),
        "aggression_range": (0.1, 0.45),
        "layering_range": (0.45, 0.92),
        "color_families": {"earth", "monochrome", "muted"},
    },
    {
        "slug": "monochrome-utility",
        "title": "Monochrome Utility",
        "mood": "Functional layering with tactical rhythm and monochrome discipline.",
        "lighting": "Hard directional contrast and edge reflections",
        "motion": "Depth snaps with quick offset transitions",
        "typography": "IBM Plex Sans + Sora",
        "palette": ["#f4f6f8", "#9fa8b2", "#3b4450", "#0f1114"],
        "supports_androgynous": True,
        "semantic_keywords": {"utility", "cargo", "modular", "tech", "strap", "function", "track"},
        "style_tags": {"Streetwear", "Athleisure", "Minimalist", "Formal"},
        "silhouettes": {"oversized", "structured", "balanced"},
        "fits": {"oversized", "relaxed", "balanced"},
        "textures": {"nylon", "cotton", "ripstop", "mesh", "denim", "wool"},
        "materials": {"technical", "matte", "distressed"},
        "aesthetic_categories": {"utility", "streetwear", "minimalist"},
        "eras": {"contemporary", "2000s"},
        "formality_range": (0.35, 0.78),
        "aggression_range": (0.35, 0.78),
        "layering_range": (0.55, 0.95),
        "color_families": {"monochrome", "neutral", "cool"},
    },
    {
        "slug": "tokyo-street",
        "title": "Tokyo Street",
        "mood": "Kinetic layering, engineered contrast, and playful directional edits.",
        "lighting": "Neon spill, reflective street highlights",
        "motion": "Fast lateral parallax and step-cut transitions",
        "typography": "Bebas Neue + Noto Sans JP",
        "palette": ["#f8f8f7", "#8da7c8", "#2d2f45", "#101015"],
        "supports_androgynous": True,
        "semantic_keywords": {"street", "layer", "neon", "cargo", "graphic", "oversized", "sneaker"},
        "style_tags": {"Streetwear", "Athleisure", "Casual"},
        "silhouettes": {"oversized", "balanced", "structured"},
        "fits": {"oversized", "relaxed", "balanced"},
        "textures": {"denim", "nylon", "mesh", "cotton", "leather"},
        "materials": {"technical", "matte", "distressed"},
        "aesthetic_categories": {"streetwear", "utility", "editorial"},
        "eras": {"2000s", "2010s", "contemporary"},
        "formality_range": (0.15, 0.58),
        "aggression_range": (0.4, 0.9),
        "layering_range": (0.6, 1.0),
        "color_families": {"cool", "monochrome", "neon"},
    },
    {
        "slug": "quiet-luxury",
        "title": "Quiet Luxury",
        "mood": "Elevated understatement with expensive texture and soft authority.",
        "lighting": "Soft daylight sculpting and controlled bloom",
        "motion": "Measured cinematic dolly and slow fades",
        "typography": "Cormorant Garamond + Manrope",
        "palette": ["#f2ece1", "#cbb79a", "#7f6b58", "#1f1a16"],
        "supports_androgynous": False,
        "semantic_keywords": {"cashmere", "silk", "tailored", "understated", "luxury", "neutral", "fine"},
        "style_tags": {"Formal", "Minimalist", "Casual"},
        "silhouettes": {"structured", "balanced", "draped"},
        "fits": {"tailored", "balanced", "body-skimming"},
        "textures": {"cashmere", "wool", "silk", "satin", "cotton", "leather"},
        "materials": {"polished", "natural", "matte"},
        "aesthetic_categories": {"quiet-luxury", "tailoring", "minimalist"},
        "eras": {"90s", "contemporary"},
        "formality_range": (0.55, 0.98),
        "aggression_range": (0.02, 0.3),
        "layering_range": (0.35, 0.75),
        "color_families": {"neutral", "earth", "muted", "monochrome"},
    },
    {
        "slug": "futuristic-editorial",
        "title": "Futuristic Editorial",
        "mood": "Speculative silhouettes with cinematic contrast and bold futurism.",
        "lighting": "Cold rim lights and metallic bloom",
        "motion": "Pulse zooms with staggered reveal cuts",
        "typography": "Orbitron + Rajdhani",
        "palette": ["#d8f4ff", "#8ac8ff", "#4f5d8f", "#111420"],
        "supports_androgynous": True,
        "semantic_keywords": {"futuristic", "editorial", "metallic", "techwear", "reflective", "avant", "neon"},
        "style_tags": {"Streetwear", "Minimalist", "Formal"},
        "silhouettes": {"oversized", "structured", "draped"},
        "fits": {"oversized", "tailored", "body-skimming"},
        "textures": {"nylon", "mesh", "leather", "satin", "technical"},
        "materials": {"technical", "polished", "sheen"},
        "aesthetic_categories": {"editorial", "avant-garde", "streetwear", "utility"},
        "eras": {"futuristic", "2000s", "contemporary"},
        "formality_range": (0.3, 0.88),
        "aggression_range": (0.45, 0.95),
        "layering_range": (0.5, 1.0),
        "color_families": {"cool", "neon", "monochrome"},
    },
    {
        "slug": "vintage-athletic",
        "title": "Vintage Athletic",
        "mood": "Retro sport codes tuned for modern daily movement.",
        "lighting": "Warm film haze with nostalgic lift",
        "motion": "Elastic bounce and tape-rewind cuts",
        "typography": "Archivo Black + Barlow Condensed",
        "palette": ["#f3e4c7", "#d09a68", "#6f4d3a", "#1e1b20"],
        "supports_androgynous": True,
        "semantic_keywords": {"retro", "track", "varsity", "runner", "club", "sport", "vintage"},
        "style_tags": {"Vintage", "Athleisure", "Casual", "Streetwear"},
        "silhouettes": {"balanced", "oversized", "slim"},
        "fits": {"relaxed", "balanced", "tailored"},
        "textures": {"cotton", "denim", "mesh", "nylon", "knit"},
        "materials": {"matte", "distressed", "technical"},
        "aesthetic_categories": {"athletic", "vintage", "streetwear"},
        "eras": {"70s", "80s", "90s", "2000s"},
        "formality_range": (0.1, 0.55),
        "aggression_range": (0.25, 0.72),
        "layering_range": (0.4, 0.88),
        "color_families": {"earth", "warm", "muted", "cool"},
    },
    {
        "slug": "nordic-clean",
        "title": "Nordic Clean",
        "mood": "Soft utility with muted tones and serene compositional balance.",
        "lighting": "Diffuse overcast glow and low-contrast shadows",
        "motion": "Slow fade stacks and soft scroll drift",
        "typography": "Plus Jakarta Sans + DM Sans",
        "palette": ["#f4f7f6", "#d2ddd8", "#96a6a0", "#2a3733"],
        "supports_androgynous": True,
        "semantic_keywords": {"clean", "muted", "functional", "soft", "calm", "minimal", "knit"},
        "style_tags": {"Minimalist", "Casual", "Formal"},
        "silhouettes": {"balanced", "structured", "draped"},
        "fits": {"balanced", "relaxed", "tailored"},
        "textures": {"cotton", "wool", "knit", "linen", "denim"},
        "materials": {"natural", "matte"},
        "aesthetic_categories": {"minimalist", "utility", "quiet-luxury"},
        "eras": {"contemporary", "90s"},
        "formality_range": (0.35, 0.8),
        "aggression_range": (0.02, 0.3),
        "layering_range": (0.4, 0.85),
        "color_families": {"neutral", "cool", "muted", "earth"},
    },
    {
        "slug": "avant-garde-structure",
        "title": "Avant-Garde Structure",
        "mood": "Sculptural experimentation with directional silhouette architecture.",
        "lighting": "Runway spot pools and high-contrast carve lights",
        "motion": "Cut-to-black rhythm with dramatic reveals",
        "typography": "Syne + Space Mono",
        "palette": ["#f0f0f0", "#b8b8b8", "#63636f", "#111113"],
        "supports_androgynous": True,
        "semantic_keywords": {"avant", "sculptural", "experimental", "asymmetry", "runway", "statement"},
        "style_tags": {"Formal", "Minimalist", "Streetwear"},
        "silhouettes": {"structured", "oversized", "draped"},
        "fits": {"tailored", "oversized", "body-skimming"},
        "textures": {"leather", "satin", "wool", "mesh", "crepe"},
        "materials": {"polished", "technical", "sheen", "matte"},
        "aesthetic_categories": {"avant-garde", "editorial", "tailoring"},
        "eras": {"futuristic", "contemporary", "90s"},
        "formality_range": (0.42, 0.95),
        "aggression_range": (0.4, 0.98),
        "layering_range": (0.45, 0.95),
        "color_families": {"monochrome", "cool", "neutral"},
    },
]

STYLE_WORLD_SLUGS = {entry["slug"] for entry in STYLE_WORLD_OPTIONS}
STYLE_WORLD_BY_SLUG = {entry["slug"]: entry for entry in STYLE_WORLD_OPTIONS}

WORLD_SCORE_WEIGHTS = {
    "silhouette": 12,
    "fit": 8,
    "texture": 8,
    "layering": 10,
    "color_palette": 9,
    "material_appearance": 8,
    "formality": 12,
    "aggression": 10,
    "aesthetic_category": 12,
    "era_influence": 6,
    "semantic": 5,
}

WARDROBE_SLOT_LABELS = [
    "outerwear",
    "footwear",
    "accessories",
    "layering pieces",
    "statement items",
    "essentials",
]


def style_world_by_slug(slug: str) -> dict | None:
    if not slug:
        return None
    return STYLE_WORLD_BY_SLUG.get(str(slug).strip().lower())


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(value: str, max_len: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        text = text[:max_len]
    return text


def _normalize_key(value: str, max_len: int = 80) -> str:
    text = _normalize_text(value, max_len=max_len).lower()
    text = re.sub(r"[^a-z0-9\-\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(*parts: str) -> set[str]:
    joined = " ".join(_normalize_key(part, max_len=240) for part in parts if part)
    return {token for token in joined.split() if token}


def _color_family(value: str) -> str:
    raw = _normalize_key(value, max_len=40)
    if not raw:
        return "neutral"
    if raw in {"black", "white", "charcoal", "grey", "gray", "graphite"}:
        return "monochrome"
    if raw in {"silver", "blue", "navy", "indigo", "emerald", "green", "teal"}:
        return "cool"
    if raw in {"beige", "cream", "ivory", "camel", "brown", "tan", "coffee"}:
        return "earth"
    if raw in {"rose", "pink", "burgundy", "maroon", "red", "orange", "gold"}:
        return "warm"
    if raw in {"neon", "lime", "electric", "fluorescent"}:
        return "neon"
    if raw in {"stone", "taupe", "muted"}:
        return "muted"
    return "neutral"


def _normalize_texture(value: str, tokens: set[str]) -> str:
    explicit = _normalize_key(value, max_len=40)
    if explicit:
        return explicit.split()[0]
    texture_map = [
        ("satin", {"satin", "silk", "lustre"}),
        ("wool", {"wool", "cashmere", "flannel", "tweed"}),
        ("denim", {"denim", "jean"}),
        ("leather", {"leather", "suede"}),
        ("mesh", {"mesh"}),
        ("nylon", {"nylon", "ripstop", "tech"}),
        ("knit", {"knit"}),
        ("cotton", {"cotton", "jersey", "tee"}),
        ("linen", {"linen"}),
    ]
    for label, vocab in texture_map:
        if tokens & vocab:
            return label
    return "cotton"


def _material_from_texture(texture: str, tokens: set[str]) -> str:
    if texture in {"nylon", "mesh"} or tokens & {"utility", "technical", "techwear"}:
        return "technical"
    if texture in {"satin", "silk"}:
        return "sheen"
    if texture in {"leather"}:
        return "polished"
    if texture in {"denim"} or tokens & {"washed", "distressed", "vintage"}:
        return "distressed"
    if texture in {"wool", "cotton", "linen", "knit"}:
        return "natural"
    return "matte"


def _silhouette_from_tokens(tokens: set[str], category: str) -> str:
    if tokens & {"oversized", "boxy", "puffer", "cargo"}:
        return "oversized"
    if tokens & {"tailored", "structured", "blazer", "coat", "trouser"}:
        return "structured"
    if tokens & {"slim", "fitted", "skinny"}:
        return "slim"
    if tokens & {"draped", "flowing", "satin", "slip", "abaya", "kaftan", "jilbab"}:
        return "draped"
    if category in {"outerwear", "top"}:
        return "structured"
    if category in {"dress", "set"}:
        return "balanced"
    return "balanced"


def _fit_from_tokens(tokens: set[str], silhouette: str) -> str:
    if tokens & {"oversized", "relaxed", "loose"}:
        return "oversized" if "oversized" in tokens else "relaxed"
    if tokens & {"tailored", "structured", "sharp"}:
        return "tailored"
    if tokens & {"fitted", "body", "bodycon", "slim"}:
        return "body-skimming"
    if silhouette == "slim":
        return "tailored"
    return "balanced"


def _layering_potential(category: str, tokens: set[str]) -> float:
    if category in {"outerwear", "layer"}:
        return 0.9
    if category in {"top", "set"}:
        return 0.6
    if category in {"accessory", "headwear", "shoes"}:
        return 0.45
    if category == "dress":
        return 0.5
    if tokens & {"layered", "overshirt", "cardigan", "coat", "jacket", "blazer"}:
        return 0.82
    return 0.52


def _formality_score(category: str, tokens: set[str], texture: str) -> float:
    score = 0.42
    if tokens & {"formal", "tailored", "evening", "dressy", "occasion", "luxury"}:
        score += 0.35
    if tokens & {"street", "hoodie", "jogger", "gym", "athleisure", "sport"}:
        score -= 0.2
    if category in {"outerwear"} and tokens & {"overcoat", "blazer"}:
        score += 0.18
    if texture in {"satin", "silk", "wool", "leather"}:
        score += 0.1
    if texture in {"mesh", "nylon"}:
        score -= 0.05
    return clamp(score, 0.05, 1.0)


def _aggression_score(tokens: set[str], material: str) -> float:
    score = 0.28
    if tokens & {"neon", "graphic", "statement", "bold", "futuristic", "avant", "street"}:
        score += 0.35
    if tokens & {"minimal", "quiet", "classic", "clean", "neutral"}:
        score -= 0.15
    if material in {"technical", "sheen"}:
        score += 0.08
    if material in {"natural"}:
        score -= 0.05
    return clamp(score, 0.03, 0.98)


def _aesthetic_category(tokens: set[str], category: str) -> str:
    if tokens & {"avant", "editorial", "sculptural", "experimental"}:
        return "avant-garde"
    if tokens & {"quiet", "luxury", "cashmere", "fine"}:
        return "quiet-luxury"
    if tokens & {"street", "graphic", "sneaker", "cargo"}:
        return "streetwear"
    if tokens & {"utility", "technical", "modular", "track"}:
        return "utility"
    if tokens & {"tailored", "blazer", "trouser", "formal"}:
        return "tailoring"
    if tokens & {"retro", "vintage", "varsity"}:
        return "vintage"
    if tokens & {"athletic", "sport", "runner", "gym"}:
        return "athletic"
    if category in {"outerwear", "top", "bottom"}:
        return "minimalist"
    return "minimalist"


def _era_influence(tokens: set[str]) -> str:
    if tokens & {"vintage", "retro", "heritage"}:
        return "heritage"
    if tokens & {"y2k", "2000s"}:
        return "2000s"
    if tokens & {"90s", "nineties"}:
        return "90s"
    if tokens & {"70s", "seventies"}:
        return "70s"
    if tokens & {"80s", "eighties"}:
        return "80s"
    if tokens & {"futuristic", "future", "cyber"}:
        return "futuristic"
    return "contemporary"


def _slot_name(category: str, aggression: float, layering_potential: float) -> str:
    if category == "outerwear":
        return "outerwear"
    if category == "shoes":
        return "footwear"
    if category in {"accessory", "headwear"}:
        return "accessories"
    if layering_potential >= 0.74:
        return "layering pieces"
    if aggression >= 0.66:
        return "statement items"
    return "essentials"


def infer_item_attributes(item: dict) -> dict:
    title = _normalize_text(item.get("title", ""), max_len=180)
    category = _normalize_key(item.get("category", ""), max_len=40) or "accessory"
    color = _normalize_key(item.get("color", ""), max_len=40)
    texture_input = _normalize_key(item.get("texture", ""), max_len=40)

    tokens = _tokens(
        title,
        item.get("texture", ""),
        item.get("occasion", ""),
        item.get("layer_role", ""),
        item.get("aesthetic_category", ""),
        item.get("fashion_era_influence", ""),
    )

    silhouette = _normalize_key(item.get("silhouette", ""), max_len=40) or _silhouette_from_tokens(tokens, category)
    fit = _normalize_key(item.get("fit", ""), max_len=40) or _fit_from_tokens(tokens, silhouette)
    texture = texture_input or _normalize_texture("", tokens)
    layering_value = item.get("layering_potential", "")
    if str(layering_value).strip():
        layering_potential = clamp(_to_float(layering_value, 0.5), 0.0, 1.0)
    else:
        layering_potential = _layering_potential(category, tokens)

    color_palette = _normalize_key(item.get("color_palette", ""), max_len=40) or _color_family(color)
    material = _normalize_key(item.get("material_appearance", ""), max_len=40) or _material_from_texture(texture, tokens)

    formality_raw = item.get("formality_level", "")
    if str(formality_raw).strip():
        formality_level = clamp(_to_float(formality_raw, 0.5), 0.0, 1.0)
    else:
        formality_level = _formality_score(category, tokens, texture)

    aggression_raw = item.get("visual_aggression", "")
    if str(aggression_raw).strip():
        aggression = clamp(_to_float(aggression_raw, 0.3), 0.0, 1.0)
    else:
        aggression = _aggression_score(tokens, material)

    aesthetic = _normalize_key(item.get("aesthetic_category", ""), max_len=80) or _aesthetic_category(tokens, category)
    era = _normalize_key(item.get("fashion_era_influence", ""), max_len=40) or _era_influence(tokens)

    return {
        "title": title,
        "category": category,
        "color": color,
        "tokens": tokens,
        "slot_name": _slot_name(category, aggression, layering_potential),
        "attributes": {
            "silhouette": silhouette,
            "fit": fit,
            "texture": texture,
            "layering_potential": round(layering_potential, 3),
            "color_palette": color_palette,
            "material_appearance": material,
            "formality_level": round(formality_level, 3),
            "visual_aggression": round(aggression, 3),
            "aesthetic_category": aesthetic,
            "fashion_era_influence": era,
        },
    }


def _range_match(value: float, interval: tuple[float, float]) -> float:
    low, high = interval
    if low <= value <= high:
        return 1.0
    if value < low:
        distance = low - value
    else:
        distance = value - high
    return clamp(1.0 - distance / 0.6, 0.0, 1.0)


def _set_match(value: str, allowed: set[str]) -> float:
    if not allowed:
        return 0.8
    return 1.0 if value in allowed else 0.24


def _semantic_match(tokens: set[str], world: dict) -> float:
    keywords = set(world.get("semantic_keywords", set()))
    if not keywords:
        return 0.5
    overlap = len(tokens.intersection(keywords))
    return clamp((overlap + 1) / (len(keywords) * 0.45), 0.0, 1.0)


def score_item_for_world(item: dict, world_slug: str) -> dict:
    world = style_world_by_slug(world_slug)
    if not world:
        return {
            "world_slug": world_slug,
            "world_title": world_slug,
            "confidence": 0,
            "compatibility": "weak",
            "breakdown": {},
        }

    profile = infer_item_attributes(item)
    attrs = profile["attributes"]
    tokens = profile["tokens"]

    dimension_scores = {
        "silhouette": _set_match(attrs["silhouette"], set(world.get("silhouettes", set()))),
        "fit": _set_match(attrs["fit"], set(world.get("fits", set()))),
        "texture": _set_match(attrs["texture"], set(world.get("textures", set()))),
        "layering": _range_match(float(attrs["layering_potential"]), tuple(world.get("layering_range", (0.0, 1.0)))),
        "color_palette": _set_match(attrs["color_palette"], set(world.get("color_families", set()))),
        "material_appearance": _set_match(attrs["material_appearance"], set(world.get("materials", set()))),
        "formality": _range_match(float(attrs["formality_level"]), tuple(world.get("formality_range", (0.0, 1.0)))),
        "aggression": _range_match(float(attrs["visual_aggression"]), tuple(world.get("aggression_range", (0.0, 1.0)))),
        "aesthetic_category": _set_match(attrs["aesthetic_category"], set(world.get("aesthetic_categories", set()))),
        "era_influence": _set_match(attrs["fashion_era_influence"], set(world.get("eras", set()))),
        "semantic": _semantic_match(tokens, world),
    }

    weighted_total = 0.0
    weight_sum = 0.0
    breakdown = {}
    for key, raw in dimension_scores.items():
        weight = float(WORLD_SCORE_WEIGHTS.get(key, 0))
        weighted_total += raw * weight
        weight_sum += weight
        breakdown[key] = int(round(raw * 100))

    confidence = int(round((weighted_total / max(weight_sum, 1.0)) * 100))
    confidence = int(clamp(confidence, 0, 100))
    if confidence >= 78:
        compatibility = "strong"
    elif confidence >= 58:
        compatibility = "aligned"
    else:
        compatibility = "weak"

    return {
        "world_slug": world["slug"],
        "world_title": world["title"],
        "confidence": confidence,
        "compatibility": compatibility,
        "breakdown": breakdown,
        "attributes": attrs,
    }


def analyze_item_for_worlds(item: dict) -> dict:
    profile = infer_item_attributes(item)
    world_scores = [score_item_for_world(item, world["slug"]) for world in STYLE_WORLD_OPTIONS]
    world_scores.sort(key=lambda entry: (-entry["confidence"], entry["world_title"]))
    best = world_scores[0] if world_scores else None
    return {
        "item_id": _normalize_text(item.get("id", ""), max_len=80),
        "title": profile["title"],
        "category": profile["category"],
        "slot_name": profile["slot_name"],
        "attributes": profile["attributes"],
        "world_scores": world_scores,
        "best_world": best,
    }


def analyze_wardrobe_worlds(wardrobe_items: list[dict]) -> dict:
    analyses = [analyze_item_for_worlds(item) for item in wardrobe_items]
    per_world: dict[str, list[int]] = defaultdict(list)
    slots_present = {slot: False for slot in WARDROBE_SLOT_LABELS}

    for analysis in analyses:
        slot = analysis.get("slot_name", "")
        if slot in slots_present:
            slots_present[slot] = True
        for world_score in analysis.get("world_scores", []):
            per_world[world_score["world_slug"]].append(int(world_score["confidence"]))

    world_rankings = []
    for world in STYLE_WORLD_OPTIONS:
        scores = per_world.get(world["slug"], [])
        if scores:
            top_slice = sorted(scores, reverse=True)[: max(3, min(8, len(scores)))]
            confidence = int(round(sum(top_slice) / len(top_slice)))
            aligned_items = sum(1 for value in scores if value >= 58)
        else:
            confidence = 0
            aligned_items = 0
        world_rankings.append(
            {
                "slug": world["slug"],
                "title": world["title"],
                "confidence": confidence,
                "aligned_items": aligned_items,
                "lighting": world.get("lighting", ""),
                "motion": world.get("motion", ""),
                "typography": world.get("typography", ""),
                "mood": world.get("mood", ""),
                "palette": world.get("palette", []),
            }
        )

    world_rankings.sort(key=lambda entry: (-entry["confidence"], entry["title"]))
    missing_slots = [slot for slot, present in slots_present.items() if not present]
    return {
        "item_analyses": analyses,
        "world_rankings": world_rankings,
        "missing_slots": missing_slots,
        "slots_present": slots_present,
    }


def generate_outfit_systems_for_world(wardrobe_items: list[dict], world_slug: str, limit: int = 4) -> list[dict]:
    selected_world = style_world_by_slug(world_slug)
    if not selected_world:
        return []

    scored_items = []
    for item in wardrobe_items:
        world_score = score_item_for_world(item, selected_world["slug"])
        if world_score["confidence"] < 45:
            continue
        profile = infer_item_attributes(item)
        scored_items.append(
            {
                "item": item,
                "title": _normalize_text(item.get("title", ""), max_len=180),
                "category": profile["category"],
                "slot_name": profile["slot_name"],
                "confidence": world_score["confidence"],
                "attributes": profile["attributes"],
            }
        )

    if not scored_items:
        return []

    buckets: dict[str, list[dict]] = defaultdict(list)
    for entry in scored_items:
        buckets[entry["category"]].append(entry)

    for entries in buckets.values():
        entries.sort(key=lambda item: (-item["confidence"], item["title"]))

    top_or_dress = []
    top_or_dress.extend(buckets.get("top", []))
    top_or_dress.extend(buckets.get("outerwear", []))
    top_or_dress.extend(buckets.get("dress", []))
    top_or_dress.extend(buckets.get("set", []))
    top_or_dress.extend(buckets.get("layer", []))
    if not top_or_dress:
        return []

    bottoms = buckets.get("bottom", [])
    shoes = buckets.get("shoes", [])
    accessories = buckets.get("accessory", []) + buckets.get("headwear", [])

    outfits = []
    seen_signatures = set()
    for index, core in enumerate(top_or_dress[: max(limit * 2, 4)]):
        bundle = [core]
        if core["category"] not in {"dress", "set"} and bottoms:
            bundle.append(bottoms[index % len(bottoms)])
        if shoes:
            bundle.append(shoes[index % len(shoes)])
        if accessories:
            bundle.append(accessories[index % len(accessories)])

        signature = tuple(sorted(entry["title"].lower() for entry in bundle))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        confidence = int(round(sum(entry["confidence"] for entry in bundle) / len(bundle)))
        color_families = [entry["attributes"]["color_palette"] for entry in bundle]
        dominant_color = max(set(color_families), key=color_families.count)
        coherence_bonus = 6 if color_families.count(dominant_color) >= max(2, len(color_families) - 1) else 0

        outfits.append(
            {
                "world_slug": selected_world["slug"],
                "world_title": selected_world["title"],
                "confidence": int(clamp(confidence + coherence_bonus, 0, 100)),
                "narrative": f"{selected_world['title']} system built around {core['title']}.",
                "items": [
                    {
                        "title": entry["title"],
                        "category": entry["category"],
                        "confidence": entry["confidence"],
                        "color_palette": entry["attributes"]["color_palette"],
                    }
                    for entry in bundle
                ],
            }
        )
        if len(outfits) >= limit:
            break

    outfits.sort(key=lambda outfit: (-outfit["confidence"], outfit["narrative"]))
    return outfits
