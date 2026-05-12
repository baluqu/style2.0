from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

WORLD_EXPERIMENTALITY = {
    "quiet-luxury": 0.24,
    "neo-minimal": 0.22,
    "dark-academia": 0.38,
    "nordic-clean": 0.28,
    "monochrome-utility": 0.52,
    "tokyo-street": 0.62,
    "vintage-athletic": 0.5,
    "futuristic-editorial": 0.82,
    "avant-garde-structure": 0.9,
}

WORLD_EMOTION_SIGNATURES = {
    "quiet-luxury": "measured calm",
    "neo-minimal": "clarity and precision",
    "dark-academia": "romantic depth",
    "nordic-clean": "soft restraint",
    "monochrome-utility": "functional confidence",
    "tokyo-street": "kinetic experimentation",
    "vintage-athletic": "nostalgic motion",
    "futuristic-editorial": "speculative ambition",
    "avant-garde-structure": "bold self-authorship",
}

STYLE_WORLD_HINTS = {
    "streetwear": "tokyo-street",
    "athleisure": "tokyo-street",
    "casual": "neo-minimal",
    "minimalist": "neo-minimal",
    "formal": "quiet-luxury",
    "vintage": "dark-academia",
    "modest": "quiet-luxury",
    "religious": "quiet-luxury",
}

ENERGY_WORLD_HINTS = {
    "minimal": "neo-minimal",
    "sharp": "neo-minimal",
    "quiet luxury": "quiet-luxury",
    "street": "tokyo-street",
    "dark academia": "dark-academia",
    "futuristic": "futuristic-editorial",
    "editorial": "futuristic-editorial",
    "athletic": "vintage-athletic",
    "soft": "quiet-luxury",
    "avant-garde": "avant-garde-structure",
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(value, max_len: int = 80) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        text = text[:max_len]
    return text


def _normalize_key(value, max_len: int = 80) -> str:
    text = _normalize_text(value, max_len=max_len).lower()
    text = re.sub(r"[^a-z0-9\-\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_counter(raw) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, float] = {}
    for key, value in raw.items():
        normalized = _normalize_key(key, max_len=90)
        if not normalized:
            continue
        cleaned[normalized] = _clamp(_to_float(value, 0.0), 0.0, 100000.0)
    return cleaned


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_identity_memory(raw_memory: dict | None) -> dict:
    source = raw_memory if isinstance(raw_memory, dict) else {}
    raw_events = source.get("events", [])
    events: list[dict] = []
    if isinstance(raw_events, list):
        for entry in raw_events[-720:]:
            if not isinstance(entry, dict):
                continue
            event_type = _normalize_key(entry.get("type", ""), max_len=64)
            if not event_type:
                continue
            events.append(
                {
                    "type": event_type,
                    "timestamp": _normalize_text(entry.get("timestamp", ""), 40) or _iso_now(),
                    "source": _normalize_key(entry.get("source", ""), max_len=40),
                    "world_slug": _normalize_key(entry.get("world_slug", ""), max_len=64),
                    "look_slug": _normalize_key(entry.get("look_slug", ""), max_len=80),
                    "recommendation_slug": _normalize_key(entry.get("recommendation_slug", ""), max_len=80),
                    "duration_ms": int(_clamp(_to_int(entry.get("duration_ms", 0), 0), 0, 600000)),
                    "hover_ms": int(_clamp(_to_int(entry.get("hover_ms", 0), 0), 0, 600000)),
                    "meta": entry.get("meta", {}) if isinstance(entry.get("meta"), dict) else {},
                }
            )

    counters = source.get("counters", {})
    if not isinstance(counters, dict):
        counters = {}

    identity_memory = {
        "version": 1,
        "events": events,
        "counters": {
            "world_dwell_seconds": _clean_counter(counters.get("world_dwell_seconds")),
            "world_visits": _clean_counter(counters.get("world_visits")),
            "world_saves": _clean_counter(counters.get("world_saves")),
            "world_clicks": _clean_counter(counters.get("world_clicks")),
            "world_impressions": _clean_counter(counters.get("world_impressions")),
            "world_ignores": _clean_counter(counters.get("world_ignores")),
            "world_transitions": _clean_counter(counters.get("world_transitions")),
            "colors": _clean_counter(counters.get("colors")),
            "silhouettes": _clean_counter(counters.get("silhouettes")),
            "layering_bands": _clean_counter(counters.get("layering_bands")),
            "accessory_behavior": _clean_counter(counters.get("accessory_behavior")),
            "experimental": _clean_counter(counters.get("experimental")),
            "meta_counts": _clean_counter(counters.get("meta_counts")),
        },
        "state": {
            "last_world_slug": _normalize_key(
                (source.get("state", {}) if isinstance(source.get("state"), dict) else {}).get("last_world_slug", ""),
                64,
            ),
            "updated_at": _normalize_text(
                (source.get("state", {}) if isinstance(source.get("state"), dict) else {}).get("updated_at", ""),
                40,
            ),
        },
    }
    return identity_memory


def world_experimentality(world_slug: str) -> float:
    slug = _normalize_key(world_slug, max_len=64)
    return float(WORLD_EXPERIMENTALITY.get(slug, 0.46))


def infer_color_family(color_value: str) -> str:
    raw = _normalize_key(color_value, max_len=40)
    if not raw:
        return "neutral"
    if raw in {"black", "white", "charcoal", "grey", "gray", "graphite"}:
        return "monochrome"
    if raw in {"silver", "blue", "navy", "indigo", "emerald", "green", "teal"}:
        return "cool"
    if raw in {"beige", "cream", "ivory", "camel", "brown", "tan", "coffee", "khaki"}:
        return "earth"
    if raw in {"rose", "pink", "burgundy", "maroon", "red", "orange", "gold"}:
        return "warm"
    if raw in {"stone", "taupe", "muted"}:
        return "muted"
    if raw in {"neon", "lime", "electric"}:
        return "neon"
    return "neutral"


def record_identity_event(memory: dict | None, raw_event: dict | None) -> dict:
    event = raw_event if isinstance(raw_event, dict) else {}
    normalized = normalize_identity_memory(memory if isinstance(memory, dict) else {})
    event_type = _normalize_key(event.get("type", ""), max_len=64)
    if not event_type:
        return normalized

    source = _normalize_key(event.get("source", ""), max_len=40)
    world_slug = _normalize_key(event.get("world_slug", ""), max_len=64)
    look_slug = _normalize_key(event.get("look_slug", ""), max_len=80)
    rec_slug = _normalize_key(event.get("recommendation_slug", ""), max_len=80)
    duration_ms = int(_clamp(_to_int(event.get("duration_ms", 0), 0), 0, 600000))
    hover_ms = int(_clamp(_to_int(event.get("hover_ms", 0), 0), 0, 600000))
    meta = event.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}

    normalized["events"].append(
        {
            "type": event_type,
            "timestamp": _iso_now(),
            "source": source,
            "world_slug": world_slug,
            "look_slug": look_slug,
            "recommendation_slug": rec_slug,
            "duration_ms": duration_ms,
            "hover_ms": hover_ms,
            "meta": meta,
        }
    )
    normalized["events"] = normalized["events"][-720:]

    counters = normalized["counters"]
    meta_counts = counters["meta_counts"]

    if world_slug:
        counters["world_visits"][world_slug] = counters["world_visits"].get(world_slug, 0.0) + 1.0

    if duration_ms > 0 and world_slug:
        dwell_seconds = duration_ms / 1000.0
        counters["world_dwell_seconds"][world_slug] = counters["world_dwell_seconds"].get(world_slug, 0.0) + dwell_seconds
        if dwell_seconds >= 8.0:
            meta_counts["hesitation_world_seconds"] = meta_counts.get("hesitation_world_seconds", 0.0) + dwell_seconds

    if hover_ms >= 900:
        meta_counts["hesitation_cards"] = meta_counts.get("hesitation_cards", 0.0) + 1.0

    if event_type in {"recommendation_impression", "world_recommendations_rendered"}:
        if world_slug:
            counters["world_impressions"][world_slug] = counters["world_impressions"].get(world_slug, 0.0) + 1.0
        if rec_slug:
            meta_counts[f"impression:{rec_slug}"] = meta_counts.get(f"impression:{rec_slug}", 0.0) + 1.0

    if event_type in {"recommendation_click", "look_view"}:
        if world_slug:
            counters["world_clicks"][world_slug] = counters["world_clicks"].get(world_slug, 0.0) + 1.0
        if rec_slug:
            meta_counts[f"click:{rec_slug}"] = meta_counts.get(f"click:{rec_slug}", 0.0) + 1.0

    if event_type in {"recommendation_ignore", "recommendation_ignored"} and world_slug:
        counters["world_ignores"][world_slug] = counters["world_ignores"].get(world_slug, 0.0) + 1.0

    if event_type in {"look_saved", "look_save_toggle"} and world_slug:
        counters["world_saves"][world_slug] = counters["world_saves"].get(world_slug, 0.0) + 1.0

    color_family = infer_color_family(meta.get("color", "") or meta.get("color_family", ""))
    if color_family:
        counters["colors"][color_family] = counters["colors"].get(color_family, 0.0) + 1.0

    silhouettes = meta.get("silhouettes", [])
    if isinstance(silhouettes, str):
        silhouettes = [silhouettes]
    if isinstance(silhouettes, list):
        for raw_silhouette in silhouettes:
            silhouette = _normalize_key(raw_silhouette, max_len=40)
            if silhouette:
                counters["silhouettes"][silhouette] = counters["silhouettes"].get(silhouette, 0.0) + 1.0

    layering_score = _clamp(_to_float(meta.get("layering_score", 0.0), 0.0), 0.0, 1.0)
    if layering_score >= 0.67:
        counters["layering_bands"]["high"] = counters["layering_bands"].get("high", 0.0) + 1.0
    elif layering_score >= 0.38:
        counters["layering_bands"]["medium"] = counters["layering_bands"].get("medium", 0.0) + 1.0
    else:
        counters["layering_bands"]["low"] = counters["layering_bands"].get("low", 0.0) + 1.0

    accessory_count = int(_clamp(_to_int(meta.get("accessory_count", 0), 0), 0, 16))
    if accessory_count > 0:
        counters["accessory_behavior"]["engaged"] = counters["accessory_behavior"].get("engaged", 0.0) + 1.0
        if event_type in {"look_saved", "look_save_toggle", "recommendation_click"}:
            counters["accessory_behavior"]["positive"] = counters["accessory_behavior"].get("positive", 0.0) + 1.0
    elif event_type in {"recommendation_ignore", "recommendation_ignored"}:
        counters["accessory_behavior"]["ignored"] = counters["accessory_behavior"].get("ignored", 0.0) + 1.0

    experimental_score = _clamp(_to_float(meta.get("experimental_score", world_experimentality(world_slug)), 0.0), 0.0, 1.0)
    if experimental_score >= 0.62:
        counters["experimental"]["attempted"] = counters["experimental"].get("attempted", 0.0) + 1.0
        if event_type in {"recommendation_click", "look_saved", "look_save_toggle"}:
            counters["experimental"]["accepted"] = counters["experimental"].get("accepted", 0.0) + 1.0
        if event_type in {"recommendation_ignore", "recommendation_ignored"}:
            counters["experimental"]["ignored"] = counters["experimental"].get("ignored", 0.0) + 1.0
    else:
        counters["experimental"]["comfort"] = counters["experimental"].get("comfort", 0.0) + 1.0

    last_world = normalized["state"].get("last_world_slug", "")
    if world_slug and last_world and last_world != world_slug:
        transition_key = f"{last_world}>{world_slug}"
        counters["world_transitions"][transition_key] = counters["world_transitions"].get(transition_key, 0.0) + 1.0
    if world_slug:
        normalized["state"]["last_world_slug"] = world_slug
    normalized["state"]["updated_at"] = _iso_now()
    return normalized


def _dominant_items(counter: dict[str, float], limit: int = 3) -> list[tuple[str, float]]:
    if not counter:
        return []
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return ordered[: max(1, limit)]


def _top_share(counter: dict[str, float]) -> float:
    if not counter:
        return 0.0
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    top = max(counter.values())
    return _clamp(top / total, 0.0, 1.0)


def _world_score_map(memory: dict, saved_worlds: list[str] | None = None) -> dict[str, float]:
    counters = memory["counters"]
    scores: defaultdict[str, float] = defaultdict(float)
    for world, value in counters["world_dwell_seconds"].items():
        scores[world] += value * 0.07
    for world, value in counters["world_visits"].items():
        scores[world] += value * 1.35
    for world, value in counters["world_impressions"].items():
        scores[world] += value * 0.22
    for world, value in counters["world_clicks"].items():
        scores[world] += value * 1.8
    for world, value in counters["world_saves"].items():
        scores[world] += value * 2.4
    for world, value in counters["world_ignores"].items():
        scores[world] -= value * 0.75

    if saved_worlds:
        for world in saved_worlds:
            key = _normalize_key(world, 64)
            if key:
                scores[key] += 2.8

    return dict(scores)


def compute_identity_profile(profile_data: dict | None, *, saved_worlds: list[str] | None = None) -> dict:
    data = profile_data if isinstance(profile_data, dict) else {}
    memory = normalize_identity_memory(data.get("identity_memory", {}))
    counters = memory["counters"]
    events = memory["events"]
    event_depth = len(events)

    world_scores = _world_score_map(memory, saved_worlds=saved_worlds)
    if sum(abs(value) for value in world_scores.values()) < 1.0:
        style_pref = _normalize_key(data.get("style_preference", ""), 80)
        if style_pref in STYLE_WORLD_HINTS:
            world_scores[STYLE_WORLD_HINTS[style_pref]] = world_scores.get(STYLE_WORLD_HINTS[style_pref], 0.0) + 4.8
        for style in data.get("favorite_styles", []) if isinstance(data.get("favorite_styles"), list) else []:
            key = _normalize_key(style, 80)
            world = STYLE_WORLD_HINTS.get(key, "")
            if world:
                world_scores[world] = world_scores.get(world, 0.0) + 2.1
        for energy in data.get("style_energy", []) if isinstance(data.get("style_energy"), list) else []:
            key = _normalize_key(energy, 80)
            world = ENERGY_WORLD_HINTS.get(key, "")
            if world:
                world_scores[world] = world_scores.get(world, 0.0) + 1.4

    world_ranked = sorted(world_scores.items(), key=lambda item: (-item[1], item[0]))
    dominant_world = world_ranked[0][0] if world_ranked else ""
    dominant_world_score = world_ranked[0][1] if world_ranked else 0.0
    total_world_score = sum(max(0.0, score) for _, score in world_ranked) or 1.0
    world_focus_share = _clamp(max(0.0, dominant_world_score) / total_world_score, 0.0, 1.0)

    experimentation_samples = counters["experimental"]
    experimental_attempts = experimentation_samples.get("attempted", 0.0)
    experimental_accepted = experimentation_samples.get("accepted", 0.0)
    experimental_ignored = experimentation_samples.get("ignored", 0.0)
    comfort_actions = experimentation_samples.get("comfort", 0.0)
    experimental_acceptance = experimental_accepted / max(1.0, experimental_attempts + experimental_ignored)

    world_ignore_total = sum(counters["world_ignores"].values())
    world_click_total = sum(counters["world_clicks"].values())
    world_save_total = sum(counters["world_saves"].values())
    interaction_volume = world_click_total + world_save_total + sum(counters["world_visits"].values())
    ignore_rate = world_ignore_total / max(1.0, world_ignore_total + interaction_volume)

    color_counter = counters["colors"]
    silhouette_counter = counters["silhouettes"]
    layering_counter = counters["layering_bands"]
    accessory_counter = counters["accessory_behavior"]

    dominant_color = _dominant_items(color_counter, limit=1)
    dominant_silhouette = _dominant_items(silhouette_counter, limit=1)
    layering_top = _dominant_items(layering_counter, limit=1)
    layering_label = layering_top[0][0] if layering_top else "medium"

    accessory_positive = accessory_counter.get("positive", 0.0)
    accessory_engaged = accessory_counter.get("engaged", 0.0)
    accessory_ratio = accessory_positive / max(1.0, accessory_engaged)
    if accessory_engaged < 3:
        accessory_label = "calibrating"
    elif accessory_ratio >= 0.62:
        accessory_label = "intentional accessorizing"
    elif accessory_ratio >= 0.32:
        accessory_label = "selective accessorizing"
    else:
        accessory_label = "minimal accessory behavior"

    consistency = int(
        round(
            _clamp(
                38.0
                + world_focus_share * 42.0
                + _top_share(color_counter) * 10.0
                + _top_share(silhouette_counter) * 9.0
                - ignore_rate * 28.0,
                8.0,
                98.0,
            )
        )
    )

    confidence_growth = int(
        round(
            _clamp(
                26.0
                + math.log1p(max(0.0, interaction_volume)) * 12.0
                + experimental_acceptance * 24.0
                - ignore_rate * 18.0,
                6.0,
                97.0,
            )
        )
    )

    experimentation = int(
        round(
            _clamp(
                18.0
                + (experimental_attempts * 4.2)
                + (experimental_acceptance * 28.0)
                + (comfort_actions * 0.8),
                4.0,
                99.0,
            )
        )
    )

    comfort_experimentality = 0.26
    if world_ranked:
        weighted_total = 0.0
        weighted_value = 0.0
        for world, score in world_ranked[:8]:
            positive = max(0.0, score)
            weighted_total += positive
            weighted_value += positive * world_experimentality(world)
        comfort_experimentality = weighted_value / max(1e-6, weighted_total)
    comfort_experimentality = _clamp(comfort_experimentality, 0.1, 0.94)

    readiness = _clamp((confidence_growth / 100.0) * 0.56 + (experimental_acceptance * 0.44), 0.05, 0.95)
    step_ceiling = _clamp(0.07 + readiness * 0.22, 0.08, 0.32)
    target_experimentality = _clamp(comfort_experimentality + step_ceiling, 0.14, 0.98)

    aspirational_worlds: list[dict] = []
    actual_worlds: list[dict] = []
    curiosity_worlds: list[dict] = []
    for world, score in world_ranked[:6]:
        aspirational = counters["world_dwell_seconds"].get(world, 0.0) + counters["world_visits"].get(world, 0.0) * 2.2
        actual = counters["world_saves"].get(world, 0.0) * 3.2 + counters["world_clicks"].get(world, 0.0) * 2.1
        aspirational_worlds.append({"slug": world, "weight": round(aspirational, 2)})
        actual_worlds.append({"slug": world, "weight": round(actual, 2)})
        if aspirational >= 6.0 and actual < aspirational * 0.42:
            curiosity_worlds.append({"slug": world, "weight": round(aspirational - actual, 2)})

    transitions = []
    for key, value in sorted(counters["world_transitions"].items(), key=lambda item: (-item[1], item[0]))[:6]:
        if ">" not in key:
            continue
        from_slug, to_slug = key.split(">", 1)
        transitions.append({"from": from_slug, "to": to_slug, "count": int(round(value))})

    signature_palette = [name for name, _ in _dominant_items(color_counter, limit=3)]
    dominant_silhouette_name = dominant_silhouette[0][0] if dominant_silhouette else "balanced"

    world_affinity_progression = []
    for world, score in world_ranked[:8]:
        world_affinity_progression.append(
            {
                "slug": world,
                "actual": round(counters["world_saves"].get(world, 0.0) * 2.2 + counters["world_clicks"].get(world, 0.0), 2),
                "aspirational": round(counters["world_dwell_seconds"].get(world, 0.0) * 0.2 + counters["world_visits"].get(world, 0.0), 2),
                "score": round(score, 2),
            }
        )

    emotional_pattern = WORLD_EMOTION_SIGNATURES.get(dominant_world, "identity calibration")
    if confidence_growth >= 68 and experimentation >= 62:
        emotional_line = f"Behavior suggests growing confidence in {emotional_pattern} with bolder acceptance."
    elif consistency >= 66:
        emotional_line = f"Behavior remains coherent around {emotional_pattern} with stable identity reinforcement."
    else:
        emotional_line = f"Behavior indicates active exploration; the system is translating curiosity into {emotional_pattern}."

    summary_lines = [
        f"Identity coherence currently reads at {consistency}%.",
        f"Experimental readiness is {int(round(readiness * 100))}% with a controlled evolution ceiling.",
        emotional_line,
    ]

    return {
        "signal_depth": int(event_depth),
        "aesthetic_consistency": consistency,
        "confidence_growth": confidence_growth,
        "experimentation_tendency": experimentation,
        "dominant_world": dominant_world,
        "dominant_worlds": [
            {"slug": slug, "score": round(score, 2), "emotion": WORLD_EMOTION_SIGNATURES.get(slug, "adaptive")}
            for slug, score in world_ranked[:4]
        ],
        "aspirational_identity": aspirational_worlds[:4],
        "actual_behavior": actual_worlds[:4],
        "temporary_curiosity": curiosity_worlds[:4],
        "long_term_preferences": [entry for entry in actual_worlds if entry["weight"] >= 4][:4],
        "world_affinity_progression": world_affinity_progression,
        "transition_paths": transitions,
        "signature_palette": signature_palette,
        "dominant_silhouette": dominant_silhouette_name,
        "layering_frequency": layering_label,
        "accessory_behavior": accessory_label,
        "emotional_pattern": emotional_line,
        "evolution_path": {
            "comfort_experimentality": round(comfort_experimentality, 3),
            "target_experimentality": round(target_experimentality, 3),
            "step_ceiling": round(step_ceiling, 3),
            "readiness": round(readiness, 3),
        },
        "summary_lines": summary_lines,
    }


def recommendation_evolution_adjustment(identity_profile: dict | None, world_slug: str, look_experimentality: float) -> dict:
    profile = identity_profile if isinstance(identity_profile, dict) else {}
    evolution = profile.get("evolution_path", {}) if isinstance(profile.get("evolution_path"), dict) else {}
    comfort = _clamp(_to_float(evolution.get("comfort_experimentality", 0.32), 0.32), 0.05, 0.95)
    target = _clamp(_to_float(evolution.get("target_experimentality", comfort + 0.12), comfort + 0.12), 0.08, 0.98)
    step = _clamp(_to_float(evolution.get("step_ceiling", 0.16), 0.16), 0.08, 0.35)
    readiness = _clamp(_to_float(evolution.get("readiness", 0.35), 0.35), 0.02, 0.98)
    score = _clamp(_to_float(look_experimentality, world_experimentality(world_slug)), 0.0, 1.0)

    bonus = 0
    guidance = "coherent reinforcement"
    if score > comfort + step * 1.35:
        bonus -= int(round(10 + (score - comfort) * 16))
        guidance = "held back to avoid abrupt identity drift"
    elif score > comfort and score <= target + 0.08:
        bonus += int(round(6 + readiness * 10))
        guidance = "guided identity expansion"
    elif abs(score - comfort) <= 0.08:
        bonus += int(round(4 + readiness * 4))
        guidance = "confidence consolidation"
    else:
        bonus += 1

    dominant_worlds = profile.get("dominant_worlds", []) if isinstance(profile.get("dominant_worlds"), list) else []
    dominant_slugs = {str(entry.get("slug", "")) for entry in dominant_worlds if isinstance(entry, dict)}
    if world_slug in dominant_slugs:
        bonus += 4

    curiosity_worlds = profile.get("temporary_curiosity", []) if isinstance(profile.get("temporary_curiosity"), list) else []
    curiosity_slugs = {str(entry.get("slug", "")) for entry in curiosity_worlds if isinstance(entry, dict)}
    if world_slug in curiosity_slugs and readiness >= 0.48:
        bonus += 3
        guidance = "curiosity bridged into structured experimentation"
    elif world_slug in curiosity_slugs and readiness < 0.3:
        bonus -= 3

    return {
        "score_bonus": int(_clamp(bonus, -24, 18)),
        "guidance": guidance,
    }


def adapt_world_for_identity(world: dict, motion_profile: dict, identity_profile: dict | None) -> dict:
    source_world = dict(world or {})
    source_motion = dict(motion_profile or {})
    profile = identity_profile if isinstance(identity_profile, dict) else {}

    dominant_silhouette = _normalize_key(profile.get("dominant_silhouette", ""), 40)
    layering = _normalize_key(profile.get("layering_frequency", "medium"), 20)
    confidence_growth = _to_int(profile.get("confidence_growth", 40), 40)
    experimentation = _to_int(profile.get("experimentation_tendency", 40), 40)

    slug = _normalize_key(source_world.get("slug", ""), 64)
    variant = "balanced axis"
    mood = source_world.get("mood", "")
    motion = source_world.get("motion", "")
    lighting = source_world.get("lighting", "")
    pace = source_motion.get("pace", "")

    if slug == "quiet-luxury":
        if dominant_silhouette in {"tailored", "structured"}:
            variant = "tailored monochrome axis"
            mood = "Elevated restraint with precise tailoring, clean monochrome tension, and low-noise authority."
            motion = "Measured glide with crisp directional framing."
            lighting = "Soft key light with high-precision edge control."
        elif layering == "high":
            variant = "soft layered axis"
            mood = "Understated luxury softened through layered proportion and calmer transitions."
            motion = "Gentle cinematic drift with breathable depth stacking."
            lighting = "Muted daylight with warm reflective gradients."
    elif slug in {"tokyo-street", "monochrome-utility"}:
        if confidence_growth >= 64:
            variant = "engineered experimental axis"
            mood = "Directional confidence with controlled experimentation and coherent rhythm."
            motion = "Kinetic parallax with disciplined cadence."
        else:
            variant = "disciplined transition axis"
            mood = "Street-coded structure with moderated contrast for confidence-building progression."
            motion = "Balanced lateral drift with reduced volatility."
    elif slug == "dark-academia" and layering == "low":
        variant = "streamlined heritage axis"
        mood = "Heritage depth interpreted through cleaner silhouettes and restrained layering."
        motion = "Slow narrative pans with reduced visual density."

    motion_multiplier = 1.0 + ((confidence_growth - 50) / 320.0)
    contrast_shift = (experimentation - 50) / 260.0
    blur_shift = (40 - confidence_growth) / 400.0

    source_motion["tempo"] = round(_clamp(_to_float(source_motion.get("tempo", 1.0), 1.0) * motion_multiplier, 0.5, 1.35), 3)
    source_motion["drift"] = round(_clamp(_to_float(source_motion.get("drift", 0.8), 0.8), 0.45, 1.28), 3)
    source_motion["contrast"] = round(
        _clamp(_to_float(source_motion.get("contrast", 1.0), 1.0) + contrast_shift, 0.62, 1.34),
        3,
    )
    source_motion["blur"] = round(_clamp(_to_float(source_motion.get("blur", 0.5), 0.5) + blur_shift, 0.24, 0.94), 3)
    if pace:
        source_motion["pace"] = pace

    source_world.update(
        {
            "mood": mood,
            "motion": motion,
            "lighting": lighting,
            "identity_variant": variant,
        }
    )
    return {"world": source_world, "motion_profile": source_motion}
