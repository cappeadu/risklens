"""Streamlit app for manual Phase 2 Item 1A annotation."""

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_DIR = PROJECT_ROOT / "data/annotations"
CANDIDATES_PATH = ANNOTATIONS_DIR / "annotation_candidates_v1.jsonl"
ANNOTATIONS_PATH = ANNOTATIONS_DIR / "annotations_v1.jsonl"
SOURCE_RECORDS_PATH = PROJECT_ROOT / "data/raw/filing_records.jsonl"
GUIDELINE_VERSION = "v1"
LABELS = (
    "RISK_STATEMENT",
    "MITIGATION",
    "SUPPORTED_CONTEXT",
    "BOILERPLATE",
)


@st.cache_data
def load_jsonl(path: str) -> list[dict]:
    """Load JSONL records without changing the source file."""
    records = []
    with Path(path).open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))
    return records


def load_candidates() -> list[dict]:
    if not CANDIDATES_PATH.exists():
        return []
    return load_jsonl(str(CANDIDATES_PATH))


@st.cache_data
def build_block_index(path: str) -> dict[tuple[str, str], dict]:
    """Index source blocks so annotation context can include neighboring sentences."""
    records = load_jsonl(path)
    return {
        (str(record.get("filing_id")), str(block.get("block_id"))): {
            "filing_id": record.get("filing_id"),
            "filename": record.get("filename"),
            "block": block,
        }
        for record in records
        for block in record.get("blocks") or []
    }


def source_context(candidate: dict) -> dict:
    """Return the containing block and neighboring source sentences."""
    if not SOURCE_RECORDS_PATH.exists():
        return {}

    indexed = build_block_index(str(SOURCE_RECORDS_PATH))
    source = indexed.get(
        (str(candidate.get("filing_id")), str(candidate.get("block_id")))
    )
    if not source:
        return {}

    block = source["block"]
    sentences = block.get("sentences") or []
    sentence_index = next(
        (
            index
            for index, sentence in enumerate(sentences)
            if str(sentence.get("sentence_id")) == str(candidate.get("sentence_id"))
        ),
        None,
    )
    if sentence_index is None:
        return {"block": block, "filename": source.get("filename")}

    return {
        "block": block,
        "filename": source.get("filename"),
        "previous_sentence": sentences[sentence_index - 1]
        if sentence_index > 0
        else None,
        "next_sentence": sentences[sentence_index + 1]
        if sentence_index + 1 < len(sentences)
        else None,
    }


def load_annotations() -> dict[tuple[str, str], dict]:
    if not ANNOTATIONS_PATH.exists():
        return {}
    records = load_jsonl(str(ANNOTATIONS_PATH))
    return {
        (str(record.get("annotator_id")), str(record.get("sentence_id"))): record
        for record in records
    }


def annotation_key(annotator_id: str, sentence_id: str) -> tuple[str, str]:
    return annotator_id.strip(), str(sentence_id)


def set_label_state(sentence_id: str, annotation: dict | None) -> None:
    """Initialize the widget state for the selected sentence."""
    label_key = f"labels_{sentence_id}"
    none_key = f"none_other_{sentence_id}"
    if label_key in st.session_state or none_key in st.session_state:
        return
    st.session_state[label_key] = (annotation or {}).get("labels", [])
    st.session_state[none_key] = bool((annotation or {}).get("none_other", False))


def labels_changed(sentence_id: str) -> None:
    """Selecting any target label automatically disables NONE_OTHER."""
    if st.session_state.get(f"labels_{sentence_id}"):
        st.session_state[f"none_other_{sentence_id}"] = False


def none_other_changed(sentence_id: str) -> None:
    """Selecting NONE_OTHER automatically clears all target labels."""
    if st.session_state.get(f"none_other_{sentence_id}"):
        st.session_state[f"labels_{sentence_id}"] = []


def _set_none_false(label_key: str, none_key: str) -> None:
    if st.session_state.get(label_key):
        st.session_state[none_key] = False


def _clear_labels_when_none(none_key: str, label_key: str) -> None:
    if st.session_state.get(none_key):
        st.session_state[label_key] = []


def save_annotation(annotation: dict, existing: dict[tuple[str, str], dict]) -> None:
    """Upsert one annotation while preserving other annotators and sentences."""
    key = annotation_key(annotation["annotator_id"], annotation["sentence_id"])
    existing[key] = annotation
    ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        existing.values(),
        key=lambda record: (
            str(record.get("sentence_id")),
            str(record.get("annotator_id")),
        ),
    )
    with ANNOTATIONS_PATH.open("w", encoding="utf-8", newline="\n") as file:
        for record in ordered:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_annotation(
    candidate: dict,
    annotator_id: str,
    labels: list[str],
    none_other: bool,
    rationale: str,
) -> dict:
    return {
        "sentence_id": candidate["sentence_id"],
        "sample_id": candidate.get("sample_id"),
        "filing_id": candidate.get("filing_id"),
        "block_id": candidate.get("block_id"),
        "annotator_id": annotator_id.strip(),
        "labels": labels,
        "none_other": none_other,
        "guideline_version": GUIDELINE_VERSION,
        "annotation_status": "annotated",
        "rationale": rationale.strip(),
        "source_offsets": {
            "start": candidate.get("source_start"),
            "end": candidate.get("source_end"),
        },
        "annotated_at": datetime.now(timezone.utc).isoformat(),
    }


def disagreement_groups(
    annotations: dict[tuple[str, str], dict],
) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for record in annotations.values():
        if record.get("annotation_status") != "annotated":
            continue
        grouped.setdefault(str(record.get("sentence_id")), []).append(record)

    return {
        sentence_id: records
        for sentence_id, records in grouped.items()
        if len(
            {
                (
                    tuple(sorted(record.get("labels", []))),
                    bool(record.get("none_other")),
                )
                for record in records
            }
        )
        > 1
    }


def render_adjudication(
    candidates: list[dict],
    annotations: dict[tuple[str, str], dict],
    adjudicator_id: str,
) -> None:
    candidate_by_id = {
        str(candidate["sentence_id"]): candidate for candidate in candidates
    }
    disagreements = disagreement_groups(annotations)
    if not disagreements:
        st.success("No disagreements are currently available for adjudication.")
        st.info("Use different annotator IDs to create independent annotations first.")
        return

    selected_id = st.selectbox("Disputed sentence", sorted(disagreements))
    candidate = candidate_by_id.get(selected_id)
    if not candidate:
        st.error("The disputed sentence is missing from the candidate dataset.")
        return

    st.subheader("Sentence context")
    st.write(candidate.get("sentence_text", ""))
    st.caption("Heading path: " + " > ".join(candidate.get("heading_path") or []))
    st.json(disagreements[selected_id], expanded=False)

    adjudicated_key = annotation_key(adjudicator_id, selected_id)
    saved = annotations.get(adjudicated_key, {})
    label_key = f"adjudicated_labels_{selected_id}"
    none_key = f"adjudicated_none_other_{selected_id}"
    if label_key not in st.session_state:
        st.session_state[label_key] = saved.get("labels", [])
    if none_key not in st.session_state:
        st.session_state[none_key] = bool(saved.get("none_other", False))

    st.multiselect(
        "Final labels",
        LABELS,
        key=label_key,
        on_change=_set_none_false,
        args=(label_key, none_key),
    )
    st.checkbox(
        "Final decision is NONE_OTHER",
        key=none_key,
        on_change=_clear_labels_when_none,
        args=(none_key, label_key),
    )
    rationale = st.text_area(
        "Adjudication rationale",
        value=saved.get("rationale", ""),
        height=120,
    )

    if st.button("Save adjudicated decision", type="primary"):
        labels = list(st.session_state.get(label_key, []))
        none_other = bool(st.session_state.get(none_key, False))
        if labels and none_other:
            st.error("Choose final labels or NONE_OTHER, not both.")
            return
        if not labels and not none_other:
            st.error("Select at least one final label or NONE_OTHER.")
            return

        record = build_annotation(
            candidate, adjudicator_id, labels, none_other, rationale
        )
        record["annotation_status"] = "adjudicated"
        record["annotator_labels"] = {
            item.get("annotator_id"): item.get("labels", [])
            for item in disagreements[selected_id]
        }
        record["adjudicated_labels"] = labels
        record["adjudicated_none_other"] = none_other
        save_annotation(record, annotations)
        load_jsonl.clear()
        st.success("Adjudicated decision saved.")


def main() -> None:
    st.set_page_config(page_title="RiskLens Annotation", layout="wide")
    st.title("RiskLens Item 1A Annotation")
    st.caption("Manual Phase 2 annotation; source candidates are read-only.")

    candidates = load_candidates()
    if not candidates:
        st.error("No annotation candidates found.")
        st.info(
            "Run `python -m scripts.sample_annotations` first, then refresh this page."
        )
        st.stop()

    annotator_id = st.sidebar.text_input("Annotator ID", value="annotator_01").strip()
    if not annotator_id:
        st.sidebar.warning("Enter an annotator ID before saving.")
        st.stop()

    annotations = load_annotations()
    mode = st.sidebar.radio("Mode", ["Annotate", "Adjudicate"])
    if mode == "Adjudicate":
        st.caption(
            "Original annotator records remain unchanged; only the adjudicated record is added or updated."
        )
        render_adjudication(candidates, annotations, annotator_id)
        return

    candidate_by_id = {
        str(candidate["sentence_id"]): candidate for candidate in candidates
    }
    annotated_ids = {
        sentence_id
        for (saved_annotator, sentence_id), record in annotations.items()
        if saved_annotator == annotator_id
        and record.get("annotation_status") == "annotated"
    }
    filter_mode = st.sidebar.radio("Candidate filter", ["Unannotated", "All"], index=0)
    visible = [
        candidate
        for candidate in candidates
        if filter_mode == "All" or str(candidate["sentence_id"]) not in annotated_ids
    ]
    if not visible:
        st.success("All candidates are annotated for this annotator.")
        st.stop()

    options = [str(candidate["sentence_id"]) for candidate in visible]
    selected_id = st.sidebar.selectbox(
        "Sentence",
        options,
        format_func=lambda sentence_id: (
            f"{candidate_by_id[sentence_id].get('sample_order', '?')}: "
            f"{candidate_by_id[sentence_id].get('company_name', 'Unknown')}"
        ),
    )
    candidate = candidate_by_id[selected_id]
    saved = annotations.get(annotation_key(annotator_id, selected_id))
    set_label_state(selected_id, saved)

    st.progress(
        len(annotated_ids) / len(candidates),
        text=f"{len(annotated_ids)} of {len(candidates)} candidates saved",
    )
    st.subheader("Sentence context")
    st.write(candidate.get("sentence_text", ""))
    st.json(
        {
            "sample_id": candidate.get("sample_id"),
            "sentence_id": candidate.get("sentence_id"),
            "filing_id": candidate.get("filing_id"),
            "company": candidate.get("company_name"),
            "filename": candidate.get("filename"),
            "block_id": candidate.get("block_id"),
            "block_type": candidate.get("block_type"),
            "heading_path": candidate.get("heading_path"),
            "source_offsets": [
                candidate.get("source_start"),
                candidate.get("source_end"),
            ],
            "boundary_uncertain": candidate.get("boundary_uncertain"),
        },
        expanded=False,
    )
    with st.expander("Neighboring/source context", expanded=False):
        context = source_context(candidate)
        if not context:
            st.info("Source block context is unavailable for this candidate.")
        else:
            block = context["block"]
            st.caption(
                "Source file: {} | Block: {} | Offsets: [{}:{}]".format(
                    context.get("filename", "unknown"),
                    block.get("block_id", "unknown"),
                    block.get("start_offset", "?"),
                    block.get("end_offset", "?"),
                )
            )
            previous = context.get("previous_sentence")
            next_sentence = context.get("next_sentence")
            if previous:
                st.markdown("**Previous sentence**")
                st.write(previous.get("text", ""))
            else:
                st.caption("No previous sentence in this block.")
            st.markdown("**Containing block**")
            st.text_area(
                "Original block text",
                block.get("raw_block_text", block.get("text", "")),
                height=220,
                disabled=True,
                label_visibility="collapsed",
            )
            if next_sentence:
                st.markdown("**Next sentence**")
                st.write(next_sentence.get("text", ""))
            else:
                st.caption("No next sentence in this block.")

    label_key = f"labels_{selected_id}"
    none_key = f"none_other_{selected_id}"
    st.multiselect(
        "Target labels",
        LABELS,
        key=label_key,
        on_change=labels_changed,
        args=(selected_id,),
        help="Labels are independent. More than one may be selected.",
    )
    st.checkbox(
        "NONE_OTHER",
        key=none_key,
        on_change=none_other_changed,
        args=(selected_id,),
        help="Selecting this clears all target labels.",
    )
    rationale = st.text_area(
        "Rationale",
        value=(saved or {}).get("rationale", ""),
        height=120,
        help="Required for NONE_OTHER and useful for ambiguous or multi-label decisions.",
    )

    if st.button("Save annotation", type="primary"):
        labels = list(st.session_state.get(label_key, []))
        none_other = bool(st.session_state.get(none_key, False))
        if labels and none_other:
            st.error("Choose target labels or NONE_OTHER, not both.")
        elif not labels and not none_other:
            st.error("Select at least one target label or NONE_OTHER.")
        elif none_other and not rationale.strip():
            st.error("Add a rationale for NONE_OTHER.")
        else:
            record = build_annotation(
                candidate, annotator_id, labels, none_other, rationale
            )
            save_annotation(record, annotations)
            load_jsonl.clear()
            st.success("Annotation saved.")


if __name__ == "__main__":
    main()
