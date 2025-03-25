"""
Loglama yardımcıları
"""
import logging
from pathlib import Path
from colorama import init, Fore, Style, Back
import sys

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
            return logger
        
        logger.setLevel(log_level)
        
        # Dosya işleyicisi
        file_handler = logging.FileHandler(
            logs_path / 'bot.log',
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Konsol işleyicisi
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Biçimlendiriciler
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = ColoredFormatter('%(message)s')
        
        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)
        
        # İşleyicileri ekle
        logger.addHandler(file_handler)
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
        }