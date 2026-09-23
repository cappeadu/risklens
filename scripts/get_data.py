from scripts.filings import DataCreator


def create_csv_dataset(file_name: str = "sec_10k"):
    """Compatibility wrapper for the shared filing CSV creator."""
    return DataCreator.create_csv_dataset(file_name=file_name)


if __name__ == "__main__":
    create_csv_dataset()
