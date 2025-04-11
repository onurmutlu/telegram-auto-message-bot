# -*- coding: utf-8 -*-
"""
# ============================================================================ #
# Dosya: logger_setup.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/logger_setup.py
# İşlev: Uygulama için Logger yapılandırması.
# ============================================================================ #
"""
import os
import logging
from datetime import datetime
from pythonjsonlogger import jsonlogger # Ensure this dependency is in requirements.txt if used

def setup_logger(debug_mode=False):
    """
    Logger yapılandırmasını yapar.

    Hem konsol çıktısı hem de dosya günlüğü için yapılandırma yapar.
    Debug modunda daha detaylı loglama yapılır, normal modda
    daha özet bilgiler loglanır.

    Args:
        debug_mode (bool): Debug modunda çalıştırılacaksa True

    Returns:
        logging.Logger: Yapılandırılmış logger nesnesi
    """
    # Log seviyesini belirle (debug veya info)
    log_level = logging.DEBUG if debug_mode else logging.INFO

    # Ana logger'ı yapılandır
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Önceki handler'ları temizle
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Konsol handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # Grup mesajlarını filtrele ve yalnızca önemli olanları logla
    class GroupMessageFilter(logging.Filter):
        def filter(self, record):
            # Grup mesajlarını filtrele
            message = str(record.getMessage())
            if "Received group message in chat" in message:
                return False

            # Düşük öncelikli telethon mesajlarını filtrele
            if record.name.startswith('telethon') and record.levelno < logging.WARNING:
                return False

            return True

    console_handler.addFilter(GroupMessageFilter())

    # Formatlayıcı
    if debug_mode:
        # Debug modunda daha detaylı format kullan
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        # Normal modda daha basit format kullan
        formatter = logging.Formatter('%(asctime)s - %(message)s')

    console_handler.setFormatter(formatter)

    # Handler'ı ekle
    root_logger.addHandler(console_handler)

    # Log dosyası klasörü oluştur
    try:
        log_dir = "runtime/logs"
        os.makedirs(log_dir, exist_ok=True)

        # Tarih damgalı log dosyası adı
        now = datetime.now()
        log_file_name = now.strftime(f"{log_dir}/bot_%Y%m%d_%H%M%S.log")

        # Dosya handler
        file_handler = logging.FileHandler(log_file_name, encoding='utf-8') # Add encoding
        file_handler.setLevel(log_level)

        # Debug modunda JSON formatında log
        if debug_mode:
            # Ensure pythonjsonlogger is installed: pip install python-json-logger
            try:
                json_formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
                file_handler.setFormatter(json_formatter)
            except ImportError:
                 print("Uyarı: python-json-logger kurulu değil. JSON loglama devre dışı.")
                 file_handler.setFormatter(formatter) # Fallback to standard formatter
        else:
            file_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)

        # runtime/logs/latest.log sembolik link oluştur (Unix sistemlerde)
        try:
            if os.name != 'nt':
                latest_link = os.path.join(log_dir, "latest.log")
                if os.path.lexists(latest_link): # Use lexists for symlinks
                    os.remove(latest_link)
                # Use relative path for symlink target for portability
                os.symlink(os.path.basename(log_file_name), latest_link)
        except Exception as e:
            print(f"Sembolik link oluşturma hatası: {e}")
    except Exception as e:
        print(f"Log dosyası oluşturma hatası: {e}")

    # Return the specific logger for the calling module, not the root logger directly
    # This is generally better practice.
    return logging.getLogger(__name__) # Or pass a specific name if needed
