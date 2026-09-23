import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from configs.config import ROOT_DIR, logger

SEC_ARCHIVE_PATTERN = re.compile(
    r"/Archives/edgar/data/(?P<cik>\d+)/"
    r"(?P<accession>\d{10}-\d{2}-\d{6}|\d{18})",
    re.IGNORECASE,
)
FILING_FILENAME_PATTERN = re.compile(
    r"(?P<cik>\d+)_10K_(?P<year>\d{4})_(?P<accession>\d{10}-\d{2}-\d{6})"
)


class DataCreator:
    """Download company CIKs and create derived filing datasets.

    Raw extracted filings are read-only inputs. This class never writes to the
    raw filings directory; derived outputs are written separately.
    """

    RAW_FILINGS_DIR = ROOT_DIR / "data/extracted_filings/10-K"
    DERIVED_DATA_DIR = ROOT_DIR / "data/raw"
    MANIFEST_FILENAME = "dataset_manifest.json"
    DATASET_VERSION = "filings-v1"
    PARSER_VERSION = "not-yet-parsed"
    NORMALIZATION_VERSION = "raw-text-only"
    REQUIRED_METADATA_FIELDS = (
        "cik",
        "company",
        "filing_type",
        "filing_date",
        "period_of_report",
        "filename",
        "item_1A",
    )
    SOURCE_LINK_FIELDS = (
        "filing_html_index",
        "htm_filing_link",
        "complete_text_filing_link",
    )

    def __init__(self):
        self.sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    def download_company_cik(
        self, file_name: str = "company_ciks", num_sample: int | None = None
    ):
        """Download company CIK for S&P 500 companies as .txt file.

        Args:
            file_name (str, optional): File name for CIKs. Defaults to "company_ciks".
            sample (int | None, optional): If chosen, select a sample of CIKs. Defaults to None.
        """

        companies_df = pd.read_html(
            self.sp500_url, storage_options={"User-Agent": "Mozilla/5.0"}
        )[0]
        companies_df = companies_df.sample(num_sample) if num_sample else companies_df
        output_path = ROOT_DIR / f"data/raw/{file_name}.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(output_path, "w") as f:
                ciks_str = [f"{cik!s}\n" for cik in companies_df.CIK]
                f.writelines(ciks_str)
        except FileNotFoundError as e:
            logger.error(e)
        metadata_ciks = {
            "total_ciks_downloaded": len(ciks_str),
            "downloaded from": self.sp500_url,
        }
        logger.info(json.dumps(metadata_ciks, indent=2))
        return ciks_str

    @classmethod
    def load_raw_filings(cls):
        """Load extracted filing JSON records without modifying source files.

        Returns:
            list[dict]: Filing records read from the raw extracted-filings
                directory in deterministic filename order.

        Raises:
            FileNotFoundError: If the raw filings directory does not exist.
        """
        if not cls.RAW_FILINGS_DIR.is_dir():
            raise FileNotFoundError(
                f"Raw filings directory does not exist: {cls.RAW_FILINGS_DIR}"
            )

        records = []
        for file_path in cls._raw_filing_paths():
            with file_path.open(encoding="utf-8") as file:
                records.append(json.load(file))
        return records

    @classmethod
    def _raw_filing_paths(cls):
        """Return raw filing paths in deterministic order."""
        if not cls.RAW_FILINGS_DIR.is_dir():
            raise FileNotFoundError(
                f"Raw filings directory does not exist: {cls.RAW_FILINGS_DIR}"
            )
        return sorted(cls.RAW_FILINGS_DIR.glob("*.json"))

    @staticmethod
    def _normalized_identifier(value):
        """Normalize numeric identifiers for consistency checks."""
        return str(value).strip().lstrip("0") or "0"

    @staticmethod
    def _normalized_accession(value):
        """Normalize hyphenated and compact SEC accession formats."""
        return str(value).strip().replace("-", "")

    @classmethod
    def _validate_filing(cls, file_path: Path, record: dict):
        """Return validation issues for one raw filing record."""
        issues = []

        for field in cls.REQUIRED_METADATA_FIELDS:
            if field not in record or record[field] in (None, ""):
                issues.append(
                    {
                        "severity": "error",
                        "file": file_path.name,
                        "field": field,
                        "message": "Required filing metadata is missing",
                    }
                )

        filename = str(record.get("filename", ""))
        filename_parts = FILING_FILENAME_PATTERN.fullmatch(Path(filename).stem)
        source_parts = FILING_FILENAME_PATTERN.fullmatch(file_path.stem)
        if filename and Path(filename).stem != file_path.stem:
            issues.append(
                {
                    "severity": "error",
                    "file": file_path.name,
                    "field": "filename",
                    "message": "Record filename does not match source JSON filename",
                }
            )

        if source_parts and "cik" in record:
            if cls._normalized_identifier(record["cik"]) != cls._normalized_identifier(
                source_parts.group("cik")
            ):
                issues.append(
                    {
                        "severity": "error",
                        "file": file_path.name,
                        "field": "cik",
                        "message": "Record CIK does not match source filename",
                    }
                )

        if filename_parts and source_parts:
            if filename_parts.group("accession") != source_parts.group("accession"):
                issues.append(
                    {
                        "severity": "error",
                        "file": file_path.name,
                        "field": "filename",
                        "message": "Record accession does not match source filename",
                    }
                )

        for field in cls.SOURCE_LINK_FIELDS:
            link = record.get(field)
            parsed = urlparse(str(link)) if link else None
            if (
                not parsed
                or parsed.scheme != "https"
                or parsed.netloc.lower() != "www.sec.gov"
            ):
                issues.append(
                    {
                        "severity": "error",
                        "file": file_path.name,
                        "field": field,
                        "message": "Source link must be an HTTPS www.sec.gov URL",
                    }
                )
                continue

            archive_match = SEC_ARCHIVE_PATTERN.search(parsed.path)
            if not archive_match or not source_parts:
                issues.append(
                    {
                        "severity": "warning",
                        "file": file_path.name,
                        "field": field,
                        "message": "SEC source link does not contain a recognizable accession path",
                    }
                )
                continue

            if archive_match.group("cik").lstrip("0") != source_parts.group(
                "cik"
            ).lstrip("0"):
                issues.append(
                    {
                        "severity": "warning",
                        "file": file_path.name,
                        "field": field,
                        "message": "SEC URL archive CIK differs from source filename CIK",
                    }
                )
            if cls._normalized_accession(
                archive_match.group("accession")
            ) != cls._normalized_accession(source_parts.group("accession")):
                issues.append(
                    {
                        "severity": "warning",
                        "file": file_path.name,
                        "field": field,
                        "message": "SEC URL accession differs from source filename accession",
                    }
                )

        return issues

    @classmethod
    def validate_raw_filings(cls, strict: bool = False):
        """Validate raw filing metadata and SEC source links.

        Args:
            strict: Raise ``ValueError`` when any error-level issue is found.

        Returns:
            list[dict]: Validation issues with severity, file, field, and message.
        """
        issues = []
        for file_path in cls._raw_filing_paths():
            try:
                with file_path.open(encoding="utf-8") as file:
                    record = json.load(file)
            except json.JSONDecodeError as error:
                issues.append(
                    {
                        "severity": "error",
                        "file": file_path.name,
                        "field": None,
                        "message": f"Invalid JSON: {error.msg}",
                    }
                )
                continue
            issues.extend(cls._validate_filing(file_path, record))

        if strict and any(issue["severity"] == "error" for issue in issues):
            raise ValueError(json.dumps(issues, indent=2))
        return issues

    @staticmethod
    def _sha256_file(file_path: Path):
        """Return the SHA-256 digest for a source file."""
        digest = hashlib.sha256()
        with file_path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def write_dataset_manifest(cls, records, validation_issues):
        """Write a manifest describing the current derived filing dataset."""
        source_paths = cls._raw_filing_paths()
        manifest = {
            "dataset_version": cls.DATASET_VERSION,
            "source_glob": "data/extracted_filings/10-K/*.json",
            "source_file_count": len(source_paths),
            "source_hashes": {
                file_path.name: cls._sha256_file(file_path)
                for file_path in source_paths
            },
            "parser_version": cls.PARSER_VERSION,
            "normalization_version": cls.NORMALIZATION_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "record_counts": {
                "filings": len(records),
                "blocks": 0,
                "sentences": 0,
            },
            "validation": {
                "issue_count": len(validation_issues),
                "errors": sum(
                    issue["severity"] == "error" for issue in validation_issues
                ),
                "warnings": sum(
                    issue["severity"] == "warning" for issue in validation_issues
                ),
            },
        }

        manifest_path = cls.DERIVED_DATA_DIR / cls.MANIFEST_FILENAME
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", encoding="utf-8") as file:
            json.dump(manifest, file, indent=2)
            file.write("\n")
        return manifest_path

    @classmethod
    def create_csv_dataset(cls, file_name: str = "sec_10k"):
        """Create CSV dataset for filings. Searches for filings in .json and creates a CSV.

        Args:
            file_name (str, optional): File name for CSV. Defaults to "sec_10k".
        """
        output_path = cls.DERIVED_DATA_DIR / f"{file_name}.csv"
        if output_path.resolve().is_relative_to(cls.RAW_FILINGS_DIR.resolve()):
            raise ValueError("Derived output cannot be written inside raw filings")

        validation_issues = cls.validate_raw_filings()
        if validation_issues:
            logger.info(
                json.dumps(
                    {
                        "validation_issue_count": len(validation_issues),
                        "validation_errors": sum(
                            issue["severity"] == "error" for issue in validation_issues
                        ),
                        "validation_warnings": sum(
                            issue["severity"] == "warning"
                            for issue in validation_issues
                        ),
                    },
                    indent=2,
                )
            )

        records = cls.load_raw_filings()
        df = pd.DataFrame(records)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        df_metadata = {
            "filing_type": "SEC 10-K Item 1A",
            "total_columns": df.shape[1],
            "data_size (rows)": df.shape[0],
        }
        logger.info(json.dumps(df_metadata, indent=2))
        manifest_path = cls.write_dataset_manifest(records, validation_issues)
        logger.info(f"Dataset manifest written: {manifest_path}")
        return df


if __name__ == "__main__":
    data_creator = DataCreator()
    # download cik in csv
    ciks = data_creator.download_company_cik(num_sample=5)
    # create filings in csv
    df = data_creator.create_csv_dataset()
