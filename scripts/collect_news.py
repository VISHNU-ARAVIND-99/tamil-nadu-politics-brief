#!/usr/bin/env python3
"""
Step 2 & Step 3 of Pipeline:
- Extracts real newspaper publisher names from Google News RSS items
  (never shows internal 'TN Secretariat & Policy Wire' labels)
- Strips Google News secondary headline bundles (&nbsp; Publisher)
- Uses only clean <meta name="description"> for article enrichment (never scrapes sidebar headlines)
"""

import email.utils
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

try:
    import feedparser
except ImportError:
    feedparser = None

from scripts.config import (
    HTTP_TIMEOUT_SECONDS,
    IST,
    SOURCES_FILE,
    USER_AGENT,
    has_tamil_script,
    sanitize_untrusted_text,
    translate_tamil_to_english,
)

GENERIC_BULLETIN_PATTERNS = [
    re.compile(r"today\s+headlines", re.IGNORECASE),
    re.compile(r"தலைப்புச்\s*செய்திகள்", re.IGNORECASE),
    re.compile(r"விரைவுச்\s*செய்திகள்", re.IGNORECASE),
    re.compile(r"speed\s+news", re.IGNORECASE),
    re.compile(r"equity\s+trading\s+insights", re.IGNORECASE),
    re.compile(r"tvk:ca", re.IGNORECASE),
]


def parse_pub_date_to_ist(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    date_str = date_str.strip()
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST)
    except Exception:
        pass

    try:
        iso_clean = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except Exception:
        return None


def parse_rss_xml_fallback(xml_bytes: bytes) -> list[dict]:
    entries = []
    root = ET.fromstring(xml_bytes)
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        desc = item.findtext("description") or ""
        pub_date = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
        src_el = item.find("source")
        src_title = src_el.text.strip() if (src_el is not None and src_el.text) else ""
        entries.append({
            "title": title,
            "link": link,
            "summary": desc,
            "published": pub_date,
            "source_title": src_title,
        })
    return entries


def fetch_article_meta_description(url: str) -> str:
    """
    Safely fetch ONLY the official <meta property="og:description"> or <meta name="description">
    from direct newspaper URLs. Never scrapes random <p> tags from sidebars.
    """
    if not url or "news.google.com" in url:
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw_html = resp.read(45000).decode("utf-8", errors="ignore")
        meta_match = re.search(
            r'<meta[^>]+(?:property=["\']og:description["\']|name=["\']description["\'])[^>]+content=["\']([^"\']+)["\']',
            raw_html,
            re.IGNORECASE,
        )
        if not meta_match:
            meta_match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property=["\']og:description["\']|name=["\']description["\'])',
                raw_html,
                re.IGNORECASE,
            )
        desc = html.unescape(meta_match.group(1)) if meta_match else ""
        return sanitize_untrusted_text(desc, max_length=550)
    except Exception:
        return ""


def fetch_feed_items(source: dict, window_start: datetime, window_end: datetime) -> list[dict]:
    feed_url = source.get("feed_url", "")
    if not feed_url or not source.get("enabled", True):
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
        print(f"[WARN] Failed to fetch {source['name']}: {exc}")
        return []

    raw_entries = []
    if feedparser is not None:
        parsed = feedparser.parse(raw_bytes)
        for entry in parsed.entries:
            src_obj = getattr(entry, "source", None)
            src_title = ""
            if isinstance(src_obj, dict):
                src_title = src_obj.get("title", "")
            elif hasattr(src_obj, "title"):
                src_title = getattr(src_obj, "title", "")
            raw_entries.append(
                {
                    "title": getattr(entry, "title", ""),
                    "link": getattr(entry, "link", ""),
                    "summary": getattr(entry, "summary", getattr(entry, "description", "")),
                    "published": getattr(entry, "published", getattr(entry, "updated", "")),
                    "source_title": src_title,
                }
            )
    else:
        try:
            raw_entries = parse_rss_xml_fallback(raw_bytes)
        except Exception:
            return []

    collected = []
    for item in raw_entries:
        pub_dt = parse_pub_date_to_ist(item.get("published"))
        if pub_dt is None or not (window_start <= pub_dt <= window_end):
            continue

        raw_title = html.unescape(item.get("title", "")).strip()
        if any(pat.search(raw_title) for pat in GENERIC_BULLETIN_PATTERNS):
            continue

        # Extract real publisher name from <source> tag or trailing " - Publisher"
        real_publisher = (item.get("source_title") or "").strip()
        if " - " in raw_title and ("news.google.com" in feed_url or real_publisher):
            title_part, trailing_pub = raw_title.rsplit(" - ", 1)
            raw_title = title_part.strip()
            if not real_publisher and len(trailing_pub.strip()) < 40:
                real_publisher = trailing_pub.strip()

        publisher_name = real_publisher or source["name"]

        clean_title = sanitize_untrusted_text(raw_title, max_length=220)
        raw_summary = item.get("summary", "")

        # Google News RSS descriptions just repeat the title + related links; ignore if it's a Google News feed
        if "news.google.com" in feed_url:
            clean_snippet = ""
        else:
            clean_snippet = sanitize_untrusted_text(raw_summary, max_length=600)

        link = (item.get("link") or "").strip()
        if not clean_title or not link.startswith(("http://", "https://")):
            continue

        if len(clean_snippet) < 80 or clean_snippet.lower().startswith(clean_title[:35].lower()):
            extra = fetch_article_meta_description(link)
            if len(extra) > len(clean_snippet):
                clean_snippet = extra

        if has_tamil_script(clean_title):
            clean_title = translate_tamil_to_english(clean_title)
        if has_tamil_script(clean_snippet):
            clean_snippet = translate_tamil_to_english(clean_snippet)

        # Remove trailing publisher name if it remained inside clean_snippet
        if clean_snippet.endswith(f" {publisher_name}"):
            clean_snippet = clean_snippet[: -len(publisher_name)].strip(" -–—•|")

        # Require at least 4 alphabetic words so stub titles like "MK Stalin Meets OPS" or "Cuddalore Protest:-????" are skipped
        alpha_words = re.findall(r"[A-Za-z]{3,}", clean_title)
        if len(alpha_words) < 4 or has_tamil_script(clean_title):
            continue

        collected.append(
            {
                "source_id": source["id"],
                "publisher": publisher_name,
                "language": "en",
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