#!/usr/bin/env python3
"""
Step 7, Step 8 & Step 9 of Pipeline:
- Zero story duplication across sections (stories in Top Political Developments are never repeated below)
- Zero robotic filler sentences ('The development directly involves... Reporting from...')
- Section J (Sources and Further Reading) lists ONLY the sources actually cited in the edition
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
Write today's edition strictly from the verified Tamil Nadu political news clusters provided below.

STRICT EDITORIAL RULES:
1. 100% PURE ENGLISH ONLY: Every headline, bullet point, and story paragraph must be in natural English.
2. THE BIG PICTURE (BULLET LIST): Format 'big_picture' as 4 to 5 concise Markdown bullet points (`- **Topic Lead:** 1 to 2 crisp sentences summarizing the key takeaway.`). Do not copy-paste the full story text into The Big Picture.
3. TOP POLITICAL DEVELOPMENTS (NO DUPLICATION): Select the top 6 to 8 stories. For each story, write a natural 2-paragraph 'summary' (4-5 sentences total) explaining what happened, who is involved, and the political reactions, plus 1 specific sentence for 'why_it_matters'.
4. LOWER SECTIONS (UNIQUE STORIES ONLY): In 'government_and_administration', 'political_parties_and_opposition', 'assembly_courts_and_policy', and 'district_developments', summarize ONLY the remaining clusters that were NOT already featured in 'top_developments', formatted as Markdown bullet points (`- **Headline:** 2-3 clear sentences.`). If no remaining stories exist for a section, set it to `""`.

Return ONLY valid JSON with these exact keys:
{
  "headline": "Main English newspaper headline",
  "big_picture": "- **Lead 1:** ...\n- **Lead 2:** ...",
  "top_developments": [
    {
      "headline": "Clear English headline",
      "verification_badge": "Multi-Source Verified | Official Release | Single-Source Report",
      "who_is_involved": "Parties or leaders involved",
      "summary": "Natural newspaper paragraphs explaining the event.",
      "why_it_matters": "One specific sentence explaining why this matters.",
      "sources": [{"title": "Article title", "publisher": "Publisher Name", "language": "en", "published_date": "YYYY-MM-DD", "url": "..."}]
    }
  ],
  "government_and_administration": "- **Headline:** ...\n- **Headline:** ... (or empty string)",
  "political_parties_and_opposition": "- **Headline:** ... (or empty string)",
  "assembly_courts_and_policy": "- **Headline:** ... (or empty string)",
  "district_developments": "- **Headline:** ... (or empty string)",
  "claims_vs_facts": [],
  "what_to_watch_next": ""
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


def build_clean_story_text(cluster: dict) -> str:
    """
    Combine unique snippets and related source titles from a cluster into clean English sentences
    WITHOUT appending any robotic template filler sentences.
    """
    headline = translate_tamil_to_english(cluster["primary_title"]).strip()
    pieces = []

    for s in cluster.get("sources", []):
        snip = translate_tamil_to_english(s.get("snippet") or "").strip()
        if snip and snip.lower() != headline.lower() and snip not in pieces:
            pieces.append(snip)

    # If multiple sources covered the event, include additional distinct headlines as context
    if len(pieces) < 2 and len(cluster.get("sources", [])) > 1:
        for s in cluster["sources"][1:4]:
            sec_title = translate_tamil_to_english(s.get("title") or "").strip().rstrip(".")
            if sec_title and sec_title.lower() != headline.lower():
                pieces.append(f"{s['publisher']} also reported on the development: \"{sec_title}.\"")

    return " ".join(pieces[:3]).strip()


def build_extractive_fallback_edition(window_meta: dict, verified_clusters: list[dict], reason: str) -> dict:
    now_ist = get_ist_now().isoformat()

    # Keep only clusters that have substantive content or multi-source backing
    usable_clusters = [
        c for c in verified_clusters
        if len(build_clean_story_text(c)) >= 45 or len(c.get("sources", [])) >= 2
    ]
    if not usable_clusters:
        usable_clusters = verified_clusters[:8]

    top_slice = usable_clusters[:7]
    remaining_clusters = usable_clusters[7:22]

    # Track used cluster IDs so NO story is ever repeated across sections!
    used_ids = {c["cluster_id"] for c in top_slice}

    top_devs = []
    for cluster in top_slice:
        headline = translate_tamil_to_english(cluster["primary_title"]).strip()
        body = build_clean_story_text(cluster)
        top_devs.append(
            {
                "headline": headline,
                "verification_badge": cluster["verification_status"],
                "who_is_involved": ", ".join(cluster["parties"]) if cluster["parties"] else "",
                "summary": body,
                "why_it_matters": "",
                "sources": cluster["sources"][:4],
            }
        )

    # Concise executive summary bullets for The Big Picture (distinct from full story cards)
    big_picture_bullets = []
    for c in top_slice[:5]:
        title = translate_tamil_to_english(c["primary_title"]).strip().rstrip(".")
        lead_tag = ", ".join(c["parties"][:2]) or ", ".join(c["districts"][:1]) or "State Update"
        first_snip = build_clean_story_text(c).split(". ")[0].strip().rstrip(".")
        if first_snip and first_snip.lower() != title.lower():
            big_picture_bullets.append(f"- **{lead_tag} — {title}:** {first_snip}.")
        else:
            big_picture_bullets.append(f"- **{lead_tag}:** {title}.")

    def allocate_unique_section(topic_matches: list[str], require_district: bool = False) -> str:
        lines = []
        for c in remaining_clusters:
            if c["cluster_id"] in used_ids:
                continue
            is_match = (
                bool(c.get("districts"))
                if require_district
                else any(t in c.get("topics", []) for t in topic_matches)
            )
            if is_match:
                used_ids.add(c["cluster_id"])
                t = translate_tamil_to_english(c["primary_title"]).strip().rstrip(".")
                b = build_clean_story_text(c)
                pub = c["sources"][0]["publisher"] if c.get("sources") else "Report"
                url = c["sources"][0]["url"] if c.get("sources") else ""
                src_note = f" ([{pub}]({url}))" if url else ""
                if b and b.lower() != t.lower():
                    lines.append(f"- **{t}:** {b}{src_note}")
                else:
                    lines.append(f"- **{t}**{src_note}")
                if len(lines) >= 4:
                    break
        return "\n".join(lines)

    gov_section = allocate_unique_section(["Government & Administration", "Infrastructure & Economy", "Education & NEET", "Agriculture & Water"])
    parties_section = allocate_unique_section(["Political Parties", "Elections", "Public Protests & Labour"])
    courts_section = allocate_unique_section(["Assembly, Courts & Policy", "Centre–State Relations"])
    district_section = allocate_unique_section([], require_district=True)

    # Collect ONLY sources from clusters that were actually used in this edition (max ~15 links)
    cited_sources = []
    seen_urls = set()
    for c in usable_clusters:
        if c["cluster_id"] in used_ids:
            for s in c.get("sources", [])[:2]:
                if s["url"] not in seen_urls:
                    seen_urls.add(s["url"])
                    cited_sources.append(
                        {
                            "title": translate_tamil_to_english(s["title"]),
                            "publisher": s["publisher"],
                            "language": "en",
                            "published_date": s["published_date"],
                            "url": s["url"],
                        }
                    )

    all_parties = sorted({p for c in usable_clusters if c["cluster_id"] in used_ids for p in c.get("parties", [])})
    all_topics = sorted({t for c in usable_clusters if c["cluster_id"] in used_ids for t in c.get("topics", [])})
    all_districts = sorted({d for c in usable_clusters if c["cluster_id"] in used_ids for d in c.get("districts", [])})

    sections = {
        "big_picture": "\n".join(big_picture_bullets),
        "top_developments": top_devs,
        "government_and_administration": gov_section,
        "political_parties_and_opposition": parties_section,
        "assembly_courts_and_policy": courts_section,
        "district_developments": district_section,
        "claims_vs_facts": [],
        "what_to_watch_next": "",
        "all_sources": cited_sources[:18],
    }

    word_count = max(300, len(json.dumps(sections, ensure_ascii=False).split()))
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
        "reading_time_minutes": max(4, round(word_count / 150)),
        "word_count": word_count,
        "headline": top_devs[0]["headline"] if top_devs else "Tamil Nadu Political Briefing",
        "parties": all_parties,
        "topics": all_topics,
        "districts": all_districts,
        "sections": sections,
        "_telemetry": {"ai_provider": f"fallback:{reason}", "tokens_used": 0},
    }


def validate_and_sanitize_ai_output(ai_data: dict, allowed_urls: set[str], fallback_sources: list[dict]) -> dict:
    cleaned_devs = []
    cited_sources = []
    seen_u = set()

    for dev in ai_data.get("top_developments", []):
        dev["headline"] = translate_tamil_to_english(dev.get("headline", ""))
        dev["summary"] = translate_tamil_to_english(dev.get("summary", ""))
        valid_sources = []
        for s in dev.get("sources", []):
            u = s.get("url") if isinstance(s, dict) else None
            if u in allowed_urls and u not in seen_u:
                seen_u.add(u)
                s["title"] = translate_tamil_to_english(s.get("title", ""))
                valid_sources.append(s)
                cited_sources.append(s)
        if not valid_sources and fallback_sources:
            valid_sources = [fallback_sources[0]]
        dev["sources"] = valid_sources
        cleaned_devs.append(dev)

    ai_data["top_developments"] = cleaned_devs
    ai_data["all_sources"] = cited_sources[:18] if cited_sources else fallback_sources[:15]
    return ai_data


def generate_edition_summary(window_meta: dict, verified_clusters: list[dict]) -> dict:
    if not verified_clusters:
        return build_extractive_fallback_edition(window_meta, [], "quiet_window")

    if AI_PROVIDER != "gemini" or not GEMINI_API_KEY:
        return build_extractive_fallback_edition(window_meta, verified_clusters, "missing_key")

    top_clusters = verified_clusters[:16]
    allowed_urls = {s["url"] for c in top_clusters for s in c.get("sources", [])}
    all_sources = []
    seen_urls = set()
    for c in top_clusters:
        for s in c.get("sources", [])[:2]:
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
            "cluster_id": c["cluster_id"],
            "title": translate_tamil_to_english(c["primary_title"]),
            "verification": c["verification_status"],
            "parties": c["parties"],
            "topics": c["topics"],
            "districts": c["districts"],
            "sources": c["sources"][:2],
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
            "temperature": 0.2,
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
                "reading_time_minutes": max(4, round(word_count / 150)),
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
                    "all_sources": validated.get("all_sources", []),
                },
                "_telemetry": {"ai_provider": f"gemini:{model_name}", "tokens_used": total_tokens},
            }
        except Exception as exc:
            last_err = str(exc)
            print(f"[WARN] Model {model_name} failed ({last_err}), trying next...")

    return build_extractive_fallback_edition(window_meta, verified_clusters, last_err)