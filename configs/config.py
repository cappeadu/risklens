import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# to filter logs
def show_info_only(example):
    return example.levelname == "INFO"


# 1. set up logger
logger = logging.getLogger("risklens")
logger.setLevel(logging.DEBUG)

# 2. output format
formatter = logging.Formatter(
    fmt="{levelname} - {asctime} - [{name}:{filename}:{funcName}:{lineno}\n{message}\n]",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
)

# 3. get stream handlers
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)
stream_handler.filter(show_info_only)

# 4. info file handlers
info_handler = RotatingFileHandler(
    LOGS_DIR / "info.log", maxBytes=1024 * 1024 * 5, backupCount=10, encoding="utf-8"
)
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(formatter)

# error file handler
error_handler = RotatingFileHandler(
    LOGS_DIR / "error.log", maxBytes=1024 * 1024 * 5, backupCount=10, encoding="utf-8"
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

# add handlers to logger
logger.addHandler(stream_handler)
logger.addHandler(info_handler)
