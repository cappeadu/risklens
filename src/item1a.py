"""Stage 1 extraction of filing-level Item 1A records."""

import hashlib
import json
from pathlib import Path

from configs.config import ROOT_DIR

RAW_FILINGS_DIR = ROOT_DIR / "data/extracted_filings/10-K"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "data/raw/filing_records.jsonl"


def _filing_id(raw_record: dict) -> str:
    """Create a deterministic ID from stable filing metadata."""
    identity = {
        "cik": str(raw_record.get("cik", "")),
        "filing_type": str(raw_record.get("filing_type", "")),
        "period_of_report": str(raw_record.get("period_of_report", "")),
        "filename": str(raw_record.get("filename", "")),
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_filing_record(raw_record: dict) -> dict:
    """Build one filing-level record without changing Item 1A text."""
    item_1a_text = raw_record.get("item_1A")
    if not isinstance(item_1a_text, str) or not item_1a_text:
        raise ValueError("Filing record has no non-empty item_1A text")

    metadata = {
        key: value for key, value in raw_record.items() if key != "item_1A"
    }
    return {
        "filing_id": _filing_id(raw_record),
        **metadata,
        "item_1a_text": item_1a_text,
    }


def extract_filing_records(source_dir: Path = RAW_FILINGS_DIR) -> list[dict]:
    """Extract filing-level records from raw JSON in deterministic order."""
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Raw filings directory does not exist: {source_dir}")

    records = []
    for file_path in sorted(source_dir.glob("*.json")):
        with file_path.open(encoding="utf-8") as file:
            raw_record = json.load(file)
        records.append(build_filing_record(raw_record))
    return records


def write_filing_records(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    source_dir: Path = RAW_FILINGS_DIR,
) -> tuple[Path, int]:
    """Write filing-level records as UTF-8 JSON Lines."""
    records = extract_filing_records(source_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path, len(records)
