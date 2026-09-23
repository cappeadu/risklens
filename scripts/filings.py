import json

import pandas as pd

from configs.config import ROOT_DIR, logger


class DataCreator:
    """Download company CIKs and create derived filing datasets.

    Raw extracted filings are read-only inputs. This class never writes to the
    raw filings directory; derived outputs are written separately.
    """

    RAW_FILINGS_DIR = ROOT_DIR / "data/extracted_filings/10-K"
    DERIVED_DATA_DIR = ROOT_DIR / "data/raw"

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
        for file_path in sorted(cls.RAW_FILINGS_DIR.glob("*.json")):
            with file_path.open(encoding="utf-8") as file:
                records.append(json.load(file))
        return records

    @classmethod
    def create_csv_dataset(cls, file_name: str = "sec_10k"):
        """Create CSV dataset for filings. Searches for filings in .json and creates a CSV.

        Args:
            file_name (str, optional): File name for CSV. Defaults to "sec_10k".
        """
        output_path = cls.DERIVED_DATA_DIR / f"{file_name}.csv"
        if output_path.resolve().is_relative_to(cls.RAW_FILINGS_DIR.resolve()):
            raise ValueError("Derived output cannot be written inside raw filings")

        df = pd.DataFrame(cls.load_raw_filings())

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        df_metadata = {
            "filing_type": "SEC 10-K Item 1A",
            "total_columns": df.shape[1],
            "data_size (rows)": df.shape[0],
        }
        logger.info(json.dumps(df_metadata, indent=2))
        return df


if __name__ == "__main__":
    data_creator = DataCreator()
    # download cik in csv
    ciks = data_creator.download_company_cik(num_sample=5)
    # create filings in csv
    df = data_creator.create_csv_dataset()
