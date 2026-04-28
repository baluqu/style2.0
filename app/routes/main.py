from __future__ import annotations

import csv
import io
import json
import secrets
import uuid
import html
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit

from flask import Blueprint, render_template, current_app, jsonify, request, abort, redirect, url_for, flash, session, Response
from flask_login import login_required, current_user, logout_user

from .. import db, limiter
from ..models import Item, SellerOrder, SellerProduct, User
from ..security import assign_role, audit, require_permission
from ..storage import UploadStorageError, save_uploaded_file

bp = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MODEL_ALLOWED_EXTENSIONS = {"glb", "gltf"}
MAX_TITLE_LENGTH = 300
MAX_URL_LENGTH = 1200
DEMO_MODEL_ALLOWED_PREFIXES = ("/static/models/", "/static/uploads/demo-models/")
DEMO_SAMPLE_MODELS = [
    {
        "slug": "reference",
        "title": "Reference Character",
        "description": "Fast to load. Best default for motion tests.",
        "url": "/static/models/toji-reference.glb",
    },
    {
        "slug": "formal-olive",
        "title": "Formal Olive Look",
        "description": "Balanced silhouette with clean proportions.",
        "url": "/static/models/formal-olive-look.glb",
    },
    {
        "slug": "satin-slip",
        "title": "Satin Slip Dress",
        "description": "Lightweight dress model for quick demos.",
        "url": "/static/models/satin-slip-dress.glb",
    },
]

STYLE_OPTIONS = [
    "Streetwear",
    "Casual",
    "Minimalist",
    "Formal",
    "Vintage",
    "Athleisure",
    "Modest",
    "Religious",
]

GENDER_OPTIONS = [
    "Womenswear",
    "Menswear",
    "Unisex",
]

RELIGION_OPTIONS = [
    "Islam",
    "Christianity",
    "Hinduism",
    "Judaism",
    "Traditional / Spiritual",
    "Other",
]

ACCESSORY_OPTIONS = [
    "Shoes",
    "Watches",
    "Glasses",
    "Bags",
    "Jewelry",
]

GARMENT_OPTIONS = [
    "Abaya",
    "Buibui",
    "Thobe",
    "Kandura",
    "Jubba",
    "Jalabiya",
    "Kurta",
    "Bisht",
    "Kaftan",
    "Jilbab",
    "Hijab",
    "Shayla",
    "Ghutra",
    "Kufi",
]

BUDGET_OPTIONS = [
    "Budget-friendly",
    "Mid-range",
    "Premium",
]

BUDGET_ORDER = {
    "Budget-friendly": 0,
    "Mid-range": 1,
    "Premium": 2,
}

BODY_TYPE_OPTIONS = [
    "Petite",
    "Straight",
    "Curvy",
    "Tall",
    "Athletic",
    "Plus size",
]

SCAN_COVERAGE_OPTIONS = {
    "portrait",
    "upper-body",
    "full-body",
}

SCAN_SILHOUETTE_OPTIONS = {
    "balanced",
    "top-dominant",
    "bottom-dominant",
}

SCAN_PALETTE_OPTIONS = {
    "warm",
    "cool",
    "neutral",
}

SCAN_LIGHTING_OPTIONS = {
    "bright",
    "balanced",
    "low-light",
}

PROFILE_SETTING_DEFAULTS = {
    "show_intro_splash": True,
    "saved_look_reminders": False,
    "daily_outfit_suggestions": True,
}

BAG_TITLE_STOPWORDS = {
    "and",
    "day",
    "edit",
    "fit",
    "for",
    "from",
    "loop",
    "move",
    "night",
    "reset",
    "set",
    "stack",
    "studio",
    "the",
    "with",
}

TRYON_COLOR_SWATCHES = {
    "black": {"primary": "#1f2937", "secondary": "#0f172a", "accent": "#7dd3fc"},
    "blue": {"primary": "#1d4ed8", "secondary": "#172554", "accent": "#93c5fd"},
    "brown": {"primary": "#8b5e34", "secondary": "#3f2a1d", "accent": "#f6ad55"},
    "pearl": {"primary": "#f3e4cc", "secondary": "#d6c1a5", "accent": "#f59e0b"},
    "rose": {"primary": "#f43f5e", "secondary": "#831843", "accent": "#fda4af"},
    "emerald": {"primary": "#10b981", "secondary": "#064e3b", "accent": "#6ee7b7"},
    "green": {"primary": "#16a34a", "secondary": "#14532d", "accent": "#86efac"},
    "white": {"primary": "#f8fafc", "secondary": "#cbd5e1", "accent": "#38bdf8"},
    "neutral": {"primary": "#a8a29e", "secondary": "#44403c", "accent": "#f5d0fe"},
}

TRYON_FULL_LENGTH_KEYWORDS = {
    "abaya",
    "buibui",
    "thobe",
    "kandura",
    "jubba",
    "jalabiya",
    "kaftan",
    "jilbab",
    "dress",
    "gown",
}


def catalog_item(sku: str, title: str, category: str, brand: str, price: int) -> dict:
    return {"sku": sku, "title": title, "category": category, "brand": brand, "price": price}


def build_look(
    slug: str,
    title: str,
    creator: str,
    tagline: str,
    styles: list[str],
    brands: list[str],
    genders: list[str],
    budget: str,
    color: str,
    image_url: str,
    gradient: str,
    items: list[tuple[str, str, str, str, int]],
    *,
    body_types: list[str] | None = None,
    religions: list[str] | None = None,
    match_text: str = "",
) -> dict:
    look_items = [catalog_item(*item) for item in items]
    return {
        "slug": slug,
        "title": title,
        "creator": creator,
        "tagline": tagline,
        "styles": styles,
        "brands": brands,
        "genders": genders,
        "religions": religions or [],
        "body_types": body_types or BODY_TYPE_OPTIONS,
        "budget": budget,
        "color": color,
        "price_total": sum(item["price"] for item in look_items),
        "image_url": image_url,
        "match_text": match_text or f"A strong match for shoppers browsing {', '.join(styles[:2]).lower()} looks.",
        "items": look_items,
        "gradient": gradient,
    }

LOOKS = [
    {
        "slug": "monochrome-runway",
        "title": "Monochrome Runway Reset",
        "creator": "StyleBridge Edit",
        "tagline": "Clean layers, sharp tailoring, and a low-stress weekday flex.",
        "styles": ["Minimalist", "Formal"],
        "brands": ["COS", "Arket"],
        "genders": ["Womenswear", "Menswear", "Unisex"],
        "body_types": ["Straight", "Tall", "Athletic"],
        "budget": "Premium",
        "color": "Black",
        "price_total": 316,
        "image_url": "https://images.pexels.com/photos/18794492/pexels-photo-18794492.jpeg?cs=srgb&dl=pexels-braks-alexandros-2366968-18794492.jpg&fm=jpg",
        "match_text": "Strong match for polished, minimal wardrobes.",
        "items": [
            {"sku": "coat-01", "title": "Structured black coat", "category": "Outerwear", "brand": "COS", "price": 148},
            {"sku": "pant-01", "title": "Tapered charcoal trouser", "category": "Bottom", "brand": "Arket", "price": 88},
            {"sku": "shoe-01", "title": "Leather derby", "category": "Shoes", "brand": "Vagabond", "price": 80},
        ],
        "gradient": "from-slate-700 via-slate-900 to-black",
    },
    {
        "slug": "streetwear-weekend",
        "title": "Streetwear Weekend Stack",
        "creator": "Community Trend",
        "tagline": "Relaxed shape, layered texture, and an easy weekend cart builder.",
        "styles": ["Streetwear", "Casual"],
        "brands": ["Nike", "Weekday"],
        "genders": ["Womenswear", "Menswear", "Unisex"],
        "body_types": ["Petite", "Straight", "Athletic"],
        "budget": "Mid-range",
        "color": "Blue",
        "price_total": 214,
        "image_url": "https://images.pexels.com/photos/19243446/pexels-photo-19243446.jpeg?cs=srgb&dl=pexels-felix-young-449360607-19243446.jpg&fm=jpg",
        "match_text": "Great for users who save oversized, athletic, and denim-heavy looks.",
        "items": [
            {"sku": "hoodie-01", "title": "Oversized washed hoodie", "category": "Top", "brand": "Weekday", "price": 64},
            {"sku": "denim-01", "title": "Relaxed denim", "category": "Bottom", "brand": "Weekday", "price": 72},
            {"sku": "shoe-02", "title": "Retro runner", "category": "Shoes", "brand": "Nike", "price": 78},
        ],
        "gradient": "from-sky-500 via-blue-700 to-slate-950",
    },
    {
        "slug": "after-hours-satin",
        "title": "After-Hours Satin",
        "creator": "StyleBridge Studio",
        "tagline": "Fluid shine, elegant balance, and a full-look checkout nudge.",
        "styles": ["Formal", "Vintage"],
        "brands": ["Mango", "Charles & Keith"],
        "genders": ["Womenswear", "Unisex"],
        "body_types": ["Petite", "Straight", "Curvy"],
        "budget": "Premium",
        "color": "Pearl",
        "price_total": 284,
        "image_url": "https://images.pexels.com/photos/33781201/pexels-photo-33781201.jpeg?cs=srgb&dl=pexels-peterdanthy-33781201.jpg&fm=jpg",
        "match_text": "High resonance for eveningwear, satin, and elevated silhouettes.",
        "items": [
            {"sku": "dress-01", "title": "Bias-cut satin dress", "category": "Dress", "brand": "Mango", "price": 156},
            {"sku": "heel-01", "title": "Strap heel", "category": "Shoes", "brand": "Charles & Keith", "price": 74},
            {"sku": "bag-01", "title": "Mini shoulder bag", "category": "Accessory", "brand": "Mango", "price": 54},
        ],
        "gradient": "from-rose-600 via-fuchsia-900 to-slate-950",
    },
    {
        "slug": "campus-athleisure",
        "title": "Campus Athleisure Loop",
        "creator": "Daily Drop",
        "tagline": "Built for movement, layered comfort, and daily repeat wear.",
        "styles": ["Athleisure", "Casual"],
        "brands": ["Adidas", "Puma"],
        "genders": ["Womenswear", "Menswear", "Unisex"],
        "body_types": ["Athletic", "Straight", "Petite", "Plus size"],
        "budget": "Budget-friendly",
        "color": "Brown",
        "price_total": 162,
        "image_url": "https://images.pexels.com/photos/13360782/pexels-photo-13360782.jpeg?cs=srgb&dl=pexels-hoa-tran-293444577-13360782.jpg&fm=jpg",
        "match_text": "Works best for comfort-first shoppers and repeat daily outfits.",
        "items": [
            {"sku": "zip-01", "title": "Performance zip hoodie", "category": "Top", "brand": "Adidas", "price": 58},
            {"sku": "jogger-01", "title": "Slim jogger", "category": "Bottom", "brand": "Puma", "price": 46},
            {"sku": "trainer-01", "title": "Everyday trainer", "category": "Shoes", "brand": "Adidas", "price": 58},
        ],
        "gradient": "from-slate-400 via-slate-700 to-slate-950",
    },
    {
        "slug": "soft-tailoring-studio",
        "title": "Soft Tailoring Studio",
        "creator": "Office Edit",
        "tagline": "Neutral tailoring with a relaxed blazer finish for shoppers who want polished, not rigid.",
        "styles": ["Minimalist", "Formal", "Casual"],
        "brands": ["Mango", "Massimo Dutti"],
        "genders": ["Womenswear", "Unisex"],
        "body_types": ["Petite", "Straight", "Curvy"],
        "budget": "Mid-range",
        "color": "Beige",
        "price_total": 238,
        "image_url": "https://images.pexels.com/photos/23531833/pexels-photo-23531833.jpeg?cs=srgb&dl=pexels-matheus-rodrigues-672111387-23531833.jpg&fm=jpg",
        "match_text": "Ideal for minimalist users who still want softer structure and warmer neutrals.",
        "items": [
            {"sku": "blazer-01", "title": "Relaxed beige blazer", "category": "Outerwear", "brand": "Mango", "price": 96},
            {"sku": "top-01", "title": "Ribbed bandeau top", "category": "Top", "brand": "Mango", "price": 28},
            {"sku": "jean-01", "title": "Straight light-wash denim", "category": "Bottom", "brand": "Massimo Dutti", "price": 114},
        ],
        "gradient": "from-stone-300 via-amber-200 to-slate-950",
    },
    {
        "slug": "city-knit-neutral",
        "title": "City Knit Neutral",
        "creator": "Daily Layer",
        "tagline": "A calm knit-and-trouser combo that lands between polished casual and repeat daily wear.",
        "styles": ["Casual", "Minimalist"],
        "brands": ["COS", "Zara"],
        "genders": ["Womenswear", "Unisex"],
        "body_types": ["Straight", "Tall", "Curvy"],
        "budget": "Mid-range",
        "color": "Grey",
        "price_total": 192,
        "image_url": "https://images.pexels.com/photos/15076269/pexels-photo-15076269.jpeg?cs=srgb&dl=pexels-marcus-queiroga-silva-86421404-15076269.jpg&fm=jpg",
        "match_text": "A strong fallback for shoppers who save simple city looks with clean neutrals.",
        "items": [
            {"sku": "knit-01", "title": "Light grey knit top", "category": "Top", "brand": "COS", "price": 54},
            {"sku": "pant-02", "title": "Ivory tailored trouser", "category": "Bottom", "brand": "Zara", "price": 72},
            {"sku": "shoe-03", "title": "Soft leather loafer", "category": "Shoes", "brand": "COS", "price": 66},
        ],
        "gradient": "from-slate-300 via-slate-500 to-slate-950",
    },
    {
        "slug": "denim-vintage-edit",
        "title": "Denim Vintage Edit",
        "creator": "Weekend Archive",
        "tagline": "Vintage-leaning denim, darker accessories, and a moodier urban finish.",
        "styles": ["Vintage", "Streetwear", "Casual"],
        "brands": ["Levi's", "Dr. Martens"],
        "genders": ["Womenswear", "Unisex"],
        "body_types": ["Petite", "Straight", "Curvy"],
        "budget": "Mid-range",
        "color": "Blue",
        "price_total": 226,
        "image_url": "https://images.pexels.com/photos/32320147/pexels-photo-32320147.jpeg?cs=srgb&dl=pexels-rezapix1-32320147.jpg&fm=jpg",
        "match_text": "Best for users who mix vintage denim, darker footwear, and edgier city styling.",
        "items": [
            {"sku": "jacket-01", "title": "Faded denim jacket", "category": "Outerwear", "brand": "Levi's", "price": 94},
            {"sku": "jean-02", "title": "High-rise straight jean", "category": "Bottom", "brand": "Levi's", "price": 76},
            {"sku": "boot-01", "title": "Black platform boot", "category": "Shoes", "brand": "Dr. Martens", "price": 56},
        ],
        "gradient": "from-blue-500 via-slate-700 to-slate-950",
    },
    {
        "slug": "night-tailoring-dark",
        "title": "Night Tailoring Dark",
        "creator": "After Dark",
        "tagline": "A sharper, darker tailored look for premium shoppers who want clean structure with attitude.",
        "styles": ["Formal", "Streetwear", "Minimalist"],
        "brands": ["AllSaints", "Weekday"],
        "genders": ["Menswear", "Unisex"],
        "body_types": ["Tall", "Athletic", "Straight"],
        "budget": "Premium",
        "color": "Black",
        "price_total": 304,
        "image_url": "https://images.pexels.com/photos/31061132/pexels-photo-31061132.jpeg?cs=srgb&dl=pexels-covantnyc-31061132.jpg&fm=jpg",
        "match_text": "High intent for users who want dark tailoring, sharper layers, and evening city energy.",
        "items": [
            {"sku": "coat-02", "title": "Long black overcoat", "category": "Outerwear", "brand": "AllSaints", "price": 152},
            {"sku": "top-02", "title": "Black fitted tank", "category": "Top", "brand": "Weekday", "price": 32},
            {"sku": "pant-03", "title": "Slim black trouser", "category": "Bottom", "brand": "AllSaints", "price": 120},
        ],
        "gradient": "from-zinc-700 via-slate-900 to-black",
    },
    {
        "slug": "modest-everyday-indigo",
        "title": "Indigo Everyday Abaya",
        "creator": "Modest Edit",
        "tagline": "Embroidery-led abaya layering with an easy navy palette for polished everyday dressing.",
        "styles": ["Modest", "Casual", "Minimalist"],
        "brands": ["Aab", "Haute Hijab"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Petite", "Straight", "Curvy", "Tall", "Plus size"],
        "budget": "Mid-range",
        "color": "Navy",
        "price_total": 306,
        "image_url": "https://images.pexels.com/photos/35344026/pexels-photo-35344026.jpeg?cs=srgb&dl=pexels-bymalbus-35344026.jpg&fm=jpg",
        "match_text": "Strong for shoppers looking for elegant everyday modest wear with soft structure.",
        "items": [
            {"sku": "abaya-11", "title": "Embroidered navy abaya", "category": "Dress", "brand": "Aab", "price": 118},
            {"sku": "inner-11", "title": "Soft jersey inner dress", "category": "Layer", "brand": "Aab", "price": 44},
            {"sku": "hijab-11", "title": "Stone chiffon hijab", "category": "Headwear", "brand": "Haute Hijab", "price": 28},
            {"sku": "bag-11", "title": "Structured everyday tote", "category": "Accessory", "brand": "JW Pei", "price": 62},
            {"sku": "flat-11", "title": "Minimal leather flat", "category": "Shoes", "brand": "Charles & Keith", "price": 54},
        ],
        "gradient": "from-indigo-400 via-slate-700 to-slate-950",
    },
    {
        "slug": "desert-rose-modest",
        "title": "Berry Day Buibui",
        "creator": "Community Trend",
        "tagline": "Comfort-first buibui styling with warm berry tones and light daily accessories.",
        "styles": ["Modest", "Casual", "Minimalist"],
        "brands": ["Modanisa", "Bokitta"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Petite", "Straight", "Curvy", "Plus size"],
        "budget": "Budget-friendly",
        "color": "Berry",
        "price_total": 194,
        "image_url": "https://images.pexels.com/photos/33716223/pexels-photo-33716223.jpeg?cs=srgb&dl=pexels-abdulkadir-muhammad-sani-2150944758-33716223.jpg&fm=jpg",
        "match_text": "Built for users who want breathable modest pieces that still feel styled and intentional.",
        "items": [
            {"sku": "dress-12", "title": "Flowing berry midi jilbab", "category": "Dress", "brand": "Modanisa", "price": 72},
            {"sku": "hijab-12", "title": "Sand wrap hijab", "category": "Headwear", "brand": "Bokitta", "price": 24},
            {"sku": "shoe-12", "title": "Everyday slingback flat", "category": "Shoes", "brand": "Aldo", "price": 38},
            {"sku": "bag-12", "title": "Compact crossbody pouch", "category": "Accessory", "brand": "Mango", "price": 34},
            {"sku": "layer-12", "title": "Cooling jersey underlayer", "category": "Layer", "brand": "Modanisa", "price": 26},
        ],
        "gradient": "from-rose-400 via-rose-700 to-slate-950",
    },
    {
        "slug": "silk-sand-evening",
        "title": "Silk Sand Abaya",
        "creator": "Occasion Studio",
        "tagline": "Soft neutral abaya shine and detailed sleeves for elevated eveningwear with modest coverage.",
        "styles": ["Modest", "Formal", "Minimalist"],
        "brands": ["Aab", "Haute Hijab"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Curvy", "Tall", "Plus size"],
        "budget": "Premium",
        "color": "Taupe",
        "price_total": 348,
        "image_url": "https://images.pexels.com/photos/35324626/pexels-photo-35324626.jpeg?cs=srgb&dl=pexels-bymalbus-35324626.jpg&fm=jpg",
        "match_text": "A premium match for shoppers saving soft-toned abayas, occasionwear, and elegant modest edits.",
        "items": [
            {"sku": "abaya-13", "title": "Taupe satin evening abaya", "category": "Dress", "brand": "Aab", "price": 146},
            {"sku": "slip-13", "title": "Luxe tonal slip dress", "category": "Layer", "brand": "Aab", "price": 58},
            {"sku": "hijab-13", "title": "Mocha silk shayla", "category": "Headwear", "brand": "Haute Hijab", "price": 34},
            {"sku": "heel-13", "title": "Pearl pointed mule", "category": "Shoes", "brand": "Charles & Keith", "price": 72},
            {"sku": "earring-13", "title": "Emerald drop earring", "category": "Accessory", "brand": "Ana Luisa", "price": 38},
        ],
        "gradient": "from-stone-300 via-stone-500 to-slate-950",
    },
    {
        "slug": "city-layered-modest",
        "title": "City Layered Abaya",
        "creator": "Street Layer",
        "tagline": "A layered black-and-camel abaya look that lands between modest dressing and city street styling.",
        "styles": ["Modest", "Streetwear", "Casual"],
        "brands": ["Veiled Collection", "COS"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Curvy", "Tall", "Plus size"],
        "budget": "Premium",
        "color": "Black",
        "price_total": 396,
        "image_url": "https://images.pexels.com/photos/31645096/pexels-photo-31645096.jpeg?cs=srgb&dl=pexels-2bkathmeow-31645096.jpg&fm=jpg",
        "match_text": "Great for shoppers who want modest layering with stronger outerwear and streetwear energy.",
        "items": [
            {"sku": "abaya-14", "title": "Black draped open abaya", "category": "Outerwear", "brand": "Veiled Collection", "price": 132},
            {"sku": "set-14", "title": "Wide-leg inner co-ord", "category": "Set", "brand": "COS", "price": 74},
            {"sku": "scarf-14", "title": "Jet black modal scarf", "category": "Headwear", "brand": "Haute Hijab", "price": 28},
            {"sku": "jacket-14", "title": "Camel shearling-trim jacket", "category": "Outerwear", "brand": "Mango", "price": 98},
            {"sku": "bag-14", "title": "Structured weekender tote", "category": "Accessory", "brand": "JW Pei", "price": 64},
        ],
        "gradient": "from-amber-500 via-slate-800 to-slate-950",
    },
    {
        "slug": "midnight-minimal-modest",
        "title": "Midnight Minimal Abaya",
        "creator": "Clean Lines",
        "tagline": "Dark minimal abaya dressing with crisp contrast and a clean finish.",
        "styles": ["Modest", "Minimalist", "Formal"],
        "brands": ["Aab", "Haute Hijab"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Petite", "Straight", "Curvy", "Tall"],
        "budget": "Mid-range",
        "color": "Black",
        "price_total": 292,
        "image_url": "https://images.pexels.com/photos/32208654/pexels-photo-32208654.jpeg?cs=srgb&dl=pexels-abdulkadir-muhammad-sani-2150944758-32208654.jpg&fm=jpg",
        "match_text": "A clean fit for shoppers saving dark, minimal modest looks with just enough detail.",
        "items": [
            {"sku": "abaya-15", "title": "Midnight beaded abaya", "category": "Dress", "brand": "Aab", "price": 128},
            {"sku": "hijab-15", "title": "Crisp white jersey hijab", "category": "Headwear", "brand": "Haute Hijab", "price": 22},
            {"sku": "flat-15", "title": "Polished square-toe flat", "category": "Shoes", "brand": "Charles & Keith", "price": 54},
            {"sku": "bag-15", "title": "Mini top-handle bag", "category": "Accessory", "brand": "Mango", "price": 46},
            {"sku": "slip-15", "title": "Cooling tonal underdress", "category": "Layer", "brand": "Aab", "price": 42},
        ],
        "gradient": "from-slate-500 via-slate-800 to-black",
    },
    {
        "slug": "vibrant-eid-statement",
        "title": "Vibrant Eid Statement",
        "creator": "Celebration Edit",
        "tagline": "High-color satin, soft coverage, and dressy accessories for standout festive wear.",
        "styles": ["Modest", "Vintage", "Formal"],
        "brands": ["Hanifa", "Modanisa"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Curvy", "Tall", "Plus size"],
        "budget": "Premium",
        "color": "Coral",
        "price_total": 330,
        "image_url": "https://images.pexels.com/photos/34470388/pexels-photo-34470388.jpeg?cs=srgb&dl=pexels-taiyesalawu-34470388.jpg&fm=jpg",
        "match_text": "High resonance for festive modest looks with bold color and evening energy.",
        "items": [
            {"sku": "dress-16", "title": "Vibrant satin kaftan dress", "category": "Dress", "brand": "Hanifa", "price": 154},
            {"sku": "scarf-16", "title": "Sunset wrap hijab", "category": "Headwear", "brand": "Modanisa", "price": 24},
            {"sku": "heel-16", "title": "Tonal block heel sandal", "category": "Shoes", "brand": "Zara", "price": 58},
            {"sku": "bracelet-16", "title": "Stacked gold bangles", "category": "Accessory", "brand": "Ana Luisa", "price": 42},
            {"sku": "clutch-16", "title": "Sculpted evening clutch", "category": "Accessory", "brand": "Mango", "price": 52},
        ],
        "gradient": "from-orange-400 via-rose-600 to-slate-950",
    },
    {
        "slug": "black-abaya-studio-classic",
        "title": "Black Abaya Studio Classic",
        "creator": "Abaya Edit",
        "tagline": "A clean black abaya look with light gold accents and everyday polish.",
        "styles": ["Modest", "Minimalist", "Formal"],
        "brands": ["Aab", "Haute Hijab"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Petite", "Straight", "Curvy", "Tall", "Plus size"],
        "budget": "Mid-range",
        "color": "Black",
        "price_total": 287,
        "image_url": "https://images.pexels.com/photos/13791261/pexels-photo-13791261.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Great for women searching directly for black abaya looks that feel classic and wearable.",
        "items": [
            {"sku": "abaya-31", "title": "Classic black abaya", "category": "Dress", "brand": "Aab", "price": 129},
            {"sku": "hijab-31", "title": "Silk-edge black hijab", "category": "Headwear", "brand": "Haute Hijab", "price": 32},
            {"sku": "sandal-31", "title": "Minimal buckle sandal", "category": "Shoes", "brand": "Charles & Keith", "price": 58},
            {"sku": "bag-31", "title": "Quilted phone pouch", "category": "Accessory", "brand": "JW Pei", "price": 44},
            {"sku": "ring-31", "title": "Slim gold stacking ring", "category": "Accessory", "brand": "Ana Luisa", "price": 24},
        ],
        "gradient": "from-slate-500 via-slate-800 to-black",
    },
    {
        "slug": "teal-abaya-statement",
        "title": "Teal Abaya Statement",
        "creator": "Dubai Studio",
        "tagline": "Studio-shot teal abaya styling for women who want richer color without losing modest structure.",
        "styles": ["Modest", "Formal", "Vintage"],
        "brands": ["Modanisa", "Bokitta"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Curvy", "Tall", "Plus size"],
        "budget": "Premium",
        "color": "Teal",
        "price_total": 310,
        "image_url": "https://images.pexels.com/photos/13776526/pexels-photo-13776526.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "A strong match for women looking for dressier abaya edits with a richer color story.",
        "items": [
            {"sku": "abaya-32", "title": "Teal statement abaya", "category": "Dress", "brand": "Modanisa", "price": 136},
            {"sku": "hijab-32", "title": "Soft matte wrap hijab", "category": "Headwear", "brand": "Bokitta", "price": 26},
            {"sku": "heel-32", "title": "Metallic evening heel", "category": "Shoes", "brand": "Charles & Keith", "price": 62},
            {"sku": "clutch-32", "title": "Structured satin clutch", "category": "Accessory", "brand": "Mango", "price": 48},
            {"sku": "bracelet-32", "title": "Textured cuff bracelet", "category": "Accessory", "brand": "Ana Luisa", "price": 38},
        ],
        "gradient": "from-teal-400 via-cyan-700 to-slate-950",
    },
    {
        "slug": "embroidered-rose-buibui",
        "title": "Embroidered Rose Buibui",
        "creator": "Lounge Luxe",
        "tagline": "A sofa-styled embroidered buibui with soft rose tones and easy dress-up pieces.",
        "styles": ["Modest", "Casual", "Vintage"],
        "brands": ["Veiled Collection", "Mango"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Petite", "Straight", "Curvy", "Plus size"],
        "budget": "Mid-range",
        "color": "Rose",
        "price_total": 278,
        "image_url": "https://images.pexels.com/photos/13863601/pexels-photo-13863601.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Ideal for shoppers who want softer buibui looks with embroidery and relaxed elegance.",
        "items": [
            {"sku": "buibui-33", "title": "Embroidered rose buibui", "category": "Dress", "brand": "Veiled Collection", "price": 118},
            {"sku": "hijab-33", "title": "Dusty-rose chiffon hijab", "category": "Headwear", "brand": "Mango", "price": 28},
            {"sku": "flat-33", "title": "Soft pointed flat", "category": "Shoes", "brand": "Aldo", "price": 34},
            {"sku": "bag-33", "title": "Mini handle satchel", "category": "Accessory", "brand": "Mango", "price": 52},
            {"sku": "earring-33", "title": "Pearl cluster earrings", "category": "Accessory", "brand": "Ana Luisa", "price": 46},
        ],
        "gradient": "from-rose-300 via-rose-600 to-slate-950",
    },
    {
        "slug": "mosque-marble-abaya",
        "title": "Studio Contrast Abaya",
        "creator": "Faith Edit",
        "tagline": "Elegant black-and-white abaya dressing with a serene ceremonial feel.",
        "styles": ["Modest", "Formal", "Minimalist"],
        "brands": ["Aab", "Haute Hijab"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Curvy", "Tall", "Plus size"],
        "budget": "Premium",
        "color": "Black",
        "price_total": 346,
        "image_url": "https://images.pexels.com/photos/13776527/pexels-photo-13776527.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Strong for women filtering toward elegant abaya looks with a more ceremonial mood.",
        "items": [
            {"sku": "abaya-34", "title": "Black-and-white occasion abaya", "category": "Dress", "brand": "Aab", "price": 148},
            {"sku": "shayla-34", "title": "Ivory satin shayla", "category": "Headwear", "brand": "Haute Hijab", "price": 36},
            {"sku": "heel-34", "title": "Gold-strap dress heel", "category": "Shoes", "brand": "Charles & Keith", "price": 66},
            {"sku": "bag-34", "title": "Cream clasp mini bag", "category": "Accessory", "brand": "Mango", "price": 52},
            {"sku": "cuff-34", "title": "Polished gold cuff", "category": "Accessory", "brand": "Ana Luisa", "price": 44},
        ],
        "gradient": "from-stone-100 via-stone-300 to-slate-950",
    },
    {
        "slug": "desert-breeze-buibui",
        "title": "Desert Breeze Buibui",
        "creator": "Desert Drop",
        "tagline": "An airy black buibui with sand-friendly layers and easy weekend accessories.",
        "styles": ["Modest", "Casual", "Minimalist"],
        "brands": ["East Essence", "Bokitta"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Petite", "Straight", "Curvy", "Tall", "Plus size"],
        "budget": "Budget-friendly",
        "color": "Sand",
        "price_total": 250,
        "image_url": "https://images.pexels.com/photos/2911208/pexels-photo-2911208.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "A good fit for users who want an easy buibui look with lower-cost daily accessories.",
        "items": [
            {"sku": "buibui-35", "title": "Airy black buibui", "category": "Dress", "brand": "East Essence", "price": 104},
            {"sku": "hijab-35", "title": "Sand jersey hijab", "category": "Headwear", "brand": "Bokitta", "price": 22},
            {"sku": "flat-35", "title": "Desert leather flat", "category": "Shoes", "brand": "Bata", "price": 40},
            {"sku": "bag-35", "title": "Woven shopper tote", "category": "Accessory", "brand": "Mango", "price": 48},
            {"sku": "shade-35", "title": "Soft-frame sunglasses", "category": "Accessory", "brand": "Quay", "price": 36},
        ],
        "gradient": "from-amber-300 via-stone-600 to-slate-950",
    },
    {
        "slug": "maroon-meadow-abaya",
        "title": "Maroon Meadow Abaya",
        "creator": "Weekend Escape",
        "tagline": "A flowing maroon abaya look with soft neutrals and a breezy outdoors feel.",
        "styles": ["Modest", "Casual", "Vintage"],
        "brands": ["Modanisa", "Charles & Keith"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Petite", "Straight", "Curvy", "Tall"],
        "budget": "Mid-range",
        "color": "Maroon",
        "price_total": 284,
        "image_url": "https://images.pexels.com/photos/9316579/pexels-photo-9316579.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Built for women who want maroon abaya options that feel softer and more outdoorsy.",
        "items": [
            {"sku": "abaya-36", "title": "Flowing maroon abaya", "category": "Dress", "brand": "Modanisa", "price": 124},
            {"sku": "hijab-36", "title": "Cream modal hijab", "category": "Headwear", "brand": "Bokitta", "price": 26},
            {"sku": "flat-36", "title": "Cushioned leather flat", "category": "Shoes", "brand": "Charles & Keith", "price": 46},
            {"sku": "bag-36", "title": "Crescent shoulder tote", "category": "Accessory", "brand": "Mango", "price": 56},
            {"sku": "bangle-36", "title": "Slim stacked bangles", "category": "Accessory", "brand": "Ana Luisa", "price": 32},
        ],
        "gradient": "from-rose-500 via-stone-700 to-slate-950",
    },
    {
        "slug": "gold-trim-abaya-studio",
        "title": "Gold-Trim Abaya Studio",
        "creator": "Studio Luxe",
        "tagline": "Black-and-gold abaya styling with elevated accessories for dressier days.",
        "styles": ["Modest", "Formal", "Minimalist"],
        "brands": ["Aab", "Charles & Keith"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Curvy", "Tall", "Plus size"],
        "budget": "Premium",
        "color": "Black",
        "price_total": 354,
        "image_url": "https://images.pexels.com/photos/13791251/pexels-photo-13791251.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "A premium match for shoppers specifically looking for gold-trimmed black abaya looks.",
        "items": [
            {"sku": "abaya-37", "title": "Gold-trim black abaya", "category": "Dress", "brand": "Aab", "price": 152},
            {"sku": "hijab-37", "title": "Satin black hijab", "category": "Headwear", "brand": "Haute Hijab", "price": 34},
            {"sku": "heel-37", "title": "Dressy almond-toe heel", "category": "Shoes", "brand": "Charles & Keith", "price": 68},
            {"sku": "earring-37", "title": "Crystal drop earrings", "category": "Accessory", "brand": "Ana Luisa", "price": 42},
            {"sku": "clutch-37", "title": "Metal frame clutch", "category": "Accessory", "brand": "Mango", "price": 58},
        ],
        "gradient": "from-amber-200 via-slate-800 to-black",
    },
    {
        "slug": "city-buibui-in-black",
        "title": "City Buibui in Black",
        "creator": "Urban Modest",
        "tagline": "A versatile black buibui outfit tuned for commuting, errands, and repeated daily wear.",
        "styles": ["Modest", "Casual", "Streetwear"],
        "brands": ["Veiled Collection", "COS"],
        "genders": ["Womenswear"],
        "religions": ["Islam"],
        "body_types": ["Petite", "Straight", "Curvy", "Tall", "Plus size"],
        "budget": "Mid-range",
        "color": "Black",
        "price_total": 246,
        "image_url": "https://images.pexels.com/photos/7249355/pexels-photo-7249355.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Good for women wanting a practical black buibui that still feels styled enough for the city.",
        "items": [
            {"sku": "buibui-38", "title": "Daily black buibui", "category": "Dress", "brand": "Veiled Collection", "price": 96},
            {"sku": "hijab-38", "title": "Soft cotton hijab", "category": "Headwear", "brand": "Haute Hijab", "price": 24},
            {"sku": "shoe-38", "title": "Minimal city sneaker", "category": "Shoes", "brand": "COS", "price": 42},
            {"sku": "tote-38", "title": "Large commuter tote", "category": "Accessory", "brand": "Mango", "price": 46},
            {"sku": "layer-38", "title": "Lightweight underdress", "category": "Layer", "brand": "Veiled Collection", "price": 38},
        ],
        "gradient": "from-slate-400 via-slate-700 to-black",
    },
    {
        "slug": "thobe-sunset-edit",
        "title": "White Thobe Sunset Edit",
        "creator": "Menswear Focus",
        "tagline": "Clean white thobe styling with refined accessories and a sharp minimal finish.",
        "styles": ["Modest", "Minimalist", "Formal"],
        "brands": ["East Essence", "Swiss Arabian"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Tall", "Athletic", "Plus size"],
        "budget": "Mid-range",
        "color": "White",
        "price_total": 258,
        "image_url": "https://images.pexels.com/photos/5988826/pexels-photo-5988826.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Ideal for shoppers saving clean thobes, white palettes, and polished modest menswear.",
        "items": [
            {"sku": "thobe-21", "title": "Crisp white thobe", "category": "Set", "brand": "East Essence", "price": 94},
            {"sku": "sandal-21", "title": "Brown leather sandal", "category": "Shoes", "brand": "Bata", "price": 42},
            {"sku": "cap-21", "title": "Textured kufi cap", "category": "Headwear", "brand": "East Essence", "price": 18},
            {"sku": "watch-21", "title": "Silver dress watch", "category": "Accessory", "brand": "Fossil", "price": 76},
            {"sku": "scent-21", "title": "Oud pocket fragrance", "category": "Accessory", "brand": "Swiss Arabian", "price": 28},
        ],
        "gradient": "from-slate-100 via-slate-400 to-slate-900",
    },
    {
        "slug": "heritage-occasion-white",
        "title": "Heritage Kandura Occasion",
        "creator": "Ceremony Edit",
        "tagline": "Occasion-ready Gulf tailoring with gold trim and premium formal accessories.",
        "styles": ["Modest", "Formal", "Vintage"],
        "brands": ["Bait Al Kandora", "Ounass"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Tall", "Athletic"],
        "budget": "Premium",
        "color": "Cream",
        "price_total": 454,
        "image_url": "https://images.pexels.com/photos/34171660/pexels-photo-34171660.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "A premium match for festive menswear, ceremonial dressing, and classic Gulf silhouettes.",
        "items": [
            {"sku": "bisht-22", "title": "Gold-trim ceremonial bisht", "category": "Outerwear", "brand": "Ounass", "price": 184},
            {"sku": "thobe-22", "title": "Tailored white kandura", "category": "Set", "brand": "Bait Al Kandora", "price": 112},
            {"sku": "ghutra-22", "title": "Crisp ghutra and agal set", "category": "Headwear", "brand": "Bait Al Kandora", "price": 46},
            {"sku": "loafer-22", "title": "Soft leather occasion slipper", "category": "Shoes", "brand": "Dune London", "price": 68},
            {"sku": "ring-22", "title": "Minimal signet ring", "category": "Accessory", "brand": "Swarovski", "price": 44},
        ],
        "gradient": "from-amber-100 via-stone-300 to-slate-950",
    },
    {
        "slug": "espresso-friday-fit",
        "title": "Espresso Jubba Friday",
        "creator": "Casual Friday",
        "tagline": "A darker jalabiya and jubba-inspired look with relaxed styling cues for off-duty modest menswear.",
        "styles": ["Modest", "Casual", "Streetwear"],
        "brands": ["East Essence", "Uniqlo"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Athletic", "Tall", "Plus size"],
        "budget": "Mid-range",
        "color": "Brown",
        "price_total": 242,
        "image_url": "https://images.pexels.com/photos/17364830/pexels-photo-17364830.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Works well for users who want modest menswear that feels relaxed, tonal, and contemporary.",
        "items": [
            {"sku": "jubba-23", "title": "Espresso jalabiya jubba", "category": "Set", "brand": "East Essence", "price": 88},
            {"sku": "scarf-23", "title": "Checked sand scarf", "category": "Headwear", "brand": "East Essence", "price": 26},
            {"sku": "sandal-23", "title": "Dark leather slide", "category": "Shoes", "brand": "Bata", "price": 34},
            {"sku": "shade-23", "title": "Angular black sunglasses", "category": "Accessory", "brand": "Quay", "price": 46},
            {"sku": "trouser-23", "title": "Relaxed drawstring trouser", "category": "Bottom", "brand": "Uniqlo", "price": 48},
        ],
        "gradient": "from-amber-700 via-stone-800 to-slate-950",
    },
    {
        "slug": "charcoal-kandura-night",
        "title": "Charcoal Kandura Night",
        "creator": "Evening Line",
        "tagline": "A charcoal kandura outfit with dark accessories for dressier night wear.",
        "styles": ["Modest", "Formal", "Minimalist"],
        "brands": ["Bait Al Kandora", "Fossil"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Tall", "Athletic", "Plus size"],
        "budget": "Premium",
        "color": "Charcoal",
        "price_total": 362,
        "image_url": "https://images.pexels.com/photos/34171706/pexels-photo-34171706.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Strong for men searching premium kandura looks with darker evening polish.",
        "items": [
            {"sku": "kandura-41", "title": "Tailored charcoal kandura", "category": "Set", "brand": "Bait Al Kandora", "price": 144},
            {"sku": "ghutra-41", "title": "Monochrome ghutra set", "category": "Headwear", "brand": "Bait Al Kandora", "price": 44},
            {"sku": "loafer-41", "title": "Soft black leather loafer", "category": "Shoes", "brand": "Dune London", "price": 78},
            {"sku": "watch-41", "title": "Gunmetal dress watch", "category": "Accessory", "brand": "Fossil", "price": 76},
            {"sku": "scent-41", "title": "Dark oud pocket spray", "category": "Accessory", "brand": "Swiss Arabian", "price": 20},
        ],
        "gradient": "from-zinc-500 via-slate-800 to-black",
    },
    {
        "slug": "studio-black-thobe",
        "title": "Studio Black Thobe",
        "creator": "Modern Traditional",
        "tagline": "A black thobe fit with sharper studio styling and understated luxury.",
        "styles": ["Modest", "Minimalist", "Streetwear"],
        "brands": ["East Essence", "Quay"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Tall", "Athletic"],
        "budget": "Mid-range",
        "color": "Black",
        "price_total": 274,
        "image_url": "https://images.pexels.com/photos/10080096/pexels-photo-10080096.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Great for men looking for a modern black thobe with a cleaner studio finish.",
        "items": [
            {"sku": "thobe-42", "title": "Black modern thobe", "category": "Set", "brand": "East Essence", "price": 102},
            {"sku": "keffiyeh-42", "title": "Checked kaffiyeh scarf", "category": "Headwear", "brand": "East Essence", "price": 28},
            {"sku": "sandal-42", "title": "Black leather sandal", "category": "Shoes", "brand": "Bata", "price": 36},
            {"sku": "shade-42", "title": "Studio black sunglasses", "category": "Accessory", "brand": "Quay", "price": 52},
            {"sku": "ring-42", "title": "Silver square signet ring", "category": "Accessory", "brand": "Swarovski", "price": 56},
        ],
        "gradient": "from-slate-400 via-slate-700 to-black",
    },
    {
        "slug": "cream-jubba-weekend",
        "title": "Cream Jubba Weekend",
        "creator": "Easy Weekend",
        "tagline": "A softer cream jubba look made for easy Friday wear and relaxed afternoons.",
        "styles": ["Modest", "Casual", "Minimalist"],
        "brands": ["East Essence", "Bata"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Tall", "Athletic", "Plus size"],
        "budget": "Budget-friendly",
        "color": "Cream",
        "price_total": 186,
        "image_url": "https://images.pexels.com/photos/7956646/pexels-photo-7956646.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "A strong everyday option for men who want lighter jubba looks at a lower price point.",
        "items": [
            {"sku": "jubba-43", "title": "Cream weekend jubba", "category": "Set", "brand": "East Essence", "price": 82},
            {"sku": "cap-43", "title": "Simple cream kufi", "category": "Headwear", "brand": "East Essence", "price": 16},
            {"sku": "slide-43", "title": "Everyday comfort slide", "category": "Shoes", "brand": "Bata", "price": 28},
            {"sku": "tasbih-43", "title": "Wood prayer beads", "category": "Accessory", "brand": "East Essence", "price": 18},
            {"sku": "bag-43", "title": "Compact leather pouch", "category": "Accessory", "brand": "Mango", "price": 42},
        ],
        "gradient": "from-stone-200 via-stone-400 to-slate-900",
    },
    {
        "slug": "city-white-kandura",
        "title": "City White Kandura",
        "creator": "Urban Gulf",
        "tagline": "A bright white kandura styled for city movement with crisp accessories.",
        "styles": ["Modest", "Minimalist", "Formal"],
        "brands": ["Bait Al Kandora", "Fossil"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Tall", "Athletic"],
        "budget": "Mid-range",
        "color": "White",
        "price_total": 296,
        "image_url": "https://images.pexels.com/photos/5416825/pexels-photo-5416825.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Works well for men searching clean white kandura options with polished accessories.",
        "items": [
            {"sku": "kandura-44", "title": "Bright white kandura", "category": "Set", "brand": "Bait Al Kandora", "price": 108},
            {"sku": "ghutra-44", "title": "White ghutra and agal", "category": "Headwear", "brand": "Bait Al Kandora", "price": 38},
            {"sku": "loafer-44", "title": "Light tan leather loafer", "category": "Shoes", "brand": "Dune London", "price": 66},
            {"sku": "watch-44", "title": "Minimal steel watch", "category": "Accessory", "brand": "Fossil", "price": 72},
            {"sku": "attar-44", "title": "Amber attar roller", "category": "Accessory", "brand": "Swiss Arabian", "price": 12},
        ],
        "gradient": "from-slate-100 via-slate-300 to-slate-900",
    },
    {
        "slug": "prayer-beads-thobe",
        "title": "Prayer Beads Thobe",
        "creator": "Ramadan Edit",
        "tagline": "A calm thobe outfit with prayer beads and darker formal styling cues.",
        "styles": ["Modest", "Formal", "Vintage"],
        "brands": ["East Essence", "Swiss Arabian"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Tall", "Athletic", "Plus size"],
        "budget": "Premium",
        "color": "Silver",
        "price_total": 332,
        "image_url": "https://images.pexels.com/photos/8217777/pexels-photo-8217777.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "A premium match for men wanting ceremonial thobe options with spiritual detailing.",
        "items": [
            {"sku": "thobe-45", "title": "Silver embroidered thobe", "category": "Set", "brand": "East Essence", "price": 136},
            {"sku": "cap-45", "title": "Structured black kufi", "category": "Headwear", "brand": "East Essence", "price": 24},
            {"sku": "loafer-45", "title": "Formal black slipper", "category": "Shoes", "brand": "Dune London", "price": 64},
            {"sku": "tasbih-45", "title": "Emerald prayer beads", "category": "Accessory", "brand": "East Essence", "price": 22},
            {"sku": "attar-45", "title": "Resin oud attar", "category": "Accessory", "brand": "Swiss Arabian", "price": 86},
        ],
        "gradient": "from-slate-300 via-slate-700 to-black",
    },
    {
        "slug": "street-thobe-urban",
        "title": "Street Thobe Urban",
        "creator": "Urban Modest",
        "tagline": "A white thobe with city styling touches for a sharper everyday streetwear crossover.",
        "styles": ["Modest", "Streetwear", "Casual"],
        "brands": ["East Essence", "Quay"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Athletic", "Tall"],
        "budget": "Mid-range",
        "color": "White",
        "price_total": 268,
        "image_url": "https://images.pexels.com/photos/16500663/pexels-photo-16500663.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Good for men who want a thobe that still fits modern city and streetwear styling.",
        "items": [
            {"sku": "thobe-46", "title": "Urban white thobe", "category": "Set", "brand": "East Essence", "price": 98},
            {"sku": "keffiyeh-46", "title": "Street keffiyeh wrap", "category": "Headwear", "brand": "East Essence", "price": 24},
            {"sku": "shoe-46", "title": "Low-profile leather sneaker", "category": "Shoes", "brand": "COS", "price": 74},
            {"sku": "shade-46", "title": "Rectangular dark sunglasses", "category": "Accessory", "brand": "Quay", "price": 48},
            {"sku": "watch-46", "title": "Simple brown strap watch", "category": "Accessory", "brand": "Fossil", "price": 24},
        ],
        "gradient": "from-slate-100 via-sky-400 to-slate-900",
    },
    {
        "slug": "embroidered-kurta-studio",
        "title": "Embroidered Kurta Studio",
        "creator": "South Asian Edit",
        "tagline": "An embroidered kurta look for men who want modest occasionwear beyond thobes.",
        "styles": ["Modest", "Formal", "Vintage"],
        "brands": ["Manyavar", "Dune London"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Athletic", "Tall", "Plus size"],
        "budget": "Premium",
        "color": "Olive",
        "price_total": 344,
        "image_url": "https://images.pexels.com/photos/14664890/pexels-photo-14664890.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "A strong match for men who want embroidered Muslim occasionwear with richer texture.",
        "items": [
            {"sku": "kurta-47", "title": "Olive embroidered kurta", "category": "Top", "brand": "Manyavar", "price": 122},
            {"sku": "pant-47", "title": "Tailored churidar trouser", "category": "Bottom", "brand": "Manyavar", "price": 54},
            {"sku": "jacket-47", "title": "Textured waistcoat layer", "category": "Outerwear", "brand": "Manyavar", "price": 72},
            {"sku": "shoe-47", "title": "Dress mojari shoe", "category": "Shoes", "brand": "Dune London", "price": 58},
            {"sku": "ring-47", "title": "Etched silver ring", "category": "Accessory", "brand": "Swarovski", "price": 38},
        ],
        "gradient": "from-emerald-300 via-emerald-700 to-slate-950",
    },
    {
        "slug": "brown-thobe-portrait",
        "title": "Brown Thobe Portrait",
        "creator": "Studio Portrait",
        "tagline": "A rich brown thobe fit with classic headwear and subtle formal accessories.",
        "styles": ["Modest", "Minimalist", "Formal"],
        "brands": ["East Essence", "Fossil"],
        "genders": ["Menswear"],
        "religions": ["Islam"],
        "body_types": ["Straight", "Tall", "Athletic", "Plus size"],
        "budget": "Mid-range",
        "color": "Brown",
        "price_total": 284,
        "image_url": "https://images.pexels.com/photos/33853481/pexels-photo-33853481.jpeg?auto=compress&cs=tinysrgb&w=1200",
        "match_text": "Strong for men filtering brown thobes, keffiyeh looks, and cleaner portrait-led styling.",
        "items": [
            {"sku": "thobe-48", "title": "Brown studio thobe", "category": "Set", "brand": "East Essence", "price": 104},
            {"sku": "keffiyeh-48", "title": "Patterned keffiyeh wrap", "category": "Headwear", "brand": "East Essence", "price": 28},
            {"sku": "sandal-48", "title": "Leather cross-strap sandal", "category": "Shoes", "brand": "Bata", "price": 38},
            {"sku": "watch-48", "title": "Classic steel wristwatch", "category": "Accessory", "brand": "Fossil", "price": 74},
            {"sku": "attar-48", "title": "Warm amber attar", "category": "Accessory", "brand": "Swiss Arabian", "price": 40},
        ],
        "gradient": "from-amber-500 via-stone-700 to-slate-950",
    },
]

LOOKS.extend(
    [
        build_look(
            "retro-track-weekend",
            "Retro Track Weekend",
            "Motion Archive",
            "A throwback sport look with track layers, easy denim, and weekend energy.",
            ["Streetwear", "Casual"],
            ["Adidas", "Levi's"],
            ["Womenswear", "Menswear", "Unisex"],
            "Mid-range",
            "Cobalt",
            "https://images.pexels.com/photos/19243446/pexels-photo-19243446.jpeg?cs=srgb&dl=pexels-felix-young-449360607-19243446.jpg&fm=jpg",
            "from-sky-400 via-blue-700 to-slate-950",
            [
                ("rtw-01", "Zip track jacket", "Outerwear", "Adidas", 72),
                ("rtw-02", "Relaxed straight denim", "Bottom", "Levi's", 78),
                ("rtw-03", "Retro stripe trainer", "Shoes", "Adidas", 82),
                ("rtw-04", "Canvas shoulder sling", "Accessory", "Levi's", 34),
            ],
        ),
        build_look(
            "varsity-jogger-stack",
            "Varsity Jogger Stack",
            "Campus Replay",
            "Vintage varsity lines meet comfort-first joggers and a clean sport finish.",
            ["Athleisure", "Casual"],
            ["Nike", "Puma"],
            ["Womenswear", "Menswear", "Unisex"],
            "Budget-friendly",
            "Green",
            "https://images.pexels.com/photos/13360782/pexels-photo-13360782.jpeg?cs=srgb&dl=pexels-hoa-tran-293444577-13360782.jpg&fm=jpg",
            "from-emerald-300 via-emerald-700 to-slate-950",
            [
                ("vjs-01", "Cropped varsity bomber", "Outerwear", "Nike", 64),
                ("vjs-02", "Tapered fleece jogger", "Bottom", "Puma", 48),
                ("vjs-03", "Court revival sneaker", "Shoes", "Nike", 74),
                ("vjs-04", "Vintage logo cap", "Accessory", "Puma", 22),
            ],
        ),
        build_look(
            "midnight-runner-layers",
            "Midnight Tailored Layers",
            "After Hours Edit",
            "Dark tailored layers with a sharper street silhouette and late-night city ease.",
            ["Formal", "Minimalist", "Streetwear"],
            ["AllSaints", "Weekday"],
            ["Menswear", "Unisex"],
            "Premium",
            "Black",
            "https://images.pexels.com/photos/31061132/pexels-photo-31061132.jpeg?cs=srgb&dl=pexels-covantnyc-31061132.jpg&fm=jpg",
            "from-zinc-600 via-slate-800 to-black",
            [
                ("mrl-01", "Longline black overcoat", "Outerwear", "AllSaints", 146),
                ("mrl-02", "Relaxed tailored trouser", "Bottom", "Weekday", 84),
                ("mrl-03", "Polished leather boot", "Shoes", "AllSaints", 96),
                ("mrl-04", "Slim crossbody pouch", "Accessory", "Weekday", 38),
            ],
        ),
        build_look(
            "vintage-court-warmup",
            "Soft Knit City Edit",
            "Daily Layer",
            "A soft knit-and-sneaker look with clean city lines and an easy minimal finish.",
            ["Casual", "Minimalist"],
            ["COS", "Reebok"],
            ["Womenswear", "Unisex"],
            "Mid-range",
            "Grey",
            "https://images.pexels.com/photos/15076269/pexels-photo-15076269.jpeg?cs=srgb&dl=pexels-marcus-queiroga-silva-86421404-15076269.jpg&fm=jpg",
            "from-stone-200 via-slate-500 to-slate-950",
            [
                ("vcw-01", "Soft knit cardigan", "Top", "COS", 68),
                ("vcw-02", "Pleated city skirt", "Bottom", "COS", 62),
                ("vcw-03", "Clean leather sneaker", "Shoes", "Reebok", 82),
                ("vcw-04", "Minimal shoulder tote", "Accessory", "COS", 36),
            ],
        ),
        build_look(
            "denim-sprint-club",
            "Denim Sprint Club",
            "Weekend Speed",
            "Relaxed denim and performance basics give this sporty look a nostalgic edge.",
            ["Vintage", "Streetwear", "Casual"],
            ["Levi's", "Adidas"],
            ["Womenswear", "Menswear", "Unisex"],
            "Mid-range",
            "Blue",
            "https://images.pexels.com/photos/32320147/pexels-photo-32320147.jpeg?cs=srgb&dl=pexels-rezapix1-32320147.jpg&fm=jpg",
            "from-blue-400 via-slate-700 to-slate-950",
            [
                ("dsc-01", "Boxy denim overshirt", "Outerwear", "Levi's", 94),
                ("dsc-02", "Tech jersey short", "Bottom", "Adidas", 42),
                ("dsc-03", "Suede retro runner", "Shoes", "Adidas", 88),
                ("dsc-04", "Rib sport tank", "Top", "Levi's", 28),
            ],
        ),
        build_look(
            "cargo-gym-street",
            "Cargo Gym Street",
            "Daily Circuit",
            "Utilitarian cargo styling with gym-ready comfort and streetwear layering.",
            ["Streetwear", "Casual"],
            ["Puma", "Carhartt WIP"],
            ["Menswear", "Unisex"],
            "Budget-friendly",
            "Olive",
            "https://images.pexels.com/photos/21050246/pexels-photo-21050246.jpeg?auto=compress&cs=tinysrgb&w=1200",
            "from-lime-300 via-stone-700 to-slate-950",
            [
                ("cgs-01", "Sleeveless training zip", "Top", "Puma", 44),
                ("cgs-02", "Utility cargo pant", "Bottom", "Carhartt WIP", 68),
                ("cgs-03", "Grip sole trainer", "Shoes", "Puma", 72),
                ("cgs-04", "Structured beanie", "Accessory", "Carhartt WIP", 20),
            ],
        ),
        build_look(
            "city-windbreaker-loop",
            "City Windbreaker Loop",
            "Metro Motion",
            "Windbreaker layering with a vintage sneaker base for fast city movement.",
            ["Athleisure", "Casual"],
            ["Nike", "Weekday"],
            ["Womenswear", "Menswear", "Unisex"],
            "Mid-range",
            "Orange",
            "https://images.pexels.com/photos/13360782/pexels-photo-13360782.jpeg?cs=srgb&dl=pexels-hoa-tran-293444577-13360782.jpg&fm=jpg",
            "from-orange-300 via-rose-700 to-slate-950",
            [
                ("cwl-01", "Oversized windbreaker", "Outerwear", "Nike", 82),
                ("cwl-02", "Soft track trouser", "Bottom", "Weekday", 54),
                ("cwl-03", "Panelled street runner", "Shoes", "Nike", 84),
                ("cwl-04", "Sport shoulder bag", "Accessory", "Weekday", 32),
            ],
        ),
        build_look(
            "washed-hoodie-circuit",
            "Washed Hoodie Circuit",
            "Daily Repeat",
            "An easy washed hoodie fit with archival sport references and soft movement.",
            ["Streetwear", "Casual"],
            ["Weekday", "New Balance"],
            ["Womenswear", "Menswear", "Unisex"],
            "Budget-friendly",
            "Grey",
            "https://images.pexels.com/photos/19243446/pexels-photo-19243446.jpeg?cs=srgb&dl=pexels-felix-young-449360607-19243446.jpg&fm=jpg",
            "from-slate-300 via-slate-600 to-slate-950",
            [
                ("whc-01", "Washed oversized hoodie", "Top", "Weekday", 58),
                ("whc-02", "Striped breakaway pant", "Bottom", "Weekday", 52),
                ("whc-03", "Chunky mesh sneaker", "Shoes", "New Balance", 86),
                ("whc-04", "Logo crew socks", "Accessory", "New Balance", 18),
            ],
        ),
        build_look(
            "throwback-sneaker-rush",
            "Throwback Sneaker Rush",
            "Sneaker Desk",
            "Bright throwback sneakers lead a relaxed sport look with retro denim attitude.",
            ["Vintage", "Streetwear", "Casual"],
            ["Reebok", "Levi's"],
            ["Womenswear", "Menswear", "Unisex"],
            "Mid-range",
            "Red",
            "https://images.pexels.com/photos/32320147/pexels-photo-32320147.jpeg?cs=srgb&dl=pexels-rezapix1-32320147.jpg&fm=jpg",
            "from-rose-400 via-red-700 to-slate-950",
            [
                ("tsr-01", "Ringer baby tee", "Top", "Levi's", 28),
                ("tsr-02", "Loose cuffed denim", "Bottom", "Levi's", 76),
                ("tsr-03", "Throwback high-top", "Shoes", "Reebok", 92),
                ("tsr-04", "Sport mini backpack", "Accessory", "Reebok", 38),
            ],
        ),
        build_look(
            "utility-track-set",
            "Utility Track Set",
            "System Sport",
            "Technical sport pieces with utility trims for a sharper streetwear crossover.",
            ["Athleisure", "Streetwear", "Casual"],
            ["Adidas", "Carhartt WIP"],
            ["Menswear", "Unisex"],
            "Premium",
            "Khaki",
            "https://images.pexels.com/photos/17037282/pexels-photo-17037282.jpeg?auto=compress&cs=tinysrgb&w=1200",
            "from-stone-300 via-stone-700 to-slate-950",
            [
                ("uts-01", "Technical zip overshirt", "Outerwear", "Adidas", 108),
                ("uts-02", "Pocket track cargo", "Bottom", "Carhartt WIP", 84),
                ("uts-03", "Terrain trainer", "Shoes", "Adidas", 96),
                ("uts-04", "Utility belt bag", "Accessory", "Carhartt WIP", 42),
            ],
        ),
        build_look(
            "graffiti-training-day",
            "Graffiti Training Day",
            "Street Session",
            "Sport layers, bold graphics, and a vintage-street mix that feels playful.",
            ["Streetwear", "Casual"],
            ["Puma", "Weekday"],
            ["Womenswear", "Menswear", "Unisex"],
            "Budget-friendly",
            "Purple",
            "https://images.pexels.com/photos/19189048/pexels-photo-19189048.jpeg?auto=compress&cs=tinysrgb&w=1200",
            "from-fuchsia-400 via-violet-700 to-slate-950",
            [
                ("gtd-01", "Graphic training tee", "Top", "Puma", 32),
                ("gtd-02", "Snap track pant", "Bottom", "Weekday", 48),
                ("gtd-03", "Color pop trainer", "Shoes", "Puma", 74),
                ("gtd-04", "Graffiti cap", "Accessory", "Weekday", 20),
            ],
        ),
        build_look(
            "downtown-mesh-motion",
            "Downtown Mesh Motion",
            "Mesh Club",
            "Breathable sport mesh and old-school layering for city days that keep moving.",
            ["Streetwear", "Casual"],
            ["New Balance", "COS"],
            ["Womenswear", "Menswear", "Unisex"],
            "Mid-range",
            "Silver",
            "https://images.pexels.com/photos/19243446/pexels-photo-19243446.jpeg?cs=srgb&dl=pexels-felix-young-449360607-19243446.jpg&fm=jpg",
            "from-slate-200 via-slate-500 to-slate-950",
            [
                ("dmm-01", "Mesh long-sleeve jersey", "Top", "New Balance", 54),
                ("dmm-02", "Wide-leg track pant", "Bottom", "COS", 72),
                ("dmm-03", "Silver pace runner", "Shoes", "New Balance", 94),
                ("dmm-04", "Compact tote sling", "Accessory", "COS", 36),
            ],
        ),
        build_look(
            "tailored-tennis-edit",
            "Tailored Tennis Edit",
            "Club House",
            "Sharp lines and sport references meet in a polished movement-first outfit.",
            ["Formal", "Minimalist"],
            ["Arket", "Adidas"],
            ["Womenswear", "Menswear", "Unisex"],
            "Premium",
            "Cream",
            "https://images.pexels.com/photos/18794492/pexels-photo-18794492.jpeg?cs=srgb&dl=pexels-braks-alexandros-2366968-18794492.jpg&fm=jpg",
            "from-stone-200 via-stone-500 to-slate-950",
            [
                ("tte-01", "Tailored tennis cardigan", "Top", "Arket", 96),
                ("tte-02", "Knife-pleat sport trouser", "Bottom", "Arket", 92),
                ("tte-03", "Minimal leather court shoe", "Shoes", "Adidas", 98),
                ("tte-04", "Structured visor cap", "Accessory", "Adidas", 26),
            ],
        ),
        build_look(
            "monochrome-track-suiting",
            "Monochrome Track Suiting",
            "Sharp Motion",
            "A clean monochrome outfit that reads formal from afar but moves like sportswear.",
            ["Formal", "Minimalist"],
            ["COS", "Nike"],
            ["Menswear", "Unisex"],
            "Premium",
            "Black",
            "https://images.pexels.com/photos/31061132/pexels-photo-31061132.jpeg?cs=srgb&dl=pexels-covantnyc-31061132.jpg&fm=jpg",
            "from-zinc-700 via-slate-900 to-black",
            [
                ("mts-01", "Technical suit jacket", "Outerwear", "COS", 132),
                ("mts-02", "Elastic waist tux trouser", "Bottom", "COS", 104),
                ("mts-03", "Minimal black runner", "Shoes", "Nike", 92),
                ("mts-04", "Leather phone case strap", "Accessory", "COS", 42),
            ],
        ),
        build_look(
            "clean-studio-warmup",
            "Clean Studio Warmup",
            "Studio Form",
            "Tailored warmup pieces designed for clean profiles and easy repeat wear.",
            ["Formal", "Minimalist", "Casual"],
            ["Mango", "Puma"],
            ["Womenswear", "Unisex"],
            "Mid-range",
            "Taupe",
            "https://images.pexels.com/photos/23531833/pexels-photo-23531833.jpeg?cs=srgb&dl=pexels-matheus-rodrigues-672111387-23531833.jpg&fm=jpg",
            "from-stone-300 via-amber-300 to-slate-950",
            [
                ("csw-01", "Wrap-front sport blazer", "Outerwear", "Mango", 88),
                ("csw-02", "Soft ponte pant", "Bottom", "Mango", 64),
                ("csw-03", "Minimal suede trainer", "Shoes", "Puma", 78),
                ("csw-04", "Slim zip pouch", "Accessory", "Mango", 28),
            ],
        ),
        build_look(
            "aero-blazer-move",
            "Aero Blazer Move",
            "Transit Edit",
            "A blazer-led commute fit that stays airy, athletic, and tailored.",
            ["Formal", "Minimalist", "Casual"],
            ["Massimo Dutti", "New Balance"],
            ["Womenswear", "Menswear", "Unisex"],
            "Premium",
            "Stone",
            "https://images.pexels.com/photos/15076269/pexels-photo-15076269.jpeg?cs=srgb&dl=pexels-marcus-queiroga-silva-86421404-15076269.jpg&fm=jpg",
            "from-stone-200 via-slate-500 to-slate-950",
            [
                ("abm-01", "Airweight blazer", "Outerwear", "Massimo Dutti", 128),
                ("abm-02", "Drawcord tailored pant", "Bottom", "Massimo Dutti", 96),
                ("abm-03", "Muted pace sneaker", "Shoes", "New Balance", 94),
                ("abm-04", "Slim commuter backpack", "Accessory", "Massimo Dutti", 52),
            ],
        ),
        build_look(
            "courtline-minimal-motion",
            "Courtline Minimal Motion",
            "Quiet Performance",
            "Quiet tones, court references, and a crisp formal-athletic balance.",
            ["Formal", "Minimalist"],
            ["COS", "Reebok"],
            ["Womenswear", "Menswear", "Unisex"],
            "Mid-range",
            "Ivory",
            "https://images.pexels.com/photos/18794492/pexels-photo-18794492.jpeg?cs=srgb&dl=pexels-braks-alexandros-2366968-18794492.jpg&fm=jpg",
            "from-slate-100 via-slate-400 to-slate-950",
            [
                ("cmm-01", "Structured knit polo", "Top", "COS", 62),
                ("cmm-02", "Cuffed tailored jogger", "Bottom", "COS", 84),
                ("cmm-03", "Leather court low-top", "Shoes", "Reebok", 88),
                ("cmm-04", "Minimal duffel tote", "Accessory", "COS", 44),
            ],
        ),
        build_look(
            "luxe-commute-set",
            "Luxe Commute Set",
            "Office Motion",
            "Built for polished commutes with enough stretch and softness for all-day wear.",
            ["Formal", "Minimalist", "Casual"],
            ["Arket", "Adidas"],
            ["Womenswear", "Menswear", "Unisex"],
            "Premium",
            "Navy",
            "https://images.pexels.com/photos/23531833/pexels-photo-23531833.jpeg?cs=srgb&dl=pexels-matheus-rodrigues-672111387-23531833.jpg&fm=jpg",
            "from-indigo-300 via-slate-700 to-slate-950",
            [
                ("lcs-01", "Travel knit blazer", "Outerwear", "Arket", 118),
                ("lcs-02", "Performance pleat trouser", "Bottom", "Arket", 102),
                ("lcs-03", "Navy leather trainer", "Shoes", "Adidas", 96),
                ("lcs-04", "Structured laptop sleeve", "Accessory", "Arket", 46),
            ],
        ),
        build_look(
            "precision-travel-flex",
            "Precision Travel Flex",
            "Gate Ready",
            "A refined travel uniform balancing stretch comfort, structure, and clean lines.",
            ["Formal", "Minimalist"],
            ["COS", "New Balance"],
            ["Menswear", "Unisex"],
            "Premium",
            "Grey",
            "https://images.pexels.com/photos/31061132/pexels-photo-31061132.jpeg?cs=srgb&dl=pexels-covantnyc-31061132.jpg&fm=jpg",
            "from-slate-300 via-slate-700 to-slate-950",
            [
                ("ptf-01", "Packable travel overshirt", "Outerwear", "COS", 122),
                ("ptf-02", "Precision stretch trouser", "Bottom", "COS", 98),
                ("ptf-03", "Quiet luxury runner", "Shoes", "New Balance", 102),
                ("ptf-04", "Passport crossbody pouch", "Accessory", "COS", 38),
            ],
        ),
        build_look(
            "studio-lounge-tailored-active",
            "Studio Lounge Tailored Active",
            "Quiet Studio",
            "Soft lounge pieces cut with tailored lines for an elevated active wardrobe.",
            ["Casual", "Minimalist"],
            ["Mango", "Nike"],
            ["Womenswear", "Unisex"],
            "Mid-range",
            "Rose",
            "https://images.pexels.com/photos/15076269/pexels-photo-15076269.jpeg?cs=srgb&dl=pexels-marcus-queiroga-silva-86421404-15076269.jpg&fm=jpg",
            "from-rose-200 via-rose-500 to-slate-950",
            [
                ("slt-01", "Soft shoulder lounge blazer", "Outerwear", "Mango", 82),
                ("slt-02", "Tailored flare track pant", "Bottom", "Mango", 66),
                ("slt-03", "Low-profile comfort trainer", "Shoes", "Nike", 84),
                ("slt-04", "Slim satin headband", "Accessory", "Mango", 18),
            ],
        ),
    ]
)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_model_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in MODEL_ALLOWED_EXTENSIONS


def resolve_demo_model(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""

    for model in DEMO_SAMPLE_MODELS:
        if value == model["slug"]:
            return model["url"]

    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return ""
    path = (parsed.path or value).strip()
    if not path.startswith("/") or ".." in path:
        return ""
    if path.startswith(DEMO_MODEL_ALLOWED_PREFIXES):
        return path
    return ""


def sanitize_text(text: str, max_length: int = 1000) -> str:
    if not text:
        return ""
    sanitized = str(text).strip()
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return html.escape(sanitized)


def sanitize_url(url: str, max_length: int = 1200) -> str:
    if not url:
        return ""
    url = str(url).strip()
    if len(url) > max_length:
        url = url[:max_length]
    if url and not (url.startswith("http://") or url.startswith("https://")):
        return ""
    return url


def cart_items() -> list[dict]:
    return session.setdefault("cart", [])


def cart_total() -> float:
    return round(sum(item.get("price", 0) * item.get("quantity", 1) for item in cart_items()), 2)


def parse_profile_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalized_profile_data(data: dict | None) -> dict:
    profile = dict(data or {})
    favorite_styles = profile.get("favorite_styles")
    profile["favorite_styles"] = [str(style) for style in favorite_styles] if isinstance(favorite_styles, list) else []
    favorite_brands = profile.get("favorite_brands")
    profile["favorite_brands"] = [str(brand) for brand in favorite_brands] if isinstance(favorite_brands, list) else []
    for key, default in PROFILE_SETTING_DEFAULTS.items():
        profile[key] = parse_profile_bool(profile.get(key), default)
    return profile


def profile_data() -> dict:
    if not current_user.is_authenticated:
        return {}
    return normalized_profile_data(current_user.get_profile_data())


def profile_payload_from_form(existing: dict | None = None) -> dict:
    data = normalized_profile_data(existing)

    favorite_styles = []
    for raw_style in request.form.getlist("favorite_styles"):
        style = sanitize_text(raw_style, 80)
        if style in STYLE_OPTIONS and style not in favorite_styles:
            favorite_styles.append(style)

    favorite_brands = []
    for raw_part in request.form.get("favorite_brands", "").split(","):
        brand = sanitize_text(raw_part, 80)
        if brand and brand not in favorite_brands:
            favorite_brands.append(brand)

    data.update(
        {
            "gender": sanitize_text(request.form.get("gender", ""), 60),
            "religion": sanitize_text(request.form.get("religion", ""), 80),
            "style_preference": sanitize_text(request.form.get("style_preference", ""), 80),
            "budget_range": sanitize_text(request.form.get("budget_range", ""), 80),
            "favorite_styles": favorite_styles,
            "body_type": sanitize_text(request.form.get("body_type", ""), 80),
            "favorite_brands": favorite_brands,
        }
    )

    for key, default in PROFILE_SETTING_DEFAULTS.items():
        if key in request.form:
            data[key] = request.form.get(key) == "1"
        else:
            data[key] = data.get(key, default)

    return data


def profile_vector_from(data: dict) -> dict:
    vector = {
        "gender": data.get("gender", ""),
        "religion": data.get("religion", ""),
        "budget": data.get("budget_range", ""),
        "body_type": data.get("body_type", ""),
        "styles": {style: 1 for style in data.get("favorite_styles", [])},
        "brands": {brand: 1 for brand in data.get("favorite_brands", [])},
    }
    return vector


def budget_distance(user_budget: str, look_budget: str) -> int:
    if user_budget not in BUDGET_ORDER or look_budget not in BUDGET_ORDER:
        return 0
    return abs(BUDGET_ORDER[user_budget] - BUDGET_ORDER[look_budget])


def look_styles(look: dict) -> list[str]:
    styles = list(look.get("styles", []))
    if look.get("religions") and "Religious" not in styles:
        styles.append("Religious")
    return styles


def look_garment_tags(look: dict) -> list[str]:
    text_parts = [look.get("title", "")]
    text_parts.extend(item.get("title", "") for item in look.get("items", []))
    haystack = " ".join(text_parts).lower()
    tag_patterns = [
        ("Abaya", ("abaya",)),
        ("Buibui", ("buibui",)),
        ("Thobe", ("thobe",)),
        ("Kandura", ("kandura",)),
        ("Jubba", ("jubba",)),
        ("Jalabiya", ("jalabiya", "jallaba", "djellaba")),
        ("Kurta", ("kurta",)),
        ("Bisht", ("bisht",)),
        ("Kaftan", ("kaftan",)),
        ("Jilbab", ("jilbab",)),
        ("Hijab", ("hijab",)),
        ("Shayla", ("shayla",)),
        ("Ghutra", ("ghutra", "keffiyeh", "kaffiyeh", "agal")),
        ("Kufi", ("kufi",)),
    ]
    tags = []
    for tag, patterns in tag_patterns:
        if any(pattern in haystack for pattern in patterns):
            tags.append(tag)
    return tags


def item_matches_accessory(item: dict, accessory: str) -> bool:
    title = (item.get("title") or "").lower()
    token_set = set(re.sub(r"[^a-z0-9]+", " ", title).split())
    if accessory == "Shoes":
        return item.get("category") == "Shoes"
    if accessory == "Watches":
        return "watch" in title
    if accessory == "Glasses":
        return any(term in title for term in ("glasses", "sunglasses", "shades"))
    if accessory == "Bags":
        return any(term in title for term in ("bag", "tote", "pouch", "clutch", "satchel", "backpack"))
    if accessory == "Jewelry":
        jewelry_tokens = {
            "ring",
            "rings",
            "earring",
            "earrings",
            "bracelet",
            "bracelets",
            "bangle",
            "bangles",
            "cuff",
            "cuffs",
            "chain",
            "chains",
            "necklace",
            "necklaces",
        }
        return item.get("category") == "Accessory" and bool(token_set & jewelry_tokens)
    return False


def look_has_accessory(look: dict, accessory: str) -> bool:
    return any(item_matches_accessory(item, accessory) for item in look.get("items", []))


def look_collection_label(look: dict) -> str:
    title = (look.get("title") or "").lower()
    tokens = re.findall(r"[a-z0-9]+", title)
    interesting = [token.title() for token in tokens if len(token) > 2 and token not in BAG_TITLE_STOPWORDS]
    if interesting:
        return " ".join(interesting[:2])
    color = (look.get("color") or "").strip()
    return color.title() if color else "Signature"


def bag_title_for_look(
    look: dict,
    styles: set[str],
    *,
    is_religious: bool,
    is_menswear: bool,
    is_womenswear: bool,
) -> str:
    label = look_collection_label(look)
    if is_religious and is_menswear:
        return f"{label} leather document pouch"
    if is_religious and is_womenswear:
        return f"{label} market tote"
    if "Formal" in styles:
        return f"{label} atelier satchel"
    if "Athleisure" in styles or "Streetwear" in styles:
        return f"{label} utility sling bag"
    return f"{label} shoulder tote"


def glasses_title_for_look(look: dict, styles: set[str]) -> str:
    label = look_collection_label(look)
    if "Formal" in styles or "Minimalist" in styles:
        return f"{label} slim frame sunglasses"
    if "Athleisure" in styles or "Streetwear" in styles:
        return f"{label} tinted sport sunglasses"
    return f"{label} soft round sunglasses"


def accessory_item_for_look(look: dict, accessory: str) -> dict:
    slug_token = look["slug"].replace("-", "")
    styles = set(look_styles(look))
    genders = set(look.get("genders", []))
    is_menswear = "Menswear" in genders and "Womenswear" not in genders
    is_womenswear = "Womenswear" in genders and "Menswear" not in genders
    is_religious = bool(look.get("religions"))
    color = (look.get("color") or "Neutral").lower()

    if accessory == "Watches":
        if is_religious and is_menswear:
            return catalog_item(f"watch-{slug_token}", "Prayer time steel watch", "Accessory", "Casio", 48)
        if "Formal" in styles or "Minimalist" in styles:
            return catalog_item(f"watch-{slug_token}", f"{color.title()} dress watch", "Accessory", "Fossil", 72)
        if "Athleisure" in styles or "Streetwear" in styles:
            return catalog_item(f"watch-{slug_token}", "Sport chronograph watch", "Accessory", "Casio", 54)
        return catalog_item(f"watch-{slug_token}", "Everyday analog watch", "Accessory", "Timex", 42)

    if accessory == "Glasses":
        if "Formal" in styles or "Minimalist" in styles:
            return catalog_item(
                f"glasses-{slug_token}",
                glasses_title_for_look(look, styles),
                "Accessory",
                "Ray-Ban",
                58,
            )
        if "Athleisure" in styles or "Streetwear" in styles:
            return catalog_item(
                f"glasses-{slug_token}",
                glasses_title_for_look(look, styles),
                "Accessory",
                "Quay",
                46,
            )
        return catalog_item(
            f"glasses-{slug_token}",
            glasses_title_for_look(look, styles),
            "Accessory",
            "Quay",
            38,
        )

    if accessory == "Bags":
        if is_religious and is_menswear:
            return catalog_item(
                f"bag-{slug_token}",
                bag_title_for_look(look, styles, is_religious=True, is_menswear=True, is_womenswear=False),
                "Accessory",
                "Mango",
                40,
            )
        if is_religious and is_womenswear:
            return catalog_item(
                f"bag-{slug_token}",
                bag_title_for_look(look, styles, is_religious=True, is_menswear=False, is_womenswear=True),
                "Accessory",
                "JW Pei",
                58,
            )
        if "Formal" in styles:
            return catalog_item(
                f"bag-{slug_token}",
                bag_title_for_look(look, styles, is_religious=False, is_menswear=False, is_womenswear=False),
                "Accessory",
                "Mango",
                52,
            )
        if "Athleisure" in styles or "Streetwear" in styles:
            return catalog_item(
                f"bag-{slug_token}",
                bag_title_for_look(look, styles, is_religious=False, is_menswear=False, is_womenswear=False),
                "Accessory",
                "Nike",
                34,
            )
        return catalog_item(
            f"bag-{slug_token}",
            bag_title_for_look(look, styles, is_religious=False, is_menswear=False, is_womenswear=False),
            "Accessory",
            "COS",
            44,
        )

    if accessory == "Jewelry":
        if is_menswear:
            return catalog_item(f"jewel-{slug_token}", "Brushed signet ring", "Accessory", "Swarovski", 38)
        if "Formal" in styles:
            return catalog_item(f"jewel-{slug_token}", "Polished gold cuff", "Accessory", "Ana Luisa", 42)
        if "Streetwear" in styles:
            return catalog_item(f"jewel-{slug_token}", "Layered chain bracelet", "Accessory", "Ana Luisa", 34)
        return catalog_item(f"jewel-{slug_token}", "Minimal bangle bracelet", "Accessory", "Ana Luisa", 28)

    raise ValueError(f"Unsupported accessory: {accessory}")


def accessory_type_for_item(item: dict) -> str:
    for accessory in ACCESSORY_OPTIONS:
        if item_matches_accessory(item, accessory):
            return accessory
    return ""


def seeded_hue(seed_text: str, offset: int = 0) -> int:
    seed = sum((index + 1 + offset) * ord(char) for index, char in enumerate(seed_text))
    return seed % 360


def seeded_number(seed_text: str, modulus: int = 1000000) -> int:
    seed = sum((index + 1) * ord(char) for index, char in enumerate(seed_text))
    return (seed % max(1, modulus)) + 1


def shoe_style_key(title: str) -> str:
    title = (title or "").lower()
    if any(term in title for term in ("heel", "pump", "slingback", "mule")):
        return "heel"
    if any(term in title for term in ("sandal", "slide")):
        return "sandal"
    if any(term in title for term in ("boot", "high-top")):
        return "boot"
    if any(term in title for term in ("loafer", "slipper", "mojari", "flat")):
        return "loafer"
    if any(term in title for term in ("derby", "oxford")):
        return "derby"
    return "trainer"


def accessory_figure_svg(accessory_type: str, outline: str, accent: str, item_title: str = "") -> str:
    if accessory_type == "Shoes":
        shoe_style = shoe_style_key(item_title)
        if shoe_style == "heel":
            return (
                f'<path d="M340 588 C410 530 492 500 576 510 C650 518 710 548 758 568 C802 586 826 604 826 626 L358 626 C324 626 294 604 282 572 C278 560 298 550 340 588 Z" fill="none" stroke="{accent}" stroke-width="24" stroke-linejoin="round"/>'
                f'<path d="M494 548 C552 536 614 544 666 566" fill="none" stroke="{outline}" stroke-width="16" stroke-linecap="round" opacity="0.88"/>'
                f'<path d="M790 568 L822 420" fill="none" stroke="{outline}" stroke-width="18" stroke-linecap="round"/>'
                f'<line x1="350" y1="626" x2="834" y2="626" stroke="{outline}" stroke-width="10" opacity="0.45"/>'
            )
        if shoe_style == "sandal":
            return (
                f'<path d="M318 626 C404 588 506 568 618 572 C738 576 834 594 906 626" fill="none" stroke="{accent}" stroke-width="24" stroke-linecap="round"/>'
                f'<path d="M452 474 C522 508 572 552 606 624" fill="none" stroke="{outline}" stroke-width="18" stroke-linecap="round"/>'
                f'<path d="M664 456 C724 494 770 542 808 620" fill="none" stroke="{outline}" stroke-width="18" stroke-linecap="round"/>'
                f'<path d="M378 594 C474 564 580 554 698 564 C794 572 866 592 920 620" fill="none" stroke="{outline}" stroke-width="14" stroke-linecap="round" opacity="0.75"/>'
            )
        if shoe_style == "boot":
            return (
                f'<path d="M400 252 L612 252 C638 252 658 272 658 298 L658 482 C712 512 776 538 842 546 C892 552 934 582 950 626 L384 626 C344 626 312 596 312 556 L312 522 C312 504 326 490 344 490 L400 490 Z" fill="none" stroke="{accent}" stroke-width="24" stroke-linejoin="round"/>'
                f'<path d="M434 310 L434 490" fill="none" stroke="{outline}" stroke-width="16" stroke-linecap="round" opacity="0.82"/>'
                f'<path d="M522 316 L522 470" fill="none" stroke="{outline}" stroke-width="12" stroke-linecap="round" opacity="0.48"/>'
                f'<line x1="366" y1="626" x2="954" y2="626" stroke="{outline}" stroke-width="10" opacity="0.45"/>'
            )
        if shoe_style == "loafer":
            return (
                f'<path d="M320 590 C394 532 480 506 574 514 C654 520 734 552 804 560 C860 566 906 592 928 626 L346 626 C312 626 280 604 268 572 C264 560 282 550 320 590 Z" fill="none" stroke="{accent}" stroke-width="24" stroke-linejoin="round"/>'
                f'<path d="M496 546 C546 540 604 548 658 570" fill="none" stroke="{outline}" stroke-width="16" stroke-linecap="round" opacity="0.84"/>'
                f'<path d="M446 562 C502 582 556 594 612 596" fill="none" stroke="{outline}" stroke-width="12" stroke-linecap="round" opacity="0.58"/>'
                f'<line x1="344" y1="626" x2="932" y2="626" stroke="{outline}" stroke-width="10" opacity="0.45"/>'
            )
        if shoe_style == "derby":
            return (
                f'<path d="M332 590 C398 520 474 490 558 496 C632 502 710 536 790 544 C850 550 900 578 926 626 L350 626 C316 626 286 602 276 572 C272 560 290 548 332 590 Z" fill="none" stroke="{accent}" stroke-width="24" stroke-linejoin="round"/>'
                f'<path d="M474 528 C526 522 576 534 620 560" fill="none" stroke="{outline}" stroke-width="16" stroke-linecap="round" opacity="0.9"/>'
                f'<path d="M450 548 L512 540 L540 568" fill="none" stroke="{outline}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" opacity="0.72"/>'
                f'<line x1="350" y1="626" x2="930" y2="626" stroke="{outline}" stroke-width="10" opacity="0.45"/>'
            )
        return (
            f'<path d="M290 584 C364 520 446 488 532 494 C620 500 706 544 792 556 C852 564 906 590 930 626 L324 626 C290 626 258 604 248 572 C244 558 262 548 290 584 Z" fill="none" stroke="{accent}" stroke-width="24" stroke-linejoin="round"/>'
            f'<path d="M396 544 C450 528 516 528 582 544 C646 558 706 586 756 594" fill="none" stroke="{outline}" stroke-width="16" stroke-linecap="round" opacity="0.86"/>'
            f'<path d="M430 566 L520 552 L618 572" fill="none" stroke="{outline}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" opacity="0.64"/>'
            f'<line x1="326" y1="626" x2="932" y2="626" stroke="{outline}" stroke-width="10" opacity="0.45"/>'
        )
    if accessory_type == "Watches":
        return (
            f'<rect x="520" y="120" width="160" height="160" rx="36" fill="none" stroke="{outline}" stroke-width="20" opacity="0.7"/>'
            f'<rect x="520" y="560" width="160" height="160" rx="36" fill="none" stroke="{outline}" stroke-width="20" opacity="0.7"/>'
            f'<circle cx="600" cy="420" r="150" fill="none" stroke="{accent}" stroke-width="24"/>'
            f'<circle cx="600" cy="420" r="96" fill="none" stroke="{outline}" stroke-width="10" opacity="0.85"/>'
            f'<line x1="600" y1="420" x2="600" y2="340" stroke="{outline}" stroke-width="16" stroke-linecap="round"/>'
            f'<line x1="600" y1="420" x2="666" y2="456" stroke="{outline}" stroke-width="14" stroke-linecap="round"/>'
        )
    if accessory_type == "Glasses":
        return (
            f'<circle cx="470" cy="420" r="118" fill="none" stroke="{accent}" stroke-width="20"/>'
            f'<circle cx="730" cy="420" r="118" fill="none" stroke="{accent}" stroke-width="20"/>'
            f'<path d="M588 420 L612 420" stroke="{outline}" stroke-width="16" stroke-linecap="round"/>'
            f'<path d="M352 400 C300 376 268 348 232 320" stroke="{outline}" stroke-width="16" stroke-linecap="round" fill="none" opacity="0.8"/>'
            f'<path d="M848 400 C900 376 932 348 968 320" stroke="{outline}" stroke-width="16" stroke-linecap="round" fill="none" opacity="0.8"/>'
        )
    if accessory_type == "Bags":
        return (
            f'<rect x="360" y="290" width="480" height="340" rx="52" fill="none" stroke="{accent}" stroke-width="24"/>'
            f'<path d="M470 292 C470 220 520 172 600 172 C680 172 730 220 730 292" fill="none" stroke="{outline}" stroke-width="22" stroke-linecap="round"/>'
            f'<line x1="450" y1="390" x2="750" y2="390" stroke="{outline}" stroke-width="12" opacity="0.7"/>'
        )
    if accessory_type == "Jewelry":
        return (
            f'<circle cx="530" cy="430" r="118" fill="none" stroke="{accent}" stroke-width="22"/>'
            f'<circle cx="530" cy="430" r="64" fill="none" stroke="{outline}" stroke-width="12" opacity="0.8"/>'
            f'<path d="M732 316 L770 386 L844 398 L790 452 L804 528 L732 492 L660 528 L674 452 L620 398 L694 386 Z" fill="none" stroke="{outline}" stroke-width="14" stroke-linejoin="round"/>'
        )
    return (
        f'<path d="M304 548 C378 470 458 444 554 458 C652 472 708 526 812 530 C868 532 916 560 916 626 L330 626 C292 626 260 594 260 556 Z" fill="none" stroke="{accent}" stroke-width="24" stroke-linejoin="round"/>'
        f'<path d="M370 550 C428 524 500 520 566 534 C620 546 700 584 770 586" fill="none" stroke="{outline}" stroke-width="16" stroke-linecap="round" opacity="0.85"/>'
        f'<line x1="340" y1="626" x2="930" y2="626" stroke="{outline}" stroke-width="10" opacity="0.45"/>'
    )


def accessory_preview_svg(item: dict, look: dict, accessory_type: str) -> str:
    seed_text = f"{item.get('sku', '')}-{item.get('title', '')}-{look.get('slug', '')}-{accessory_type}"
    hue_one = seeded_hue(seed_text)
    hue_two = seeded_hue(seed_text, 73)
    hue_three = seeded_hue(seed_text, 147)
    background_one = f"hsl({hue_one}, 76%, 16%)"
    background_two = f"hsl({hue_two}, 78%, 34%)"
    accent = f"hsl({hue_three}, 88%, 66%)"
    outline = "white"
    accessory_label = html.escape(accessory_type[:14])
    title = html.escape((item.get('title') or accessory_type)[:36])
    brand = html.escape((item.get('brand') or "StyleBridge")[:24])
    look_title = html.escape((look.get('title') or "StyleBridge look")[:30])
    price = f"${float(item.get('price', 0)):.0f}"
    figure = accessory_figure_svg(accessory_type, outline, accent, item.get("title", ""))
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 900" role="img" aria-label="{title}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{background_one}" />
      <stop offset="100%" stop-color="{background_two}" />
    </linearGradient>
    <linearGradient id="panel" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="white" stop-opacity="0.14" />
      <stop offset="100%" stop-color="white" stop-opacity="0.04" />
    </linearGradient>
  </defs>
  <rect width="1200" height="900" fill="url(#bg)" rx="44" />
  <circle cx="190" cy="170" r="160" fill="{accent}" opacity="0.12" />
  <circle cx="1030" cy="760" r="220" fill="{accent}" opacity="0.1" />
  <rect x="76" y="72" width="1048" height="756" rx="36" fill="#0f172a" fill-opacity="0.2" stroke="white" stroke-opacity="0.12" />
  <rect x="96" y="94" width="262" height="56" rx="28" fill="white" fill-opacity="0.14" />
  <text x="130" y="130" fill="white" font-size="28" font-family="Arial, sans-serif" font-weight="700" letter-spacing="3">{accessory_label.upper()}</text>
  <text x="130" y="720" fill="white" font-size="64" font-family="Arial, sans-serif" font-weight="700">{title}</text>
  <text x="130" y="772" fill="white" fill-opacity="0.82" font-size="30" font-family="Arial, sans-serif">{brand} | From {look_title}</text>
  <text x="1030" y="130" text-anchor="end" fill="white" font-size="42" font-family="Arial, sans-serif" font-weight="700">{price}</text>
  <g transform="translate(0 0)">{figure}</g>
</svg>
""".strip()


def accessory_preview_image(item: dict, look: dict, accessory_type: str) -> str:
    return "data:image/svg+xml;charset=UTF-8," + quote(accessory_preview_svg(item, look, accessory_type))


def accessory_search_keywords(item: dict, accessory_type: str) -> str:
    title = (item.get("title") or "").lower()
    keywords = []

    if accessory_type == "Shoes":
        if any(term in title for term in ("sneaker", "trainer", "runner", "court", "high-top")):
            keywords = ["sneaker", "shoe", "fashion"]
        elif "boot" in title:
            keywords = ["boot", "shoe", "fashion"]
        elif any(term in title for term in ("sandal", "slide", "heel", "flat", "loafer", "mule", "slipper")):
            keywords = ["sandal", "shoe", "fashion"]
        else:
            keywords = ["shoe", "fashion", "accessory"]
    elif accessory_type == "Watches":
        if "chronograph" in title:
            keywords = ["chronograph", "watch", "accessory"]
        else:
            keywords = ["watch", "accessory", "fashion"]
    elif accessory_type == "Glasses":
        if "sunglasses" in title or "shades" in title:
            keywords = ["sunglasses", "eyewear", "fashion"]
        else:
            keywords = ["glasses", "eyewear", "fashion"]
    elif accessory_type == "Bags":
        if "backpack" in title:
            keywords = ["backpack", "bag", "fashion"]
        elif "clutch" in title:
            keywords = ["clutch", "bag", "fashion"]
        elif any(term in title for term in ("tote", "shopper", "weekender")):
            keywords = ["tote", "bag", "fashion"]
        elif any(term in title for term in ("crossbody", "satchel", "pouch", "sling")):
            keywords = ["crossbody", "bag", "fashion"]
        else:
            keywords = ["handbag", "bag", "fashion"]
    elif accessory_type == "Jewelry":
        if "ring" in title or "signet" in title:
            keywords = ["ring", "jewelry", "fashion"]
        elif any(term in title for term in ("bracelet", "bangle", "cuff")):
            keywords = ["bracelet", "jewelry", "fashion"]
        elif "earring" in title:
            keywords = ["earring", "jewelry", "fashion"]
        elif any(term in title for term in ("chain", "necklace")):
            keywords = ["necklace", "jewelry", "fashion"]
        else:
            keywords = ["jewelry", "accessory", "fashion"]
    else:
        keywords = ["fashion", "accessory"]

    return ",".join(keywords)


def online_accessory_image_url(item: dict, look: dict, accessory_type: str) -> str:
    sku = item.get("sku", "accessory")
    keywords = accessory_search_keywords(item, accessory_type)
    lock = seeded_number(f"{sku}-{item.get('title', '')}-{look.get('slug', '')}", 999983)
    return f"https://loremflickr.com/1200/900/{keywords}/all?lock={lock}&sku={sku}"


def local_accessory_asset_url(item: dict) -> str:
    sku = item.get("sku", "accessory")
    static_dir = Path(__file__).resolve().parent.parent / "static" / "img" / "accessories"
    for extension in (".jpg", ".jpeg", ".png", ".webp", ".svg"):
        static_asset_path = static_dir / f"{sku}{extension}"
        if static_asset_path.exists():
            return f"/static/img/accessories/{sku}{extension}"
    return ""


def item_image_url(item: dict, look: dict) -> str:
    explicit_image = (item.get("image_url") or "").strip()
    if explicit_image:
        return explicit_image
    accessory_type = accessory_type_for_item(item)
    if accessory_type:
        # Prefer curated local assets whenever they exist. This avoids repeated
        # placeholder photos and gives us stable previews for frequently browsed
        # accessory categories.
        local_asset = local_accessory_asset_url(item)
        if local_asset:
            return local_asset
        if accessory_type in {"Shoes", "Watches", "Jewelry"}:
            return accessory_preview_image(item, look, accessory_type)
        return online_accessory_image_url(item, look, accessory_type)
    return look.get("image_url", "")


def tryon_wearable_items(look: dict) -> list[dict]:
    return [item for item in look.get("items", []) if item.get("category") not in {"Accessory", "Shoes"}]


def tryon_haystack(look: dict) -> str:
    parts = [look.get("title", ""), look.get("tagline", "")]
    parts.extend(item.get("title", "") for item in look.get("items", []))
    return " ".join(parts).lower()


def tryon_palette(look: dict) -> dict:
    swatch = TRYON_COLOR_SWATCHES.get((look.get("color") or "").strip().lower(), TRYON_COLOR_SWATCHES["neutral"])
    accent_hue = seeded_hue(f"{look.get('slug', '')}-{look.get('title', '')}", 41)
    glow_hue = seeded_hue(f"{look.get('slug', '')}-{look.get('budget', '')}", 173)
    return {
        "primary": swatch["primary"],
        "secondary": swatch["secondary"],
        "accent": swatch["accent"],
        "line": "rgba(255,255,255,0.9)",
        "panel": f"hsla({accent_hue}, 92%, 72%, 0.18)",
        "glow": f"hsla({glow_hue}, 96%, 68%, 0.26)",
    }


def tryon_is_full_length(look: dict) -> bool:
    haystack = tryon_haystack(look)
    tags = {tag.lower() for tag in look.get("garment_tags", [])}
    if any(keyword in haystack for keyword in TRYON_FULL_LENGTH_KEYWORDS):
        return True
    return bool(tags.intersection(TRYON_FULL_LENGTH_KEYWORDS))


def tryon_top_variant(look: dict) -> str:
    haystack = tryon_haystack(look)
    if any(term in haystack for term in ("abaya", "thobe", "kandura", "jubba", "jalabiya", "kaftan", "jilbab", "kurta", "bisht")):
        return "robe"
    if any(term in haystack for term in ("blazer", "tailored", "coat", "jacket", "structured")):
        return "tailored"
    if any(term in haystack for term in ("hoodie", "sweatshirt", "zip", "track")):
        return "hoodie"
    if any(term in haystack for term in ("dress", "satin", "slip", "gown")):
        return "drape"
    return "relaxed"


def tryon_bottom_variant(look: dict) -> str:
    haystack = tryon_haystack(look)
    if any(term in haystack for term in ("skirt", "maxi", "pleated")):
        return "skirt"
    if any(term in haystack for term in ("jogger", "track", "athleisure")):
        return "jogger"
    if "denim" in haystack:
        return "denim"
    if any(term in haystack for term in ("trouser", "pant", "tailored", "flare")):
        return "trouser"
    return "straight"


def tryon_default_controls(look: dict, mode: str) -> dict:
    if tryon_is_full_length(look):
        defaults = {
            "full": {"offset_x": 0, "offset_y": 7, "scale": 72, "rotation": 0, "opacity": 82},
            "top": {"offset_x": 0, "offset_y": -15, "scale": 74, "rotation": 0, "opacity": 80},
            "bottom": {"offset_x": 0, "offset_y": 22, "scale": 76, "rotation": 0, "opacity": 78},
        }
    else:
        defaults = {
            "full": {"offset_x": 0, "offset_y": 4, "scale": 70, "rotation": 0, "opacity": 80},
            "top": {"offset_x": 0, "offset_y": -18, "scale": 74, "rotation": 0, "opacity": 80},
            "bottom": {"offset_x": 0, "offset_y": 20, "scale": 72, "rotation": 0, "opacity": 78},
        }
    return defaults.get(mode, defaults["full"])


def tryon_ar_profile(look: dict) -> dict:
    full_length = tryon_is_full_length(look)
    top_variant = tryon_top_variant(look)
    bottom_variant = tryon_bottom_variant(look)

    top_profiles = {
        "robe": {
            "bounds": {"x": 0.18, "y": 0.1, "w": 0.64, "h": 0.7},
            "fit": {"shoulder_width": 1.44, "torso_height": 1.36, "hip_width": 1.46, "y_shift": 0.04},
            "arm_coverage": "long",
        },
        "tailored": {
            "bounds": {"x": 0.22, "y": 0.14, "w": 0.56, "h": 0.44},
            "fit": {"shoulder_width": 1.18, "torso_height": 0.94, "hip_width": 1.04, "y_shift": -0.015},
            "arm_coverage": "long",
        },
        "hoodie": {
            "bounds": {"x": 0.2, "y": 0.15, "w": 0.6, "h": 0.46},
            "fit": {"shoulder_width": 1.28, "torso_height": 1.02, "hip_width": 1.12, "y_shift": 0.0},
            "arm_coverage": "long",
        },
        "drape": {
            "bounds": {"x": 0.24, "y": 0.13, "w": 0.52, "h": 0.46},
            "fit": {"shoulder_width": 1.12, "torso_height": 1.08, "hip_width": 1.16, "y_shift": 0.01},
            "arm_coverage": "short",
        },
        "relaxed": {
            "bounds": {"x": 0.2, "y": 0.15, "w": 0.6, "h": 0.44},
            "fit": {"shoulder_width": 1.2, "torso_height": 0.98, "hip_width": 1.08, "y_shift": -0.005},
            "arm_coverage": "short",
        },
    }
    bottom_profiles = {
        "skirt": {
            "bounds": {"x": 0.24, "y": 0.47, "w": 0.52, "h": 0.45},
            "fit": {"hip_width": 1.18, "hem_width": 1.58, "leg_length": 1.08, "y_shift": 0.02},
            "hem_style": "flare",
        },
        "jogger": {
            "bounds": {"x": 0.28, "y": 0.49, "w": 0.44, "h": 0.42},
            "fit": {"hip_width": 1.04, "hem_width": 0.84, "leg_length": 1.0, "y_shift": 0.015},
            "hem_style": "tapered",
        },
        "denim": {
            "bounds": {"x": 0.28, "y": 0.49, "w": 0.44, "h": 0.42},
            "fit": {"hip_width": 1.02, "hem_width": 0.9, "leg_length": 1.02, "y_shift": 0.015},
            "hem_style": "straight",
        },
        "trouser": {
            "bounds": {"x": 0.29, "y": 0.49, "w": 0.42, "h": 0.43},
            "fit": {"hip_width": 1.0, "hem_width": 0.82, "leg_length": 1.06, "y_shift": 0.012},
            "hem_style": "tailored",
        },
        "straight": {
            "bounds": {"x": 0.28, "y": 0.49, "w": 0.44, "h": 0.43},
            "fit": {"hip_width": 1.04, "hem_width": 0.92, "leg_length": 1.02, "y_shift": 0.014},
            "hem_style": "straight",
        },
    }

    if full_length:
        bottom_profile = {
            "bounds": {"x": 0.23, "y": 0.45, "w": 0.54, "h": 0.45},
            "fit": {"hip_width": 1.24, "hem_width": 1.5, "leg_length": 1.74, "y_shift": 0.03},
            "hem_style": "drape",
        }
    else:
        bottom_profile = bottom_profiles.get(bottom_variant, bottom_profiles["straight"])

    top_profile = top_profiles.get(top_variant, top_profiles["relaxed"])
    base_controls = tryon_default_controls(look, "full")

    return {
        "full_length": full_length,
        "top_variant": top_variant,
        "bottom_variant": bottom_variant,
        "arm_coverage": top_profile["arm_coverage"],
        "top_bounds": top_profile["bounds"],
        "bottom_bounds": bottom_profile["bounds"],
        "top_fit": top_profile["fit"],
        "bottom_fit": bottom_profile["fit"],
        "hem_style": bottom_profile["hem_style"],
        "calibration": {
            "scale_bias": round((base_controls["scale"] - 70) / 100, 3),
            "offset_x": round(base_controls["offset_x"] / 100, 3),
            "offset_y": round(base_controls["offset_y"] / 100, 3),
            "opacity": round(base_controls["opacity"] / 100, 3),
        },
    }


def tryon_accessory_fragment(look: dict, palette: dict) -> str:
    haystack = tryon_haystack(look)
    if "bag" in haystack or "tote" in haystack or "satchel" in haystack or "pouch" in haystack:
        return (
            f'<path d="M706 540 C748 496 820 494 860 538 L860 690 C860 718 838 740 810 740 L686 740 C658 740 636 718 636 690 L636 582 '
            f'C636 552 656 530 686 530 L706 530 Z" fill="{palette["panel"]}" stroke="{palette["line"]}" stroke-width="12"/>'
            f'<path d="M694 530 C696 486 722 460 748 460 C782 460 808 490 812 530" fill="none" stroke="{palette["accent"]}" stroke-width="12" stroke-linecap="round"/>'
        )
    if "watch" in haystack:
        return (
            f'<circle cx="744" cy="476" r="42" fill="{palette["panel"]}" stroke="{palette["line"]}" stroke-width="10"/>'
            f'<rect x="726" y="396" width="36" height="56" rx="18" fill="{palette["accent"]}" opacity="0.55"/>'
            f'<rect x="726" y="500" width="36" height="56" rx="18" fill="{palette["accent"]}" opacity="0.55"/>'
        )
    return ""


def tryon_top_fragment(variant: str, palette: dict, *, full_length: bool) -> str:
    if variant == "robe":
        return (
            f'<path d="M302 246 C362 186 426 156 500 156 C574 156 638 186 698 246 L772 416 L710 1142 L290 1142 L228 416 Z" '
            f'fill="url(#fabric)" stroke="{palette["line"]}" stroke-width="14" stroke-linejoin="round"/>'
            f'<path d="M338 274 C386 240 438 220 500 220 C562 220 614 240 662 274" fill="none" stroke="{palette["accent"]}" stroke-width="12" stroke-linecap="round"/>'
            f'<path d="M426 252 L426 1112" stroke="rgba(255,255,255,0.22)" stroke-width="8" stroke-linecap="round"/>'
            f'<path d="M574 252 L574 1112" stroke="rgba(255,255,255,0.22)" stroke-width="8" stroke-linecap="round"/>'
            f'<path d="M246 418 L114 710" fill="none" stroke="{palette["line"]}" stroke-width="18" stroke-linecap="round"/>'
            f'<path d="M754 418 L886 710" fill="none" stroke="{palette["line"]}" stroke-width="18" stroke-linecap="round"/>'
        )
    if variant == "tailored":
        return (
            f'<path d="M318 252 C376 198 432 174 500 174 C568 174 624 198 682 252 L748 430 L688 760 L572 744 L548 522 L452 522 L428 744 L312 760 L252 430 Z" '
            f'fill="url(#fabric)" stroke="{palette["line"]}" stroke-width="14" stroke-linejoin="round"/>'
            f'<path d="M430 248 C456 286 476 334 500 432 C524 334 544 286 570 248" fill="none" stroke="{palette["accent"]}" stroke-width="12" stroke-linecap="round"/>'
            f'<path d="M378 362 L450 520" fill="none" stroke="rgba(255,255,255,0.22)" stroke-width="8" stroke-linecap="round"/>'
            f'<path d="M622 362 L550 520" fill="none" stroke="rgba(255,255,255,0.22)" stroke-width="8" stroke-linecap="round"/>'
        )
    if variant == "hoodie":
        return (
            f'<path d="M302 282 C356 222 420 194 500 194 C580 194 644 222 698 282 L766 432 L712 738 L598 738 L574 620 L426 620 L402 738 L288 738 L234 432 Z" '
            f'fill="url(#fabric)" stroke="{palette["line"]}" stroke-width="14" stroke-linejoin="round"/>'
            f'<path d="M410 240 C438 210 466 194 500 194 C534 194 562 210 590 240 L638 316 C596 336 552 348 500 350 C448 348 404 336 362 316 Z" '
            f'fill="none" stroke="{palette["accent"]}" stroke-width="12" stroke-linejoin="round"/>'
            f'<rect x="420" y="560" width="160" height="64" rx="28" fill="rgba(255,255,255,0.12)" stroke="rgba(255,255,255,0.22)" stroke-width="8"/>'
        )
    if variant == "drape":
        return (
            f'<path d="M338 242 C384 198 438 176 500 176 C562 176 616 198 662 242 L716 392 L668 692 C654 734 624 760 588 760 L412 760 C376 760 346 734 332 692 L284 392 Z" '
            f'fill="url(#fabric)" stroke="{palette["line"]}" stroke-width="14" stroke-linejoin="round"/>'
            f'<path d="M404 238 C438 272 470 288 500 288 C530 288 562 272 596 238" fill="none" stroke="{palette["accent"]}" stroke-width="12" stroke-linecap="round"/>'
            f'<path d="M392 420 C436 462 466 486 500 490 C534 486 564 462 608 420" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="8" stroke-linecap="round"/>'
        )
    return (
        f'<path d="M316 268 C372 220 434 196 500 196 C566 196 628 220 684 268 L754 432 L702 730 L582 730 L552 598 L448 598 L418 730 L298 730 L246 432 Z" '
        f'fill="url(#fabric)" stroke="{palette["line"]}" stroke-width="14" stroke-linejoin="round"/>'
        f'<path d="M390 258 C430 286 466 298 500 298 C534 298 570 286 610 258" fill="none" stroke="{palette["accent"]}" stroke-width="12" stroke-linecap="round"/>'
    )


def tryon_bottom_fragment(variant: str, palette: dict, *, full_length: bool) -> str:
    if full_length:
        return (
            f'<path d="M304 666 C366 706 430 726 500 726 C570 726 634 706 696 666 L740 1132 C742 1170 714 1202 676 1202 L324 1202 '
            f'C286 1202 258 1170 260 1132 Z" fill="url(#fabricSecondary)" stroke="{palette["line"]}" stroke-width="12" stroke-linejoin="round"/>'
            f'<path d="M404 756 L388 1172" stroke="rgba(255,255,255,0.2)" stroke-width="8" stroke-linecap="round"/>'
            f'<path d="M596 756 L612 1172" stroke="rgba(255,255,255,0.2)" stroke-width="8" stroke-linecap="round"/>'
        )
    if variant == "skirt":
        return (
            f'<path d="M360 706 C412 736 456 752 500 752 C544 752 588 736 640 706 L728 1176 C734 1212 706 1244 670 1244 L330 1244 '
            f'C294 1244 266 1212 272 1176 Z" fill="url(#fabricSecondary)" stroke="{palette["line"]}" stroke-width="12" stroke-linejoin="round"/>'
            f'<path d="M404 770 L374 1184 M500 760 L500 1194 M596 770 L626 1184" stroke="rgba(255,255,255,0.22)" stroke-width="8" stroke-linecap="round"/>'
        )
    if variant == "jogger":
        return (
            f'<path d="M394 698 L486 698 L450 1186 C446 1214 422 1234 394 1234 L340 1234 C310 1234 286 1208 290 1178 Z" fill="url(#fabricSecondary)" stroke="{palette["line"]}" stroke-width="12" stroke-linejoin="round"/>'
            f'<path d="M606 698 L514 698 L550 1186 C554 1214 578 1234 606 1234 L660 1234 C690 1234 714 1208 710 1178 Z" fill="url(#fabricSecondary)" stroke="{palette["line"]}" stroke-width="12" stroke-linejoin="round"/>'
            f'<path d="M346 1206 L392 1206 M608 1206 L654 1206" stroke="{palette["accent"]}" stroke-width="10" stroke-linecap="round"/>'
        )
    if variant == "trouser":
        return (
            f'<path d="M398 692 L494 692 L466 1198 C462 1226 438 1248 410 1248 L364 1248 C334 1248 310 1222 312 1192 Z" fill="url(#fabricSecondary)" stroke="{palette["line"]}" stroke-width="12" stroke-linejoin="round"/>'
            f'<path d="M602 692 L506 692 L534 1198 C538 1226 562 1248 590 1248 L636 1248 C666 1248 690 1222 688 1192 Z" fill="url(#fabricSecondary)" stroke="{palette["line"]}" stroke-width="12" stroke-linejoin="round"/>'
            f'<path d="M500 692 L500 1224" stroke="rgba(255,255,255,0.18)" stroke-width="8" stroke-linecap="round"/>'
        )
    if variant == "denim":
        return (
            f'<path d="M398 688 L494 688 L470 1206 C466 1230 444 1248 420 1248 L360 1248 C332 1248 308 1224 310 1194 Z" fill="url(#fabricSecondary)" stroke="{palette["line"]}" stroke-width="12" stroke-linejoin="round"/>'
            f'<path d="M602 688 L506 688 L530 1206 C534 1230 556 1248 580 1248 L640 1248 C668 1248 692 1224 690 1194 Z" fill="url(#fabricSecondary)" stroke="{palette["line"]}" stroke-width="12" stroke-linejoin="round"/>'
            f'<path d="M390 772 L448 772 M552 772 L610 772" stroke="{palette["accent"]}" stroke-width="8" stroke-linecap="round"/>'
        )
    return (
        f'<path d="M398 698 L492 698 L470 1198 C466 1226 444 1248 418 1248 L362 1248 C334 1248 310 1222 312 1192 Z" fill="url(#fabricSecondary)" stroke="{palette["line"]}" stroke-width="12" stroke-linejoin="round"/>'
        f'<path d="M602 698 L508 698 L530 1198 C534 1226 556 1248 582 1248 L638 1248 C666 1248 690 1222 688 1192 Z" fill="url(#fabricSecondary)" stroke="{palette["line"]}" stroke-width="12" stroke-linejoin="round"/>'
    )


def tryon_overlay_svg(look: dict, mode: str) -> str:
    palette = tryon_palette(look)
    full_length = tryon_is_full_length(look)
    top_variant = tryon_top_variant(look)
    bottom_variant = tryon_bottom_variant(look)
    accent_fragment = tryon_accessory_fragment(look, palette) if mode == "full" else ""
    title = html.escape((look.get("title") or "StyleBridge look")[:80])

    if mode == "top":
        garment_markup = tryon_top_fragment(top_variant, palette, full_length=full_length)
    elif mode == "bottom":
        garment_markup = tryon_bottom_fragment(bottom_variant, palette, full_length=full_length)
    else:
        garment_markup = (
            tryon_top_fragment(top_variant, palette, full_length=full_length)
            + tryon_bottom_fragment(bottom_variant, palette, full_length=full_length)
            + accent_fragment
        )

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1400" role="img" aria-label="{title}">
  <defs>
    <linearGradient id="fabric" x1="300" y1="180" x2="700" y2="900" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{palette["primary"]}" stop-opacity="0.9" />
      <stop offset="100%" stop-color="{palette["secondary"]}" stop-opacity="0.84" />
    </linearGradient>
    <linearGradient id="fabricSecondary" x1="300" y1="640" x2="700" y2="1260" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{palette["secondary"]}" stop-opacity="0.92" />
      <stop offset="100%" stop-color="{palette["primary"]}" stop-opacity="0.82" />
    </linearGradient>
    <filter id="glow" x="120" y="120" width="760" height="1180" filterUnits="userSpaceOnUse">
      <feGaussianBlur stdDeviation="24"/>
    </filter>
  </defs>
  <ellipse cx="500" cy="716" rx="250" ry="516" fill="{palette["glow"]}" filter="url(#glow)" />
  <g opacity="0.96">{garment_markup}</g>
</svg>
""".strip()


def tryon_overlay_image(look: dict, mode: str) -> str:
    return "data:image/svg+xml;charset=UTF-8," + quote(tryon_overlay_svg(look, mode))


def look_tryon_payload(look: dict) -> dict:
    wearable_items = tryon_wearable_items(look)
    palette = tryon_palette(look)
    layers = []
    layer_specs = [
        ("full", "Full look"),
        ("top", "Top focus"),
        ("bottom", "Bottom focus"),
    ]

    for layer_id, label in layer_specs:
        layers.append(
            {
                "id": layer_id,
                "label": label,
                "image_url": tryon_overlay_image(look, layer_id),
                "defaults": tryon_default_controls(look, layer_id),
            }
        )

    return {
        "fit_mode": "full-body" if tryon_is_full_length(look) else "separates",
        "wearable_summary": [item.get("title", "") for item in wearable_items[:3]],
        "palette": {
            "primary": palette["primary"],
            "secondary": palette["secondary"],
            "accent": palette["accent"],
        },
        "ar_profile": tryon_ar_profile(look),
        "layers": layers,
    }


for look in LOOKS:
    for accessory in ("Watches", "Glasses", "Bags", "Jewelry"):
        if not look_has_accessory(look, accessory):
            item = accessory_item_for_look(look, accessory)
            look["items"].append(item)
            look["price_total"] += item["price"]


LOOKS_BY_SLUG = {look["slug"]: look for look in LOOKS}


def look_matches_gender(look: dict, gender: str) -> bool:
    if not gender:
        return True
    look_genders = set(look.get("genders", []))
    if not look_genders:
        return True
    return gender in look_genders or "Unisex" in look_genders


def look_matches_gender_filter(look: dict, gender: str) -> bool:
    if not gender:
        return True
    look_genders = set(look.get("genders", []))
    if not look_genders:
        return False
    if gender == "Menswear":
        return "Menswear" in look_genders and "Womenswear" not in look_genders
    if gender == "Womenswear":
        return "Womenswear" in look_genders and "Menswear" not in look_genders
    if gender == "Unisex":
        return "Unisex" in look_genders and "Menswear" not in look_genders and "Womenswear" not in look_genders
    return gender in look_genders


def look_matches_religion(look: dict, religion: str) -> bool:
    if not religion:
        return True
    return religion in set(look.get("religions", []))


def ensure_onboarding():
    if not current_user.is_authenticated:
        return None
    if current_user.has_role("seller"):
        profile = getattr(current_user, "seller_profile", None)
        if profile and profile.onboarding_complete:
            return redirect(url_for("seller.dashboard"))
        return redirect(url_for("seller.onboarding"))
    if current_user.onboarding_complete:
        return None
    return redirect(url_for("main.onboarding"))


def score_look(look: dict, data: dict) -> int:
    score = 0
    style_preference = data.get("style_preference", "")
    favorite_styles = set(data.get("favorite_styles", []))
    favorite_brands = set(data.get("favorite_brands", []))
    gender = data.get("gender", "")
    religion = data.get("religion", "")
    body_type = data.get("body_type", "")
    style_set = set(look_styles(look))

    if style_preference and style_preference in style_set:
        score += 12
    if favorite_styles:
        score += len(favorite_styles.intersection(style_set)) * 6
    if favorite_brands:
        score += len(favorite_brands.intersection(set(look["brands"]))) * 5
    if data.get("budget_range") == look["budget"]:
        score += 5
    else:
        score += max(0, 2 - budget_distance(data.get("budget_range", ""), look["budget"]))

    look_genders = set(look.get("genders", []))
    if gender:
        if gender in look_genders:
            score += 4
        elif look_matches_gender(look, gender):
            score += 2
        elif look_genders:
            score -= 3

    look_religions = set(look.get("religions", []))
    if religion:
        if religion in look_religions:
            score += 8
        elif look_religions:
            score -= 2

    look_body_types = set(look.get("body_types", []))
    if body_type:
        if body_type in look_body_types:
            score += 4
        elif look_body_types:
            score -= 1

    return score


def match_reason(look: dict, data: dict) -> str:
    reasons = []
    style_preference = data.get("style_preference", "")
    favorite_styles = set(data.get("favorite_styles", []))
    favorite_brands = set(data.get("favorite_brands", []))
    gender = data.get("gender", "")
    religion = data.get("religion", "")
    body_type = data.get("body_type", "")
    style_set = set(look_styles(look))

    if style_preference and style_preference in style_set:
        reasons.append(f"{style_preference} styling")

    matched_styles = sorted(favorite_styles.intersection(style_set))
    if matched_styles:
        reasons.append("favorite styles")

    matched_brands = sorted(favorite_brands.intersection(set(look["brands"])))
    if matched_brands:
        reasons.append(", ".join(matched_brands[:2]))

    if data.get("budget_range") == look["budget"]:
        reasons.append(f"{look['budget'].lower()} budget")

    if gender and look_matches_gender(look, gender):
        reasons.append("profile fit")

    if religion and look_matches_religion(look, religion):
        if religion == "Islam":
            reasons.append("modest Muslim-friendly styling")
        else:
            reasons.append("religion-aware styling")

    if body_type and body_type in look.get("body_types", []):
        reasons.append(f"{body_type.lower()} body match")

    if reasons:
        return "Matched for " + " + ".join(reasons[:3]) + "."

    return look["match_text"]


def normalize_scan_bucket(value: str, allowed: set[str]) -> str:
    normalized = sanitize_text(str(value or ""), 40).strip().lower()
    return normalized if normalized in allowed else ""


def normalized_scan_context(raw: dict | None) -> dict:
    payload = raw if isinstance(raw, dict) else {}
    try:
        confidence = float(payload.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "coverage": normalize_scan_bucket(payload.get("coverage", ""), SCAN_COVERAGE_OPTIONS),
        "silhouette": normalize_scan_bucket(payload.get("silhouette", ""), SCAN_SILHOUETTE_OPTIONS),
        "palette": normalize_scan_bucket(payload.get("palette", ""), SCAN_PALETTE_OPTIONS),
        "lighting": normalize_scan_bucket(payload.get("lighting", ""), SCAN_LIGHTING_OPTIONS),
        "confidence": max(0.0, min(confidence, 1.0)),
    }


def body_type_hints_from_scan(scan: dict) -> set[str]:
    silhouette = scan.get("silhouette", "")
    if silhouette == "top-dominant":
        return {"Athletic", "Straight", "Tall"}
    if silhouette == "bottom-dominant":
        return {"Curvy", "Plus size", "Straight"}
    if silhouette == "balanced":
        return {"Straight", "Petite", "Tall"}
    return set()


def scan_color_match_score(look: dict, palette: str) -> int:
    look_color = (look.get("color") or "").strip().lower()
    if palette == "warm":
        return 4 if look_color in {"brown", "rose", "pearl", "white", "neutral"} else 0
    if palette == "cool":
        return 4 if look_color in {"black", "blue", "emerald", "green"} else 0
    if palette == "neutral":
        return 3 if look_color in {"black", "white", "brown", "neutral"} else 1
    return 0


def scan_fit_score(look: dict, scan: dict) -> int:
    score = 0
    body_hints = body_type_hints_from_scan(scan)
    look_body_types = set(look.get("body_types", []))
    look_styles_set = set(look_styles(look))

    if body_hints.intersection(look_body_types):
        score += 6

    coverage = scan.get("coverage", "")
    if coverage == "full-body":
        score += 3 if tryon_is_full_length(look) else 1
    elif coverage == "upper-body":
        score += 3 if not tryon_is_full_length(look) else 1
    elif coverage == "portrait":
        score += 2 if not tryon_is_full_length(look) else 0

    score += scan_color_match_score(look, scan.get("palette", ""))

    lighting = scan.get("lighting", "")
    look_color = (look.get("color") or "").strip().lower()
    if lighting == "low-light":
        if look_styles_set.intersection({"Formal", "Minimalist", "Modest"}):
            score += 2
        if look_color in {"black", "blue", "emerald"}:
            score += 1
    elif lighting == "bright":
        if look_styles_set.intersection({"Casual", "Streetwear", "Athleisure"}):
            score += 2
        if look_color in {"white", "rose", "brown", "pearl"}:
            score += 1

    return score


def scan_reason_for_look(look: dict, scan: dict) -> str:
    reasons = []
    silhouette = scan.get("silhouette", "")
    coverage = scan.get("coverage", "")
    palette = scan.get("palette", "")

    if silhouette == "top-dominant" and set(look.get("body_types", [])).intersection({"Athletic", "Straight", "Tall"}):
        reasons.append("supports a stronger shoulder line")
    elif silhouette == "bottom-dominant" and set(look.get("body_types", [])).intersection({"Curvy", "Plus size", "Straight"}):
        reasons.append("balances a lower-body-led frame")
    elif silhouette == "balanced" and "Straight" in set(look.get("body_types", [])):
        reasons.append("keeps a balanced frame looking clean")

    if palette == "warm" and (look.get("color") or "").strip().lower() in {"brown", "rose", "pearl", "white", "neutral"}:
        reasons.append("its warmer palette should read smoothly against this photo")
    elif palette == "cool" and (look.get("color") or "").strip().lower() in {"black", "blue", "emerald", "green"}:
        reasons.append("its cooler tones should sit cleanly on camera")
    elif palette == "neutral":
        reasons.append("its neutral palette will stay easy to wear across occasions")

    if coverage == "full-body" and tryon_is_full_length(look):
        reasons.append("the longer silhouette will preview clearly in a full-body shot")
    elif coverage in {"portrait", "upper-body"} and not tryon_is_full_length(look):
        reasons.append("separate layers will be easier to judge from this crop")

    if not reasons:
        return "Recommended from your saved style profile."
    return "Scan pick: " + "; ".join(reasons[:2]) + "."


def build_style_scan_report(scan: dict) -> dict:
    coverage = scan.get("coverage", "")
    silhouette = scan.get("silhouette", "")
    palette = scan.get("palette", "")
    lighting = scan.get("lighting", "")
    confidence = int(round(float(scan.get("confidence", 0)) * 100))

    coverage_labels = {
        "portrait": "Portrait crop",
        "upper-body": "Upper-body crop",
        "full-body": "Full-body framing",
    }
    silhouette_labels = {
        "balanced": "Balanced frame",
        "top-dominant": "Top-led frame",
        "bottom-dominant": "Bottom-led frame",
    }
    palette_labels = {
        "warm": "Warm palette",
        "cool": "Cool palette",
        "neutral": "Neutral palette",
    }
    lighting_labels = {
        "bright": "Bright light",
        "balanced": "Balanced light",
        "low-light": "Low light",
    }

    chips = []
    if coverage:
        chips.append({"label": "Frame", "value": coverage_labels[coverage]})
    if silhouette:
        chips.append({"label": "Shape", "value": silhouette_labels[silhouette]})
    if palette:
        chips.append({"label": "Palette", "value": palette_labels[palette]})
    if lighting:
        chips.append({"label": "Light", "value": lighting_labels[lighting]})
    if confidence:
        chips.append({"label": "Confidence", "value": f"{confidence}%"})

    if not chips:
        return {
            "headline": "Scan saved",
            "summary": "The photo was saved, but the scan did not get enough body signal. Recommendations below fall back to your saved style profile.",
            "chips": [{"label": "Status", "value": "Profile-based suggestions"}],
        }

    summary_parts = []
    if coverage:
        summary_parts.append(coverage_labels[coverage].lower())
    if silhouette:
        summary_parts.append(silhouette_labels[silhouette].lower())
    if palette:
        summary_parts.append(palette_labels[palette].lower())

    summary_text = ", ".join(summary_parts[:3])
    return {
        "headline": "Scan complete",
        "summary": f"We detected {summary_text} and used that with your saved preferences to rank what should wear best on camera.",
        "chips": chips,
    }


def build_tryon_style_suggestions(scan: dict, limit: int = 3) -> list[dict]:
    base_looks = personalized_looks()
    scored = []
    user_budget = profile_data().get("budget_range", "")

    for look in base_looks:
        total_score = int(look.get("match_score", 0)) + scan_fit_score(look, scan)
        scored.append(
            (
                -total_score,
                budget_distance(user_budget, look.get("budget", "")),
                look.get("title", ""),
                look,
            )
        )

    scored.sort(key=lambda entry: (entry[0], entry[1], entry[2]))

    suggestions = []
    seen = set()
    for _, __, ___, look in scored:
        key = (look.get("image_url") or "").strip() or look.get("slug")
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(
            {
                "slug": look["slug"],
                "title": look["title"],
                "creator": look.get("creator", ""),
                "image_url": look.get("image_url", ""),
                "styles": look.get("styles", []),
                "price_total": look.get("price_total", 0),
                "shop_url": url_for("main.look_detail", slug=look["slug"]),
                "match_reason": look.get("match_reason", ""),
                "scan_reason": scan_reason_for_look(look, scan),
            }
        )
        if len(suggestions) >= limit:
            break

    return suggestions


def enrich_look(look: dict, data: dict) -> dict:
    enriched = dict(look)
    enriched["styles"] = look_styles(look)
    enriched["garment_tags"] = look_garment_tags(look)
    enriched["items"] = [{**item, "image_url": item_image_url(item, look)} for item in look["items"]]
    enriched["match_score"] = score_look(look, data)
    enriched["match_reason"] = match_reason(look, data)
    return enriched


def accessory_catalog(
    data: dict,
    *,
    query: str = "",
    style: str = "",
    budget: str = "",
    gender: str = "",
    religion: str = "",
    brand: str = "",
    color: str = "",
) -> list[dict]:
    accessories = []
    for raw_look in LOOKS:
        look = enrich_look(raw_look, data)
        if style and style not in look["styles"]:
            continue
        if budget and budget != look["budget"]:
            continue
        if gender and not look_matches_gender_filter(look, gender):
            continue
        if religion and not look_matches_religion(look, religion):
            continue
        if color and color != look["color"].lower():
            continue

        for item in look["items"]:
            accessory_type = accessory_type_for_item(item)
            if not accessory_type:
                continue

            item_brand = (item.get("brand") or "").lower()
            haystack = " ".join(
                [
                    item.get("title", ""),
                    item.get("category", ""),
                    item.get("brand", ""),
                    accessory_type,
                    look["title"],
                    look["tagline"],
                    look.get("color", ""),
                    " ".join(look["styles"]),
                    " ".join(look["brands"]),
                    " ".join(look.get("religions", [])),
                    " ".join(look.get("garment_tags", [])),
                ]
            ).lower()

            if query and query not in haystack:
                continue
            if brand and brand not in f"{item_brand} {' '.join(look['brands']).lower()}":
                continue

            accessories.append(
                {
                    "sku": item["sku"],
                    "title": item["title"],
                    "category": item.get("category", ""),
                    "brand": item.get("brand", ""),
                    "price": item.get("price", 0),
                    "image_url": item.get("image_url") or look.get("image_url", ""),
                    "accessory_type": accessory_type,
                    "look_slug": look["slug"],
                    "look_title": look["title"],
                    "look_styles": look["styles"],
                    "look_genders": look.get("genders", []),
                    "look_religions": look.get("religions", []),
                    "look_color": look.get("color", ""),
                    "budget": look.get("budget", ""),
                    "match_score": look["match_score"],
                    "match_reason": look["match_reason"],
                }
            )

    accessories.sort(
        key=lambda item: (
            -item["match_score"],
            ACCESSORY_OPTIONS.index(item["accessory_type"]) if item["accessory_type"] in ACCESSORY_OPTIONS else 999,
            item["title"],
            item["look_title"],
        )
    )
    return accessories


def dedupe_looks_by_image(looks: list[dict]) -> list[dict]:
    unique = []
    seen_images = set()
    for look in looks:
        image_url = (look.get("image_url") or "").strip()
        key = image_url or look.get("slug")
        if key in seen_images:
            continue
        seen_images.add(key)
        unique.append(look)
    return unique


def personalized_looks() -> list[dict]:
    data = profile_data()
    enriched = [enrich_look(look, data) for look in LOOKS]
    ordered = sorted(
        enriched,
        key=lambda look: (-look["match_score"], budget_distance(data.get("budget_range", ""), look["budget"]), look["title"]),
    )
    return dedupe_looks_by_image(ordered)


def append_order_to_history(order_payload: dict) -> None:
    history = current_user.get_order_history()
    history.insert(0, order_payload)
    current_user.set_order_history(history[:20])
    db.session.commit()


def validate_seller_cart_items() -> str:
    for item in cart_items():
        product_id = item.get("seller_product_id")
        if not product_id:
            continue
        try:
            product = db.session.get(SellerProduct, int(product_id))
        except (TypeError, ValueError):
            product = None
        quantity = max(1, int(item.get("quantity", 1) or 1))
        if not product or product.status == "Out of stock" or product.stock_quantity < quantity:
            return f"{item.get('title', 'A seller item')} is no longer available in that quantity."
    return ""


def record_seller_orders(order_payload: dict) -> None:
    grouped: dict[int, dict] = {}
    for item in order_payload.get("items", []):
        product_id = item.get("seller_product_id")
        if not product_id:
            continue
        try:
            product = db.session.get(SellerProduct, int(product_id))
        except (TypeError, ValueError):
            product = None
        if not product:
            continue

        quantity = max(1, int(item.get("quantity", 1) or 1))
        product.stock_quantity = max(0, product.stock_quantity - quantity)
        product.orders_count += quantity
        if product.stock_quantity == 0:
            product.status = "Out of stock"

        bucket = grouped.setdefault(
            product.seller_id,
            {
                "items": [],
                "total": 0.0,
            },
        )
        bucket["items"].append(
            {
                "product_id": product.id,
                "title": product.title,
                "quantity": quantity,
                "price": product.price,
                "image_url": product.image_url,
            }
        )
        bucket["total"] += product.price * quantity

    for seller_id, payload in grouped.items():
        seller_order = SellerOrder(
            seller_id=seller_id,
            buyer_user_id=int(current_user.get_id()),
            external_reference=order_payload["reference"],
            customer_name=order_payload["shipping_name"],
            customer_email=current_user.email,
            customer_phone=current_user.phone,
            delivery_location=order_payload["shipping_address"],
            total_amount=round(payload["total"], 2),
            status="Pending",
            payout_status="Pending",
        )
        seller_order.set_items(payload["items"])
        db.session.add(seller_order)

    if grouped:
        db.session.commit()


@bp.get("/")
def home():
    if current_user.is_authenticated:
        if current_user.has_role("seller"):
            profile = getattr(current_user, "seller_profile", None)
            if profile and profile.onboarding_complete:
                return redirect(url_for("seller.dashboard"))
            return redirect(url_for("seller.onboarding"))
    return render_template("home.html")


@bp.get("/demo")
def demo():
    requested_model = resolve_demo_model(request.args.get("model", ""))
    initial_model = requested_model or DEMO_SAMPLE_MODELS[0]["url"]
    actor = f"user:{current_user.id}" if current_user.is_authenticated else "guest"
    current_app.logger.info("demo.view actor=%s model=%s ip=%s", actor, initial_model, request.remote_addr)
    return render_template(
        "demo.html",
        sample_models=DEMO_SAMPLE_MODELS,
        initial_model=initial_model,
    )


@bp.post("/demo/upload-model")
@limiter.limit("20 per hour")
def demo_upload_model():
    model_file = request.files.get("model")
    if not model_file or not model_file.filename:
        return jsonify({"ok": False, "error": "Missing model file."}), 400
    if not allowed_model_file(model_file.filename):
        return jsonify({"ok": False, "error": "Only .glb and .gltf files are allowed."}), 400

    try:
        url = save_uploaded_file(model_file, "guest-model", subdirectory="demo-models")
    except UploadStorageError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    safe_url = resolve_demo_model(url) or url
    actor = f"user:{current_user.id}" if current_user.is_authenticated else "guest"
    audit("demo.model_uploaded", target=actor, meta={"url": safe_url})
    return jsonify(
        {
            "ok": True,
            "url": safe_url,
            "filename": sanitize_text(model_file.filename, 160),
        }
    )


@bp.get("/feedback")
def feedback():
    return render_template("feedback.html")


@bp.post("/feedback")
@limiter.limit("20 per hour")
def feedback_post():
    contact = sanitize_text(request.form.get("contact", ""), 180)
    message = sanitize_text(request.form.get("message", ""), 3000)
    if not message:
        flash("Share at least one line of feedback.", "error")
        return redirect(url_for("main.feedback")), 302

    actor = f"user:{current_user.id}" if current_user.is_authenticated else "guest"
    audit("feedback.submitted", target=actor, meta={"contact": contact, "message": message})
    flash("Thanks. Feedback saved.", "success")
    return redirect(url_for("main.feedback")), 302


@bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    existing = profile_data()

    if request.method == "POST":
        data = profile_payload_from_form(existing)
        current_user.onboarding_complete = True
        current_user.set_profile_data(data)
        current_user.set_profile_vector(profile_vector_from(data))
        db.session.commit()
        audit("profile.onboarding_completed", target=f"user:{current_user.id}")
        flash("Your style profile is ready.", "success")
        return redirect(url_for("main.feed"))

    return render_template(
        "onboarding.html",
        gender_options=GENDER_OPTIONS,
        religion_options=RELIGION_OPTIONS,
        style_options=STYLE_OPTIONS,
        budget_options=BUDGET_OPTIONS,
        body_type_options=BODY_TYPE_OPTIONS,
        existing=existing,
    )


@bp.get("/feed")
@login_required
def feed():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect
    looks = personalized_looks()
    saved = set(current_user.get_saved_looks())
    return render_template("feed.html", looks=looks, saved=saved, profile=profile_data())


@bp.get("/accessories")
@login_required
def accessories():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect

    data = profile_data()
    query = (request.args.get("q") or "").strip().lower()
    style = (request.args.get("style") or "").strip()
    budget = (request.args.get("budget") or "").strip()
    gender = (request.args.get("gender") or "").strip()
    religion = (request.args.get("religion") or "").strip()
    accessory = (request.args.get("accessory") or "").strip()
    brand = (request.args.get("brand") or "").strip().lower()
    color = (request.args.get("color") or "").strip().lower()

    all_accessories = accessory_catalog(
        data,
        query=query,
        style=style,
        budget=budget,
        gender=gender,
        religion=religion,
        brand=brand,
        color=color,
    )
    results = [item for item in all_accessories if not accessory or item["accessory_type"] == accessory]
    accessory_counts = {option: sum(1 for item in all_accessories if item["accessory_type"] == option) for option in ACCESSORY_OPTIONS}

    return render_template(
        "accessories.html",
        accessories=results,
        accessory_counts=accessory_counts,
        accessory_options=ACCESSORY_OPTIONS,
        gender_options=GENDER_OPTIONS,
        religion_options=RELIGION_OPTIONS,
        style_options=STYLE_OPTIONS,
        budget_options=BUDGET_OPTIONS,
        filters={
            "q": query,
            "style": style,
            "budget": budget,
            "gender": gender,
            "religion": religion,
            "accessory": accessory,
            "brand": brand,
            "color": color,
        },
    )


@bp.route("/discover")
@login_required
def discover():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect

    data = profile_data()
    query = (request.args.get("q") or "").strip().lower()
    style = (request.args.get("style") or "").strip()
    budget = (request.args.get("budget") or "").strip()
    gender = (request.args.get("gender") or "").strip()
    religion = (request.args.get("religion") or "").strip()
    garment = (request.args.get("garment") or "").strip()
    accessory = (request.args.get("accessory") or "").strip()
    brand = (request.args.get("brand") or "").strip().lower()
    color = (request.args.get("color") or "").strip().lower()

    results = []
    for raw_look in LOOKS:
        look = enrich_look(raw_look, data)
        item_terms = " ".join(
            f"{item.get('title', '')} {item.get('category', '')} {item.get('brand', '')}" for item in look["items"]
        )
        haystack = " ".join(
            [
                look["title"],
                look["tagline"],
                look.get("color", ""),
                " ".join(look["styles"]),
                " ".join(look.get("garment_tags", [])),
                " ".join(look["brands"]),
                " ".join(look.get("religions", [])),
                item_terms,
            ]
        ).lower()
        if query and query not in haystack:
            continue
        if style and style not in look["styles"]:
            continue
        if budget and budget != look["budget"]:
            continue
        if gender and not look_matches_gender_filter(look, gender):
            continue
        if religion and not look_matches_religion(look, religion):
            continue
        if garment and garment not in look.get("garment_tags", []):
            continue
        if accessory and not look_has_accessory(look, accessory):
            continue
        if brand and brand not in " ".join(look["brands"]).lower():
            continue
        if color and color != look["color"].lower():
            continue
        results.append(look)

    results.sort(
        key=lambda look: (-look["match_score"], budget_distance(data.get("budget_range", ""), look["budget"]), look["title"])
    )
    results = dedupe_looks_by_image(results)

    return render_template(
        "discover.html",
        looks=results,
        gender_options=GENDER_OPTIONS,
        religion_options=RELIGION_OPTIONS,
        garment_options=GARMENT_OPTIONS,
        accessory_options=ACCESSORY_OPTIONS,
        style_options=STYLE_OPTIONS,
        budget_options=BUDGET_OPTIONS,
        filters={
            "q": query,
            "style": style,
            "budget": budget,
            "gender": gender,
            "religion": religion,
            "garment": garment,
            "accessory": accessory,
            "brand": brand,
            "color": color,
        },
    )


@bp.get("/looks/<slug>")
@login_required
def look_detail(slug: str):
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect

    raw_look = LOOKS_BY_SLUG.get(slug)
    if not raw_look:
        abort(404)

    look = enrich_look(raw_look, profile_data())
    related = [candidate for candidate in personalized_looks() if candidate["slug"] != slug][:3]
    saved = slug in set(current_user.get_saved_looks())
    return render_template("look_detail.html", look=look, related=related, saved=saved)


@bp.post("/looks/<slug>/save")
@login_required
def save_look(slug: str):
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect

    if slug not in LOOKS_BY_SLUG:
        abort(404)

    saved = current_user.get_saved_looks()
    if slug in saved:
        saved = [item for item in saved if item != slug]
        flash("Removed from saved looks.", "info")
    else:
        saved.append(slug)
        flash("Saved to your looks.", "success")

    current_user.set_saved_looks(saved)
    db.session.commit()
    audit("looks.saved_toggle", target=f"user:{current_user.id}", meta={"slug": slug})
    return redirect(request.referrer or url_for("main.look_detail", slug=slug))


@bp.post("/cart/add")
@login_required
def cart_add():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect

    look_slug = request.form.get("look_slug", "")
    item_sku = request.form.get("item_sku", "")
    buy_all = request.form.get("buy_all") == "1"
    look = LOOKS_BY_SLUG.get(look_slug)
    if not look:
        abort(404)

    basket = cart_items()
    items_to_add = look["items"] if buy_all else [item for item in look["items"] if item["sku"] == item_sku]
    if not items_to_add:
        abort(400)

    for item in items_to_add:
        basket.append(
            {
                "id": f"{look_slug}:{item['sku']}",
                "look_slug": look_slug,
                "look_title": look["title"],
                "title": item["title"],
                "brand": item["brand"],
                "price": item["price"],
                "quantity": 1,
            }
        )

    session.modified = True
    flash("Added to cart.", "success")
    return redirect(request.referrer or url_for("main.cart"))


@bp.get("/cart")
@login_required
def cart():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect
    return render_template("cart.html", cart_items=cart_items(), cart_total=cart_total())


@bp.post("/cart/remove")
@login_required
def cart_remove():
    item_id = request.form.get("item_id", "")
    session["cart"] = [item for item in cart_items() if item.get("id") != item_id]
    session.modified = True
    flash("Removed from cart.", "info")
    return redirect(url_for("main.cart"))


@bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect

    if not cart_items():
        flash("Your cart is empty.", "error")
        return redirect(url_for("main.feed"))

    seller_stock_issue = validate_seller_cart_items()
    if seller_stock_issue:
        flash(seller_stock_issue, "error")
        return redirect(url_for("main.cart"))

    if request.method == "POST":
        shipping_name = sanitize_text(request.form.get("shipping_name", ""), 120)
        shipping_address = sanitize_text(request.form.get("shipping_address", ""), 240)
        payment_method = sanitize_text(request.form.get("payment_method", ""), 60)
        if not shipping_name or not shipping_address or not payment_method:
            flash("Fill in shipping and payment details.", "error")
            return render_template("checkout.html", cart_items=cart_items(), cart_total=cart_total()), 400

        current_user.phone = sanitize_text(request.form.get("phone", ""), 40) or current_user.phone
        order_ref = f"SB-{uuid.uuid4().hex[:8].upper()}"
        order_payload = {
            "reference": order_ref,
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "items": cart_items(),
            "total": cart_total(),
            "payment_method": payment_method,
            "shipping_name": shipping_name,
            "shipping_address": shipping_address,
        }
        append_order_to_history(order_payload)
        record_seller_orders(order_payload)
        audit("checkout.completed", target=f"user:{current_user.id}", meta={"reference": order_ref, "total": cart_total()})
        session["last_order"] = order_payload
        session["cart"] = []
        session.modified = True
        flash("Order placed successfully.", "success")
        return redirect(url_for("main.order_success"))

    return render_template("checkout.html", cart_items=cart_items(), cart_total=cart_total())


@bp.get("/order/success")
@login_required
def order_success():
    order = session.get("last_order")
    if not order:
        flash("No recent order found.", "info")
        return redirect(url_for("main.feed"))
    suggestions = personalized_looks()[:3]
    return render_template("order_success.html", order=order, suggestions=suggestions)


@bp.get("/profile")
@login_required
def profile():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect

    data = profile_data()
    saved_looks = [enrich_look(LOOKS_BY_SLUG[slug], data) for slug in current_user.get_saved_looks() if slug in LOOKS_BY_SLUG]
    saved_looks = dedupe_looks_by_image(saved_looks)
    return render_template(
        "profile.html",
        profile=profile_data(),
        profile_vector=current_user.get_profile_vector(),
        saved_looks=saved_looks,
        orders=current_user.get_order_history(),
        gender_options=GENDER_OPTIONS,
        religion_options=RELIGION_OPTIONS,
        style_options=STYLE_OPTIONS,
        budget_options=BUDGET_OPTIONS,
        body_type_options=BODY_TYPE_OPTIONS,
    )


@bp.post("/profile/preferences")
@login_required
def profile_preferences_update():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect

    data = profile_payload_from_form(current_user.get_profile_data())
    current_user.set_profile_data(data)
    current_user.set_profile_vector(profile_vector_from(data))
    db.session.commit()
    audit("profile.preferences_updated", target=f"user:{current_user.id}")
    flash("Preferences updated.", "success")
    return redirect(url_for("main.profile"))


@bp.post("/profile/reset-account")
@login_required
def profile_reset_account():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect

    current_user.onboarding_complete = False
    current_user.phone = None
    current_user.set_profile_data({})
    current_user.set_profile_vector({})
    current_user.set_saved_looks([])
    current_user.set_order_history([])
    db.session.commit()
    audit("profile.account_reset", target=f"user:{current_user.id}")

    session.pop("cart", None)
    session.pop("last_order", None)
    logout_user()
    flash("Your shopper profile was reset and you have been signed out.", "info")
    return redirect(url_for("main.home", splash=1))


@bp.get("/upload")
@login_required
def upload():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return maybe_redirect

    data = profile_data()
    selected_slug = (request.args.get("look") or "").strip()
    looks = personalized_looks()[:6]
    if not looks:
        looks = [enrich_look(raw_look, data) for raw_look in LOOKS[:6]]

    selected_look = next((look for look in looks if look.get("slug") == selected_slug), None) or looks[0]
    studio_looks = []
    for look in looks:
        studio_looks.append(
            {
                "slug": look["slug"],
                "title": look["title"],
                "tagline": look.get("tagline", ""),
                "creator": look.get("creator", ""),
                "image_url": look.get("image_url", ""),
                "styles": look.get("styles", []),
                "body_types": look.get("body_types", []),
                "color": look.get("color", ""),
                "price_total": look.get("price_total", 0),
                "match_reason": look.get("match_reason", ""),
                "shop_url": url_for("main.look_detail", slug=look["slug"]),
                "try_on": look_tryon_payload(look),
            }
        )

    return render_template(
        "upload.html",
        studio_looks=studio_looks,
        selected_look_slug=selected_look["slug"],
        latest_selfie_url=data.get("latest_selfie_url", ""),
        latest_selfie_name=data.get("latest_selfie_name", ""),
        latest_style_scan=data.get("latest_style_scan", {}) if isinstance(data.get("latest_style_scan", {}), dict) else {},
        latest_style_suggestions=data.get("latest_style_suggestions", []) if isinstance(data.get("latest_style_suggestions", []), list) else [],
    )


@bp.post("/upload")
@login_required
@limiter.limit("10 per hour")
def upload_post():
    maybe_redirect = ensure_onboarding()
    if maybe_redirect:
        return jsonify({"ok": False, "error": "Complete onboarding first."}), 403

    file = request.files.get("selfie")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Missing file"}), 400
    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "File type not allowed"}), 400

    try:
        url = save_uploaded_file(file, f"user-{current_user.get_id()}", subdirectory="selfies")
    except UploadStorageError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    raw_scan_context = request.form.get("scan_context", "")
    try:
        parsed_scan_context = json.loads(raw_scan_context) if raw_scan_context else {}
    except (TypeError, ValueError):
        parsed_scan_context = {}

    scan_context = normalized_scan_context(parsed_scan_context)
    scan_report = build_style_scan_report(scan_context)
    suggestions = build_tryon_style_suggestions(scan_context, limit=3)

    data = profile_data()
    data["latest_selfie_url"] = url
    data["latest_selfie_name"] = sanitize_text(file.filename, 120)
    data["latest_style_scan"] = scan_report
    data["latest_style_suggestions"] = suggestions
    current_user.set_profile_data(data)
    current_user.set_profile_vector(profile_vector_from(data))
    db.session.commit()
    audit("tryon.selfie_uploaded", target=f"user:{current_user.id}", meta={"url": url})
    return jsonify(
        {
            "ok": True,
            "url": url,
            "filename": data["latest_selfie_name"],
            "scan": scan_report,
            "suggestions": suggestions,
        }
    )


@bp.route("/admin/grant", methods=["GET", "POST"])
@limiter.limit("5 per hour")
@login_required
def admin_grant():
    if request.method == "POST":
        supplied = (request.form.get("admin_key") or "").strip()
        expected = (current_app.config.get("ADMIN_KEY") or "").strip()
        if not expected:
            flash("ADMIN_KEY is not set in .env", "error")
            return redirect(url_for("main.admin_grant"))
        if not supplied or not secrets.compare_digest(supplied, expected):
            flash("Bad admin key.", "error")
            return redirect(url_for("main.admin_grant"))

        u = db.session.get(User, int(current_user.get_id()))
        u.is_admin = True
        assign_role(u, "superadmin")
        db.session.commit()
        audit("admin.grant_superadmin", target=f"user:{u.id}")
        flash("Admin enabled for this account.", "success")
        return redirect(url_for("main.admin_inventory_upload"))

    return render_template("admin/grant.html")


@bp.route("/admin/inventory/upload", methods=["GET", "POST"])
@limiter.limit("5 per hour")
@login_required
def admin_inventory_upload():
    require_permission("inventory:write")(lambda: None)()

    if request.method == "POST":
        fmt = (request.form.get("format") or "csv").strip().lower()
        saved = 0

        if fmt == "csv":
            f = request.files.get("file")
            if not f or not f.filename:
                flash("Pick a CSV file.", "error")
                return redirect(url_for("main.admin_inventory_upload"))
            if not f.filename.lower().endswith(".csv"):
                flash("Only CSV files are allowed.", "error")
                return redirect(url_for("main.admin_inventory_upload"))

            raw = f.read()
            text_data = raw.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text_data))

            for row in reader:
                title = sanitize_text((row.get("title") or "").strip(), MAX_TITLE_LENGTH)
                if not title:
                    continue
                try:
                    price = float((row.get("price") or "0").strip())
                    if price < 0 or price > 999999:
                        price = 0.0
                except (ValueError, TypeError):
                    price = 0.0
                image_url = sanitize_url((row.get("image_url") or row.get("image") or "").strip(), MAX_URL_LENGTH)
                item = Item(
                    external_id=f"upload:{uuid.uuid4().hex}",
                    title=title,
                    price=price,
                    image_url=image_url if image_url else None,
                )
                db.session.add(item)
                saved += 1

        elif fmt == "json":
            raw = (request.form.get("json_text") or "").strip()
            if not raw:
                flash("Paste JSON.", "error")
                return redirect(url_for("main.admin_inventory_upload"))
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError) as exc:
                flash(f"Invalid JSON: {str(exc)[:50]}", "error")
                return redirect(url_for("main.admin_inventory_upload"))
            if not isinstance(data, list):
                flash("JSON must be a list of items.", "error")
                return redirect(url_for("main.admin_inventory_upload"))

            for entry in data:
                if not isinstance(entry, dict):
                    continue
                title = sanitize_text((entry.get("title") or "").strip(), MAX_TITLE_LENGTH)
                if not title:
                    continue
                try:
                    price = float(entry.get("price") or 0)
                    if price < 0 or price > 999999:
                        price = 0.0
                except (ValueError, TypeError):
                    price = 0.0
                image_url = sanitize_url((entry.get("image_url") or "").strip(), MAX_URL_LENGTH)
                db.session.add(
                    Item(
                        external_id=f"upload:{uuid.uuid4().hex}",
                        title=title,
                        price=price,
                        image_url=image_url if image_url else None,
                    )
                )
                saved += 1
        else:
            flash("Unknown format.", "error")
            return redirect(url_for("main.admin_inventory_upload"))

        db.session.commit()
        audit("inventory.upload", meta={"format": fmt, "count": saved})
        flash(f"Uploaded {saved} items.", "success")
        return redirect(url_for("main.admin_inventory_upload"))

    count = Item.query.count()
    return render_template("admin/inventory_upload.html", item_count=count)


@bp.route("/admin/users", methods=["GET"])
@login_required
def admin_users():
    require_permission("users:write")(lambda: None)()
    users = User.query.order_by(User.id.asc()).all()
    return render_template("admin/users.html", users=users)


@bp.route("/admin/users/<int:user_id>/roles", methods=["POST"])
@login_required
def admin_user_roles_update(user_id: int):
    require_permission("users:write")(lambda: None)()
    u = db.session.get(User, user_id)
    if not u:
        abort(404)
    role = (request.form.get("role") or "").strip().lower()
    if not role:
        abort(400)
    assign_role(u, role)
    if role in {"admin", "superadmin"}:
        u.is_admin = True
    db.session.commit()
    audit("users.assign_role", target=f"user:{u.id}", meta={"role": role})
    flash(f"Role '{role}' granted to {u.email}", "success")
    return redirect(url_for("main.admin_users"))


@bp.get("/health")
def health():
    return Response("ok", status=200, mimetype="text/plain")
