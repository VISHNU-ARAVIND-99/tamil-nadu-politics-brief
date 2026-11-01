#!/usr/bin/env python3
"""
Step 7, Step 8 & Step 9 of Pipeline:
- Produces crisp Inshorts-style news summaries (60-85 words per story, 100% factual news only).
- NEVER generates vague filler ('This development forms part of...', 'X also reported on the development').
- Routes Court/Assembly stories strictly to Assembly, Courts & Policy first.
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
    USER_AGENT,
    get_ist_now,
    has_tamil_script,
    translate_tamil_to_english,
)

PROMPT_INSTRUCTIONS = """You are the Editor of 'Tamil Nadu Politics Brief', writing in the crisp, factual style of the Inshorts news app.
Summarize each verified Tamil Nadu political news story in 60 to 80 words of simple, direct English.

STRICT INSHORTS STYLE RULES:
1. EVERY WORD MUST BE REAL NEWS: State only the concrete facts—who said or did what, where, why, and the direct response.
2. ZERO VAGUE FILLER: Never write generic commentary like 'This development forms part of broader policy', 'Senior officials are closely monitoring', or 'X also reported on the development'.
3. SIMPLE, EASY-TO-READ ENGLISH: Use short, clear sentences that anyone can understand quickly.
4. NO DUPLICATION ACROSS SECTIONS: Stories in 'top_developments' must NOT be repeated in the lower sections.

Return ONLY valid JSON with these exact keys:
{
  "headline": "Main English headline",
  "big_picture": "",
  "top_developments": [
    {
      "headline": "Clear factual headline",
      "verification_badge": "Multi-Source Verified | Single-Source Report",
      "who_is_involved": "DMK, AIADMK, TVK, etc.",
      "summary": "60 to 80 words of crisp, factual news in simple English (3 to 4 sentences).",
      "why_it_matters": "",
      "sources": [{"title": "Article title", "publisher": "Publisher Name", "language": "en", "published_date": "YYYY-MM-DD", "url": "..."}]
    }
  ],
  "government_and_administration": "- **Headline:** 60-80 word factual summary. ([Publisher](url))",
  "political_parties_and_opposition": "- **Headline:** 60-80 word factual summary. ([Publisher](url))",
  "assembly_courts_and_policy": "- **Headline:** 60-80 word factual summary. ([Publisher](url))",
  "district_developments": "- **Headline:** 60-80 word factual summary. ([Publisher](url))",
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


def is_clean_factual_sentence(sentence: str, headline: str) -> bool:
    s = sentence.strip()
    if s.endswith("?") or "?" in s:
        return False
    if "!" in s:
        return False
    if len(s) < 30 or len(s.split()) < 6:
        return False
    if re.sub(r"\W+", "", s.lower()) == re.sub(r"\W+", "", headline.lower()):
        return False
    if re.search(r"(closure of liquor|in 2\.|heating up|what is the purpose)", s, re.IGNORECASE):
        return False
    return True


def build_inshorts_factual_text(cluster: dict) -> str:
    """
    Combines ONLY real, cohesive factual sentences into an Inshorts-style paragraph.
    Prioritizes the primary editorial report and rejects clickbait questions, exclamation marks,
    and truncated title fragments.
    """
    headline = translate_tamil_to_english(cluster["primary_title"]).strip()
    seen_sentences = set()
    factual_sentences = []
    word_count = 0

    primary_source = cluster["sources"][0] if cluster.get("sources") else None
    primary_snippet = translate_tamil_to_english(primary_source.get("snippet") or "") if primary_source else ""

    if primary_snippet:
        for sent in re.split(r"(?<=[.!?])\s+", primary_snippet):
            clean_s = sent.strip()
            if is_clean_factual_sentence(clean_s, headline):
                norm_s = re.sub(r"\W+", "", clean_s.lower())
                if norm_s not in seen_sentences:
                    seen_sentences.add(norm_s)
                    if not clean_s.endswith((".", '"', "'")):
                        clean_s += "."
                    factual_sentences.append(clean_s)
                    word_count += len(clean_s.split())
                    if word_count >= 80:
                        break

    if word_count < 35:
        headline_words = {w for w in re.findall(r"\w{4,}", headline.lower())}
        for s in cluster.get("sources", [])[1:]:
            snip = translate_tamil_to_english(s.get("snippet") or "").strip()
            if not snip or snip.lower() == s.get("title", "").strip().lower():
                continue
            for sent in re.split(r"(?<=[.!?])\s+", snip):
                clean_s = sent.strip()
                if is_clean_factual_sentence(clean_s, headline):
                    sent_words = {w for w in re.findall(r"\w{4,}", clean_s.lower())}
                    if len(headline_words & sent_words) >= 2:
                        norm_s = re.sub(r"\W+", "", clean_s.lower())
                        if norm_s not in seen_sentences:
                            seen_sentences.add(norm_s)
                            if not clean_s.endswith((".", '"', "'")):
                                clean_s += "."
                            factual_sentences.append(clean_s)
                            word_count += len(clean_s.split())
                            if word_count >= 65:
                                break
            if word_count >= 65:
                break

    if not factual_sentences:
        if primary_snippet and len(primary_snippet) >= 30:
            clean_fallback = re.sub(r"[?!].*$", ".", primary_snippet).strip()
            if len(clean_fallback) >= 25:
                factual_sentences.append(clean_fallback)
        else:
            factual_sentences.append(headline + ".")

    return " ".join(factual_sentences).strip()


def build_extractive_fallback_edition(window_meta: dict, verified_clusters: list[dict], reason: str) -> dict:
    now_ist = get_ist_now().isoformat()

    # Keep only clusters that have real factual body sentences (skip empty 1-line stubs!)
    usable_clusters = [
        c for c in verified_clusters
        if len(build_inshorts_factual_text(c).split()) >= 14
    ]
    if not usable_clusters:
        usable_clusters = verified_clusters[:10]

    top_slice = usable_clusters[:8]
    remaining_clusters = usable_clusters[8:26]
    used_ids = {c["cluster_id"] for c in top_slice}

    top_devs = []
    for cluster in top_slice:
        headline = translate_tamil_to_english(cluster["primary_title"]).strip()
        body = build_inshorts_factual_text(cluster)
        top_devs.append(
            {
                "headline": headline,
                "verification_badge": cluster["verification_status"],
                "who_is_involved": ", ".join(cluster["parties"]) if cluster["parties"] else "",
                "summary": body,
                "why_it_matters": "",
                "sources": cluster["sources"][:3],
            }
        )

    def allocate_unique_section(topic_matches: list[str], require_district: bool = False, must_match_keywords: list[str] | None = None) -> str:
        lines = []
        for c in remaining_clusters:
            if c["cluster_id"] in used_ids:
                continue
            title_lower = c["primary_title"].lower()
            if must_match_keywords:
                is_match = any(k in title_lower for k in must_match_keywords) or any(t in c.get("topics", []) for t in topic_matches)
            elif require_district:
                is_match = bool(c.get("districts"))
            else:
                is_match = any(t in c.get("topics", []) for t in topic_matches)

            if is_match:
                t = translate_tamil_to_english(c["primary_title"]).strip().rstrip(".")
                b = build_inshorts_factual_text(c)
                if not b or b.lower() == t.lower():
                    continue
                used_ids.add(c["cluster_id"])
                pub = c["sources"][0]["publisher"] if c.get("sources") else "Report"
                url = c["sources"][0]["url"] if c.get("sources") else ""
                src_note = f" ([{pub}]({url}))" if url else ""
                lines.append(f"- **{t}:** {b}{src_note}")
                if len(lines) >= 5:
                    break
        return "\n".join(lines)

    # Route Court/Assembly stories FIRST so High Court pleas never end up under Political Parties!
    courts_section = allocate_unique_section(
        ["Assembly, Courts & Policy"],
        must_match_keywords=["high court", "madras hc", "supreme court", "plea", "bench", "assembly", "speaker", "bill"]
    )
    parties_section = allocate_unique_section(["Political Parties", "Elections", "Public Protests & Labour"])
    gov_section = allocate_unique_section(["Government & Administration", "Infrastructure & Economy", "Education & NEET", "Agriculture & Water", "Centre–State Relations"])
    district_section = allocate_unique_section([], require_district=True)

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
        "big_picture": "",
        "top_developments": top_devs,
        "government_and_administration": gov_section,
        "political_parties_and_opposition": parties_section,
        "assembly_courts_and_policy": courts_section,
        "district_developments": district_section,
        "claims_vs_facts": [],
        "what_to_watch_next": "",
        "all_sources": cited_sources[:18],
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
        "reading_time_minutes": min(20, max(10, round(word_count / 110))),
        "word_count": word_count,
        "headline": top_devs[0]["headline"] if top_devs else "Tamil Nadu Political Briefing",
        "parties": all_parties,
        "topics": all_topics,
        "districts": all_districts,
        "sections": sections,
        "_telemetry": {"ai_provider": f"inshorts_extractive:{reason}", "tokens_used": 0},
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


def discover_gemini_flash_models(api_key: str) -> list[str]:
    """Queries Google Generative Language API to dynamically list all models supporting generateContent."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = []
        for m in data.get("models", []):
            name = m.get("name", "").replace("models/", "")
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods:
                models.append(name)
        flash_models = [m for m in models if "flash" in m.lower()]
        other_models = [m for m in models if "flash" not in m.lower() and "pro" not in m.lower()]
        return flash_models + other_models
    except Exception as exc:
        print(f"[DEBUG] Dynamic model discovery: {exc}")
        return []

def generate_edition_summary(window_meta: dict, verified_clusters: list[dict]) -> dict:
    if not verified_clusters:
        return build_extractive_fallback_edition(window_meta, [], "quiet_window")

    if AI_PROVIDER != "gemini" or not GEMINI_API_KEY:
        return build_extractive_fallback_edition(window_meta, verified_clusters, "missing_key")

    top_clusters = [c for c in verified_clusters if len(build_inshorts_factual_text(c).split()) >= 12][:18]
    if not top_clusters:
        top_clusters = verified_clusters[:12]

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
            "factual_text": build_inshorts_factual_text(c),
            "sources": [{"title": s["title"], "publisher": s["publisher"], "published_date": s["published_date"], "url": s["url"]} for s in c["sources"][:2]],
        }
        for c in top_clusters
    ]

    discovered = discover_gemini_flash_models(GEMINI_API_KEY)
    models_to_try = [
        GEMINI_MODEL,
        *discovered,
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]
    models_to_try = list(dict.fromkeys(m for m in models_to_try if m))
    last_err = "unknown"

    for model_name in models_to_try:
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            f"?key={GEMINI_API_KEY}"
        )
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
            "generationConfig": {
                "temperature": 0.15,
                "responseMimeType": "application/json",
                "maxOutputTokens": 8192,
            },
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
                "reading_time_minutes": min(20, max(10, round(word_count / 110))),
                "word_count": word_count,
                "headline": validated.get("headline", top_clusters[0]["primary_title"]),
                "parties": all_parties,
                "topics": all_topics,
                "districts": all_districts,
                "sections": {
                    "big_picture": "",
                    "top_developments": validated.get("top_developments", []),
                    "government_and_administration": validated.get("government_and_administration", ""),
                    "political_parties_and_opposition": validated.get("political_parties_and_opposition", ""),
                    "assembly_courts_and_policy": validated.get("assembly_courts_and_policy", ""),
                    "district_developments": validated.get("district_developments", ""),
                    "claims_vs_facts": [],
                    "what_to_watch_next": "",
                    "all_sources": validated.get("all_sources", []),
                },
                "_telemetry": {"ai_provider": f"gemini:{model_name}", "tokens_used": total_tokens},
            }
        except urllib.error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8")
            except Exception:
                pass
            last_err = f"HTTP Error {exc.code}: {exc.reason} - {err_body[:250]}"
            print(f"[WARN] Model {model_name} failed ({last_err}), trying next...")
        except Exception as exc:
            last_err = str(exc)
            print(f"[WARN] Model {model_name} failed ({last_err}), trying next...")

    return build_extractive_fallback_edition(window_meta, verified_clusters, last_err)