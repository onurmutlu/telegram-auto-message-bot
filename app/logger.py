import logging
from logging.handlers import RotatingFileHandler
import os

# Log dosyası yolu
LOG_FILE = 'bot.log'

# Log formatı
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Logger oluşturma
def setup_logger():
    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(console_handler)

    # File handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1024 * 1024 * 5,  # 5MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)

    return logger

# Logger'ı başlat
logger = setup_logger()
