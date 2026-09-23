from scripts.filings import DataCreator


def download_company_cik(file_name: str = "company_ciks", sample: int | None = None):
    """Compatibility wrapper for the shared CIK downloader."""
    return DataCreator().download_company_cik(
        file_name=file_name,
        num_sample=sample,
    )


if __name__ == "__main__":
    download_company_cik(sample=5)
