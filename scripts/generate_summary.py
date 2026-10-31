#!/usr/bin/env python3
"""
Step 7, Step 8 & Step 9 of Pipeline:
- Translates Tamil news into natural English using Gemini Free Tier
- Retries across active free models (gemini-2.0-flash, gemini-1.5-flash, gemini-2.5-flash)
- Disables thinking token overhead where applicable so JSON responses never truncate
- Eliminates robotic fallback boilerplate even when running without an API key
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

PROMPT_INSTRUCTIONS = """You are the Editor-in-Chief of 'Tamil Nadu Politics Brief', an English digital newspaper.
Write today's edition in clear, simple, neutral English strictly from the verified news clusters below.

STRICT RULES:
1. ENGLISH ONLY: Translate all Tamil headlines, quotes, and snippets into natural English. Do not leave Tamil script in headlines or story summaries.
2. NO ROBOTIC COUNTS OR LISTS: In 'big_picture', write 2 engaging newspaper paragraphs summarizing the top 3-4 actual political developments. Never write generic lists of party names or topic categories.
3. CLEAN STORYTELLING: For each story in 'top_developments' (pick top 6-8 political stories), provide:
   - 'headline': A clear, non-sensational English headline.
   - 'verification_badge': 'Multi-Source Verified' or 'Single-Source Report'.
   - 'who_is_involved': Specific leaders, parties, or departments involved.
   - 'summary': 1 to 2 paragraphs explaining what happened, the context, and political reactions.
   - 'why_it_matters': One specific sentence explaining the impact on Tamil Nadu politics or citizens.
   - 'sources': Exact URLs from the input cluster.

Return ONLY valid JSON with these exact keys:
{
  "headline": "...",
  "big_picture": "...",
  "top_developments": [
    {
      "headline": "...",
      "verification_badge": "...",
      "who_is_involved": "...",
      "summary": "...",
      "why_it_matters": "...",
      "sources": [{"title": "...", "publisher": "...", "language": "en", "published_date": "YYYY-MM-DD", "url": "..."}]
    }
  ],
  "government_and_administration": "...",
  "political_parties_and_opposition": "...",
  "assembly_courts_and_policy": "...",
  "district_developments": "...",
  "claims_vs_facts": [{"claim": "...", "claimant": "...", "verified_evidence": "..."}],
  "what_to_watch_next": "..."
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
                all_sources.append(s)

    top_devs = []
    for cluster in verified_clusters[:8]:
        rep_src = cluster["sources"][0]
        snippet = (rep_src.get("snippet") or "").strip()
        headline = cluster["primary_title"].strip()
        if snippet.lower() == headline.lower():
            snippet = ""
        top_devs.append(
            {
                "headline": headline,
                "verification_badge": cluster["verification_status"],
                "who_is_involved": ", ".join(cluster["parties"]) if cluster["parties"] else "",
                "summary": snippet,
                "why_it_matters": "",
                "sources": cluster["sources"],
            }
        )

    lead_headlines = [c["primary_title"] for c in verified_clusters[:4]]
    big_picture = (
        "Key developments in this 12-hour briefing include: "
        + "; ".join(lead_headlines)
        + "."
        if lead_headlines
        else "No major verified political developments were recorded during this 12-hour window."
    )

    sections = {
        "big_picture": big_picture,
        "top_developments": top_devs,
        "government_and_administration": "Refer to the top developments and linked official releases below for departmental updates.",
        "political_parties_and_opposition": "Refer to the top developments above for statements from DMK, AIADMK, BJP, TVK, NTK, and allied parties.",
        "assembly_courts_and_policy": "Judicial and legislative developments from this window are listed in the primary source links below.",
        "district_developments": f"Regional reporting in this window covered: {', '.join(all_districts) if all_districts else 'Chennai and major district headquarters'}.",
        "claims_vs_facts": [],
        "what_to_watch_next": "Next automated edition publishes at the next 6:00 AM / 6:00 PM IST cycle.",
        "all_sources": all_sources,
    }

    word_count = max(200, len(json.dumps(sections, ensure_ascii=False).split()))
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
        "reading_time_minutes": max(3, round(word_count / 140)),
        "word_count": word_count,
        "headline": verified_clusters[0]["primary_title"] if verified_clusters else "Tamil Nadu Political Briefing",
        "parties": all_parties,
        "topics": all_topics,
        "districts": all_districts,
        "sections": sections,
        "_telemetry": {"ai_provider": f"fallback:{reason}", "tokens_used": 0},
    }


def validate_and_sanitize_ai_output(ai_data: dict, allowed_urls: set[str], fallback_sources: list[dict]) -> dict:
    cleaned_devs = []
    for dev in ai_data.get("top_developments", []):
        valid_sources = []
        seen_u = set()
        for s in dev.get("sources", []):
            u = s.get("url") if isinstance(s, dict) else None
            if u in allowed_urls and u not in seen_u:
                seen_u.add(u)
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
        print("[WARN] GEMINI_API_KEY missing. Using clean extractive mode.")
        return build_extractive_fallback_edition(window_meta, verified_clusters, "missing_key")

    top_clusters = verified_clusters[:12]
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

    compact_clusters = [
        {
            "title": c["primary_title"],
            "verification": c["verification_status"],
            "parties": c["parties"],
            "topics": c["topics"],
            "districts": c["districts"],
            "sources": c["sources"][:3],
        }
        for c in top_clusters
    ]

    models_to_try = [GEMINI_MODEL, "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]
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

            print(f"[INFO] Successfully generated AI edition with {model_name} ({total_tokens} tokens).")
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
                "reading_time_minutes": max(4, round(word_count / 140)),
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
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8", errors="ignore")[:300]
            last_err = f"HTTP_{http_err.code}:{err_body}"
            print(f"[WARN] Model {model_name} HTTP error: {last_err}")
        except Exception as exc:
            last_err = str(exc)
            print(f"[WARN] Model {model_name} failed ({last_err}), trying next...")

    return build_extractive_fallback_edition(window_meta, verified_clusters, last_err)
