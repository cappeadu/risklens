"""Phase 1 extraction and line-ending normalization for Item 1A records."""

import hashlib
import json
import re
from pathlib import Path

from configs.config import ROOT_DIR

RAW_FILINGS_DIR = ROOT_DIR / "data/extracted_filings/10-K"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "data/raw/filing_records.jsonl"
ITEM_1A_HEADING_PATTERN = re.compile(
    r"^ITEM\s*1A\.?\s*RISK\s+FACTORS\s*$", re.IGNORECASE
)


def _display_heading(line: str) -> str:
    """Collapse formatting whitespace for a heading label."""
    return re.sub(r"\s+", " ", line.strip())


def _heading_level(line: str) -> int | None:
    """Return a conservative heading level for one normalized text line."""
    heading = _display_heading(line)
    if not heading:
        return None
    if ITEM_1A_HEADING_PATTERN.fullmatch(heading):
        return 1

    has_letters = any(character.isalpha() for character in heading)
    is_uppercase = heading == heading.upper()
    has_terminal_punctuation = heading[-1] in ".!?;:"
    if has_letters and is_uppercase and not has_terminal_punctuation and len(heading) <= 120:
        return 2
    return None


def detect_headings(text: str) -> list[dict]:
    """Detect Item 1A and conservative section headings in normalized text."""
    headings = []
    heading_path = []
    for line_number, line in enumerate(text.splitlines()):
        level = _heading_level(line)
        if level is None:
            continue

        heading = _display_heading(line)
        if level == 1:
            heading_path = [heading]
        else:
            heading_path = heading_path[:1] + [heading] if heading_path else [heading]

        headings.append(
            {
                "line_number": line_number,
                "heading": heading,
                "heading_level": level,
                "heading_path": heading_path.copy(),
                "block_type": "heading",
            }
        )
    return headings


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


def normalize_line_endings(text: str) -> str:
    """Normalize CRLF and CR line endings without changing other characters."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def build_filing_record(raw_record: dict) -> dict:
    """Build one filing-level record with raw and line-normalized text."""
    item_1a_text = raw_record.get("item_1A")
    if not isinstance(item_1a_text, str) or not item_1a_text:
        raise ValueError("Filing record has no non-empty item_1A text")

    normalized_text = normalize_line_endings(item_1a_text)
    metadata = {
        key: value for key, value in raw_record.items() if key != "item_1A"
    }
    return {
        "filing_id": _filing_id(raw_record),
        **metadata,
        "item_1a_text": item_1a_text,
        "raw_text": item_1a_text,
        "text": normalized_text,
        "normalization_status": "line_endings_only",
        "headings": detect_headings(normalized_text),
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
