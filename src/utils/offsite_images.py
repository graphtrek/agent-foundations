"""Fetch real example images for the corporate offsite planner demo.

Images are downloaded from Wikimedia Commons (freely licensed, no API key) and
cached under ``resources/offsite``. Two "good" and two "bad" options are
provided for both venues and catering, so a vision model can recommend a best
option and a genuine alternative while rejecting the poor ones.

Each entry lists fallback search queries; the first query that yields a usable
bitmap wins. Downloaded images are normalised to a ~640px-wide RGB JPEG.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image  # type: ignore

IMAGE_DIR = Path(__file__).resolve().parent.parent / "resources" / "offsite"

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "agent-foundations-offsite-demo/1.0 (educational example)"
TARGET_WIDTH = 640
REQUEST_DELAY = 1.5  # polite spacing between Wikimedia requests (seconds)

# Ordered fallback search queries per image slot.
QUERIES: dict[str, list[str]] = {
    "venue_good_1.jpg": [
        "elegant banquet hall wedding reception",
        "elegant hotel ballroom event decorated",
    ],
    "venue_good_2.jpg": [
        "elegant ballroom wedding table setting decoration",
        "luxury hotel ballroom banquet",
    ],
    "venue_bad_1.jpg": [
        "abandoned ballroom",
        "abandoned hotel interior",
    ],
    "venue_bad_2.jpg": [
        "abandoned hotel interior",
        "derelict interior hall",
    ],
    "meal_good_1.jpg": [
        "gourmet plated fine dining dish",
        "gourmet plated restaurant food",
    ],
    "meal_good_2.jpg": [
        "gourmet plated steak restaurant",
        "fine dining plated seafood dish",
    ],
    "meal_bad_1.jpg": [
        "airline meal tray",
        "hospital food tray",
    ],
    "meal_bad_2.jpg": [
        "burnt overcooked food",
        "rotten spoiled food",
    ],
}


def _search_thumb_urls(query: str, limit: int = 6) -> list[str]:
    """Return candidate thumbnail URLs for a Commons bitmap search."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "iiurlwidth": str(TARGET_WIDTH),
    }
    url = f"{COMMONS_API}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    time.sleep(REQUEST_DELAY)
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)

    pages = data.get("query", {}).get("pages", {})
    # Preserve search rank order rather than the dict's arbitrary key order.
    ranked = sorted(pages.values(), key=lambda p: p.get("index", 0))
    urls: list[str] = []
    for page in ranked:
        info = (page.get("imageinfo") or [{}])[0]
        if not str(info.get("mime", "")).startswith("image/"):
            continue
        thumb = info.get("thumburl")
        original = info.get("url")
        # Prefer the rendered thumbnail, but fall back to the CDN-cached
        # original when thumbnail rendering is rate limited.
        if thumb:
            urls.append(thumb)
        if original and original != thumb:
            urls.append(original)
    return urls


def _download_jpeg(thumb_url: str, dest: Path) -> bool:
    """Download an image and save it as a normalised RGB JPEG. Return success."""
    request = urllib.request.Request(thumb_url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            time.sleep(REQUEST_DELAY)
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
            with Image.open(BytesIO(raw)) as image:
                image = image.convert("RGB")
                if image.width > TARGET_WIDTH:
                    ratio = TARGET_WIDTH / image.width
                    image = image.resize((TARGET_WIDTH, int(image.height * ratio)))
                image.save(dest, format="JPEG", quality=88)
            return True
        except urllib.error.HTTPError as error:
            if error.code == 429 and attempt < 3:  # rate limited -> back off
                time.sleep(2 ** attempt * 2)
                continue
            print(f"  skip {thumb_url[:70]}...: {error}")
            return False
        except Exception as error:  # unreadable image -> try next candidate
            print(f"  skip {thumb_url[:70]}...: {error}")
            return False
    return False


def _fetch_slot(name: str, queries: list[str], dest: Path) -> bool:
    for query in queries:
        try:
            candidates = _search_thumb_urls(query)
        except Exception as error:
            print(f"  search failed for '{query}': {error}")
            continue
        for thumb_url in candidates:
            if _download_jpeg(thumb_url, dest):
                print(f"  {name} <- '{query}'")
                return True
    return False


def generate_images(force: bool = False) -> dict[str, Path]:
    """Download the example images (if missing) and return a name -> path map."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, queries in QUERIES.items():
        path = IMAGE_DIR / name
        if force or not path.exists():
            if not _fetch_slot(name, queries, path):
                raise RuntimeError(f"Could not fetch an image for {name}")
        paths[name] = path
    return paths


if __name__ == "__main__":
    for name, path in generate_images(force=True).items():
        print(f"Ready {name} -> {path}")
