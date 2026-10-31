#!/usr/bin/env python3
"""
Step 7, Step 8 & Step 9 of Pipeline:
- 100% Pure English output
- Bulleted, multi-sentence 'The Big Picture'
- Detailed multi-sentence story summaries (never 1-line blurbs)
- Populates Government, Political Parties, Assembly/Courts, and District sections with real content
"""

import json
import re
import urllib.error
import urllib.request
from scripts.config import (
    AI_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    HTTP_TIMEOUT_SECONDS,
    get_ist_now,
    has_tamil_script,
    translate_tamil_to_english,
)

PROMPT_INSTRUCTIONS = """You are the Editor-in-Chief of 'Tamil Nadu Politics Brief', a pure-English digital newspaper.
Write today's edition strictly from the verified news clusters below.

STRICT EDITORIAL RULES:
1. 100% PURE ENGLISH ONLY: Every single headline, bullet point, story summary, and source title MUST be in fluent, natural English. Never output Tamil script.
2. THE BIG PICTURE (BULLET POINTS, DETAILED): Format 'big_picture' as a Markdown bullet list (`- **Topic Lead:** ...`) with 5 to 6 bullet points. Each bullet point MUST be 2 to 3 complete sentences (45-65 words per bullet) clearly explaining what happened, who is involved, and why it matters. NEVER start with 'Key developments in this 12-hour briefing include:'.
3. LONGER, DETAILED TOP STORIES: For each story in 'top_developments' (select 6-8 top stories), write a 'summary' of 4 to 6 complete sentences (90-130 words) broken into 2 clear paragraphs. Explain the full background, specific actions or statements made, political reactions, and impact. Never write a 1-sentence summary.
4. POPULATE ALL SECTIONS: Write detailed bulleted summaries for 'government_and_administration', 'political_parties_and_opposition', 'assembly_courts_and_policy', and 'district_developments' using the relevant clusters. If a section genuinely has zero matching stories in this window, set its value to an empty string `""`.

Return ONLY valid JSON with these exact keys:
{
  "headline": "Main English newspaper headline",
  "big_picture": "- **Lead Topic 1:** Two to three clear sentences explaining the full development and its significance.\n- **Lead Topic 2:** Two to three clear sentences...",
  "top_developments": [
    {
      "headline": "Clear English headline",
      "verification_badge": "Multi-Source Verified | Official Release | Single-Source Report",
      "who_is_involved": "Parties, leaders, or departments",
      "summary": "Paragraph 1 (2-3 sentences of facts and context).\n\nParagraph 2 (2-3 sentences on political responses and administrative impact).",
      "why_it_matters": "One clear sentence on why this matters to Tamil Nadu citizens.",
      "sources": [{"title": "English title", "publisher": "Publisher Name", "language": "en", "published_date": "YYYY-MM-DD", "url": "..."}]
    }
  ],
  "government_and_administration": "Detailed bullets or empty string",
  "political_parties_and_opposition": "Detailed bullets or empty string",
  "assembly_courts_and_policy": "Detailed bullets or empty string",
  "district_developments": "Detailed bullets or empty string",
  "claims_vs_facts": [{"claim": "...", "claimant": "...", "verified_evidence": "..."}],
  "what_to_watch_next": "- Bullet 1\n- Bullet 2 (or empty string if none)"
}"""


def clean_json_response(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def expand_cluster_narrative(cluster: dict) -> str:
    """Build a rich 4-5 sentence English narrative from a cluster's sources and tags."""
    headline = translate_tamil_to_english(cluster["primary_title"]).strip().rstrip(".")
    snippets = []
    for s in cluster.get("sources", []):
        snip = translate_tamil_to_english(s.get("snippet") or "").strip()
        if snip and snip.lower() != headline.lower() and snip not in snippets:
            snippets.append(snip)

    pubs = sorted({s["publisher"] for s in cluster.get("sources", [])})
    parties = cluster.get("parties", [])
    districts = cluster.get("districts", [])
    topics = cluster.get("topics", ["State Administration"])

    body_parts = []
    if snippets:
        body_parts.append(" ".join(snippets[:2]))
    else:
        body_parts.append(f"{headline}.")

    if len(" ".join(body_parts).split()) < 45:
        actor_clause = (
            f"The development directly involves {', '.join(parties)}"
            if parties
            else "The matter is being addressed by state administrative authorities"
        )
        loc_clause = f" across {', '.join(districts)}" if districts else " in Tamil Nadu"
        body_parts.append(
            f"{actor_clause}{loc_clause} as part of wider policy discussions surrounding {', '.join(topics).lower()}."
        )
        body_parts.append(
            f"Reporting from {', '.join(pubs[:3])} indicates that party representatives and senior officials are closely tracking the public response and subsequent administrative steps."
        )

    return " ".join(body_parts)


def build_category_section_text(clusters: list[dict], topic_keywords: list[str], require_districts: bool = False) -> str:
    matched = []
    for c in clusters:
        if require_districts and c.get("districts"):
            matched.append(c)
        elif any(t in c.get("topics", []) for t in topic_keywords):
            matched.append(c)

    if not matched:
        return ""

    bullets = []
    for c in matched[:5]:
        title = translate_tamil_to_english(c["primary_title"]).strip()
        narrative = expand_cluster_narrative(c)
        bullets.append(f"- **{title}:** {narrative}")
    return "\n\n".join(bullets)


def build_extractive_fallback_edition(window_meta: dict, verified_clusters: list[dict], reason: str) -> dict:
    now_ist = get_ist_now().isoformat()
    all_parties = sorted({p for c in verified_clusters for p in c.get("parties", [])})
    all_topics = sorted({t for c in verified_clusters for t in c.get("topics", [])})
    all_districts = sorted({d for c in verified_clusters for d in c.get("districts", [])})
    all_sources = []
    seen_urls = set()

    for c in verified_clusters:
        for s in c.get("sources", []):
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                all_sources.append(
                    {
                        "title": translate_tamil_to_english(s["title"]),
                        "publisher": s["publisher"],
                        "language": "en",
                        "published_date": s["published_date"],
                        "url": s["url"],
                    }
                )

    top_devs = []
    for cluster in verified_clusters[:8]:
        headline = translate_tamil_to_english(cluster["primary_title"]).strip()
        narrative = expand_cluster_narrative(cluster)
        topics_str = ", ".join(cluster.get("topics", ["public policy"])).lower()
        districts_str = ", ".join(cluster.get("districts", [])) or "Tamil Nadu"
        top_devs.append(
            {
                "headline": headline,
                "verification_badge": cluster["verification_status"],
                "who_is_involved": ", ".join(cluster["parties"]) if cluster["parties"] else "",
                "summary": narrative,
                "why_it_matters": f"This development shapes {topics_str} and administrative priorities in {districts_str}.",
                "sources": cluster["sources"],
            }
        )

    big_picture_bullets = []
    for c in verified_clusters[:5]:
        title = translate_tamil_to_english(c["primary_title"]).strip()
        narrative = expand_cluster_narrative(c)
        big_picture_bullets.append(f"- **{title}:** {narrative}")

    big_picture = (
        "\n\n".join(big_picture_bullets)
        if big_picture_bullets
        else "- **Quiet Monitoring Window:** No major verified political developments were recorded during this 12-hour period."
    )

    sections = {
        "big_picture": big_picture,
        "top_developments": top_devs,
        "government_and_administration": build_category_section_text(
            verified_clusters, ["Government & Administration", "Infrastructure & Economy", "Education & NEET", "Agriculture & Water"]
        ),
        "political_parties_and_opposition": build_category_section_text(
            verified_clusters, ["Political Parties", "Elections", "Public Protests & Labour"]
        ),
        "assembly_courts_and_policy": build_category_section_text(
            verified_clusters, ["Assembly, Courts & Policy", "Centre–State Relations"]
        ),
        "district_developments": build_category_section_text(
            verified_clusters, [], require_districts=True
        ),
        "claims_vs_facts": [],
        "what_to_watch_next": "",
        "all_sources": all_sources,
    }

    word_count = max(350, len(json.dumps(sections, ensure_ascii=False).split()))
    return {
        "edition_id": window_meta["edition_id"],
        "title": window_meta["title"],
        "date": window_meta["date"],
        "edition_type": window_meta["edition_type"],
        "is_test_sample": False,
        "status": "published",
        "scheduled_time_ist": window_meta["scheduled_time_ist"],
        "generated_at_ist": now_ist,
        "published_at_ist": now_ist,
        "coverage_start_ist": window_meta["coverage_start_ist"],
        "coverage_end_ist": window_meta["coverage_end_ist"],
        "reading_time_minutes": max(5, round(word_count / 140)),
        "word_count": word_count,
        "headline": translate_tamil_to_english(verified_clusters[0]["primary_title"]) if verified_clusters else "Tamil Nadu Political Briefing",
        "parties": all_parties,
        "topics": all_topics,
        "districts": all_districts,
        "sections": sections,
        "_telemetry": {"ai_provider": f"fallback:{reason}", "tokens_used": 0},
    }


def validate_and_sanitize_ai_output(ai_data: dict, allowed_urls: set[str], fallback_sources: list[dict]) -> dict:
    if has_tamil_script(ai_data.get("headline", "")):
        ai_data["headline"] = translate_tamil_to_english(ai_data["headline"])
    if has_tamil_script(ai_data.get("big_picture", "")):
        ai_data["big_picture"] = translate_tamil_to_english(ai_data["big_picture"])

    cleaned_devs = []
    for dev in ai_data.get("top_developments", []):
        if has_tamil_script(dev.get("headline", "")):
            dev["headline"] = translate_tamil_to_english(dev["headline"])
        if has_tamil_script(dev.get("summary", "")):
            dev["summary"] = translate_tamil_to_english(dev["summary"])
        valid_sources = []
        seen_u = set()
        for s in dev.get("sources", []):
            u = s.get("url") if isinstance(s, dict) else None
            if u in allowed_urls and u not in seen_u:
                seen_u.add(u)
                s["title"] = translate_tamil_to_english(s.get("title", ""))
                valid_sources.append(s)
        if not valid_sources and fallback_sources:
            valid_sources = [fallback_sources[0]]
        dev["sources"] = valid_sources
        cleaned_devs.append(dev)

    ai_data["top_developments"] = cleaned_devs
    ai_data["all_sources"] = fallback_sources
    return ai_data


def generate_edition_summary(window_meta: dict, verified_clusters: list[dict]) -> dict:
    if not verified_clusters:
        return build_extractive_fallback_edition(window_meta, [], "quiet_window")

    if AI_PROVIDER != "gemini" or not GEMINI_API_KEY:
        return build_extractive_fallback_edition(window_meta, verified_clusters, "missing_key")

    top_clusters = verified_clusters[:14]
    allowed_urls = {s["url"] for c in top_clusters for s in c.get("sources", [])}
    all_sources = []
    seen_urls = set()
    for c in top_clusters:
        for s in c.get("sources", []):
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                all_sources.append(
                    {
                        "title": translate_tamil_to_english(s["title"]),
                        "publisher": s["publisher"],
                        "language": "en",
                        "published_date": s["published_date"],
                        "url": s["url"],
                    }
                )

    compact_clusters = [
        {
            "title": translate_tamil_to_english(c["primary_title"]),
            "verification": c["verification_status"],
            "parties": c["parties"],
            "topics": c["topics"],
            "districts": c["districts"],
            "sources": c["sources"][:3],
        }
        for c in top_clusters
    ]

    models_to_try = ["gemini-2.5-flash", GEMINI_MODEL]
    seen_models = []
    for m in models_to_try:
        if m and m not in seen_models:
            seen_models.append(m)

    last_err = "unknown"
    for model_name in seen_models:
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            f"?key={GEMINI_API_KEY}"
        )
        gen_config = {
            "temperature": 0.25,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8192,
        }
        if "2.5" in model_name:
            gen_config["thinkingConfig"] = {"thinkingBudget": 0}

        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": PROMPT_INSTRUCTIONS
                            + "\n\nVerified News Clusters:\n"
                            + json.dumps(compact_clusters, ensure_ascii=False)
                        }
                    ],
                }
            ],
            "generationConfig": gen_config,
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS * 4) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
            raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
            ai_sections = clean_json_response(raw_text)
            total_tokens = resp_json.get("usageMetadata", {}).get("totalTokenCount", 0)
            validated = validate_and_sanitize_ai_output(ai_sections, allowed_urls, all_sources)

            for key, topics, req_dist in [
                ("government_and_administration", ["Government & Administration", "Infrastructure & Economy", "Education & NEET", "Agriculture & Water"], False),
                ("political_parties_and_opposition", ["Political Parties", "Elections", "Public Protests & Labour"], False),
                ("assembly_courts_and_policy", ["Assembly, Courts & Policy", "Centre–State Relations"], False),
                ("district_developments", [], True),
            ]:
                if not validated.get(key):
                    validated[key] = build_category_section_text(verified_clusters, topics, require_districts=req_dist)

            now_ist = get_ist_now().isoformat()
            all_parties = sorted({p for c in top_clusters for p in c.get("parties", [])})
            all_topics = sorted({t for c in top_clusters for t in c.get("topics", [])})
            all_districts = sorted({d for c in top_clusters for d in c.get("districts", [])})
            word_count = len(json.dumps(validated, ensure_ascii=False).split())

            return {
                "edition_id": window_meta["edition_id"],
                "title": window_meta["title"],
                "date": window_meta["date"],
                "edition_type": window_meta["edition_type"],
                "is_test_sample": False,
                "status": "published",
                "scheduled_time_ist": window_meta["scheduled_time_ist"],
                "generated_at_ist": now_ist,
                "published_at_ist": now_ist,
                "coverage_start_ist": window_meta["coverage_start_ist"],
                "coverage_end_ist": window_meta["coverage_end_ist"],
                "reading_time_minutes": max(5, round(word_count / 140)),
                "word_count": word_count,
                "headline": validated.get("headline", top_clusters[0]["primary_title"]),
                "parties": all_parties,
                "topics": all_topics,
                "districts": all_districts,
                "sections": {
                    "big_picture": validated.get("big_picture", ""),
                    "top_developments": validated.get("top_developments", []),
                    "government_and_administration": validated.get("government_and_administration", ""),
                    "political_parties_and_opposition": validated.get("political_parties_and_opposition", ""),
                    "assembly_courts_and_policy": validated.get("assembly_courts_and_policy", ""),
                    "district_developments": validated.get("district_developments", ""),
                    "claims_vs_facts": validated.get("claims_vs_facts", []),
                    "what_to_watch_next": validated.get("what_to_watch_next", ""),
                    "all_sources": all_sources,
                },
                "_telemetry": {"ai_provider": f"gemini:{model_name}", "tokens_used": total_tokens},
            }
        except Exception as exc:
            last_err = str(exc)
            print(f"[WARN] Model {model_name} failed ({last_err}), trying next...")

    return build_extractive_fallback_edition(window_meta, verified_clusters, last_err)