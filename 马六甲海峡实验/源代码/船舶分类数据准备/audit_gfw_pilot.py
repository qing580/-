#!/usr/bin/env python3
"""Audit cached GFW vessel-search responses without treating inferred data as truth."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


TARGET_TYPE_MAP = {
    "FISHING": "fishing",
    "PASSENGER": "passenger",
    "TANKER": "tanker",
}
FIELDS = [
    "mmsi",
    "vessel_name",
    "ais_rough_categories",
    "query_priority",
    "query_value",
    "request_status",
    "response_entry_count",
    "mmsi_aligned_entry_count",
    "identity_alignment",
    "name_alignment",
    "registry_record_count",
    "registry_sources",
    "registry_geartypes",
    "combined_shiptypes",
    "combined_shiptype_sources",
    "candidate_target_class",
    "evidence_level",
    "five_class_label_status",
    "review_reason",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_name(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def values(items: list[dict], field: str) -> set[str]:
    return {str(item.get(field) or "").strip() for item in items if str(item.get(field) or "").strip()}


def entry_matches_mmsi(entry: dict, mmsi: str) -> bool:
    identity_rows = list(entry.get("selfReportedInfo") or []) + list(entry.get("registryInfo") or [])
    return mmsi in values(identity_rows, "ssvid")


def audit_payload(sample: dict[str, str], status: dict[str, str] | None, payload: dict | None) -> dict[str, object]:
    request_status = (status or {}).get("status", "missing_status")
    entries = list((payload or {}).get("entries") or [])
    aligned = [entry for entry in entries if entry_matches_mmsi(entry, sample["mmsi"])]

    registry_rows: list[dict] = []
    self_rows: list[dict] = []
    combined_rows: list[dict] = []
    for entry in aligned:
        registry_rows.extend(entry.get("registryInfo") or [])
        self_rows.extend(entry.get("selfReportedInfo") or [])
        combined_rows.extend(entry.get("combinedSourcesInfo") or [])

    local_name = normalize_name(sample.get("vessel_name"))
    external_names = {normalize_name(row.get("shipname")) for row in registry_rows + self_rows}
    external_names.discard("")
    if not local_name:
        name_alignment = "local_name_missing"
    elif local_name in external_names:
        name_alignment = "exact_normalized"
    elif external_names:
        name_alignment = "different"
    else:
        name_alignment = "external_name_missing"

    registry_sources = sorted({source for row in registry_rows for source in (row.get("sourceCode") or [])})
    registry_gears = sorted({str(gear) for row in registry_rows for gear in (row.get("geartypes") or []) if gear})
    type_records = [record for row in combined_rows for record in (row.get("shiptypes") or [])]
    shiptypes = sorted({str(record.get("name")) for record in type_records if record.get("name")})
    shiptype_sources = sorted({str(record.get("source")) for record in type_records if record.get("source")})

    candidate_classes = sorted({TARGET_TYPE_MAP[item] for item in shiptypes if item in TARGET_TYPE_MAP})
    registry_fishing = bool(registry_gears) and "FISHING" in shiptypes
    direct_list_target = any(
        record.get("name") in TARGET_TYPE_MAP and record.get("source") == "GFW_VESSEL_LIST"
        for record in type_records
    )
    if len(candidate_classes) > 1:
        candidate = "conflict"
        evidence = "conflicting_candidate"
        label_status = "manual_review"
        reason = "GFW current MMSI records contain multiple target classes"
    elif candidate_classes:
        candidate = candidate_classes[0]
        if registry_fishing:
            evidence = "registry_supported"
            label_status = "candidate_requires_policy_review"
            reason = "Registry gear evidence supports fishing; retain source and validity period"
        elif direct_list_target:
            evidence = "gfw_list_supported"
            label_status = "candidate_requires_policy_review"
            reason = "Target class comes from GFW vessel list; verify temporal alignment before labeling"
        else:
            evidence = "combined_inference_candidate"
            label_status = "not_gold_label"
            reason = "Class comes from combined registry/AIS neural inference and is not registry truth"
    elif "CARGO" in shiptypes:
        candidate = "cargo_unspecified"
        evidence = "broad_cargo_only"
        label_status = "insufficient_for_five_class"
        reason = "Broad cargo cannot distinguish container ship from bulk carrier"
    elif shiptypes:
        candidate = "non_target_or_unknown"
        evidence = "non_target_type"
        label_status = "insufficient_for_five_class"
        reason = "Returned shiptype does not map to the five target classes"
    else:
        candidate = "unknown"
        evidence = "no_shiptype"
        label_status = "manual_review"
        reason = "No shiptype evidence was returned for the current MMSI"

    if request_status != "success":
        evidence = "request_failed"
        label_status = "retry_required"
        reason = (status or {}).get("error") or "Request did not complete"
    elif not aligned:
        evidence = "identity_not_aligned"
        label_status = "manual_review"
        reason = "Search result does not contain the local MMSI"

    return {
        "mmsi": sample["mmsi"],
        "vessel_name": sample.get("vessel_name", ""),
        "ais_rough_categories": sample.get("ais_rough_categories", ""),
        "query_priority": sample.get("query_priority", ""),
        "query_value": sample.get("query_value", ""),
        "request_status": request_status,
        "response_entry_count": len(entries),
        "mmsi_aligned_entry_count": len(aligned),
        "identity_alignment": "aligned" if aligned else "not_aligned",
        "name_alignment": name_alignment,
        "registry_record_count": len(registry_rows),
        "registry_sources": "|".join(registry_sources),
        "registry_geartypes": "|".join(registry_gears),
        "combined_shiptypes": "|".join(shiptypes),
        "combined_shiptype_sources": "|".join(shiptype_sources),
        "candidate_target_class": candidate,
        "evidence_level": evidence,
        "five_class_label_status": label_status,
        "review_reason": reason,
    }


def cache_path(raw_dir: Path, sample: dict[str, str]) -> Path:
    return raw_dir / f"{sample['query_priority']}_{sample['query_value']}.json"


def run_audit(pilot_path: Path, status_path: Path, raw_dir: Path) -> tuple[list[dict[str, object]], dict]:
    pilot = read_csv(pilot_path)
    statuses = {row["mmsi"]: row for row in read_csv(status_path)}
    rows = []
    for sample in pilot:
        target = cache_path(raw_dir, sample)
        payload = None
        if target.is_file():
            with target.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        rows.append(audit_payload(sample, statuses.get(sample["mmsi"]), payload))

    request_counts = Counter(str(row["request_status"]) for row in rows)
    evidence_counts = Counter(str(row["evidence_level"]) for row in rows)
    candidate_counts = Counter(str(row["candidate_target_class"]) for row in rows)
    aligned_success = sum(row["request_status"] == "success" and row["identity_alignment"] == "aligned" for row in rows)
    summary = {
        "pilot_vessels": len(rows),
        "request_status_counts": dict(request_counts),
        "successful_identity_aligned_vessels": aligned_success,
        "evidence_level_counts": dict(evidence_counts),
        "candidate_target_class_counts": dict(candidate_counts),
        "container_or_bulk_labels_obtained": sum(
            row["candidate_target_class"] in {"container", "bulk"} for row in rows
        ),
        "verdict": "PARTIAL_PASS_NOT_A_FIVE_CLASS_GOLD_LABEL_SOURCE",
        "decision": (
            "The GFW API is usable for identity cross-checking and selected fishing/passenger candidates, "
            "but this pilot does not separate container ships from bulk carriers and mixed inferred shiptypes "
            "must not be treated as registry ground truth."
        ),
    }
    return rows, summary


def write_outputs(output_dir: Path, rows: list[dict[str, object]], summary: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "gfw_pilot_evidence_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / "gfw_pilot_evidence_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit cached GFW vessel identity pilot evidence.")
    parser.add_argument("--pilot", required=True, type=Path)
    parser.add_argument("--status", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    rows, summary = run_audit(args.pilot, args.status, args.raw_dir)
    write_outputs(args.output_dir, rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
