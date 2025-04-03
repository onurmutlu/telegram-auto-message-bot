"""
# ============================================================================ #
# Dosya: logger_setup.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/logger_setup.py
# Açıklama: Telegram botu için özelleştirilmiş loglama (logging) yapılandırması.
#
# Bu modül, Telegram botunun loglama işlemlerini yapılandırır.
# Temel Özellikler:
# - Hem dosyaya hem de konsola log yazabilme.
# - Farklı log seviyelerini (DEBUG, INFO, WARNING, ERROR, CRITICAL) destekleme.
# - Renkli konsol çıktıları ile logları daha okunabilir hale getirme.
# - Telethon kütüphanesi için özel log seviyesi ayarlayabilme.
#
# Geliştirme: 2025-04-01
# Versiyon: v3.4.0
# Lisans: MIT
#
# Telif Hakkı (c) 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır.
# ============================================================================ #
"""
import logging
import os
import sys
from pathlib import Path
from colorama import Fore, Style, init

# Colorama başlat
init(autoreset=True)

def setup_logger(config, level=logging.INFO):
    """
    Logger'ı yapılandırır.

    Bu fonksiyon, belirtilen yapılandırma ve log seviyesine göre bir logger nesnesi oluşturur ve yapılandırır.
    Hem konsola renkli çıktı veren bir handler, hem de dosyaya log yazan bir handler ekler.

    Args:
        config: Yapılandırma nesnesi. LOG_FILE_PATH özelliğini içermelidir.
        level (logging.INFO): Logger seviyesi. Varsayılan olarak INFO seviyesindedir.

    Returns:
        logging.Logger: Yapılandırılmış logger nesnesi.
    """
    # Logger yapılandırması
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Ana logger seviyesi her zaman DEBUG
    
    # Eğer önceki handler'lar varsa temizle
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Dosya handler'ı oluştur
    try:
        log_path = Path(config.LOG_FILE_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Dosya handler seviyesi DEBUG
        
        # Formatlayıcı - Doğru format alanlarını kullan
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                     datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Dosyaya başlangıç mesajı yaz
        logger.info(f"Logger başarıyla yapılandırıldı: {config.LOG_FILE_PATH}")
        
        # Flush ile değişiklikleri dosyaya yaz
        file_handler.flush()
    except Exception as e:
        print(f"Log dosyası yapılandırılırken hata: {e}")
    
    # Renkli konsol handler
    console_handler = ColoredConsoleHandler()
    console_handler.setLevel(level)  # Konsol handler kullanıcı tarafından belirlenen seviyede
    
    # Renkli konsol formatı
    console_formatter = logging.Formatter('%(asctime)s - %(message)s', 
                                        datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Telethon loglama seviyesi
    telethon_logger = logging.getLogger('telethon')
    telethon_logger.setLevel(logging.WARNING)
    
    return logger

class ColoredConsoleHandler(logging.StreamHandler):
    """
    Renkli konsol çıktısı sağlayan özel bir log handler sınıfı.

    Bu sınıf, farklı log seviyeleri için farklı renkler kullanarak konsol çıktısını daha okunabilir hale getirir.
    """
    
    COLORS = {
        logging.DEBUG: Fore.BLUE,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT
    }
    
    def emit(self, record):
        """
        Log kaydını işler ve konsola renkli olarak yazdırır.

        Args:
            record (logging.LogRecord): Log kaydı nesnesi.
        """
        try:
            # Mesajı formatla
            msg = self.format(record)
            
            # Uygun rengi seç
            color = self.COLORS.get(record.levelno, Fore.WHITE)
            
            # Renkli çıktı
            formatted_msg = f"{color}{msg}{Style.RESET_ALL}"
            
            # Emoji ekle (isteğe bağlı)
            if record.levelno == logging.INFO:
                formatted_msg = f"ℹ️  {formatted_msg}"
            elif record.levelno == logging.WARNING:
                formatted_msg = f"⚠️  {formatted_msg}"
            elif record.levelno == logging.ERROR or record.levelno == logging.CRITICAL:
                formatted_msg = f"❌ {formatted_msg}"
            
            # Mesajı yazdır
            self.stream.write(formatted_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

def configure_service_logger(service_name, level=logging.INFO):
    """
    Belirli bir servis için özel bir logger yapılandırır.

    Bu fonksiyon, verilen servis adı için bir logger oluşturur ve belirtilen seviyeye ayarlar.
    Bu, farklı servislerin loglarını ayrı ayrı yönetmeyi sağlar.

    Args:
        service_name (str): Servis adı.
        level (logging.INFO): Log seviyesi. Varsayılan olarak INFO seviyesindedir.

    Returns:
        logging.Logger: Servis için yapılandırılmış logger nesnesi.
    """
    logger = logging.getLogger(f"service.{service_name}")
    logger.setLevel(level)
    
    # Handler yoksa ana logger'ın handler'larını kullanacak
    
    return logger