"""Validate the static GitHub Pages landing page without third-party dependencies."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
INDEX = SITE / "index.html"


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.resources: list[str] = []
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if identifier := values.get("id"):
            self.ids.append(identifier)
        if href := values.get("href"):
            self.hrefs.append(href)
            if tag == "link" and values.get("rel") in {"stylesheet", "icon", "manifest"}:
                self.resources.append(href)
        if src := values.get("src"):
            self.resources.append(src)
        if tag == "meta":
            key = values.get("name") or values.get("property")
            content = values.get("content")
            if key and content:
                self.meta[key] = content
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)


def local_target(raw: str) -> Path | None:
    parsed = urlparse(raw)
    if parsed.scheme or parsed.netloc or raw.startswith("#"):
        return None
    path = parsed.path
    if not path or path == "./":
        return INDEX
    if path.startswith("/"):
        return None
    return (SITE / path).resolve(strict=False)


def main() -> int:
    required = {
        "index.html",
        "styles.css",
        "app.js",
        "favicon.svg",
        "site.webmanifest",
        "robots.txt",
        "sitemap.xml",
        "404.html",
        ".nojekyll",
    }
    missing = sorted(name for name in required if not (SITE / name).exists())
    if missing:
        raise SystemExit(f"missing site files: {', '.join(missing)}")

    parser = SiteParser()
    parser.feed(INDEX.read_text(encoding="utf-8"))

    if len(parser.ids) != len(set(parser.ids)):
        raise SystemExit("index.html contains duplicate element IDs")
    ids = set(parser.ids)
    for href in parser.hrefs:
        if href.startswith("#") and href != "#" and href[1:] not in ids:
            raise SystemExit(f"broken internal anchor: {href}")

    for raw in parser.resources:
        parsed = urlparse(raw)
        if parsed.scheme or parsed.netloc:
            raise SystemExit(f"external runtime resource is not allowed: {raw}")
        target = local_target(raw)
        if target is not None and not target.is_file():
            raise SystemExit(f"missing local runtime resource: {raw}")

    title = "".join(parser.title_parts).strip()
    if not title or "Affiliate-Mate" not in title:
        raise SystemExit("page title must identify Affiliate-Mate")
    for field in ("description", "viewport", "theme-color", "og:title", "og:description"):
        if field not in parser.meta:
            raise SystemExit(f"required metadata missing: {field}")

    manifest = json.loads((SITE / "site.webmanifest").read_text(encoding="utf-8"))
    if manifest.get("name") != "Affiliate-Mate":
        raise SystemExit("web manifest has unexpected application name")

    ET.parse(SITE / "sitemap.xml")

    css_size = (SITE / "styles.css").stat().st_size
    js_size = (SITE / "app.js").stat().st_size
    if css_size > 80_000 or js_size > 20_000:
        raise SystemExit("static asset budget exceeded")

    print(
        "site validation passed: "
        f"{len(parser.ids)} ids, {len(parser.hrefs)} links, "
        f"css={css_size}B, js={js_size}B"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
