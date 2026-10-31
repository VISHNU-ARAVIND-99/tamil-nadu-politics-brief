#!/usr/bin/env python3
"""
Step 6 of Pipeline:
- Evaluates each story cluster for multi-source confirmation and primary official backing
- Assigns a transparent verification status badge
- Ranks clusters by significance (publisher count, official backing, policy/party breadth)
"""


def verify_and_rank_clusters(clusters: list[dict]) -> list[dict]:
    """
    Assign verification status and priority score to each deduplicated story cluster.
    """
    verified_clusters = []

    for cluster in clusters:
        sources = cluster.get("sources", [])
        pub_count = cluster.get("publisher_count", 1)
        has_primary_official = any(s.get("reliability_tier") == "primary_official" for s in sources)
        has_bilingual = len(cluster.get("languages", [])) > 1

        if has_primary_official and pub_count >= 2:
            verification_status = "Confirmed by Primary Official & Independent Sources"
            confidence_level = "high"
        elif has_primary_official:
            verification_status = "Official Primary Release"
            confidence_level = "high"
        elif pub_count >= 2 and has_bilingual:
            verification_status = "Multi-Source Verified (Tamil & English Reporting)"
            confidence_level = "high"
        elif pub_count >= 2:
            verification_status = "Multi-Source Verified"
            confidence_level = "high"
        else:
            verification_status = "Single-Source Report (Independently Unverified)"
            confidence_level = "single_source"

        # Calculate significance score for ordering
        score = (
            (pub_count * 10)
            + (8 if has_primary_official else 0)
            + (5 if has_bilingual else 0)
            + (len(cluster.get("parties", [])) * 3)
            + (len(cluster.get("topics", [])) * 2)
            + (len(cluster.get("districts", [])) * 1)
        )

        enriched = dict(cluster)
        enriched["verification_status"] = verification_status
        enriched["confidence_level"] = confidence_level
        enriched["significance_score"] = score
        verified_clusters.append(enriched)

    verified_clusters.sort(key=lambda c: c["significance_score"], reverse=True)
    return verified_clusters