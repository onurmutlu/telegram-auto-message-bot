"""
Logger yapılandırma modülü
"""
import os
import sys
import logging
import json
import traceback

def setup_logger(log_file="logs/bot.log", level=logging.INFO, detailed_log_file=None):
    """Logger'ı yapılandırır"""
    # Log dizinini oluştur
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # Root logger'ı yapılandır
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Önceki handlers'ları temizle
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Dosya handler'ı ekle
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Konsol handler'ı ekle - 'levellevel' hatasını düzelt
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Debug log dosyası için JSON handler
    if detailed_log_file:
        try:
            # Detailed log dizinini oluştur
            detailed_log_dir = os.path.dirname(detailed_log_file)
            if not os.path.exists(detailed_log_dir):
                os.makedirs(detailed_log_dir)
                
            # JSON formatter'ı oluştur
            class JsonFormatter(logging.Formatter):
                def format(self, record):
                    try:
                        log_data = {
                            'time': self.formatTime(record),
                            'name': record.name,
                            'level': record.levelname,
                            'message': record.getMessage()
                        }
                        
                        # Exception bilgisi varsa ekle
                        if record.exc_info:
                            log_data['exception'] = traceback.format_exception(*record.exc_info)
                        
                        return json.dumps(log_data)
                    except Exception as e:
                        # Format hatası durumunda basit bir format kullan
                        return f"{{\"error\":\"Format error: {str(e)}\", \"original_message\":\"{record.getMessage()}\"}}}}"
            
            # JSON handler'ı ekle
            json_handler = logging.FileHandler(detailed_log_file, encoding='utf-8')
            json_handler.setFormatter(JsonFormatter())
            root_logger.addHandler(json_handler)
        
        except Exception as e:
            logging.error(f"JSON log handler oluşturma hatası: {str(e)}")
    
    logging.info(f"Logger başarıyla yapılandırıldı: {log_file}")
    
    # Telethon loglarını ayarla
    telethon_logger = logging.getLogger('telethon')
    telethon_logger.setLevel(logging.WARNING)  # Sadece WARNING ve üstü
    
    # Requests kütüphanesi loglarını sessizleştir
    requests_logger = logging.getLogger('urllib3')
    requests_logger.setLevel(logging.WARNING)
    
    return root_logger

def configure_console_logger(level=logging.INFO):
    """Konsol logger yapılandırması"""
    console_debug = logging.StreamHandler(sys.stderr)
    console_debug.setLevel(level)
    console_debug.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    return console_debug

class LoggerSetup:
    """Logger kurulum yardımcı sınıfı"""
    @staticmethod
    def setup_logger(config=None):
        """Config nesnesi kullanarak logger'ı yapılandır"""
        if config:
            log_file = config.log_file if hasattr(config, 'log_file') else "logs/bot.log"
            level = getattr(logging, config.log_level.upper()) if hasattr(config, 'log_level') else logging.INFO
            detailed_log_file = "logs/detailed.json" if getattr(config, 'detailed_logging', False) else None
        else:
            log_file = "logs/bot.log"
            level = logging.INFO
            detailed_log_file = None
            
        return setup_logger(log_file, level, detailed_log_file)