import pandas as pd

from configs.config import ROOT_DIR, logger


def load_dataset(
    file_name: str = "sec_10k",
    num_sample: int | None = None,
    random_state: int | None = 42,
):
    file_path = ROOT_DIR / f"data/raw/{file_name}.csv"
    df = pd.read_csv(file_path)
    df = df.sample(num_sample, random_state=random_state) if num_sample else df
    logger.info(f"{file_name} dataset loaded")
    return df


if __name__ == "__main__":
    load_dataset()
