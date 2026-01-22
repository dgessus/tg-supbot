import logging
from logging.handlers import TimedRotatingFileHandler
import os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "bot.log")

file_handler = TimedRotatingFileHandler(
    LOG_FILE,
    when="D",
    interval=1,
    backupCount=7,
    encoding="utf-8",
    utc=True
)


class ContextFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "user_id"):
            record.user_id = "system"
        return True


file_handler.suffix = "%Y-%m-%d"

console_handler = logging.StreamHandler()

formatter = logging.Formatter(
    "%(name)s ---%(asctime)s--- %(levelname)s [%(user_id)s] <%(module)s.%(funcName)s.%(lineno)d>: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.addFilter(ContextFilter())

logging.getLogger("aiogram").setLevel(logging.WARNING)
