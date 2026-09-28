"""Validate and freeze the Phase 2 gold annotation and test-set artifacts."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT_DIR = PROJECT_ROOT / "data/annotations/splits_v1"
DEFAULT_MANIFEST = DEFAULT_SPLIT_DIR / "split_manifest_v1.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data/annotations/frozen_v1"
TARGET_LABELS = {
    "RISK_STATEMENT",
    "MITIGATION",
    "SUPPORTED_CONTEXT",
    "BOILERPLATE",
}
SPLITS = ("train", "development", "test")


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required file does not exist: {path}")
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Required file does not exist: {path}")
    records = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}"
                ) from exc
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_split_manifest(manifest: dict) -> None:
    if manifest.get("split_version") != "v1":
        raise ValueError("Only split manifest version v1 is supported")
    companies = manifest.get("companies") or {}
    if set(companies) != set(SPLITS):
        raise ValueError(
            "Split manifest must contain train, development, and test companies"
        )

    seen = set()
    for split in SPLITS:
        overlap = seen.intersection(companies[split])
        if overlap:
            raise ValueError(f"Company leakage across splits: {sorted(overlap)}")
        seen.update(companies[split])


def validate_records(records_by_split: dict[str, list[dict]], manifest: dict) -> dict:
    companies = manifest["companies"]
    seen_records = set()
    report = {"errors": [], "warnings": [], "checks": {}}

    for split, records in records_by_split.items():
        expected_companies = set(companies[split])
        actual_companies = {record.get("company_name") for record in records}
        if not actual_companies.issubset(expected_companies):
            report["errors"].append(
                f"{split} contains companies outside its manifest assignment"
            )

        for record in records:
            record_key = (
                str(record.get("annotator_id")),
                str(record.get("sentence_id")),
                str(record.get("annotation_status")),
            )
            if record_key in seen_records:
                report["errors"].append(f"Duplicate annotation record: {record_key}")
            seen_records.add(record_key)

            labels = record.get("labels") or []
            invalid_labels = set(labels).difference(TARGET_LABELS)
            if invalid_labels:
                report["errors"].append(
                    f"Invalid labels for {record.get('sentence_id')}: {sorted(invalid_labels)}"
                )
            if bool(record.get("none_other")) and labels:
                report["errors"].append(
                    f"NONE_OTHER combined with labels for {record.get('sentence_id')}"
                )
            if not labels and not record.get("none_other"):
                report["errors"].append(
                    f"No label or NONE_OTHER for {record.get('sentence_id')}"
                )

            offsets = record.get("source_offsets") or {}
            start = offsets.get("start")
            end = offsets.get("end")
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or start >= end
            ):
                report["errors"].append(
                    f"Invalid half-open offsets for {record.get('sentence_id')}"
                )

            if record.get("split") != split:
                report["errors"].append(
                    f"Incorrect split field for {record.get('sentence_id')}"
                )

    report["checks"]["records_checked"] = len(seen_records)
    report["checks"]["company_leakage"] = False
    report["checks"]["valid_labels"] = not report["errors"]
    for split in SPLITS:
        expected_count = manifest.get("record_counts", {}).get(split)
        if expected_count is not None and expected_count != len(
            records_by_split[split]
        ):
            report["errors"].append(
                f"{split} record count does not match the split manifest"
            )
    report["checks"]["valid_labels"] = not report["errors"]
    return report


def write_jsonl(records: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_freeze_manifest(
    manifest: dict,
    records_by_split: dict[str, list[dict]],
    source_hashes: dict[str, str],
    report: dict,
) -> dict:
    return {
        "freeze_version": "v1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "annotation_guideline_version": manifest.get("annotation_guideline_version"),
        "split_version": manifest.get("split_version"),
        "source_hashes": source_hashes,
        "companies": manifest["companies"],
        "record_counts": {split: len(records_by_split[split]) for split in SPLITS},
        "test_set_policy": {
            "company_held_out": True,
            "excluded_from_prompt_examples": True,
            "excluded_from_training": True,
            "excluded_from_synthetic_labels": True,
            "excluded_from_threshold_tuning": True,
            "excluded_from_feature_selection": True,
        },
        "validation": {
            "errors": len(report["errors"]),
            "warnings": len(report["warnings"]),
            "checks": report["checks"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-dir", type=Path, default=DEFAULT_SPLIT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--force", action="store_true", help="Replace an existing frozen directory"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_json(args.manifest)
    validate_split_manifest(manifest)
    records_by_split = {
        split: load_jsonl(args.split_dir / f"{split}_v1.jsonl") for split in SPLITS
    }
    report = validate_records(records_by_split, manifest)
    if report["errors"]:
        raise ValueError("Freeze validation failed: " + "; ".join(report["errors"][:5]))

    if args.output_dir.exists() and not args.force:
        raise FileExistsError(
            f"Frozen output already exists: {args.output_dir}. Use --force only for a deliberate new freeze."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_records = [record for split in SPLITS for record in records_by_split[split]]
    write_jsonl(all_records, args.output_dir / "gold_annotations_v1.jsonl")
    write_jsonl(records_by_split["test"], args.output_dir / "test_v1.jsonl")

    source_files = [args.manifest] + [
        args.split_dir / f"{split}_v1.jsonl" for split in SPLITS
    ]
    for source_value in (
        manifest.get("annotations_source"),
        manifest.get("candidates_source"),
    ):
        if source_value:
            source_path = Path(source_value)
            if source_path.exists():
                source_files.append(source_path)
    source_hashes = {str(path): sha256_file(path) for path in source_files}
    freeze_manifest = build_freeze_manifest(
        manifest, records_by_split, source_hashes, report
    )
    (args.output_dir / "freeze_manifest_v1.json").write_text(
        json.dumps(freeze_manifest, indent=2), encoding="utf-8"
    )
    (args.output_dir / "validation_report_v1.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(f"Frozen {len(all_records)} gold annotation records")
    print(f"Frozen {len(records_by_split['test'])} held-out test records")
    print(f"Wrote freeze artifacts to {args.output_dir}")


if __name__ == "__main__":
    main()
