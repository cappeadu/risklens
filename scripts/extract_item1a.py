"""CLI entry point for Phase 1, Stage 1 Item 1A extraction."""

from src.item1a import write_filing_records

if __name__ == "__main__":
    output_path, record_count = write_filing_records()
    print(f"Wrote {record_count} filing records to {output_path}")
