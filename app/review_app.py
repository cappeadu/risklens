"""Read-only Streamlit reviewer for generated Item 1A outputs."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data/raw"
RECORDS_PATH = DATA_DIR / "filing_records.jsonl"


@st.cache_data
def load_filing_records(path: str) -> list[dict]:
    """Load generated filing records without writing or regenerating data."""
    records = []
    with Path(path).open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))
    return records


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    """Load an optional generated CSV for tabular review."""
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def filing_label(record: dict) -> str:
    return "{} — {}".format(record.get("company", "Unknown company"), record.get("filename", "Unknown filing"))


def render_metadata(record: dict) -> None:
    metadata = {
        key: record.get(key)
        for key in (
            "filing_id",
            "cik",
            "company",
            "filing_type",
            "filing_date",
            "period_of_report",
            "sic",
            "filename",
            "filing_html_index",
            "htm_filing_link",
            "complete_text_filing_link",
        )
        if record.get(key) is not None
    }
    st.json(metadata, expanded=False)


def render_block_review(record: dict) -> None:
    blocks = record.get("blocks") or []
    if not blocks:
        st.warning("This filing has no generated blocks.")
        return

    if "block_index" not in st.session_state:
        st.session_state.block_index = 0
    st.session_state.block_index = min(
        st.session_state.block_index, len(blocks) - 1
    )

    previous, counter, next_button = st.columns([1, 2, 1])
    with previous:
        if st.button("← Previous", disabled=st.session_state.block_index == 0):
            st.session_state.block_index -= 1
    with next_button:
        if st.button(
            "Next →", disabled=st.session_state.block_index >= len(blocks) - 1
        ):
            st.session_state.block_index += 1

    block_index = st.session_state.block_index
    with counter:
        st.markdown(
            "<div style='text-align:center;padding-top:8px'>Block {} of {}</div>".format(
                block_index + 1, len(blocks)
            ),
            unsafe_allow_html=True,
        )

    block = blocks[block_index]
    st.subheader(block.get("heading") or block.get("block_type", "Block"))
    st.caption("Heading path: {}".format(" > ".join(block.get("heading_path") or [])))
    st.write(
        {
            "block_id": block.get("block_id"),
            "block_type": block.get("block_type"),
            "source_offsets": [block.get("start_offset"), block.get("end_offset")],
            "line_range": [block.get("start_line"), block.get("end_line")],
            "is_bullet": block.get("is_bullet"),
            "is_list_item": block.get("is_list_item"),
        }
    )
    st.text_area("Raw block text", block.get("raw_block_text", ""), height=220, disabled=True)
    st.text_area("Normalized block text", block.get("text", ""), height=220, disabled=True)

    sentences = block.get("sentences") or []
    st.markdown("#### Sentences in this block")
    if not sentences:
        st.info("No sentences are attached to this block.")
    for sentence in sentences:
        uncertainty = " ⚠️ boundary uncertain" if sentence.get("boundary_uncertain") else ""
        with st.container(border=True):
            st.markdown("**Sentence {}{}**".format(sentence.get("sentence_order", 0) + 1, uncertainty))
            st.caption(
                "{} | offsets: [{}:{}]".format(
                    sentence.get("sentence_id", "no ID"),
                    sentence.get("start_offset", "?"),
                    sentence.get("end_offset", "?"),
                )
            )
            st.write(sentence.get("text", ""))


def render_tables(record: dict) -> None:
    filing_id = record.get("filing_id")
    table_specs = (
        ("Filing metadata", "filings.csv"),
        ("Blocks", "blocks.csv"),
        ("Sentences", "sentences.csv"),
        ("Diagnostics", "parser_diagnostics.csv"),
    )
    tabs = st.tabs([name for name, _ in table_specs])
    for tab, (name, filename) in zip(tabs, table_specs):
        with tab:
            frame = load_csv(str(DATA_DIR / filename))
            if frame.empty:
                st.info("{} is not available yet.".format(filename))
                continue
            if "filing_id" in frame.columns:
                frame = frame[frame["filing_id"].astype(str) == str(filing_id)]
            elif "filename" in frame.columns:
                frame = frame[frame["filename"].astype(str) == str(record.get("filename"))]
            st.dataframe(frame, use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="RiskLens Item 1A Review", layout="wide")
    st.title("RiskLens Item 1A Review")
    st.caption("Read-only inspection of generated Phase 1 outputs")

    if not RECORDS_PATH.exists():
        st.error("Generated filing_records.jsonl was not found under data/raw/.")
        st.info("Run the extraction command manually, then refresh this page.")
        st.stop()

    records = load_filing_records(str(RECORDS_PATH))
    if not records:
        st.warning("No filing records were found.")
        st.stop()

    record_by_id = {record.get("filing_id"): record for record in records}
    filing_ids = list(record_by_id)
    selected_id = st.sidebar.selectbox(
        "Filing",
        filing_ids,
        format_func=lambda filing_id: filing_label(record_by_id[filing_id]),
    )
    if st.session_state.get("selected_filing_id") != selected_id:
        st.session_state.selected_filing_id = selected_id
        st.session_state.block_index = 0

    record = record_by_id[selected_id]
    blocks = record.get("blocks") or []
    sentences = [sentence for block in blocks for sentence in block.get("sentences", [])]
    diagnostics = record.get("parser_diagnostics") or []
    counts = {
        "blocks": len(blocks),
        "sentences": len(sentences),
        "headings": sum(block.get("block_type") == "heading" for block in blocks),
        "list_items": sum(block.get("is_list_item", False) for block in blocks),
        "uncertain_boundaries": sum(sentence.get("boundary_uncertain", False) for sentence in sentences),
        "diagnostics": len(diagnostics),
    }

    render_metadata(record)
    metric_columns = st.columns(len(counts))
    for column, (label, value) in zip(metric_columns, counts.items()):
        column.metric(label.replace("_", " ").title(), value)

    overview, full_text, blocks_tab, tables_tab = st.tabs(
        ["Overview", "Full Item 1A", "Block Review", "Tables and Diagnostics"]
    )
    with overview:
        st.write("This reviewer is read-only. It does not regenerate JSONL or CSV outputs.")
        st.write(counts)
    with full_text:
        st.text_area("Complete Item 1A", record.get("item_1a_text", ""), height=650, disabled=True)
    with blocks_tab:
        render_block_review(record)
    with tables_tab:
        render_tables(record)


if __name__ == "__main__":
    main()
