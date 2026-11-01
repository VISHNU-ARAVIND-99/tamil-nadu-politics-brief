#!/usr/bin/env python3
"""
Step 4 & Step 5 of Pipeline:
- Requires an explicit Tamil Nadu anchor (TN regional party, TN district, or 'Tamil Nadu')
  so national BJP/Congress stories from Maharashtra/Haryana (e.g., Fadnavis, Rohtak) are rejected.
- Blocks pure IMD weather/rain/depression forecasts.
- Routes High Court / Assembly stories accurately to 'Assembly, Courts & Policy'.
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
    "tamil", "nadu", "chennai", "news", "report", "state", "government", "today", "latest"
}

# Jaccard + entity similarity threshold for clustering related stories.
# Tuned empirically: 0.36 balances dedup (removing near-duplicates) vs keeping
# distinct stories with shared entities (e.g. two different DMK stories in Chennai).
CLUSTER_SIMILARITY_THRESHOLD = 0.36

# Parties that exist ONLY in Tamil Nadu (used as a strict Tamil Nadu geographic anchor)
TN_REGIONAL_PARTIES = {"DMK", "AIADMK", "TVK", "PMK", "NTK", "VCK", "MDMK", "DMDK", "AMMK"}

# TN-specific leaders of national parties
TN_NATIONAL_PARTY_LEADERS = [
    "annamalai", "nainar nagendran", "l. murugan", "tamilisai",
    "selvaperunthagai", "p. chidambaram", "karti chidambaram", "tncc",
    "k. balakrishnan", "mutharasan", "shanmugam"
]

OUT_OF_SCOPE_PATTERNS = [
    # Other states & non-TN politicians
    r"\bfadnavis\b", r"\brohtak\b", r"\bnitin\s+nabin\b", r"\bsamvidhan\s+chori\b",
    r"\bvijayawada\b", r"\bvijaya\s+deepika\b", r"\bnellore\b", r"\btirupati\b",
    r"\bandhra\s+pradesh\b", r"\bchandrababu\s+naidu\b", r"\bysrc\b", r"\btelangana\b",
    r"\bhyderabad\b", r"\bcyberabad\b", r"\bkhammam\b", r"\bnagarkurnool\b", r"\bmeerpet\b",
    r"\banantapur\b", r"\bvizianagaram\b", r"\bkarimnagar\b", r"\bbidar\b", r"\bkovvur\b",
    r"\bkishan\s+reddy\b", r"\bgudur\s+narayana\b", r"\buddhav\s+thackeray\b", r"\bshiv\s+sena\b",
    r"\bmaharashtra\b", r"\bmumbai\b", r"\bharyana\b", r"\bnayab\s+singh\s+saini\b",
    r"\bjammu\b", r"\bkashmir\b", r"\bomar\s+abdullah\b", r"\bnidhi\s+razdan\b",
    r"\bpunjab\s+polls\b", r"\bbhagwant\s+mann\b", r"\bmaryam\s+nawaz\b", r"\bbangsamoro\b",
    r"\bbarmm\b", r"\bphilippines?\b", r"\bbalochistan\b", r"\bassam\b", r"\bhimanta\b",
    r"\bguwahati\b", r"\btripura\b", r"\btripurainfo\b", r"\bhimachal\b", r"\bsukhu\b",
    r"\bchhattisgarh\b", r"\bodisha\b", r"\borissa\s+hc\b", r"\bmohan\s+charan\b",
    r"\bmohan\s+yadav\b", r"\bsuvendu\s+adhikari\b", r"\bmamata\b", r"\btrinamool\b",
    r"\bkarnataka\s+high\s+court\b", r"\bmandya\b", r"\bd\.?k\.?\s+shivakumar\b",
    r"\bkumaraswamy\b", r"\bsiddaramaiah\b",
    # Weather forecasts (IMD / cyclones / depressions without political action)
    r"\bdeep\s+depression\b", r"\bimd\s+warns\b", r"\bsqually\s+winds\b",
    r"\bcyclone\s+murasu\b", r"\bweather\s+update\b", r"\bheavy\s+rain\s+alert\b",
    # International / Sports / Cinema / Routine Crime & Accidents
    r"\btrump\b", r"\bepstein\b", r"\bwall\s+street\s+journal\b", r"\boregon\s+governor\b",
    r"\bfrankfurt\b", r"\bgermany\s+gen-z\b", r"\bfrance\s+heads\b", r"\bfrance\s+braces\b",
    r"\belon\s+musk\b", r"\bnetanyahu\b",
    r"\bchennai\s+open\b", r"\bwta\s+250\b", r"\bchennaiyin\s+fc\b", r"\bkbfc\b",
    r"\bsuper\s+sport\s+race\b", r"\bsai\s+pallavi\b", r"\bdrishyam\b", r"\bajay\s+devgn\b",
    r"\btiger\s+shroff\b", r"\bphilately\s+passport\b", r"\bdiwali\s+shopping\b",
    r"\bfridge\s+blast\b", r"\bstray\s+dogs\s+bite\b", r"\bhydroponic\s+ganja\b",
    r"\bamerican\s+tourist\s+among\s+three\b", r"\bjourney\s+to\s+the\s+centre\s+of\s+space\b",
    r"\bruna?way\s+schoolgirls\b", r"\bwearing\s+headphones\s+killed\b", r"\bcountry-made\s+guns\b",
    r"\bxxx\b", r"\bpornx\b", r"\btvk:ca\b", r"\bequity\s+trading\b",
]

COMPILED_EXCLUSIONS = [re.compile(p, re.IGNORECASE) for p in OUT_OF_SCOPE_PATTERNS]


def keyword_in_text(keyword: str, lowered_text: str) -> bool:
    kw = keyword.lower().strip()
    if not kw:
        return False
    if re.search(r"[\u0B80-\u0BFF]", kw):
        return kw in lowered_text
    pattern = r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])"
    return bool(re.search(pattern, lowered_text))


def extract_tags(text: str) -> dict:
    lowered = text.lower()
    parties = [p for p, kws in PARTY_TAXONOMY.items() if any(keyword_in_text(kw, lowered) for kw in kws)]
    topics = [t for t, kws in TOPIC_TAXONOMY.items() if any(keyword_in_text(kw, lowered) for kw in kws)]
    districts = [d for d, kws in TN_DISTRICTS.items() if any(keyword_in_text(kw, lowered) for kw in kws)]

    return {
        "parties": sorted(set(parties)),
        "topics": sorted(set(topics)),
        "districts": sorted(set(districts)),
    }


def is_politically_relevant(item: dict, tags: dict) -> bool:
    combined = f"{item.get('title', '')} {item.get('snippet', '')}"
    lowered = combined.lower()

    if any(pat.search(lowered) for pat in COMPILED_EXCLUSIONS):
        return False

    # National parties (BJP, INC, Left) alone do NOT prove a story is in Tamil Nadu!
    has_regional_party = bool(set(tags["parties"]) & TN_REGIONAL_PARTIES)
    has_tn_national_leader = any(keyword_in_text(ldr, lowered) for ldr in TN_NATIONAL_PARTY_LEADERS)
    has_tn_keyword = any(keyword_in_text(kw, lowered) for kw in TN_RELEVANCE_KEYWORDS)

    has_strict_tn_anchor = (
        bool(tags["districts"])
        or has_regional_party
        or has_tn_national_leader
        or has_tn_keyword
    )
    if not has_strict_tn_anchor:
        return False

    return bool(tags["parties"] or tags["topics"])


def tokenize_for_similarity(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9\u0B80-\u0BFF]{3,}", text.lower())
    return {w for w in words if w not in STOPWORDS}


def compute_cluster_similarity(item_a: dict, item_b: dict) -> float:
    tokens_a = item_a["_tokens"]
    tokens_b = item_b["_tokens"]
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    jaccard = intersection / union if union else 0.0

    if intersection < 2:
        return 0.0

    text_tokens_a = {t for t in tokens_a if not t.startswith("entity_")}
    text_tokens_b = {t for t in tokens_b if not t.startswith("entity_")}
    text_intersection = len(text_tokens_a & text_tokens_b)

    is_cross_lingual = item_a.get("language") != item_b.get("language")
    if not is_cross_lingual and text_intersection < 2:
        return 0.0

    shared_parties = set(item_a["parties"]) & set(item_b["parties"])
    shared_districts = set(item_a["districts"]) & set(item_b["districts"])
    shared_topics = set(item_a["topics"]) & set(item_b["topics"])

    entity_score = 0.0
    if is_cross_lingual:
        if shared_parties and shared_districts:
            entity_score += 0.30
        elif shared_parties and shared_topics:
            entity_score += 0.22
        elif shared_districts and shared_topics:
            entity_score += 0.18
    else:
        if shared_parties and shared_districts:
            entity_score += 0.15
        elif shared_parties and shared_topics:
            entity_score += 0.10

    return min(1.0, jaccard + entity_score)


def deduplicate_and_filter(raw_items: list[dict]) -> list[dict]:
    relevant_items = []
    seen_urls = set()
    seen_titles = set()

    for item in raw_items:
        url = item["url"].split("?")[0].strip()
        norm_title = re.sub(r"\W+", "", item.get("title", "").lower())
        if url in seen_urls or norm_title in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(norm_title)

        combined_text = f"{item.get('title', '')} {item.get('snippet', '')}"
        tags = extract_tags(combined_text)
        if not is_politically_relevant(item, tags):
            continue

        enriched = dict(item)
        enriched["parties"] = tags["parties"]
        enriched["topics"] = tags["topics"] or ["Government & Administration"]
        enriched["districts"] = tags["districts"]
        tok = tokenize_for_similarity(combined_text)
        for p in tags["parties"]:
            tok.add(f"entity_party_{p.lower()}")
        for d in tags["districts"]:
            tok.add(f"entity_district_{d.lower()}")
        for t in tags["topics"]:
            tok.add(f"entity_topic_{t.lower()}")
        enriched["_tokens"] = tok
        relevant_items.append(enriched)

    clusters: list[dict] = []
    for item in relevant_items:
        matched_cluster = None
        best_sim = 0.0
        for cluster in clusters:
            sim = compute_cluster_similarity(item, cluster["representative"])
            if sim >= CLUSTER_SIMILARITY_THRESHOLD and sim > best_sim:
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

    finalized = []
    for idx, cluster in enumerate(clusters, start=1):
        sources = []
        seen_src_titles = set()
        for it in cluster["items"]:
            it.pop("_tokens", None)
            title_key = it["title"].strip().lower()
            if title_key not in seen_src_titles:
                seen_src_titles.add(title_key)
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

        # Select best representative, balancing snippet richness and editorial tier
        best_rep = max(
            cluster["items"],
            key=lambda x: (
                1 if x.get("reliability_tier") == "tier_1_editorial" else 0,
                min(len((x.get("snippet") or "").split()), 70),
            ),
        )

        finalized.append(
            {
                "cluster_id": f"story-{idx}",
                "primary_title": best_rep["title"],
                "parties": cluster["parties"],
                "topics": cluster["topics"],
                "districts": cluster["districts"],
                "publisher_count": len(cluster["publishers"]),
                "languages": sorted(cluster["languages"]),
                "sources": sources,
            }
        )

    return finalized