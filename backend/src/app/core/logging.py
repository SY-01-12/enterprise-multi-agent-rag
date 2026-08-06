import logging
import sys

from app.core.config import get_settings


class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m", logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m", logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        return f"{color}{record.levelname:<8}{self.RESET}  {record.getMessage()}"


def setup_logging():
    settings = get_settings()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(settings.LOG_LEVEL)
    handler.setFormatter(ColoredFormatter())

    # 项目日志
    logging.getLogger("app").setLevel(settings.LOG_LEVEL)
    logging.getLogger("app").handlers.clear()
    logging.getLogger("app").addHandler(handler)
    logging.getLogger("app").propagate = False

    # 第三方静默
    for name in ["uvicorn.access", "httpx", "chromadb", "elasticsearch",
                  "sentence_transformers", "aiomysql", "urllib3"]:
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger("uvicorn.error").handlers.clear()
    logging.getLogger("uvicorn.error").addHandler(handler)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
