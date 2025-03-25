"""
Loglama yardımcıları
"""
import logging
from pathlib import Path
from colorama import init, Fore, Style, Back
import sys
import json
from datetime import datetime
# Biçimlendiriciler
file_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - [%(funcName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
init(autoreset=True)  # Colorama'yı başlat

class ColoredFormatter(logging.Formatter):
    """Renkli loglama biçimlendiricisi"""
    
    COLORS = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.WHITE + Back.RED
    }
    
    def format(self, record):
        levelname = record.levelname
        message = super().format(record)
        if levelname in self.COLORS:
            return f"{self.COLORS[levelname]}{message}{Style.RESET_ALL}"
        return message

class JsonFormatter(logging.Formatter):
    """
    JSON formatında log üreten biçimlendirici.
    Yapılandırılmış verileri ve ekstra alanları JSON olarak kaydeder.
    """
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Ekstra alanları ekle
        if hasattr(record, 'extra_data') and record.extra_data:
            log_data.update(record.extra_data)
            
        return json.dumps(log_data)

class ExtraAdapter(logging.LoggerAdapter):
    """Ekstra veri ile log yapmak için adapter"""
    
    def process(self, msg, kwargs):
        # Mevcut extra verileri al veya boş dict oluştur
        kwargs.setdefault('extra', {})
        # Adapter'ın extra verilerini ekle
        kwargs['extra'].update(self.extra)
        return msg, kwargs

class LoggerSetup:
    @staticmethod
    def setup_logger(logs_path: Path, log_level: int = logging.DEBUG) -> logging.Logger:
        """
        Logger kurulumu yapar
        
        Args:
            logs_path: Log dosyalarının kaydedileceği dizin
            log_level: Log seviyesi
            
        Returns:
            Logger: Yapılandırılmış logger nesnesi
        """
        # Log dizini oluştur
        logs_path.mkdir(parents=True, exist_ok=True)
        
        # Logger oluştur
        logger = logging.getLogger('telegram_bot')
        if logger.hasHandlers():
            for handler in logger.handlers:
                logger.removeHandler(handler)
        
        # ÖNEMLİ: Ana logger seviyesini DEBUG olarak ayarla
        logger.setLevel(logging.DEBUG)
        
        # ÖNEMLİ: propagate özelliğini True yap
        logger.propagate = True
        
        # Ana log dosyası - Seviyesini DEBUG olarak değiştir
        file_handler = logging.FileHandler(
            logs_path / 'bot.log',
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Bu seviyeyi DEBUG olarak ayarla
        
        # Detaylı JSON log dosyası
        json_handler = logging.FileHandler(
            logs_path / 'detailed_bot.json',
            encoding='utf-8',
            mode='a'  # Append modu
        )
        json_handler.setLevel(logging.DEBUG)
        json_formatter = JsonFormatter()
        json_handler.setFormatter(json_formatter)
        logger.addHandler(json_handler)
        
        # Sadece hataların kaydedildiği hata log dosyası
        error_handler = logging.FileHandler(
            logs_path / 'errors.log',
            encoding='utf-8'
        )
        error_handler.setLevel(logging.WARNING)
        
        # Konsol işleyicisi
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Biçimlendiriciler
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - [%(funcName)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        error_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = ColoredFormatter('%(message)s')
        
        file_handler.setFormatter(file_formatter)
        error_handler.setFormatter(error_formatter)
        console_handler.setFormatter(console_formatter)
        
        # İşleyicileri ekle
        logger.addHandler(file_handler)
        logger.addHandler(json_handler)
        logger.addHandler(error_handler)
        logger.addHandler(console_handler)
        
        # Telethon loglarını bastır
        logging.getLogger('telethon').setLevel(logging.WARNING)
        
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