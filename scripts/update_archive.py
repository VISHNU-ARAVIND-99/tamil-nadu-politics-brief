#!/usr/bin/env python3
"""
Step 10 & Step 11 Helper:
- Renders the Markdown twin of an edition
- Saves both .json and .md files into archive/YYYY/MM/
- Updates data/archive-index.json and data/latest-editions.json with bulleted card excerpts
"""

import json
from pathlib import Path
from scripts.config import (
    ARCHIVE_DIR,
    ARCHIVE_INDEX_FILE,
    LATEST_EDITIONS_FILE,
    PIPELINE_LOGS_FILE,
    get_ist_now,
)


def render_edition_markdown(edition: dict) -> str:
    sec = edition.get("sections", {})
    lines = [
        f"# {edition['title']}",
        "",
        f"- **Edition ID:** `{edition['edition_id']}`",
        f"- **Date:** {edition['date']} ({edition['edition_type'].capitalize()} Edition)",
        f"- **Coverage Period:** {edition['coverage_start_ist']} to {edition['coverage_end_ist']}",
        f"- **Published At (IST):** {edition['published_at_ist']}",
        f"- **Estimated Reading Time:** {edition['reading_time_minutes']} minutes",
        "",
        f"## Headline: {edition['headline']}",
        "",
        "## The Big Picture",
        sec.get("big_picture", ""),
        "",
        "## Top Political Developments",
    ]

    for idx, dev in enumerate(sec.get("top_developments", []), start=1):
        lines.extend(
            [
                f"### {idx}. {dev.get('headline', '')}",
                f"- **Verification Status:** {dev.get('verification_badge', 'Verified')}",
                f"{dev.get('summary', dev.get('what_happened', ''))}",
            ]
        )
        if dev.get("why_it_matters"):
            lines.append(f"- **Why it matters:** {dev.get('why_it_matters')}")
        src_links = [f"[{s['publisher']}]({s['url']})" for s in dev.get("sources", [])]
        lines.append(f"- **Sources:** {' | '.join(src_links)}")
        lines.append("")

    for heading, key in [
        ("Government and Administration", "government_and_administration"),
        ("Political Parties and Opposition", "political_parties_and_opposition"),
        ("Assembly, Courts, and Policy", "assembly_courts_and_policy"),
        ("District-Level Developments", "district_developments"),
        ("What to Watch Next", "what_to_watch_next"),
    ]:
        val = (sec.get(key) or "").strip()
        if val:
            lines.extend([f"## {heading}", val, ""])

    lines.append("## Sources and Further Reading")
    for s in sec.get("all_sources", []):
        lines.append(f"- **{s['publisher']}:** [{s['title']}]({s['url']}) ({s['published_date']})")

    return "\n".join(lines) + "\n"


def save_edition_and_update_indexes(
    edition: dict,
    archive_dir: Path = ARCHIVE_DIR,
    archive_index_file: Path = ARCHIVE_INDEX_FILE,
    latest_editions_file: Path = LATEST_EDITIONS_FILE,
) -> dict:
    year, month, _ = edition["date"].split("-")
    target_folder = archive_dir / year / month
    target_folder.mkdir(parents=True, exist_ok=True)

    edition_id = edition["edition_id"]
    json_rel_path = f"archive/{year}/{month}/{edition_id}.json"
    md_rel_path = f"archive/{year}/{month}/{edition_id}.md"

    json_full_path = archive_dir / year / month / f"{edition_id}.json"
    md_full_path = archive_dir / year / month / f"{edition_id}.md"

    clean_edition = {k: v for k, v in edition.items() if not k.startswith("_")}
    clean_edition["published_at_ist"] = get_ist_now().isoformat()

    with open(json_full_path, "w", encoding="utf-8") as f:
        json.dump(clean_edition, f, indent=2, ensure_ascii=False)

    md_content = render_edition_markdown(clean_edition)
    with open(md_full_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    if archive_index_file.exists():
        with open(archive_index_file, "r", encoding="utf-8") as f:
            index_data = json.load(f)
    else:
        index_data = {"total_editions": 0, "last_updated_ist": "", "editions": []}

    bullet_headlines = "\n".join(
        f"- {d.get('headline', '')}"
        for d in clean_edition["sections"].get("top_developments", [])[:4]
        if d.get("headline")
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
        "summary_text": bullet_headlines[:900],
        "parties": clean_edition["parties"],
        "topics": clean_edition["topics"],
        "districts": clean_edition["districts"],
        "url": f"edition.html?id={edition_id}",
        "json_path": json_rel_path,
    }

    existing_editions = [e for e in index_data.get("editions", []) if e.get("edition_id") != edition_id]
    existing_editions.append(index_entry)
    def edition_chronological_key(e):
        cov_end = e.get("coverage_end_ist")
        if not cov_end:
            cov_end = f"{e.get('date', '')}T18:00:00+05:30" if e.get("edition_type") == "evening" else f"{e.get('date', '')}T06:00:00+05:30"
        return cov_end

    existing_editions.sort(key=edition_chronological_key, reverse=True)

    index_data["editions"] = existing_editions
    index_data["total_editions"] = len(existing_editions)
    index_data["last_updated_ist"] = clean_edition["published_at_ist"]

    with open(archive_index_file, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)

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
        "big_picture_excerpt": bullet_headlines,
        "parties": clean_edition["parties"],
        "topics": clean_edition["topics"],
        "districts": clean_edition["districts"],
        "json_path": json_rel_path,
        "md_path": md_rel_path,
        "url": f"edition.html?id={edition_id}",
    }

    slot_type = clean_edition["edition_type"]
    current_slot = latest_data.get(slot_type)
    if not current_slot or edition_chronological_key(latest_card) >= edition_chronological_key(current_slot):
        latest_data[clean_edition["edition_type"]] = latest_card
        latest_data["last_updated_ist"] = clean_edition["published_at_ist"]
        latest_data["system_status"] = "operational"
        latest_data["status_message"] = f"Latest {clean_edition['edition_type']} edition published at {clean_edition['published_at_ist']}."

    with open(latest_editions_file, "w", encoding="utf-8") as f:
        json.dump(latest_data, f, indent=2, ensure_ascii=False)

    return {"json_path": json_rel_path, "md_path": md_rel_path}


def record_pipeline_log(log_entry: dict, logs_file: Path = PIPELINE_LOGS_FILE) -> None:
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