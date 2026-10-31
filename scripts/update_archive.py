#!/usr/bin/env python3
"""
Step 10 & Step 11 Helper:
- Renders the Markdown twin of an edition
- Saves both .json and .md files into archive/YYYY/MM/
- Updates data/archive-index.json and data/latest-editions.json without losing past editions
"""

import json
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

from scripts.config import (
    ARCHIVE_DIR,
    ARCHIVE_INDEX_FILE,
    LATEST_EDITIONS_FILE,
    PIPELINE_LOGS_FILE,
    get_ist_now,
)


def render_edition_markdown(edition: dict) -> str:
    """Convert structured edition JSON into a clean, permanent Markdown document."""
    sec = edition.get("sections", {})
    lines = [
        f"# {edition['title']}",
        "",
        f"- **Edition ID:** `{edition['edition_id']}`",
        f"- **Date:** {edition['date']} ({edition['edition_type'].capitalize()} Edition)",
        f"- **Coverage Period:** {edition['coverage_start_ist']} to {edition['coverage_end_ist']}",
        f"- **Scheduled Time (IST):** {edition['scheduled_time_ist']}",
        f"- **Generated At (IST):** {edition['generated_at_ist']}",
        f"- **Published At (IST):** {edition['published_at_ist']}",
        f"- **Estimated Reading Time:** {edition['reading_time_minutes']} minutes",
        "",
        f"## Headline: {edition['headline']}",
        "",
        "## B. The Big Picture",
        sec.get("big_picture", ""),
        "",
        "## C. Top Political Developments",
    ]

    for idx, dev in enumerate(sec.get("top_developments", []), start=1):
        lines.extend(
            [
                f"### {idx}. {dev.get('headline', '')}",
                f"- **Verification Status:** {dev.get('verification_badge', 'Verified')}",
                f"- **What happened?** {dev.get('what_happened', '')}",
                f"- **Who is involved?** {dev.get('who_is_involved', '')}",
                f"- **What are the verified facts?** {dev.get('verified_facts', '')}",
                f"- **Why does it matter?** {dev.get('why_it_matters', '')}",
                f"- **Political responses:** {dev.get('political_responses', '')}",
                f"- **What happens next?** {dev.get('what_happens_next', '')}",
            ]
        )
        src_links = [f"[{s['publisher']}: {s['title']}]({s['url']})" for s in dev.get("sources", [])]
        lines.append(f"- **Sources:** {' | '.join(src_links)}")
        lines.append("")

    lines.extend(
        [
            "## D. Government and Administration",
            sec.get("government_and_administration", ""),
            "",
            "## E. Political Parties and Opposition",
            sec.get("political_parties_and_opposition", ""),
            "",
            "## F. Assembly, Courts, and Policy",
            sec.get("assembly_courts_and_policy", ""),
            "",
            "## G. District-Level Developments",
            sec.get("district_developments", ""),
            "",
            "## H. Claims Versus Verified Facts",
        ]
    )

    for cf in sec.get("claims_vs_facts", []):
        lines.extend(
            [
                f"- **Claim ({cf.get('claimant', 'Statement')}):** {cf.get('claim', '')}",
                f"  - **Verified Evidence:** {cf.get('verified_evidence', '')}",
            ]
        )

    lines.extend(
        [
            "",
            "## I. What to Watch Next",
            sec.get("what_to_watch_next", ""),
            "",
            "## J. Sources and Further Reading",
        ]
    )

    for s in sec.get("all_sources", []):
        lines.append(f"- [{s['title']}]({s['url']}) — *{s['publisher']}* ({s['published_date']})")

    return "\n".join(lines) + "\n"


def save_edition_and_update_indexes(
    edition: dict,
    archive_dir: Path = ARCHIVE_DIR,
    archive_index_file: Path = ARCHIVE_INDEX_FILE,
    latest_editions_file: Path = LATEST_EDITIONS_FILE,
) -> dict:
    """Save Markdown & JSON files and atomically update archive-index.json and latest-editions.json."""
    year, month, _ = edition["date"].split("-")
    target_folder = archive_dir / year / month
    target_folder.mkdir(parents=True, exist_ok=True)

    edition_id = edition["edition_id"]
    json_rel_path = f"archive/{year}/{month}/{edition_id}.json"
    md_rel_path = f"archive/{year}/{month}/{edition_id}.md"

    json_full_path = archive_dir / year / month / f"{edition_id}.json"
    md_full_path = archive_dir / year / month / f"{edition_id}.md"

    # Strip internal telemetry before saving edition file
    clean_edition = {k: v for k, v in edition.items() if not k.startswith("_")}
    clean_edition["published_at_ist"] = get_ist_now().isoformat()

    with open(json_full_path, "w", encoding="utf-8") as f:
        json.dump(clean_edition, f, indent=2, ensure_ascii=False)

    md_content = render_edition_markdown(clean_edition)
    with open(md_full_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Update archive-index.json (preserving all past editions)
    if archive_index_file.exists():
        with open(archive_index_file, "r", encoding="utf-8") as f:
            index_data = json.load(f)
    else:
        index_data = {"total_editions": 0, "last_updated_ist": "", "editions": []}

    summary_blob = " ".join(
        [
            clean_edition["headline"],
            clean_edition["sections"].get("big_picture", ""),
            " ".join(d.get("headline", "") for d in clean_edition["sections"].get("top_developments", [])),
        ]
    )

    index_entry = {
        "edition_id": edition_id,
        "title": clean_edition["title"],
        "date": clean_edition["date"],
        "edition_type": clean_edition["edition_type"],
        "is_test_sample": clean_edition.get("is_test_sample", False),
        "status": clean_edition["status"],
        "published_at_ist": clean_edition["published_at_ist"],
        "coverage_window": f"{clean_edition['coverage_start_ist']} to {clean_edition['coverage_end_ist']}",
        "reading_time_minutes": clean_edition["reading_time_minutes"],
        "headline": clean_edition["headline"],
        "summary_text": summary_blob[:900],
        "parties": clean_edition["parties"],
        "topics": clean_edition["topics"],
        "districts": clean_edition["districts"],
        "url": f"edition.html?id={edition_id}",
        "json_path": json_rel_path,
    }

    existing_editions = [e for e in index_data.get("editions", []) if e.get("edition_id") != edition_id]
    existing_editions.append(index_entry)
    existing_editions.sort(key=lambda x: x["published_at_ist"], reverse=True)

    index_data["editions"] = existing_editions
    index_data["total_editions"] = len(existing_editions)
    index_data["last_updated_ist"] = clean_edition["published_at_ist"]

    with open(archive_index_file, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)

    # Update latest-editions.json
    if latest_editions_file.exists():
        with open(latest_editions_file, "r", encoding="utf-8") as f:
            latest_data = json.load(f)
    else:
        latest_data = {"morning": None, "evening": None}

    latest_card = {
        "edition_id": edition_id,
        "title": clean_edition["title"],
        "date": clean_edition["date"],
        "edition_type": clean_edition["edition_type"],
        "is_test_sample": clean_edition.get("is_test_sample", False),
        "status": clean_edition["status"],
        "scheduled_time_ist": clean_edition["scheduled_time_ist"],
        "generated_at_ist": clean_edition["generated_at_ist"],
        "published_at_ist": clean_edition["published_at_ist"],
        "coverage_start_ist": clean_edition["coverage_start_ist"],
        "coverage_end_ist": clean_edition["coverage_end_ist"],
        "reading_time_minutes": clean_edition["reading_time_minutes"],
        "word_count": clean_edition["word_count"],
        "headline": clean_edition["headline"],
        "big_picture_excerpt": clean_edition["sections"].get("big_picture", "")[:360] + "...",
        "parties": clean_edition["parties"],
        "topics": clean_edition["topics"],
        "districts": clean_edition["districts"],
        "json_path": json_rel_path,
        "md_path": md_rel_path,
        "url": f"edition.html?id={edition_id}",
    }

    latest_data[clean_edition["edition_type"]] = latest_card

    # Determine which edition is the latest chronologically
    morning_card = latest_data.get("morning")
    evening_card = latest_data.get("evening")
    if morning_card and evening_card:
        if evening_card["date"] > morning_card["date"]:
            active_card = evening_card
        elif morning_card["date"] > evening_card["date"]:
            active_card = morning_card
        else:
            # Same date: evening brief is chronologically newer
            active_card = evening_card
    else:
        active_card = evening_card or morning_card or latest_card

    latest_data["last_updated_ist"] = clean_edition["published_at_ist"]
    latest_data["system_status"] = "operational"
    latest_data["status_message"] = (
        f"Latest {active_card['edition_type']} edition ({active_card['date']}) published. "
        f"Updated at {clean_edition['published_at_ist']}."
    )

    with open(latest_editions_file, "w", encoding="utf-8") as f:
        json.dump(latest_data, f, indent=2, ensure_ascii=False)

    return {"json_path": json_rel_path, "md_path": md_rel_path}


def record_pipeline_log(log_entry: dict, logs_file: Path = PIPELINE_LOGS_FILE) -> None:
    """Append pipeline telemetry log and cap history at 100 entries to keep repo lean."""
    if logs_file.exists():
        try:
            with open(logs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"runs": []}
    else:
        data = {"runs": []}

    runs = data.get("runs", [])
    runs.insert(0, log_entry)
    data["runs"] = runs[:100]

    with open(logs_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
