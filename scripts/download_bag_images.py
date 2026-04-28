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

from app.routes.main import accessory_catalog


OUTPUT_DIR = PROJECT_ROOT / "app" / "static" / "img" / "accessories"
SOURCES_PATH = OUTPUT_DIR / "bag_sources.json"
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
    "favorite_brands": ["COS", "Mango", "Charles & Keith", "JW Pei", "Nike"],
}
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png"}
BAD_SOURCE_TITLE_TERMS = {"clipart", "illustration", "png sticker", "sticker", "in progress"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def iter_bags() -> list[dict]:
    seen_skus: set[str] = set()
    bags: list[dict] = []
    for item in accessory_catalog(PROFILE):
        sku = item.get("sku", "")
        if item.get("accessory_type") != "Bags" or not sku or sku in seen_skus:
            continue
        seen_skus.add(sku)
        bags.append(item)
    return bags


def add_query(queries: list[str], raw_query: str) -> None:
    cleaned = " ".join(part for part in raw_query.split() if part).strip()
    if cleaned and cleaned not in queries:
        queries.append(cleaned)


def bag_search_queries(item: dict) -> list[str]:
    title = (item.get("title") or "").lower()
    queries: list[str] = []

    if "backpack" in title or "pack" in title:
        add_query(queries, "fashion backpack")
    if "clutch" in title:
        add_query(queries, "clutch bag")
    if any(term in title for term in ("crossbody", "sling", "satchel")):
        add_query(queries, "crossbody bag")
    if any(term in title for term in ("tote", "shopper", "weekender", "shoulder", "market", "commuter")):
        add_query(queries, "tote bag")
    if any(term in title for term in ("pouch", "document", "zip")):
        add_query(queries, "leather pouch bag")
    if any(term in title for term in ("mini", "top-handle", "handle", "handbag")):
        add_query(queries, "handbag")

    add_query(queries, "fashion handbag")
    add_query(queries, "purse bag")
    return queries


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
    for extension in VALID_EXTENSIONS:
        existing = OUTPUT_DIR / f"{sku}{extension}"
        if existing.exists():
            existing.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download unique Openverse bag photos for accessory cards.")
    parser.add_argument("--limit", type=int, default=20, help="Search results to inspect per query.")
    parser.add_argument("--pause-ms", type=int, default=500, help="Delay between network requests.")
    parser.add_argument("--skus", nargs="*", default=[], help="Optional subset of bag SKUs to refresh.")
    return parser.parse_args()


def load_existing_sources() -> dict[str, dict]:
    if not SOURCES_PATH.exists():
        return {}
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))


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

    requested_skus = {sku for sku in args.skus if sku}
    bags = [item for item in iter_bags() if not requested_skus or item["sku"] in requested_skus]
    sources: dict[str, dict] = load_existing_sources() if requested_skus else {}
    failures: list[str] = []
    used_hashes: set[str] = existing_hashes(requested_skus) if requested_skus else set()
    used_source_titles: set[str] = set()

    for item in bags:
        sku = item["sku"]
        success = False

        for search_query in bag_search_queries(item):
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
                description_url = candidate.get("foreign_landing_url") or candidate.get("detail_url") or ""
                source_url = candidate.get("url") or candidate.get("thumbnail") or ""
                source_id = f"{candidate.get('source', 'openverse')}:{candidate.get('id', source_title)}"
                download_urls = [url for url in [candidate.get("thumbnail"), candidate.get("url")] if url]
                if not source_url or source_id in used_source_titles:
                    continue

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
                if not payload:
                    continue

                if len(payload) < MIN_IMAGE_BYTES:
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
                used_source_titles.add(source_id)
                sources[sku] = {
                    "title": item.get("title", ""),
                    "brand": item.get("brand", ""),
                    "look_title": item.get("look_title", ""),
                    "search_query": search_query,
                    "source_title": source_title,
                    "source_url": source_url,
                    "thumbnail_url": candidate.get("thumbnail") or "",
                    "description_url": description_url,
                    "creator": candidate.get("creator") or "",
                    "license": candidate.get("license") or "",
                    "license_version": candidate.get("license_version") or "",
                    "source": candidate.get("source") or "openverse",
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

    SOURCES_PATH.write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[done] bags={len(bags)} saved={len(sources)} failures={len(failures)}")
    if failures:
        print("[fail] " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
