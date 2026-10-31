#!/usr/bin/env python3
"""
Step 4 & Step 5 of Pipeline:
- Tags each collected item with Tamil Nadu Political Parties, Topics, and Districts
- Filters out non-political stories, cinema alerts, and routine weather updates
- Deduplicates source titles and clusters stories reporting the same event across Tamil and English outlets
- Requires at least 2 shared meaningful tokens before merging stories
"""

import re
from scripts.config import (
    PARTY_TAXONOMY,
    TN_DISTRICTS,
    TN_RELEVANCE_KEYWORDS,
    TOPIC_TAXONOMY,
)

STOPWORDS = {
    "the", "and", "for", "that", "with", "from", "this", "over", "into", "after",
    "before", "under", "says", "said", "amid", "will", "have", "has", "been",
    "tamil", "nadu", "chennai", "news", "report", "state", "government"
}

NON_POLITICAL_CINEMA_PATTERNS = [
    re.compile(r"\b(box\s*office|trailer|teaser|movie\s+review|film\s+review|ott\s+release|first\s+look|boxoffice|kollywood)\b", re.IGNORECASE),
    re.compile(r"(திரைவிமர்சனம்|டிரெய்லர்|டீசர்|திரைப்படம்|பாக்ஸ்\s*ஆபீஸ்|பாடல்\s*வெளியீடு)", re.IGNORECASE),
]

NON_POLITICAL_WEATHER_PATTERNS = [
    re.compile(r"\b(weather\s+forecast|weather\s+update|rain\s+alert|yellow\s+alert|orange\s+alert|red\s+alert)\b", re.IGNORECASE),
    re.compile(r"(வானிலை\s+அறிக்கை|வானிலை\s+மையம்|மழை\s+எச்சரிக்கை|வெப்பநிலை\s+நிலவரம்)", re.IGNORECASE),
]


def extract_tags(text: str) -> dict:
    """Identify matching political parties, topics, and TN districts in Tamil or English text."""
    lowered = text.lower()
    parties = []
    for party, keywords in PARTY_TAXONOMY.items():
        if any(kw.lower() in lowered for kw in keywords):
            parties.append(party)

    topics = []
    for topic, keywords in TOPIC_TAXONOMY.items():
        if any(kw.lower() in lowered for kw in keywords):
            topics.append(topic)

    districts = []
    for district, keywords in TN_DISTRICTS.items():
        if any(kw.lower() in lowered for kw in keywords):
            districts.append(district)

    return {
        "parties": sorted(set(parties)),
        "topics": sorted(set(topics)),
        "districts": sorted(set(districts)),
    }


def is_politically_relevant(item: dict, tags: dict) -> bool:
    """Ensure story relates to Tamil Nadu politics, governance, policy, courts, or districts."""
    combined = f"{item.get('title', '')} {item.get('snippet', '')}"
    lowered = combined.lower()

    # Filter out pure cinema / entertainment stories unless tied to government/policy action
    for pat in NON_POLITICAL_CINEMA_PATTERNS:
        if pat.search(combined):
            if not any(t in ["Assembly, Courts & Policy", "Elections"] for t in tags["topics"]):
                return False

    # Filter out pure weather forecasts unless linked to political response or relief governance
    for pat in NON_POLITICAL_WEATHER_PATTERNS:
        if pat.search(combined):
            has_gov_relief = any(
                kw in lowered
                for kw in [
                    "minister", "collector", "relief", "compensation", "stalin", "eps",
                    "அமைச்சர்", "நிவாரணம்", "அரசாணை", "முதல்வர்", "திமுக", "அதிமுக"
                ]
            )
            if not has_gov_relief and not tags["parties"]:
                return False

    if tags["parties"] or tags["topics"]:
        return True
    if tags["districts"] and any(kw in lowered for kw in TN_RELEVANCE_KEYWORDS):
        return True
    return False


def tokenize_for_similarity(text: str) -> set[str]:
    """Extract normalized word tokens and entity tags for similarity comparison."""
    words = re.findall(r"[a-zA-Z0-9\u0B80-\u0BFF]{3,}", text.lower())
    return {w for w in words if w not in STOPWORDS}


def compute_cluster_similarity(item_a: dict, item_b: dict) -> float:
    """
    Compute cross-lingual and monolingual similarity score between two stories
    using token Jaccard similarity plus shared party, district, and topic tags.
    Requires at least 2 shared meaningful tokens before merging.
    """
    tokens_a = item_a["_tokens"]
    tokens_b = item_b["_tokens"]
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = len(tokens_a & tokens_b)
    # Require at least 2 shared meaningful tokens before merging
    if intersection < 2:
        return 0.0

    union = len(tokens_a | tokens_b)
    jaccard = intersection / union if union else 0.0

    # Shared entity bonus (enables Tamil + English clustering of the same event)
    shared_parties = set(item_a["parties"]) & set(item_b["parties"])
    shared_districts = set(item_a["districts"]) & set(item_b["districts"])
    shared_topics = set(item_a["topics"]) & set(item_b["topics"])

    entity_score = 0.0
    if shared_parties and shared_districts:
        entity_score += 0.45
    elif shared_parties and shared_topics:
        entity_score += 0.30
    elif shared_districts and shared_topics:
        entity_score += 0.30

    return min(1.0, jaccard + entity_score)


def deduplicate_and_filter(raw_items: list[dict]) -> list[dict]:
    """
    Filter relevant Tamil Nadu political stories and cluster duplicate coverage
    into unified story clusters with combined source attributions.
    """
    relevant_items = []
    seen_urls = set()

    for item in raw_items:
        url = item["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        combined_text = f"{item.get('title', '')} {item.get('snippet', '')}"
        tags = extract_tags(combined_text)
        if not is_politically_relevant(item, tags):
            continue

        enriched = dict(item)
        enriched["parties"] = tags["parties"]
        enriched["topics"] = tags["topics"] or ["Government & Administration"]
        enriched["districts"] = tags["districts"]
        tokens = tokenize_for_similarity(combined_text)
        for p in tags["parties"]:
            tokens.add(f"entity_party_{p.lower()}")
        for d in tags["districts"]:
            tokens.add(f"entity_district_{d.lower()}")
        for t in tags["topics"]:
            tokens.add(f"entity_topic_{t.lower()}")
        enriched["_tokens"] = tokens
        relevant_items.append(enriched)

    clusters: list[dict] = []
    for item in relevant_items:
        matched_cluster = None
        best_sim = 0.0
        for cluster in clusters:
            rep = cluster["representative"]
            sim = compute_cluster_similarity(item, rep)
            if sim >= 0.42 and sim > best_sim:
                best_sim = sim
                matched_cluster = cluster

        if matched_cluster is not None:
            matched_cluster["items"].append(item)
            matched_cluster["parties"] = sorted(set(matched_cluster["parties"]) | set(item["parties"]))
            matched_cluster["topics"] = sorted(set(matched_cluster["topics"]) | set(item["topics"]))
            matched_cluster["districts"] = sorted(set(matched_cluster["districts"]) | set(item["districts"]))
            matched_cluster["publishers"].add(item["publisher"])
            matched_cluster["languages"].add(item["language"])
        else:
            clusters.append(
                {
                    "representative": item,
                    "items": [item],
                    "parties": list(item["parties"]),
                    "topics": list(item["topics"]),
                    "districts": list(item["districts"]),
                    "publishers": {item["publisher"]},
                    "languages": {item["language"]},
                }
            )

    # Clean internal token sets, deduplicate source titles, and serialize sets
    finalized = []
    for idx, cluster in enumerate(clusters, start=1):
        sources = []
        seen_source_urls = set()
        seen_source_titles = set()
        for it in cluster["items"]:
            it.pop("_tokens", None)
            norm_title = re.sub(r"\W+", "", it["title"].lower())
            if it["url"] not in seen_source_urls and norm_title not in seen_source_titles:
                seen_source_urls.add(it["url"])
                seen_source_titles.add(norm_title)
                sources.append(
                    {
                        "title": it["title"],
                        "publisher": it["publisher"],
                        "language": it["language"],
                        "published_date": it["published_date"],
                        "published_at_ist": it["published_at_ist"],
                        "reliability_tier": it["reliability_tier"],
                        "url": it["url"],
                        "snippet": it["snippet"],
                    }
                )

        finalized.append(
            {
                "cluster_id": f"story-{idx}",
                "primary_title": cluster["representative"]["title"],
                "parties": cluster["parties"],
                "topics": cluster["topics"],
                "districts": cluster["districts"],
                "publisher_count": len(cluster["publishers"]),
                "languages": sorted(cluster["languages"]),
                "sources": sources,
            }
        )

    return finalized
