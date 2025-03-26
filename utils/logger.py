"""
Loglama yapılandırmaları için yardımcı modül
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import json
from typing import Dict, Any, Optional
from colorama import init, Fore, Style, Back
from datetime import datetime

init(autoreset=True)  # Colorama'yı başlat

class ExtraAdapter(logging.LoggerAdapter):
    """Ekstra veri ile log yapmak için adapter"""
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        if extra:
            kwargs["extra"] = self.extra
            for key, value in extra.items():
                kwargs["extra"][key] = value
        return msg, kwargs

class JSONFormatter(logging.Formatter):
    """JSON formatında log yapılandırması"""
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record, self.datefmt),
            'name': record.name,
            'level': record.levelname,
            'message': record.getMessage(),
            'path': record.pathname,
            'line': record.lineno,
            'function': record.funcName
        }
        
        # Varsa ekstra veriyi ekle
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
            
        # Varsa hata bilgisini ekle
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

class ColoredFormatter(logging.Formatter):
    """Renklendirilmiş konsol log formatı"""
    COLORS = {
        'DEBUG': '\033[94m',  # Mavi
        'INFO': '\033[92m',   # Yeşil
        'WARNING': '\033[93m',# Sarı
        'ERROR': '\033[91m',  # Kırmızı
        'CRITICAL': '\033[41m\033[97m', # Beyaz üzerine kırmızı arkaplan
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_message = super().format(record)
        if record.levelname in self.COLORS:
            log_message = f"{self.COLORS[record.levelname]}{log_message}{self.RESET}"
        return log_message

class LoggerSetup:
    """Logger yapılandırma yardımcısı"""
    
    @staticmethod
    def setup_logger(logs_path: Path, detailed_logs_path: Optional[Path] = None, level=logging.INFO) -> logging.Logger:
        """
        Logger yapılandırmasını ayarlar
        Args:
            logs_path: Log dosyası yolu
            detailed_logs_path: Detaylı log dosyası yolu (opsiyonel)
            level: Log seviyesi
        Returns:
            logging.Logger: Yapılandırılmış logger nesnesi
        """
        # Logs dizinini oluştur (dosyanın değil, dizinin)
        logs_dir = logs_path.parent
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Root logger ayarları
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Eski handler'ları temizle
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Dosya handler'ı ekle
        # RotatingFileHandler kullanarak dosyanın üzerine yazılmasını sağla
        file_handler = RotatingFileHandler(
            filename=logs_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8',
            mode='a'  # 'w' yerine 'a' (append) kullan
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            '%Y-%m-%d %H:%M:%S'
        ))
        root_logger.addHandler(file_handler)
        
        # Detaylı JSON dosya handler'ı (opsiyonel)
        if detailed_logs_path:
            detailed_logs_dir = detailed_logs_path.parent
            detailed_logs_dir.mkdir(parents=True, exist_ok=True)
            
            json_handler = RotatingFileHandler(
                filename=detailed_logs_path, 
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8',
                mode='a'
            )
            json_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(json_handler)
        
        # Konsol handler'ı ekle
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            '%Y-%m-%d %H:%M:%S'
        ))
        root_logger.addHandler(console_handler)
        
        logger = logging.getLogger('telegram_bot')
        logger.info("Logger başarıyla yapılandırıldı: %s", logs_path)
        
        return logger

    @staticmethod
    def get_terminal_format():
        """Terminal formatı için renkli çıktı şablonlarını döndürür"""
        return {
            'tur_baslangic': f"\n{Fore.CYAN}{{}} | 🔄 Yeni tur başlıyor...{Style.RESET_ALL}",
            'grup_sayisi': f"{Fore.YELLOW}📊 Aktif Grup: {{}} | ⚠️ Devre Dışı: {{}}{Style.RESET_ALL}",
            'mesaj_durumu': f"{Fore.GREEN}✉️  Turda: {{}} | 📈 Toplam: {{}}{Style.RESET_ALL}",
            'bekleme': f"{Fore.BLUE}⏳ {{}}:{{:02d}}{Style.RESET_ALL}",
            'hata_grubu': f"{Fore.RED}⚠️  {{}}: {{}}{Style.RESET_ALL}",
            'basari': f"{Fore.GREEN}✅ {{}}{Style.RESET_ALL}",
            'uyari': f"{Fore.YELLOW}⚠️ {{}}{Style.RESET_ALL}",
            'hata': f"{Fore.RED}❌ {{}}{Style.RESET_ALL}",
            'bilgi': f"{Fore.CYAN}ℹ️ {{}}{Style.RESET_ALL}",
            'group_message': f"{Fore.MAGENTA}📨 Gruba Mesaj: {{}}{Style.RESET_ALL}",
            'user_invite': f"{Fore.YELLOW}👤 Kullanıcı Daveti: {{}}{Style.RESET_ALL}",
            'user_activity': f"{Fore.CYAN}👁️ Kullanıcı Aktivitesi: {{}}{Style.RESET_ALL}"
        }

    @staticmethod
    def log_extra(logger, level, message, **extra):
        """
        Ekstra verilerle birlikte log kaydı oluşturur
        
        Args:
            logger: Logger nesnesi
            level: Log seviyesi ('debug', 'info', 'warning', 'error', 'critical')
            message: Log mesajı
            **extra: Ekstra veri alanları
        """
        record = logging.LogRecord(
            name=logger.name,
            level=getattr(logging, level.upper()),
            pathname='',
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        record.extra_data = extra
        for handler in logger.handlers:
            handler.emit(record)

    @staticmethod
    def get_logger_with_extras(logger_name: str, **extra) -> logging.LoggerAdapter:
        """
        Extra verilerle zenginleştirilmiş logger oluşturur
        
        Args:
            logger_name: Logger adı
            **extra: Eklenecek extra veriler
            
        Returns:
            LoggerAdapter: Extra verilerle zenginleştirilmiş logger
        """
        logger = logging.getLogger(logger_name)
        return ExtraAdapter(logger, extra)