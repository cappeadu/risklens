"""CLI entry point for Phase 1 structured Item 1A exports."""

from src.item1a import (
    extract_filing_records,
    write_filing_records,
    write_structured_tables,
)

if __name__ == "__main__":
    records = extract_filing_records()
    filing_records_path, record_count = write_filing_records(records=records)
    table_paths = write_structured_tables(records)
    print(f"Wrote {record_count} filing records to {filing_records_path}")
    for table_name, table_path in table_paths.items():
        print(f"Wrote {table_name} table to {table_path}")
