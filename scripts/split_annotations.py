"""Create deterministic company-held-out Phase 2 annotation splits."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANNOTATIONS = PROJECT_ROOT / "data/annotations/annotations_v1.jsonl"
DEFAULT_CANDIDATES = PROJECT_ROOT / "data/annotations/annotation_candidates_v1.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data/annotations/splits_v1"
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "split_manifest_v1.json"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Required input does not exist: {path}")
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


def assign_companies(companies: list[str], seed: int) -> dict[str, str]:
    """Assign complete companies to approximately 8/3/3 train/dev/test groups."""
    if len(companies) < 3:
        raise ValueError("At least three companies are required for held-out splits")

    ranked = sorted(
        companies,
        key=lambda company: hashlib.sha256(f"{seed}:{company}".encode()).hexdigest(),
    )
    test_count = max(1, round(len(ranked) * 3 / 14))
    development_count = max(1, round(len(ranked) * 3 / 14))
    if test_count + development_count >= len(ranked):
        test_count = 1
        development_count = 1

    assignments = {}
    for company in ranked[:test_count]:
        assignments[company] = "test"
    for company in ranked[test_count : test_count + development_count]:
        assignments[company] = "development"
    for company in ranked[test_count + development_count :]:
        assignments[company] = "train"
    return assignments


def enrich_annotations(annotations: list[dict], candidates: list[dict]) -> list[dict]:
    candidate_by_sample_id = {str(item.get("sample_id")): item for item in candidates}
    if len(candidate_by_sample_id) != len(candidates):
        raise ValueError("Candidate sample IDs must be unique")

    enriched = []
    seen_annotation_keys = set()
    for annotation in annotations:
        sample_id = str(annotation.get("sample_id"))
        candidate = candidate_by_sample_id.get(sample_id)
        if candidate is None:
            raise ValueError(f"Annotation references missing sample ID: {sample_id}")

        annotation_key = (
            str(annotation.get("annotator_id")),
            str(annotation.get("sentence_id")),
            str(annotation.get("annotation_status")),
        )
        if annotation_key in seen_annotation_keys:
            raise ValueError(f"Duplicate annotation record: {annotation_key}")
        seen_annotation_keys.add(annotation_key)

        for annotation_field, candidate_field in (
            ("sentence_id", "sentence_id"),
            ("filing_id", "filing_id"),
            ("block_id", "block_id"),
        ):
            if annotation.get(annotation_field) != candidate.get(candidate_field):
                raise ValueError(
                    f"{annotation_field} mismatch for sample ID {sample_id}"
                )

        record = dict(annotation)
        company_name = candidate.get("company_name")
        if not company_name:
            raise ValueError(f"Candidate has no company name for sample ID {sample_id}")
        record["company_name"] = company_name
        record["cik"] = candidate.get("cik")
        record["sic"] = candidate.get("sic")
        record["filename"] = candidate.get("filename")
        record["period_of_report"] = candidate.get("period_of_report")
        record["heading_path"] = candidate.get("heading_path") or []
        record["block_type"] = candidate.get("block_type")
        record["sentence_text"] = candidate.get("sentence_text")
        enriched.append(record)
    return enriched


def label_counts(records: list[dict]) -> dict[str, int]:
    counts = Counter()
    for record in records:
        labels = record.get("labels") or []
        if not labels and record.get("none_other"):
            counts["NONE_OTHER"] += 1
        for label in labels:
            counts[label] += 1
    return dict(sorted(counts.items()))


def build_manifest(
    records: list[dict],
    assignments: dict[str, str],
    annotations_path: Path,
    candidates_path: Path,
    seed: int,
) -> dict:
    split_records = defaultdict(list)
    for record in records:
        split_records[assignments[record["company_name"]]].append(record)

    company_lists = {
        split: sorted(
            company for company, assigned in assignments.items() if assigned == split
        )
        for split in ("train", "development", "test")
    }
    return {
        "split_version": "v1",
        "annotation_guideline_version": "v1",
        "annotations_source": str(annotations_path),
        "candidates_source": str(candidates_path),
        "seed": seed,
        "assignment_rule": "all records for one company stay in one split",
        "company_counts": {
            split: len(companies) for split, companies in company_lists.items()
        },
        "companies": company_lists,
        "record_counts": {
            split: len(split_records[split])
            for split in ("train", "development", "test")
        },
        "label_counts": {
            split: label_counts(split_records[split])
            for split in ("train", "development", "test")
        },
        "annotator_counts": {
            split: dict(
                Counter(record.get("annotator_id") for record in split_records[split])
            )
            for split in ("train", "development", "test")
        },
    }


def write_split(records: list[dict], path: Path, split: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=lambda record: str(record.get("sentence_id")))
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for record in ordered:
            output = dict(record)
            output["split"] = split
            file.write(json.dumps(output, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    annotations = load_jsonl(args.annotations)
    candidates = load_jsonl(args.candidates)
    records = enrich_annotations(annotations, candidates)
    companies = sorted({record["company_name"] for record in records})
    assignments = assign_companies(companies, args.seed)

    by_split = defaultdict(list)
    for record in records:
        by_split[assignments[record["company_name"]]].append(record)
    for split in ("train", "development", "test"):
        write_split(by_split[split], args.output_dir / f"{split}_v1.jsonl", split)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(
            build_manifest(
                records, assignments, args.annotations, args.candidates, args.seed
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(by_split['train'])} training records")
    print(f"Wrote {len(by_split['development'])} development records")
    print(f"Wrote {len(by_split['test'])} test records")
    print(f"Wrote split manifest to {args.manifest}")


if __name__ == "__main__":
    main()
