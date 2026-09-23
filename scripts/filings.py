import json

import pandas as pd

from configs.config import ROOT_DIR, logger


class DataCreator:
    """Downloads company CIK's as well as creating .csv dataset for filings."""

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

    @staticmethod
    def create_csv_dataset(file_name: str = "sec_10k"):
        """Create CSV dataset for filings. Searches for filings in .json and creates a CSV.

        Args:
            file_name (str, optional): File name for CSV. Defaults to "sec_10k".
        """
        filings_path = ROOT_DIR / "data/extracted_filings/10-K"
        output_path = ROOT_DIR / f"data/raw/{file_name}.csv"

        data = []
        for file_path in filings_path.glob("*.json"):
            with open(file_path, encoding="utf-8") as f:
                data.append(json.load(f))
        df = pd.DataFrame(data)

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
