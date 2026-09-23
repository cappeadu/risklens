import json

import pandas as pd

from configs.config import ROOT_DIR, logger


def download_company_cik(file_name: str = "company_ciks", sample: int | None = None):
    """Download company CIK for S&P 500 companies as .txt file.

    Args:
        file_name (str, optional): File name for CIKs. Defaults to "company_ciks".
        sample (int | None, optional): If chosen, select a sample of CIKs. Defaults to None.
    """
    sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    companies_df = pd.read_html(
        sp500_url, storage_options={"User-Agent": "Mozilla/5.0"}
    )[0]
    companies_df = companies_df.sample(sample) if sample else companies_df
    output_path = ROOT_DIR / f"data/raw/{file_name}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, "w") as f:
            ciks_str = [f"{cik!s}\n" for cik in companies_df.CIK]
            f.writelines(ciks_str)
    except FileNotFoundError as e:
        print(e)
    total_ciks = {"total_ciks_downloaded": len(ciks_str)}
    logger.info(json.dumps(total_ciks, indent=2))


if __name__ == "__main__":
    download_company_cik(sample=5)
