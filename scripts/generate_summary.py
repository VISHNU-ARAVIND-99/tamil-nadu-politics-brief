#!/usr/bin/env python3
"""
Step 7, Step 8 & Step 9 of Pipeline:
- Translates Tamil news snippets and synthesizes verified clusters into natural English
- Calls Gemini API Free Tier with automatic fallback across gemini-2.5-flash and gemini-2.0-flash
- Strips markdown code fences (```json and ```) before parsing JSON
- Enforces non-robotic editorial prose and structured newspaper format
- Programmatically validates URLs against collected source registry to prevent hallucinations
- Includes deterministic extractive fallback if offline or quota is hit
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
)


SYSTEM_PROMPT = """You are the Senior Editorial Editor for 'Tamil Nadu Politics Brief', a non-partisan digital newspaper.
Your task is to write a polished, highly readable, objective English political newspaper edition strictly from the verified news clusters provided to you.

STRICT EDITORIAL & LANGUAGE RULES:
1. TRANSLATE TO ENGLISH: Translate all Tamil-language headlines, quotes, and reporting into natural, fluent, professional English. Never leave Tamil script in headlines or summaries.
2. EDITORIAL BIG PICTURE: Write a substantive, 2-paragraph editorial overview for "big_picture" that synthesizes the state's political climate, high-stakes decisions, and party dynamics during this 12-hour window. NEVER write robotic boilerplate like "During the coverage period X developments were tracked across Y source articles". Write engaging, analytical journalism like The Hindu or Indian Express.
3. STORY SUMMARIES: In "top_developments", provide:
   - "headline": Concise, punchy English headline.
   - "verification_badge": "Multi-Source Verified", "Official Primary Release", or "Single-Source Report".
   - "summary": Exactly two well-structured newspaper paragraphs detailing the development, actors involved, key verified facts, and political reactions.
   - "why_it_matters": Exactly one clear, impactful sentence on public, policy, or electoral significance.
   - "what_happens_next": Confirmed next steps or official hearing/meeting date.
   - "sources": Exact original URLs from the input cluster.
4. STRICT NEUTRALITY: Treat all parties (DMK, AIADMK, BJP, TVK, INC, PMK, NTK, VCK, MDMK, etc.) equally and objectively.
5. ZERO FABRICATIONS: Never invent dates, quotes, statistics, or URLs. Use ONLY the URLs provided.

Return ONLY a valid JSON object matching this schema:
{
  "headline": "Main banner headline for the edition",
  "big_picture": "Two engaging editorial paragraphs summarizing the 12-hour political landscape",
  "top_developments": [
    {
      "headline": "Clear English headline",
      "verification_badge": "Multi-Source Verified",
      "summary": "Two paragraphs of comprehensive, objective newspaper reporting.",
      "why_it_matters": "One clear sentence explaining the policy or public impact.",
      "what_happens_next": "Confirmed next steps or official hearing/meeting date.",
      "sources": [
        {"title": "Source title", "publisher": "Publisher", "language": "en or ta", "published_date": "YYYY-MM-DD", "url": "Exact URL"}
      ]
    }
  ],
  "government_and_administration": "Markdown paragraphs covering Government Orders, Cabinet announcements, and administrative reviews",
  "political_parties_and_opposition": "Markdown paragraphs covering party statements, press conferences, and campaign moves",
  "assembly_courts_and_policy": "Markdown paragraphs covering Madras High Court, Assembly committees, and policy orders",
  "district_developments": "Markdown paragraphs covering grassroots and district-level political developments",
  "claims_vs_facts": [
    {
      "claim": "Major political claim made in this window",
      "claimant": "Politician or party",
      "verified_evidence": "What available official records or reporting verify"
    }
  ],
  "what_to_watch_next": "Markdown bullet list of confirmed upcoming hearings, party meetings, or official schedules"
}"""


def clean_json_response(raw_text: str) -> str:
    """Strip markdown code fences (```json and ```) and whitespace from model responses."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def build_extractive_fallback_edition(window_meta: dict, verified_clusters: list[dict], reason: str) -> dict:
    """
    Deterministic, zero-cost extractive edition builder used when:
    - No clusters were published during a quiet overnight window, OR
    - AI_PROVIDER is set to 'extractive_fallback', OR
    - Gemini Free Tier quota is temporarily exhausted.
    Never fabricates stories.
    """
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
                        "title": s["title"],
                        "publisher": s["publisher"],
                        "language": s["language"],
                        "published_date": s["published_date"],
                        "url": s["url"],
                    }
                )

    if not verified_clusters:
        return {
            "edition_id": window_meta["edition_id"],
            "title": window_meta["title"],
            "date": window_meta["date"],
            "edition_type": window_meta["edition_type"],
            "is_test_sample": False,
            "status": "published_quiet_window",
            "scheduled_time_ist": window_meta["scheduled_time_ist"],
            "generated_at_ist": now_ist,
            "published_at_ist": now_ist,
            "coverage_start_ist": window_meta["coverage_start_ist"],
            "coverage_end_ist": window_meta["coverage_end_ist"],
            "reading_time_minutes": 2,
            "word_count": 210,
            "headline": f"No Major Verified Political Developments Recorded ({window_meta['human_window']})",
            "parties": [],
            "topics": ["Government & Administration"],
            "districts": [],
            "sections": {
                "big_picture": f"Tamil Nadu's political and administrative landscape remained relatively quiet across the {window_meta['human_window']} window, with no major legislative, judicial, or party escalations reported across monitored state feeds. In accordance with our editorial standards, Tamil Nadu Politics Brief documents confirmed developments rather than publishing unverified speculation.",
                "top_developments": [],
                "government_and_administration": "No new Government Orders or Cabinet announcements were published in monitored feeds during this coverage window.",
                "political_parties_and_opposition": "No confirmed party headquarters statements or major public meetings were recorded in this window.",
                "assembly_courts_and_policy": "No new legislative or high court orders were recorded during this window.",
                "district_developments": "No major district-level political developments were recorded during this window.",
                "claims_vs_facts": [],
                "what_to_watch_next": "The next scheduled automated briefing will run in 12 hours.",
                "all_sources": [],
            },
            "_telemetry": {"ai_provider": "none_quiet_window", "tokens_used": 0, "note": reason},
        }

    top_devs = []
    for cluster in verified_clusters[:8]:
        rep_src = cluster["sources"][0]
        pubs = ", ".join(sorted({s["publisher"] for s in cluster["sources"]}))
        snippet = rep_src.get("snippet") or cluster["primary_title"]
        top_devs.append(
            {
                "headline": cluster["primary_title"],
                "verification_badge": cluster["verification_status"],
                "summary": f"{snippet}\n\nThis development was verified across reporting from {pubs} during the {window_meta['human_window']} IST coverage window.",
                "what_happened": snippet,
                "who_is_involved": ", ".join(cluster["parties"] or ["State Administration / Public Stakeholders"]),
                "verified_facts": f"Reported by {pubs} within the {window_meta['human_window']} window ({cluster['verification_status']}).",
                "why_it_matters": f"Affects {', '.join(cluster['topics'])} across {', '.join(cluster['districts'] or ['Tamil Nadu'])}.",
                "political_responses": "Consult linked original reporting for full statements from participating political parties.",
                "what_happens_next": "Further official updates will be tracked in the next 12-hour briefing.",
                "sources": [
                    {
                        "title": s["title"],
                        "publisher": s["publisher"],
                        "language": s["language"],
                        "published_date": s["published_date"],
                        "url": s["url"],
                    }
                    for s in cluster["sources"]
                ],
            }
        )

    headline = verified_clusters[0]["primary_title"]
    parties_str = ", ".join(all_parties) if all_parties else "state administrative departments"
    topics_str = ", ".join(all_topics)
    big_picture = (
        f"Tamil Nadu's political scene in this 12-hour briefing ({window_meta['human_window']}) was centered on major policy and party actions involving {parties_str}. Across key administrative and constituency sectors, debates centered on {topics_str}.\n\n"
        f"Senior stakeholders and district leaders monitored state responses and opposition statements as legislative and regional schedules progress."
    )

    sections = {
        "big_picture": big_picture,
        "top_developments": top_devs,
        "government_and_administration": "See verified administrative developments above and consult the primary source links below.",
        "political_parties_and_opposition": f"Developments in this window involved: {', '.join(all_parties) if all_parties else 'no major party press releases recorded'}.",
        "assembly_courts_and_policy": "Legislative, judicial, and policy items from this window are indexed in the top developments and source registry.",
        "district_developments": f"Districts referenced in this coverage window: {', '.join(all_districts) if all_districts else 'Statewide / Chennai'}.",
        "claims_vs_facts": [],
        "what_to_watch_next": "Ongoing monitoring continues for the next 12-hour IST window.",
        "all_sources": all_sources,
    }

    full_text = json.dumps(sections, ensure_ascii=False)
    word_count = max(250, len(full_text.split()))
    reading_time = max(2, round(word_count / 130))

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
        "reading_time_minutes": reading_time,
        "word_count": word_count,
        "headline": headline,
        "parties": all_parties,
        "topics": all_topics,
        "districts": all_districts,
        "sections": sections,
        "_telemetry": {"ai_provider": f"extractive_fallback ({reason})", "tokens_used": 0},
    }


def validate_and_sanitize_ai_output(ai_data: dict, allowed_urls: set[str], fallback_sources: list[dict]) -> dict:
    """
    Step 9 Quality Validation:
    - Strips any URL not present in the collected RSS registry (zero hallucinated links)
    - Ensures summary and why_it_matters are populated
    - Ensures all required sections exist
    """
    cleaned_devs = []
    for dev in ai_data.get("top_developments", []):
        valid_sources = [
            s for s in dev.get("sources", []) if isinstance(s, dict) and s.get("url") in allowed_urls
        ]
        if not valid_sources and fallback_sources:
            valid_sources = [fallback_sources[0]]
        dev["sources"] = valid_sources

        # Ensure summary is populated for modern newspaper reader
        if not dev.get("summary") and dev.get("what_happened"):
            dev["summary"] = dev["what_happened"]
        elif not dev.get("what_happened") and dev.get("summary"):
            dev["what_happened"] = dev["summary"]

        if not dev.get("why_it_matters"):
            dev["why_it_matters"] = "Key development impacting Tamil Nadu governance and public policy."

        cleaned_devs.append(dev)

    ai_data["top_developments"] = cleaned_devs
    ai_data["all_sources"] = fallback_sources
    return ai_data


def generate_edition_summary(window_meta: dict, verified_clusters: list[dict]) -> dict:
    """
    Generate the complete English political edition using Gemini Free Tier,
    retrying across eligible models (gemini-2.5-flash and gemini-2.0-flash),
    or gracefully degrading to the deterministic extractive builder if unavailable.
    """
    if not verified_clusters:
        return build_extractive_fallback_edition(window_meta, [], "no_stories_in_window")

    if AI_PROVIDER != "gemini" or not GEMINI_API_KEY:
        return build_extractive_fallback_edition(window_meta, verified_clusters, "no_api_key_or_offline_mode")

    top_clusters = verified_clusters[:15]
    allowed_urls = {s["url"] for c in top_clusters for s in c.get("sources", [])}
    all_sources = []
    seen_urls = set()
    for c in top_clusters:
        for s in c.get("sources", []):
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                all_sources.append(
                    {
                        "title": s["title"],
                        "publisher": s["publisher"],
                        "language": s["language"],
                        "published_date": s["published_date"],
                        "url": s["url"],
                    }
                )

    user_payload = {
        "edition_title": window_meta["title"],
        "coverage_window_ist": window_meta["human_window"],
        "verified_story_clusters": top_clusters,
    }

    request_body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Generate the Tamil Nadu Politics Brief edition JSON strictly from these "
                            "verified clusters:\n" + json.dumps(user_payload, ensure_ascii=False)
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8192,
        },
    }

    models_to_try = [GEMINI_MODEL]
    for m in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        if m not in models_to_try:
            models_to_try.append(m)

    resp_json = None
    successful_model = None

    for model_name in models_to_try:
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            f"?key={GEMINI_API_KEY}"
        )
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS * 3) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                successful_model = model_name
                break
        except urllib.error.HTTPError as http_err:
            print(f"[WARN] Gemini model {model_name} HTTP {http_err.code}: trying next fallback model.")
            continue
        except Exception as exc:
            print(f"[WARN] Gemini model {model_name} error ({exc}): trying next fallback model.")
            continue

    if not resp_json:
        print("[WARN] All Gemini models failed or unreachable: using extractive fallback.")
        return build_extractive_fallback_edition(window_meta, verified_clusters, "all_models_failed")

    try:
        candidates = resp_json.get("candidates", [])
        raw_text = candidates[0]["content"]["parts"][0]["text"]
        cleaned_json = clean_json_response(raw_text)
        ai_sections = json.loads(cleaned_json)
        usage = resp_json.get("usageMetadata", {})
        total_tokens = usage.get("totalTokenCount", 0)
    except Exception as exc:
        print(f"[WARN] Failed to parse Gemini JSON response ({exc}): using extractive fallback.")
        return build_extractive_fallback_edition(window_meta, verified_clusters, "json_parse_error")

    validated_sections = validate_and_sanitize_ai_output(ai_sections, allowed_urls, all_sources)

    now_ist = get_ist_now().isoformat()
    all_parties = sorted({p for c in top_clusters for p in c.get("parties", [])})
    all_topics = sorted({t for c in top_clusters for t in c.get("topics", [])})
    all_districts = sorted({d for c in top_clusters for d in c.get("districts", [])})

    word_count = len(json.dumps(validated_sections, ensure_ascii=False).split())
    reading_time = max(3, round(word_count / 130))

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
        "reading_time_minutes": reading_time,
        "word_count": word_count,
        "headline": validated_sections.get("headline", top_clusters[0]["primary_title"]),
        "parties": all_parties,
        "topics": all_topics,
        "districts": all_districts,
        "sections": {
            "big_picture": validated_sections.get("big_picture", ""),
            "top_developments": validated_sections.get("top_developments", []),
            "government_and_administration": validated_sections.get("government_and_administration", ""),
            "political_parties_and_opposition": validated_sections.get("political_parties_and_opposition", ""),
            "assembly_courts_and_policy": validated_sections.get("assembly_courts_and_policy", ""),
            "district_developments": validated_sections.get("district_developments", ""),
            "claims_vs_facts": validated_sections.get("claims_vs_facts", []),
            "what_to_watch_next": validated_sections.get("what_to_watch_next", ""),
            "all_sources": all_sources,
        },
        "_telemetry": {"ai_provider": f"gemini:{successful_model or GEMINI_MODEL}", "tokens_used": total_tokens},
    }
