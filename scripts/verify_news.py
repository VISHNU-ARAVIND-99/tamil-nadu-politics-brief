#!/usr/bin/env python3
"""
Step 6 of Pipeline:
- Prioritizes core Tamil Nadu political party, election, and assembly developments
  ahead of general corporate or routine civic news.
"""


def verify_and_rank_clusters(clusters: list[dict]) -> list[dict]:
    verified_clusters = []

    for cluster in clusters:
        sources = cluster.get("sources", [])
        pub_count = cluster.get("publisher_count", 1)
        has_primary_official = any(s.get("reliability_tier") == "primary_official" for s in sources)
        has_bilingual = len(cluster.get("languages", [])) > 1
        party_count = len(cluster.get("parties", []))

        if has_primary_official and pub_count >= 2:
            verification_status = "Confirmed by Primary Official & Independent Sources"
            confidence_level = "high"
        elif has_primary_official:
            verification_status = "Official Primary Release"
            confidence_level = "high"
        elif pub_count >= 2 and has_bilingual:
            verification_status = "Multi-Source Verified (Tamil & English)"
            confidence_level = "high"
        elif pub_count >= 2:
            verification_status = "Multi-Source Verified"
            confidence_level = "high"
        else:
            verification_status = "Single-Source Report"
            confidence_level = "single_source"

        # Core political bonus ensures actual party/government politics outrank general business news
        political_core_bonus = 25 if party_count > 0 else 0

        score = (
            political_core_bonus
            + (pub_count * 8)
            + (8 if has_primary_official else 0)
            + (5 if has_bilingual else 0)
            + (party_count * 5)
            + (len(cluster.get("topics", [])) * 2)
        )

        enriched = dict(cluster)
        enriched["verification_status"] = verification_status
        enriched["confidence_level"] = confidence_level
        enriched["significance_score"] = score
        verified_clusters.append(enriched)

    verified_clusters.sort(key=lambda c: c["significance_score"], reverse=True)
    return verified_clusters