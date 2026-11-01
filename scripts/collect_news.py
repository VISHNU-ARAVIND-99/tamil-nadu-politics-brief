#!/usr/bin/env python3
"""
Step 2 & Step 3 of Pipeline:
- Fetches RSS feeds and extracts the REAL article body (first 3-5 factual sentences, ~65-85 words, Inshorts style)
  using JSON-LD 'articleBody' and BeautifulSoup <p> extraction.
- Fixes Tamil political terminology ('ரோடு ஷோ' -> 'roadshow') before translation.
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

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

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
    re.compile(r"^live\s*:", re.IGNORECASE),
    re.compile(r"standing\s+together.*greetings", re.IGNORECASE),
]

# Pre-replace Tamil political terms that Google Translate mistranslates literally
TAMIL_POLITICAL_GLOSSARY = {
    "ரோடு ஷோ": "roadshow",
    "ரோடுஷோ": "roadshow",
    "நடைபயணம்": "padayatra march",
    "பொதுக்குழு": "General Council meeting",
    "செயற்குழு": "Executive Committee meeting",
    "ஆர்ப்பாட்டம்": "protest demonstration",
    "சாலை மறியல்": "road blockade protest",
    "முற்றுகை": "picketing protest",
    "கண்டனம்": "condemnation",
    "அரசாணை": "Government Order",
}


def normalize_tamil_terms(text: str) -> str:
    if not text:
        return ""
    out = text
    for ta_term, en_term in TAMIL_POLITICAL_GLOSSARY.items():
        out = out.replace(ta_term, f" {en_term} ")
    return out


def clean_dateline_prefix(text: str) -> str:
    """Remove uppercase city datelines like 'CHENNAI: ' or 'CHENGALPET: ' for clean Inshorts flow."""
    if not text:
        return ""
    cleaned = re.sub(r"^[A-Z][A-Z\s/.-]{2,22}:\s*", "", text.strip())
    cleaned = re.sub(r"\s+[A-Z]{4,20}:\s+", " ", cleaned)
    return cleaned.strip()


def trim_to_inshorts_length(text: str, min_words: int = 55, max_words: int = 90) -> str:
    """Keep 3 to 5 complete factual sentences (~60 to 85 words, Inshorts style)."""
    cleaned = clean_dateline_prefix(text)
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    selected = []
    word_count = 0

    for sent in sentences:
        s = sent.strip()
        if len(s) < 20:
            continue
        if any(junk in s.lower() for junk in [
            "also read", "read more", "click here", "subscribe", "download the",
            "follow us", "whatsapp channel", "published -", "updated -"
        ]):
            continue
        w = len(s.split())
        if word_count + w > max_words and word_count >= min_words:
            break
        selected.append(s)
        word_count += w
        if word_count >= max_words:
            break

    result = " ".join(selected).strip()
    return result if result else cleaned


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


def fetch_real_article_summary(url: str) -> str:
    """
    Fetches the actual news article webpage and extracts the first 3-5 factual sentences
    (~65-85 words) from JSON-LD 'articleBody' or <article> <p> tags.
    Never invents or pads text.
    """
    if not url or "news.google.com" in url:
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw_html = resp.read(120000).decode("utf-8", errors="ignore")

        extracted_body = ""

        # 1. Try JSON-LD NewsArticle 'articleBody' (Used by Times of India, The Hindu, TNIE, DT Next, etc.)
        ld_matches = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            raw_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for ld_raw in ld_matches:
            try:
                ld_obj = json.loads(ld_raw.strip())
                candidates = ld_obj if isinstance(ld_obj, list) else [ld_obj]
                for item in candidates:
                    if isinstance(item, dict) and "@graph" in item and isinstance(item["@graph"], list):
                        candidates.extend(item["@graph"])
                for item in candidates:
                    if isinstance(item, dict) and item.get("articleBody"):
                        body_candidate = html.unescape(str(item["articleBody"]))
                        if len(body_candidate.split()) >= 35:
                            extracted_body = body_candidate
                            break
                if extracted_body:
                    break
            except Exception:
                continue

        # 2. If no JSON-LD articleBody, extract real <p> tags using BeautifulSoup
        if not extracted_body and BeautifulSoup is not None:
            soup = BeautifulSoup(raw_html, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "figcaption"]):
                tag.decompose()
            container = soup.find("article") or soup.find("main") or soup.body
            if container:
                paras = []
                for p in container.find_all("p"):
                    txt = p.get_text(" ", strip=True)
                    if len(txt.split()) >= 12 and not any(
                        skip in txt.lower()
                        for skip in ["also read", "subscribe", "copyright", "all rights reserved", "follow us"]
                    ):
                        paras.append(txt)
                    if len(" ".join(paras).split()) >= 95:
                        break
                extracted_body = " ".join(paras)

        # 3. Fallback to og:description if body is still empty
        if not extracted_body:
            meta_match = re.search(
                r'<meta[^>]+(?:property=["\']og:description["\']|name=["\']description["\'])[^>]+content=["\']([^"\']+)["\']',
                raw_html,
                re.IGNORECASE,
            )
            if meta_match:
                extracted_body = html.unescape(meta_match.group(1))

        if not extracted_body:
            return ""

        cleaned = sanitize_untrusted_text(extracted_body, max_length=650)
        return trim_to_inshorts_length(cleaned, min_words=55, max_words=88)
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

        raw_title = normalize_tamil_terms(html.unescape(item.get("title", "")).strip())
        if any(pat.search(raw_title) for pat in GENERIC_BULLETIN_PATTERNS):
            continue

        real_publisher = (item.get("source_title") or "").strip()
        if " - " in raw_title and ("news.google.com" in feed_url or real_publisher):
            title_part, trailing_pub = raw_title.rsplit(" - ", 1)
            raw_title = title_part.strip()
            if not real_publisher and len(trailing_pub.strip()) < 40:
                real_publisher = trailing_pub.strip()

        publisher_name = real_publisher or source["name"]
        clean_title = sanitize_untrusted_text(raw_title, max_length=220)
        raw_summary = normalize_tamil_terms(item.get("summary", ""))

        if "news.google.com" in feed_url:
            clean_snippet = ""
        else:
            clean_snippet = trim_to_inshorts_length(sanitize_untrusted_text(raw_summary, max_length=650))

        link = (item.get("link") or "").strip()
        if not clean_title or not link.startswith(("http://", "https://")):
            continue

        # Always try to fetch the real 65-85 word article body when snippet is short (< 45 words)
        if len(clean_snippet.split()) < 45:
            real_body = fetch_real_article_summary(link)
            if len(real_body.split()) > len(clean_snippet.split()):
                clean_snippet = real_body

        if has_tamil_script(clean_title):
            clean_title = translate_tamil_to_english(clean_title)
        if has_tamil_script(clean_snippet):
            clean_snippet = translate_tamil_to_english(clean_snippet)

        # Clean up any awkward literal translation artifacts
        clean_title = re.sub(r"\broad\s+crossing\b|\bcrawl\s+the\s+road\b", "roadshow", clean_title, flags=re.IGNORECASE)
        clean_snippet = re.sub(r"\broad\s+crossing\b|\bcrawl\s+the\s+road\b", "roadshow", clean_snippet, flags=re.IGNORECASE)

        if clean_snippet.endswith(f"({publisher_name}).") or clean_snippet.endswith(f"({publisher_name})"):
            clean_snippet = re.sub(rf"\s*\({re.escape(publisher_name)}\)\.?\s*$", "", clean_snippet).strip()

        alpha_words = re.findall(r"[A-Za-z]{3,}", clean_title)
        if len(alpha_words) < 5 or has_tamil_script(clean_title) or ".." in clean_title:
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