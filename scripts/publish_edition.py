#!/usr/bin/env python3
"""
Main Orchestrator CLI (Steps 1 through 12):
- Prevents duplicate edition generation unless --force is passed
- Automatically allows updating test samples and legacy robotic fallback editions
- Records honest generation and publication timestamps (marks delayed runs transparently)
- Updates failure status in data/latest-editions.json if an unrecoverable error occurs
- Supports auto-detection of morning vs evening edition based on current IST time
"""

import argparse
import json
import sys
import time
from datetime import datetime

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

from scripts.collect_news import collect_all_sources
from scripts.config import (
    ARCHIVE_DIR,
    LATEST_EDITIONS_FILE,
    compute_coverage_window,
    get_ist_now,
)
from scripts.deduplicate_news import deduplicate_and_filter
from scripts.generate_summary import generate_edition_summary
from scripts.update_archive import record_pipeline_log, save_edition_and_update_indexes
from scripts.verify_news import verify_and_rank_clusters


def auto_detect_edition_type() -> str:
    """
    Auto-detect edition type based on current IST time:
    - 00:00 to 11:59 IST -> morning edition (covers 18:00 yesterday to 06:00 today)
    - 12:00 to 23:59 IST -> evening edition (covers 06:00 today to 18:00 today)
    """
    return "morning" if get_ist_now().hour < 12 else "evening"


def edition_already_exists(edition_id: str, date_str: str) -> bool:
    """
    Check if the target edition JSON already exists and is non-test data.
    Automatically permits overwriting initial test samples or legacy robotic editions.
    """
    year, month, _ = date_str.split("-")
    json_path = ARCHIVE_DIR / year / month / f"{edition_id}.json"
    if not json_path.exists():
        return False
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        # Allow overwriting initial sample test data automatically
        if existing.get("is_test_sample", False):
            return False
        # Overwrite legacy robotic editions containing boilerplate text
        big_pic = existing.get("sections", {}).get("big_picture", "")
        if "distinct political and policy developments were tracked" in big_pic:
            return False
        return True
    except Exception:
        return False


def mark_edition_failed(window_meta: dict, error_msg: str) -> None:
    """Record transparent failure state so the website never pretends a failed run succeeded."""
    now_ist = get_ist_now().isoformat()
    if LATEST_EDITIONS_FILE.exists():
        with open(LATEST_EDITIONS_FILE, "r", encoding="utf-8") as f:
            latest_data = json.load(f)
    else:
        latest_data = {"morning": None, "evening": None}

    latest_data["system_status"] = "degraded"
    latest_data["status_message"] = (
        f"Scheduled {window_meta['edition_type']} edition ({window_meta['date']}) encountered an error "
        f"at {now_ist}: {error_msg}. Manual recovery available via GitHub Actions."
    )
    with open(LATEST_EDITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(latest_data, f, indent=2, ensure_ascii=False)


def run_pipeline(edition_type: str = "auto", target_date: str | None = None, force: bool = False) -> int:
    start_timer = time.time()
    if edition_type == "auto":
        edition_type = auto_detect_edition_type()
        print(f"[INFO] Auto-detected edition type based on current IST time: {edition_type}")

    if target_date:
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            print(f"[ERROR] Invalid --date '{target_date}'. Expected YYYY-MM-DD format (e.g. 2026-11-01).", file=sys.stderr)
            return 1

    window_meta = compute_coverage_window(edition_type, target_date)
    edition_id = window_meta["edition_id"]

    print(f"[INFO] Starting Tamil Nadu Politics Brief pipeline for: {edition_id}")
    print(f"[INFO] IST Coverage Window: {window_meta['human_window']}")

    if not force and edition_already_exists(edition_id, window_meta["date"]):
        print(f"[SKIP] Edition {edition_id} already exists. Pass --force to regenerate.")
        return 0

    try:
        # Step 2 & 3: Collect and time-filter news
        collected = collect_all_sources(window_meta["start_dt"], window_meta["end_dt"])
        print(
            f"[INFO] Checked {collected['sources_checked']} sources; "
            f"collected {collected['raw_count']} items in 12-hour window."
        )

        # Step 4 & 5: Deduplicate and filter for TN political relevance
        clusters = deduplicate_and_filter(collected["items"])
        print(f"[INFO] Formed {len(clusters)} unique Tamil Nadu political story clusters.")

        # Step 6: Verify and rank clusters
        verified_clusters = verify_and_rank_clusters(clusters)

        # Step 7, 8, 9: Summarize in English and validate quality
        edition = generate_edition_summary(window_meta, verified_clusters)

        # Check if publication is delayed by more than 45 minutes past scheduled time
        now_ist = get_ist_now()
        delay_minutes = (now_ist - window_meta["scheduled_dt"]).total_seconds() / 60.0
        if delay_minutes > 45 and edition["status"] == "published":
            edition["status"] = "published_delayed"

        # Step 10 & 11: Save archive and update indexes
        paths = save_edition_and_update_indexes(edition)
        duration = round(time.time() - start_timer, 2)
        telemetry = edition.get("_telemetry", {})

        # Step 12: Log execution
        record_pipeline_log(
            {
                "run_id": f"run-{edition_id}-{int(start_timer)}",
                "edition_id": edition_id,
                "timestamp_ist": now_ist.isoformat(),
                "status": edition["status"],
                "sources_checked": collected["sources_checked"],
                "raw_items_collected": collected["raw_count"],
                "clusters_verified": len(verified_clusters),
                "duration_seconds": duration,
                "ai_provider": telemetry.get("ai_provider", "unknown"),
                "tokens_used": telemetry.get("tokens_used", 0),
                "notes": f"Saved to {paths['json_path']}",
            }
        )
        print(f"[SUCCESS] Published {edition_id} ({edition['status']}) in {duration}s.")
        return 0

    except Exception as exc:
        duration = round(time.time() - start_timer, 2)
        print(f"[ERROR] Pipeline failed for {edition_id}: {exc}", file=sys.stderr)
        mark_edition_failed(window_meta, str(exc))
        record_pipeline_log(
            {
                "run_id": f"fail-{edition_id}-{int(start_timer)}",
                "edition_id": edition_id,
                "timestamp_ist": get_ist_now().isoformat(),
                "status": "failed",
                "sources_checked": 0,
                "raw_items_collected": 0,
                "clusters_verified": 0,
                "duration_seconds": duration,
                "ai_provider": "none",
                "tokens_used": 0,
                "notes": str(exc),
            }
        )
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish Tamil Nadu Politics Brief Edition")
    parser.add_argument(
        "--edition",
        choices=["morning", "evening", "auto"],
        default="auto",
        required=False,
        help="Target edition to generate ('morning', 'evening', or 'auto' based on current IST time)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Target date in YYYY-MM-DD format (defaults to current IST date)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration even if the edition file already exists",
    )
    args = parser.parse_args()
    sys.exit(run_pipeline(args.edition, args.date, args.force))


if __name__ == "__main__":
    main()
