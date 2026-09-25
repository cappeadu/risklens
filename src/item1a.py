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
BULLET_PATTERN = re.compile(r"^\s*(?P<marker>[•▪●◦◼‣\-*]|\(?\d+[.)])\s+")
INLINE_BULLET_PATTERN = re.compile(r"(?<!\w)(?P<marker>[•▪●◦◼‣])\s*")
RISK_HEADING_PATTERN = re.compile(
    r"\b(risk|risks|subject to|depend|dependent|ability to|failure to|unable to|"
    r"competition|cybersecurity|supply|regulatory|personnel|third parties|"
    r"operations|market|customers|laws|litigation|privacy|environmental)\b",
    re.IGNORECASE,
)
HEADING_EXCLUSION_PATTERN = re.compile(
    r"^(investors should|this report|we caution|important factors that could)",
    re.IGNORECASE,
)
WORD_ABBREVIATIONS = {
    "approx",
    "dr",
    "etc",
    "fig",
    "inc",
    "mr",
    "mrs",
    "ms",
    "no",
    "prof",
    "sec",
    "vs",
}


def _display_heading(line: str) -> str:
    """Collapse formatting whitespace for a heading label."""
    return re.sub(r"\s+", " ", line.strip())


def _heading_decision(line: str, lines: list[str], line_number: int) -> dict | None:
    """Apply deterministic rules to classify one line as a heading or candidate."""
    heading = _display_heading(line)
    if not heading:
        return None
    if ITEM_1A_HEADING_PATTERN.fullmatch(heading):
        return {
            "heading_level": 1,
            "heading_decision": "HIGH_RULE_MATCH",
            "heading_reasons": ["matches Item 1A heading pattern"],
        }

    has_letters = any(character.isalpha() for character in heading)
    is_uppercase = heading == heading.upper()
    if has_letters and is_uppercase and len(heading) <= 120:
        return {
            "heading_level": 2,
            "heading_decision": "HIGH_RULE_MATCH",
            "heading_reasons": ["short uppercase heading"],
        }

    if _list_marker(heading) or len(heading) < 20 or len(heading) > 180:
        return None
    if HEADING_EXCLUSION_PATTERN.search(heading) or heading.endswith(":"):
        return None

    following = next(
        (candidate.strip() for candidate in lines[line_number + 1 :] if candidate.strip()),
        None,
    )
    if not following or not RISK_HEADING_PATTERN.search(heading):
        return None

    reasons = ["contains a configured risk-topic phrase"]
    if len(following) >= max(80, len(heading)):
        reasons.append("followed by a longer explanatory line")
    title_words = [word for word in heading.split() if word[:1].isalpha()]
    title_like = len(title_words) >= 2 and sum(
        word[0].isupper() for word in title_words
    ) >= max(2, len(title_words) // 2)
    if title_like:
        reasons.append("title-like capitalization")

    explicit_risk_phrase = re.search(
        r"\b(our ability to|we depend|we are subject to|failure to|unable to|"
        r"we face|our business|our operations|our customers)\b",
        heading,
        re.IGNORECASE,
    )
    if explicit_risk_phrase and len(following) >= max(80, len(heading)):
        return {
            "heading_level": 3,
            "heading_decision": "HIGH_RULE_MATCH",
            "heading_reasons": reasons,
        }

    return {
        "heading_level": 3,
        "heading_decision": "MEDIUM_RULE_MATCH",
        "heading_reasons": reasons,
    }


def detect_headings(text: str) -> list[dict]:
    """Detect Item 1A and conservative section headings in normalized text."""
    headings = []
    heading_path = []
    lines = text.splitlines()
    for line_number, line in enumerate(lines):
        decision = _heading_decision(line, lines, line_number)
        if not decision or decision["heading_decision"] != "HIGH_RULE_MATCH":
            continue

        heading = _display_heading(line)
        level = decision["heading_level"]
        if level == 1:
            heading_path = [heading]
        elif level == 2:
            heading_path = heading_path[:1] + [heading] if heading_path else [heading]
        else:
            heading_path = heading_path[:2] + [heading] if len(heading_path) >= 2 else heading_path + [heading]

        headings.append(
            {
                "line_number": line_number,
                "heading": heading,
                "heading_level": level,
                "heading_path": heading_path.copy(),
                "block_type": "heading",
                "heading_decision": decision["heading_decision"],
                "heading_reasons": decision["heading_reasons"],
            }
        )
    return headings


def detect_heading_diagnostics(text: str) -> list[dict]:
    """Return medium-confidence heading candidates without changing structure."""
    diagnostics = []
    lines = text.splitlines()
    accepted_lines = {item["line_number"] for item in detect_headings(text)}
    for line_number, line in enumerate(lines):
        if line_number in accepted_lines:
            continue
        decision = _heading_decision(line, lines, line_number)
        if not decision:
            continue
        diagnostics.append(
            {
                "type": "heading_candidate",
                "line_number": line_number,
                "heading": _display_heading(line),
                "heading_decision": decision["heading_decision"],
                "heading_reasons": decision["heading_reasons"],
                "message": "Candidate retained for review and not used as a block boundary",
            }
        )
    return diagnostics


def _list_marker(line: str) -> str | None:
    """Return a list marker when a line starts with one."""
    match = BULLET_PATTERN.match(line)
    return match.group("marker") if match else None


def _clean_list_text(line: str) -> str:
    """Remove only the leading list marker from modeling text."""
    return BULLET_PATTERN.sub("", line, count=1).strip()


def _extract_inline_list_items(text: str) -> list[dict]:
    """Extract multiple inline bullets while preserving the parent text."""
    matches = list(INLINE_BULLET_PATTERN.finditer(text))
    if len(matches) < 2:
        return []

    items = []
    for item_order, match in enumerate(matches):
        start = match.end()
        end = matches[item_order + 1].start() if item_order + 1 < len(matches) else len(text)
        item_text = text[start:end].strip().strip(";,")
        item_text = re.sub(r"\s+(?:and|or)\s*$", "", item_text, flags=re.IGNORECASE)
        if item_text:
            items.append(
                {
                    "item_order": item_order,
                    "marker": match.group("marker"),
                    "text": item_text,
                    "raw_text": text[match.start() : end],
                    "is_bullet": True,
                }
            )
    return items


def _is_abbreviation_period(text: str, index: int) -> bool:
    """Return whether a period belongs to a common abbreviation."""
    if (
        index + 2 < len(text)
        and text[index + 1].isalpha()
        and text[index + 2] == "."
    ):
        return True
    prefix = text[: index + 1]
    if re.search(r"\b(?:[A-Za-z]\.){2,}$", prefix):
        return True

    match = re.search(r"\b([A-Za-z]+)\.$", prefix)
    return bool(match and match.group(1).lower() in WORD_ABBREVIATIONS)


def _is_sentence_boundary(text: str, index: int) -> bool:
    """Identify a sentence boundary without splitting common SEC text."""
    punctuation = text[index]
    if punctuation not in ".!?":
        return False
    if punctuation == "." and _is_abbreviation_period(text, index):
        return False

    next_index = index + 1
    while next_index < len(text) and text[next_index] in "\"'”’)]":
        next_index += 1
    return next_index == len(text) or text[next_index].isspace()


def segment_sentences(text: str) -> list[dict]:
    """Segment one block while preserving SEC abbreviations and punctuation."""
    sentences = []
    sentence_start = 0
    for index in range(len(text)):
        if not _is_sentence_boundary(text, index):
            continue

        segment_start = sentence_start
        segment_end = index + 1
        segment = text[segment_start:segment_end]
        leading = len(segment) - len(segment.lstrip())
        trailing = len(segment) - len(segment.rstrip())
        raw_start = segment_start + leading
        raw_end = segment_end - trailing
        sentence_text = text[raw_start:raw_end]
        if sentence_text:
            sentences.append(
                {
                    "sentence_order": len(sentences),
                    "raw_text": text[raw_start:raw_end],
                    "text": sentence_text,
                    "_start_offset": raw_start,
                    "_end_offset": raw_end,
                }
            )
        sentence_start = index + 1

    remainder = text[sentence_start:].strip()
    if remainder:
        sentences.append(
            {
                "sentence_order": len(sentences),
                "raw_text": text[sentence_start:].strip(),
                "text": remainder,
                "_start_offset": sentence_start + len(text[sentence_start:]) - len(text[sentence_start:].lstrip()),
                "_end_offset": len(text),
            }
        )
    return sentences


def _raw_offset_map(raw_text: str, normalized_text: str) -> list[int]:
    """Map every normalized-text offset to its raw-text offset."""
    offsets = [0]
    raw_index = 0
    for character in normalized_text:
        if raw_text.startswith("\r\n", raw_index):
            raw_index += 2
        elif raw_text.startswith("\r", raw_index):
            raw_index += 1
        else:
            raw_index += 1
        offsets.append(raw_index)
    return offsets


def _boundary_diagnostics(text: str, offset_map: list[int]) -> list[dict]:
    """Find likely sentence boundaries that lack whitespace."""
    diagnostics = []
    for index, character in enumerate(text[:-1]):
        if character not in ".!?" or text[index + 1].isspace():
            continue
        if character == "." and _is_abbreviation_period(text, index):
            continue
        if text[index + 1].isupper():
            diagnostics.append(
                {
                    "type": "possible_sentence_boundary_without_whitespace",
                    "start_offset": offset_map[index],
                    "end_offset": offset_map[index + 1],
                    "message": "Punctuation is followed immediately by an uppercase character",
                }
            )
    return diagnostics


def split_blocks(text: str, raw_text: str | None = None) -> tuple[list[dict], list[dict]]:
    """Split normalized Item 1A text into blocks and parser diagnostics."""
    raw_text = text if raw_text is None else raw_text
    offset_map = _raw_offset_map(raw_text, text)
    line_records = []
    offset = 0
    for line_with_ending in text.splitlines(keepends=True):
        line = line_with_ending[:-1] if line_with_ending.endswith("\n") else line_with_ending
        line_records.append((line, offset, offset + len(line)))
        offset += len(line_with_ending)

    lines = [record[0] for record in line_records]
    headings = {item["line_number"]: item for item in detect_headings(text)}
    blocks = []
    current = None
    heading_path = []

    def flush_current():
        if current is not None:
            start_offset = current.pop("_start_offset")
            end_offset = current.pop("_end_offset")
            current["raw_block_text"] = raw_text[
                offset_map[start_offset] : offset_map[end_offset]
            ]
            current["text"] = "\n".join(current.pop("text_lines"))
            current["_normalized_start_offset"] = start_offset
            current["_normalized_end_offset"] = end_offset
            current["start_offset"] = offset_map[start_offset]
            current["end_offset"] = offset_map[end_offset]
            blocks.append(current.copy())

    for line_number, (line, line_start, line_end) in enumerate(line_records):
        stripped = line.strip()
        heading = headings.get(line_number)
        marker = _list_marker(line)

        if not stripped:
            flush_current()
            current = None
            continue

        if heading:
            flush_current()
            current = None
            heading_path = heading["heading_path"]
            blocks.append(
                {
                    "block_order": len(blocks),
                    "block_type": "heading",
                    "heading": heading["heading"],
                    "heading_path": heading_path.copy(),
                    "start_line": line_number,
                    "end_line": line_number,
                    "_normalized_start_offset": line_start,
                    "_normalized_end_offset": line_end,
                    "start_offset": offset_map[line_start],
                    "end_offset": offset_map[line_end],
                    "raw_block_text": raw_text[offset_map[line_start] : offset_map[line_end]],
                    "text": heading["heading"],
                    "is_bullet": False,
                    "is_list_item": False,
                }
            )
            continue

        if marker:
            flush_current()
            current = {
                "block_order": len(blocks),
                "block_type": "list_item",
                "heading": heading_path[-1] if heading_path else None,
                "heading_path": heading_path.copy(),
                "start_line": line_number,
                "end_line": line_number,
                "_start_offset": line_start,
                "_end_offset": line_end,
                "raw_lines": [line],
                "text_lines": [_clean_list_text(line)],
                "is_bullet": True,
                "is_list_item": True,
            }
            continue

        if current is not None and current["is_list_item"]:
            current["raw_lines"].append(line)
            current["text_lines"].append(stripped)
            current["end_line"] = line_number
            current["_end_offset"] = line_end
            continue

        if current is not None:
            current["raw_lines"].append(line)
            current["text_lines"].append(stripped)
            current["end_line"] = line_number
            current["_end_offset"] = line_end
            continue

        next_nonempty = next(
            (candidate.strip() for candidate in lines[line_number + 1 :] if candidate.strip()),
            None,
        )
        block_type = (
            "bullet_group"
            if stripped.endswith(":") and next_nonempty and _list_marker(next_nonempty)
            else "paragraph"
        )
        current = {
            "block_order": len(blocks),
            "block_type": block_type,
            "heading": heading_path[-1] if heading_path else None,
            "heading_path": heading_path.copy(),
            "start_line": line_number,
            "end_line": line_number,
            "_start_offset": line_start,
            "_end_offset": line_end,
            "raw_lines": [line],
            "text_lines": [stripped],
            "is_bullet": False,
            "is_list_item": False,
        }

    flush_current()
    diagnostics = _boundary_diagnostics(text, offset_map)
    for diagnostic in detect_heading_diagnostics(text):
        line_number = diagnostic["line_number"]
        if line_number < len(line_records):
            _, line_start, line_end = line_records[line_number]
            diagnostic["start_offset"] = offset_map[line_start]
            diagnostic["end_offset"] = offset_map[line_end]
        diagnostics.append(diagnostic)

    for block_order, block in enumerate(blocks):
        block["block_order"] = block_order
        if block["block_type"] == "heading":
            block["sentences"] = []
            block["contains_inline_bullets"] = False
            block["list_items"] = []
            continue

        normalized_start_offset = block.pop("_normalized_start_offset")
        normalized_end_offset = block.pop("_normalized_end_offset")
        normalized_block = text[normalized_start_offset:normalized_end_offset]
        sentences = []
        for sentence in segment_sentences(normalized_block):
            start = sentence.pop("_start_offset")
            end = sentence.pop("_end_offset")
            normalized_start = normalized_start_offset + start
            normalized_end = normalized_start_offset + end
            raw_start = offset_map[normalized_start]
            raw_end = offset_map[normalized_end]
            sentence["start_offset"] = raw_start
            sentence["end_offset"] = raw_end
            sentence["raw_text"] = raw_text[raw_start:raw_end]
            sentence["boundary_uncertain"] = any(
                diagnostic["start_offset"] >= raw_start
                and diagnostic["start_offset"] < raw_end
                for diagnostic in diagnostics
            )
            sentences.append(sentence)
        inline_items = _extract_inline_list_items(block["text"])
        if inline_items and block["block_type"] == "paragraph":
            block["block_type"] = "inline_bullet_group"
        block["contains_inline_bullets"] = bool(inline_items)
        block["list_items"] = inline_items
        block["sentences"] = sentences
    return blocks, diagnostics


def _stable_id(prefix: str, values: dict) -> str:
    """Create a deterministic ID from canonical record values."""
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def assign_structured_ids(
    filing_id: str, blocks: list[dict], diagnostics: list[dict]
) -> None:
    """Assign deterministic IDs to blocks, sentences, and diagnostics in place."""
    for block in blocks:
        block["filing_id"] = filing_id
        block["block_id"] = _stable_id(
            "block",
            {
                "filing_id": filing_id,
                "start_offset": block["start_offset"],
                "end_offset": block["end_offset"],
                "block_type": block["block_type"],
            },
        )
        for sentence in block["sentences"]:
            sentence["filing_id"] = filing_id
            sentence["block_id"] = block["block_id"]
            sentence["sentence_id"] = _stable_id(
                "sentence",
                {
                    "block_id": block["block_id"],
                    "start_offset": sentence["start_offset"],
                    "end_offset": sentence["end_offset"],
                    "sentence_order": sentence["sentence_order"],
                },
            )
        for item in block.get("list_items", []):
            item["list_item_id"] = _stable_id(
                "list-item",
                {
                    "block_id": block["block_id"],
                    "item_order": item["item_order"],
                    "text": item["text"],
                },
            )

    for diagnostic in diagnostics:
        diagnostic["filing_id"] = filing_id
        diagnostic["diagnostic_id"] = _stable_id(
            "diagnostic",
            {
                "filing_id": filing_id,
                "type": diagnostic["type"],
                "start_offset": diagnostic["start_offset"],
                "end_offset": diagnostic["end_offset"],
            },
        )


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
    blocks, diagnostics = split_blocks(normalized_text, item_1a_text)
    filing_id = _filing_id(raw_record)
    assign_structured_ids(filing_id, blocks, diagnostics)
    metadata = {
        key: value for key, value in raw_record.items() if key != "item_1A"
    }
    return {
        "filing_id": filing_id,
        **metadata,
        "item_1a_text": item_1a_text,
        "raw_text": item_1a_text,
        "text": normalized_text,
        "normalization_status": "line_endings_only",
        "headings": detect_headings(normalized_text),
        "blocks": blocks,
        "parser_diagnostics": diagnostics,
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
    records: list[dict] | None = None,
) -> tuple[Path, int]:
    """Write filing-level records as UTF-8 JSON Lines."""
    records = extract_filing_records(source_dir) if records is None else records
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path, len(records)


def write_structured_tables(
    records: list[dict], output_dir: Path = ROOT_DIR / "data/raw"
) -> dict[str, Path]:
    """Write block, sentence, and diagnostic tables from extracted records."""
    import pandas as pd

    block_rows = []
    sentence_rows = []
    diagnostic_rows = []
    for record in records:
        for block in record["blocks"]:
            block_rows.append(
                {
                    "filing_id": record["filing_id"],
                    "block_id": block["block_id"],
                    "block_order": block["block_order"],
                    "block_type": block["block_type"],
                    "heading": block["heading"],
                    "heading_path": json.dumps(block["heading_path"]),
                    "start_line": block["start_line"],
                    "end_line": block["end_line"],
                    "start_offset": block["start_offset"],
                    "end_offset": block["end_offset"],
                    "raw_block_text": block["raw_block_text"],
                    "text": block["text"],
                    "is_bullet": block["is_bullet"],
                    "is_list_item": block["is_list_item"],
                    "contains_inline_bullets": block["contains_inline_bullets"],
                    "list_items": json.dumps(block.get("list_items", []), ensure_ascii=False),
                }
            )
            for sentence in block["sentences"]:
                sentence_rows.append(
                    {
                        "filing_id": record["filing_id"],
                        "block_id": block["block_id"],
                        "sentence_id": sentence["sentence_id"],
                        "sentence_order": sentence["sentence_order"],
                        "raw_text": sentence["raw_text"],
                        "text": sentence["text"],
                        "start_offset": sentence["start_offset"],
                        "end_offset": sentence["end_offset"],
                        "boundary_uncertain": sentence["boundary_uncertain"],
                    }
                )
        for diagnostic in record["parser_diagnostics"]:
            diagnostic_rows.append(diagnostic)

    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "blocks": ("blocks.csv", block_rows),
        "sentences": ("sentences.csv", sentence_rows),
        "parser_diagnostics": ("parser_diagnostics.csv", diagnostic_rows),
    }
    paths = {}
    for name, (filename, rows) in tables.items():
        path = output_dir / filename
        pd.DataFrame(rows).to_csv(path, index=False)
        paths[name] = path
    return paths
