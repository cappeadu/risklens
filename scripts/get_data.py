import json

import pandas as pd

from configs.config import ROOT_DIR, logger


def create_csv_dataset(file_name: str = "sec_10k"):
    """Create CSV dataset for filings.

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


if __name__ == "__main__":
    create_csv_dataset()
