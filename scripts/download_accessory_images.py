from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.routes.main import accessory_catalog, shoe_style_key


OUTPUT_DIR = PROJECT_ROOT / "app" / "static" / "img" / "accessories"
SOURCE_PATHS = {
    "Shoes": OUTPUT_DIR / "shoe_sources.json",
    "Glasses": OUTPUT_DIR / "glasses_sources.json",
}
TARGET_TYPES = set(SOURCE_PATHS)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"
)
OPENVERSE_API = "https://api.openverse.org/v1/images/"
MIN_IMAGE_BYTES = 8_000
PROFILE = {
    "gender": "Womenswear",
    "religion": "Islam",
    "style_preference": "Minimalist",
    "budget_range": "Mid-range",
    "favorite_styles": ["Minimalist", "Casual", "Streetwear", "Formal"],
    "body_type": "Straight",
    "favorite_brands": ["COS", "Mango", "Charles & Keith", "JW Pei", "Nike", "Bata", "Dune London", "Quay"],
}
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png"}
BAD_SOURCE_TITLE_TERMS = {
    "clipart",
    "drawing",
    "illustration",
    "icon",
    "logo",
    "mockup",
    "png sticker",
    "sticker",
    "svg",
    "template",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def iter_accessories(categories: set[str]) -> list[dict]:
    seen_skus: set[str] = set()
    accessories: list[dict] = []
    for item in accessory_catalog(PROFILE):
        accessory_type = item.get("accessory_type")
        sku = item.get("sku", "")
        if accessory_type not in categories or not sku or sku in seen_skus:
            continue
        seen_skus.add(sku)
        accessories.append(item)
    return accessories


def add_query(queries: list[str], raw_query: str) -> None:
    cleaned = " ".join(part for part in raw_query.split() if part).strip()
    if cleaned and cleaned not in queries:
        queries.append(cleaned)


def shoe_search_queries(item: dict) -> list[str]:
    title = (item.get("title") or "").lower()
    queries: list[str] = []
    style = shoe_style_key(title)

    if style == "trainer":
        add_query(queries, "fashion sneaker")
        add_query(queries, "lifestyle sneaker product photo")
    elif style == "boot":
        add_query(queries, "fashion boot")
        add_query(queries, "leather boot product photo")
    elif style == "sandal":
        add_query(queries, "fashion sandal")
        add_query(queries, "leather sandal product photo")
    elif style == "loafer":
        add_query(queries, "loafer shoe fashion")
        add_query(queries, "loafer product photo")
    elif style == "derby":
        add_query(queries, "derby shoe fashion")
        add_query(queries, "leather derby shoe")
    elif style == "heel":
        add_query(queries, "high heel shoe fashion")
        add_query(queries, "dress heel product photo")

    add_query(queries, "fashion shoe")
    add_query(queries, "shoe product photo")
    return queries


def glasses_search_queries(item: dict) -> list[str]:
    title = (item.get("title") or "").lower()
    queries: list[str] = []

    if "sport" in title:
        add_query(queries, "sport sunglasses")
    if any(term in title for term in ("round", "soft round")):
        add_query(queries, "round sunglasses")
    if any(term in title for term in ("slim", "rectangular", "rectangle", "angular")):
        add_query(queries, "rectangular sunglasses")
    if "tinted" in title:
        add_query(queries, "tinted sunglasses")
    if "black" in title:
        add_query(queries, "black sunglasses")

    add_query(queries, "fashion sunglasses")
    add_query(queries, "sunglasses product photo")
    add_query(queries, "eyewear fashion")
    return queries


def search_queries(item: dict) -> list[str]:
    accessory_type = item.get("accessory_type")
    if accessory_type == "Shoes":
        return shoe_search_queries(item)
    if accessory_type == "Glasses":
        return glasses_search_queries(item)
    return []


def request_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def openverse_candidates(search_query: str, limit: int) -> list[dict]:
    params = {
        "q": search_query,
        "page_size": str(limit),
        "mature": "false",
        "license_type": "commercial",
        "filter_dead": "true",
    }
    payload = request_json(f"{OPENVERSE_API}?{urlencode(params)}")
    return payload.get("results", [])


def download_bytes(url: str) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=45) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        payload = response.read()
    return payload, content_type


def detect_extension(payload: bytes, source_url: str, content_type: str) -> str:
    if payload.startswith(b"\xff\xd8\xff") or "jpeg" in content_type or source_url.lower().endswith((".jpg", ".jpeg")):
        return ".jpg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n") or "png" in content_type or source_url.lower().endswith(".png"):
        return ".png"
    return ""


def remove_existing_targets(sku: str) -> None:
    for extension in (".jpg", ".jpeg", ".png", ".webp"):
        existing = OUTPUT_DIR / f"{sku}{extension}"
        if existing.exists():
            existing.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download unique Openverse shoe and glasses photos for accessory cards.")
    parser.add_argument(
        "--categories",
        nargs="+",
        default=sorted(TARGET_TYPES),
        choices=sorted(TARGET_TYPES),
        help="Accessory categories to refresh.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Search results to inspect per query.")
    parser.add_argument("--pause-ms", type=int, default=500, help="Delay between network requests.")
    parser.add_argument("--skus", nargs="*", default=[], help="Optional subset of accessory SKUs to refresh.")
    return parser.parse_args()


def load_existing_sources(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def existing_hashes(excluded_skus: set[str]) -> set[str]:
    hashes: set[str] = set()
    for path in OUTPUT_DIR.iterdir():
        if path.suffix.lower() not in VALID_EXTENSIONS or path.stem in excluded_skus:
            continue
        hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
    return hashes


def skip_source_title(source_title: str) -> bool:
    lowered = source_title.lower()
    return any(term in lowered for term in BAD_SOURCE_TITLE_TERMS)


def main() -> int:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    categories = set(args.categories)
    requested_skus = {sku for sku in args.skus if sku}
    accessories = [
        item for item in iter_accessories(categories) if not requested_skus or item.get("sku", "") in requested_skus
    ]
    sources_by_type: dict[str, dict[str, dict]] = {}
    for accessory_type in categories:
        path = SOURCE_PATHS[accessory_type]
        sources_by_type[accessory_type] = load_existing_sources(path) if requested_skus else {}

    failures: list[str] = []
    used_hashes: set[str] = existing_hashes(requested_skus) if requested_skus else set()
    used_source_ids: set[str] = set()
    for source_map in sources_by_type.values():
        for metadata in source_map.values():
            source_id = metadata.get("source_id")
            if source_id:
                used_source_ids.add(source_id)

    for item in accessories:
        sku = item["sku"]
        accessory_type = item["accessory_type"]
        success = False

        for search_query in search_queries(item):
            try:
                candidates = openverse_candidates(search_query, args.limit)
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"[warn] {sku}: search failed for {search_query!r} ({exc})")
                time.sleep(args.pause_ms / 1000)
                continue

            for candidate in candidates:
                source_title = (candidate.get("title") or "").strip() or f"Openverse image {candidate.get('id', '')}".strip()
                if skip_source_title(source_title):
                    continue

                source_id = f"{candidate.get('source', 'openverse')}:{candidate.get('id', source_title)}"
                if source_id in used_source_ids:
                    continue

                source_url = candidate.get("url") or candidate.get("thumbnail") or ""
                if not source_url:
                    continue

                description_url = candidate.get("foreign_landing_url") or candidate.get("detail_url") or ""
                download_urls = [url for url in [candidate.get("thumbnail"), candidate.get("url")] if url]

                payload = b""
                content_type = ""
                downloaded_from = ""
                for download_url in download_urls:
                    try:
                        payload, content_type = download_bytes(download_url)
                        downloaded_from = download_url
                        break
                    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                        print(f"[warn] {sku}: download failed for {source_title!r} ({exc})")
                        time.sleep(args.pause_ms / 1000)

                if not payload or len(payload) < MIN_IMAGE_BYTES:
                    continue

                extension = detect_extension(payload, downloaded_from or source_url, content_type)
                if extension not in VALID_EXTENSIONS:
                    continue

                payload_hash = hashlib.sha256(payload).hexdigest()
                if payload_hash in used_hashes:
                    continue

                remove_existing_targets(sku)
                target_path = OUTPUT_DIR / f"{sku}{extension}"
                target_path.write_bytes(payload)
                used_hashes.add(payload_hash)
                used_source_ids.add(source_id)
                sources_by_type[accessory_type][sku] = {
                    "title": item.get("title", ""),
                    "brand": item.get("brand", ""),
                    "look_title": item.get("look_title", ""),
                    "accessory_type": accessory_type,
                    "search_query": search_query,
                    "source_title": source_title,
                    "source_url": source_url,
                    "thumbnail_url": candidate.get("thumbnail") or "",
                    "description_url": description_url,
                    "creator": candidate.get("creator") or "",
                    "license": candidate.get("license") or "",
                    "license_version": candidate.get("license_version") or "",
                    "source": candidate.get("source") or "openverse",
                    "source_id": source_id,
                    "expected_file": str(target_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                }
                print(f"[ ok ] {sku}: saved {target_path.name} from {source_title}")
                success = True
                break

            if success:
                break

            time.sleep(args.pause_ms / 1000)

        if not success:
            print(f"[fail] {sku}: no unique Openverse image found")
            failures.append(sku)

    for accessory_type, source_map in sources_by_type.items():
        path = SOURCE_PATHS[accessory_type]
        path.write_text(json.dumps(source_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"[done] accessories={len(accessories)} saved={sum(len(source_map) for source_map in sources_by_type.values())} failures={len(failures)}")
    if failures:
        print("[fail] " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
