"""Create a deterministic, reviewable Phase 2 annotation candidate sample."""

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data/raw/filing_records.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/annotations/annotation_candidates_v1.jsonl"
DEFAULT_MANIFEST = PROJECT_ROOT / "data/annotations/annotation_sample_manifest_v1.json"

RISK_TERMS = re.compile(
    r"\b(risk|risks|could|may|adversely|uncertain|uncertainty|failure|unable|"
    r"disrupt|loss|litigation|cyber|breach|competition|regulatory|depend)\b",
    re.IGNORECASE,
)
MITIGATION_TERMS = re.compile(
    r"\b(maintain|monitor|monitoring|plan|plans|control|controls|protect|"
    r"prevent|reduce|mitigate|respond|response|backup|insurance|alternative|"
    r"diversif|continuity|safeguard)\w*\b",
    re.IGNORECASE,
)
BOILERPLATE_TERMS = re.compile(
    r"\b(forward-looking statements|risks and uncertainties|annual report|"
    r"securities and exchange commission|incorporated by reference)\b",
    re.IGNORECASE,
)


def _stable_rank(sentence_id: str, seed: int) -> str:
    """Return a deterministic sortable value without process-randomized hashes."""
    return hashlib.sha256(f"{seed}:{sentence_id}".encode()).hexdigest()


def _length_bucket(text: str) -> str:
    length = len(text)
    if length <= 80:
        return "short"
    if length <= 240:
        return "medium"
    return "long"


def _sampling_signals(text: str) -> list[str]:
    """Identify sampling hints only; these are not annotation labels."""
    signals = []
    if RISK_TERMS.search(text):
        signals.append("risk_term_hint")
    if MITIGATION_TERMS.search(text):
        signals.append("mitigation_term_hint")
    if BOILERPLATE_TERMS.search(text):
        signals.append("boilerplate_term_hint")
    return signals or ["no_configured_term_hint"]


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Input filing records do not exist: {path}")

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


def flatten_sentences(records: list[dict], seed: int) -> list[dict]:
    candidates = []
    for record in records:
        for block in record.get("blocks") or []:
            if block.get("block_type") == "heading":
                continue
            for sentence in block.get("sentences") or []:
                text = sentence.get("text", "")
                sentence_id = sentence.get("sentence_id")
                if not sentence_id or not text.strip():
                    continue

                candidates.append(
                    {
                        "sentence_id": sentence_id,
                        "filing_id": record.get("filing_id"),
                        "company_name": record.get("company"),
                        "cik": record.get("cik"),
                        "filename": record.get("filename"),
                        "filing_date": record.get("filing_date"),
                        "period_of_report": record.get("period_of_report"),
                        "sic": record.get("sic"),
                        "block_id": block.get("block_id"),
                        "block_order": block.get("block_order"),
                        "block_type": block.get("block_type"),
                        "heading_path": block.get("heading_path") or [],
                        "sentence_order": sentence.get("sentence_order"),
                        "sentence_text": text,
                        "raw_text": sentence.get("raw_text", text),
                        "source_start": sentence.get("start_offset"),
                        "source_end": sentence.get("end_offset"),
                        "boundary_uncertain": bool(sentence.get("boundary_uncertain")),
                        "length_bucket": _length_bucket(text),
                        "sampling_signals": _sampling_signals(text),
                        "sampling_rank": _stable_rank(sentence_id, seed),
                    }
                )

    return sorted(candidates, key=lambda item: item["sentence_id"])


def _add_candidate(candidate: dict, selected: dict[str, dict], limit: int) -> bool:
    if len(selected) >= limit or candidate["sentence_id"] in selected:
        return False
    selected[candidate["sentence_id"]] = candidate
    return True


def sample_candidates(candidates: list[dict], limit: int) -> list[dict]:
    if limit < 1:
        raise ValueError("Sample size must be positive")
    if not candidates:
        return []

    limit = min(limit, len(candidates))
    selected: dict[str, dict] = {}
    ranked = sorted(candidates, key=lambda item: item["sampling_rank"])

    # First guarantee company coverage, then cover important structural strata.
    companies = defaultdict(list)
    for candidate in ranked:
        companies[str(candidate.get("company_name") or candidate.get("cik"))].append(
            candidate
        )
    for company in sorted(companies):
        _add_candidate(companies[company][0], selected, limit)

    strata = defaultdict(list)
    for candidate in ranked:
        company = str(candidate.get("company_name") or candidate.get("cik"))
        base = (company, candidate["block_type"], candidate["length_bucket"])
        if candidate["boundary_uncertain"]:
            strata[base + ("boundary_uncertain",)].append(candidate)
        else:
            strata[base + ("ordinary",)].append(candidate)
        for signal in candidate["sampling_signals"]:
            strata[base + (signal,)].append(candidate)

    for key in sorted(strata):
        best = min(strata[key], key=lambda item: item["sampling_rank"])
        _add_candidate(best, selected, limit)
        if len(selected) >= limit:
            break

    # Fill the remaining sample in deterministic company round-robin order.
    company_names = sorted(companies)
    company_positions = {company: 0 for company in company_names}
    while len(selected) < limit:
        added = False
        for company in company_names:
            pool = companies[company]
            while (
                company_positions[company] < len(pool)
                and pool[company_positions[company]]["sentence_id"] in selected
            ):
                company_positions[company] += 1
            if company_positions[company] >= len(pool):
                continue
            candidate = pool[company_positions[company]]
            company_positions[company] += 1
            added = _add_candidate(candidate, selected, limit) or added
            if len(selected) >= limit:
                break
        if not added:
            break

    return sorted(selected.values(), key=lambda item: item["sentence_id"])


def build_manifest(
    candidates: list[dict],
    selected: list[dict],
    input_path: Path,
    limit: int,
    seed: int,
) -> dict:
    def counts(items: list[dict], field: str) -> dict[str, int]:
        result = defaultdict(int)
        for item in items:
            result[str(item.get(field))] += 1
        return dict(sorted(result.items()))

    return {
        "sample_version": "v1",
        "source_file": str(input_path),
        "requested_sample_size": limit,
        "actual_sample_size": len(selected),
        "source_sentence_count": len(candidates),
        "seed": seed,
        "sampling_rule": (
            "deterministic company coverage, structural-strata coverage, "
            "then company round-robin fill; sampling hints are not labels"
        ),
        "company_counts": counts(selected, "company_name"),
        "block_type_counts": counts(selected, "block_type"),
        "length_bucket_counts": counts(selected, "length_bucket"),
        "uncertain_boundary_count": sum(
            item["boundary_uncertain"] for item in selected
        ),
        "selected_sentence_ids": [item["sentence_id"] for item in selected],
    }


def write_sample(selected: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        for order, candidate in enumerate(selected):
            record = dict(candidate)
            record.pop("sampling_rank", None)
            record["sample_order"] = order
            record["sample_id"] = (
                "sample-"
                + hashlib.sha256(candidate["sentence_id"].encode("utf-8")).hexdigest()[
                    :16
                ]
            )
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_records(args.input)
    candidates = flatten_sentences(records, args.seed)
    selected = sample_candidates(candidates, args.size)
    write_sample(selected, args.output)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(
            build_manifest(candidates, selected, args.input, args.size, args.seed),
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(selected)} annotation candidates to {args.output}")
    print(f"Wrote sampling manifest to {args.manifest}")


if __name__ == "__main__":
    main()
