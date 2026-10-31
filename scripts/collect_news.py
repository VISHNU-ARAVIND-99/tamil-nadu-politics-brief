#!/usr/bin/env python3
"""
Step 2 & Step 3 of Pipeline:
- Reads configurable data/sources.json
- Respects robots.txt before fetching RSS/Atom feeds
- Parses publication timestamps and normalizes to IST (Asia/Kolkata)
- Filters items strictly to the 12-hour edition coverage window
- Sanitizes text and stores only permitted metadata + brief summary snippet
"""

import email.utils
import json
import sys
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

try:
    import feedparser
except ImportError:
    feedparser = None

from scripts.config import (
    HTTP_TIMEOUT_SECONDS,
    IST,
    SOURCES_FILE,
    USER_AGENT,
    sanitize_untrusted_text,
)


def is_allowed_by_robots(url: str) -> bool:
    """Verify robots.txt compliance before making a request."""
    try:
        parsed = urllib.parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            rp.parse(raw.splitlines())
            return rp.can_fetch(USER_AGENT, url)
    except Exception:
        # Standard web convention: if robots.txt is unreachable or times out, allow public RSS feed
        return True


def parse_pub_date_to_ist(date_str: str | None) -> datetime | None:
    """Parse RFC-2822 or ISO-8601 date strings and normalize to IST."""
    if not date_str:
        return None
    date_str = date_str.strip()
    # Try RFC 2822 (standard RSS pubDate)
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST)
    except Exception:
        pass

    # Try ISO 8601 (Atom / modern feeds)
    try:
        iso_clean = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except Exception:
        return None


def parse_rss_xml_fallback(xml_bytes: bytes) -> list[dict]:
    """Built-in ElementTree RSS/Atom parser fallback if feedparser is unavailable."""
    entries = []
    root = ET.fromstring(xml_bytes)
    # Standard RSS 2.0 <item>
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        desc = item.findtext("description") or ""
        pub_date = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
        entries.append({"title": title, "link": link, "summary": desc, "published": pub_date})
    # Atom <entry>
    if not entries:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", ns):
            title = entry.findtext("atom:title", default="", namespaces=ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.attrib.get("href", "") if link_el is not None else ""
            desc = entry.findtext("atom:summary", default="", namespaces=ns)
            pub_date = entry.findtext("atom:updated", default="", namespaces=ns) or entry.findtext(
                "atom:published", default="", namespaces=ns
            )
            entries.append({"title": title, "link": link, "summary": desc, "published": pub_date})
    return entries


def fetch_feed_items(source: dict, window_start: datetime, window_end: datetime) -> list[dict]:
    """Fetch and time-filter items from a single RSS source."""
    feed_url = source.get("feed_url", "")
    if not feed_url or not source.get("enabled", True):
        return []

    if not is_allowed_by_robots(feed_url):
        print(f"[SKIP] Disallowed by robots.txt: {source['name']}")
        return []

    req = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
            raw_bytes = response.read()
    except Exception as exc:
        print(f"[WARN] Failed to fetch {source['name']} ({feed_url}): {exc}")
        return []

    raw_entries = []
    if feedparser is not None:
        parsed = feedparser.parse(raw_bytes)
        for entry in parsed.entries:
            raw_entries.append(
                {
                    "title": getattr(entry, "title", ""),
                    "link": getattr(entry, "link", ""),
                    "summary": getattr(entry, "summary", getattr(entry, "description", "")),
                    "published": getattr(entry, "published", getattr(entry, "updated", "")),
                }
            )
    else:
        try:
            raw_entries = parse_rss_xml_fallback(raw_bytes)
        except Exception as exc:
            print(f"[WARN] XML parse error for {source['name']}: {exc}")
            return []

    collected = []
    for item in raw_entries:
        pub_dt = parse_pub_date_to_ist(item.get("published"))
        if pub_dt is None:
            continue

        # Strict 12-hour coverage window filter
        if not (window_start <= pub_dt <= window_end):
            continue

        clean_title = sanitize_untrusted_text(item.get("title", ""), max_length=220)
        clean_snippet = sanitize_untrusted_text(item.get("summary", ""), max_length=550)
        link = (item.get("link") or "").strip()

        if not clean_title or not link.startswith(("http://", "https://")):
            continue

        collected.append(
            {
                "source_id": source["id"],
                "publisher": source["name"],
                "language": source.get("language", "en"),
                "category": source.get("category", "news"),
                "reliability_tier": source.get("reliability_tier", "tier_1_editorial"),
                "title": clean_title,
                "snippet": clean_snippet,
                "url": link,
                "published_at_ist": pub_dt.isoformat(),
                "published_date": pub_dt.strftime("%Y-%m-%d"),
            }
        )

    return collected


def collect_all_sources(window_start: datetime, window_end: datetime, sources_path=SOURCES_FILE) -> dict:
    """Iterate through all enabled sources in data/sources.json and collect time-filtered items."""
    with open(sources_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    sources = registry.get("sources", [])
    all_items = []
    sources_checked = 0

    for src in sources:
        if not src.get("enabled", True):
            continue
        sources_checked += 1
        items = fetch_feed_items(src, window_start, window_end)
        all_items.extend(items)

    return {
        "sources_checked": sources_checked,
        "raw_count": len(all_items),
        "items": all_items,
    }
