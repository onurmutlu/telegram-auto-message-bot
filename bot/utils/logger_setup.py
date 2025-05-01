# -*- coding: utf-8 -*-
"""
# ============================================================================ #
# Dosya: logger_setup.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/logger_setup.py
# İşlev: Loglama yapılandırmasını sağlar
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import platform
import time
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme
from rich.style import Style
from pathlib import Path

# Özel tema tanımla - Daha modern ve okunaklı görünüm için
rich_theme = Theme({
    "info": Style(color="cyan", bold=False),
    "warning": Style(color="yellow", bold=True),
    "error": Style(color="red", bold=True),
    "critical": Style(color="white", bgcolor="red", bold=True),
    "debug": Style(color="green", dim=True),
    
    # Özel seviyeler ve servisler
    "service": Style(color="magenta", bold=True),
    "database": Style(color="blue", bold=True),
    "network": Style(color="cyan"),
    "success": Style(color="green", bold=True),
})

# Rich konsolunu yapılandır
console = Console(theme=rich_theme, width=120)

class CustomRichHandler(RichHandler):
    """Özelleştirilmiş RichHandler, daha temiz ve düzenli log formatı için"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def render(self, record, traceback=None, message_renderable=None):
        """Log kaydını daha okunabilir şekilde render et"""
        # Modül adını kısalt
        if record.name.startswith("bot."):
            record.name = record.name[4:]  # "bot." kısmını kaldır
            
        # Zamanı daha okunaklı formatta ekle
        time_format = f"[dim]{time.strftime('%H:%M:%S')}[/dim]"
        
        # Servis/modül adını stilize et
        module = f"[blue]{record.name:<20}[/blue]"
        
        # Log seviyesini farklı renklerde göster
        level_styles = {
            "DEBUG": "[dim green]DEBUG[/dim green]",
            "INFO": "[cyan]INFO[/cyan]",
            "WARNING": "[yellow bold]WARN[/yellow bold]",
            "ERROR": "[red bold]ERROR[/red bold]",
            "CRITICAL": "[white on red]CRIT[/white on red]",
        }
        level = level_styles.get(record.levelname, f"[bold]{record.levelname}[/bold]")
        
        # Message renk kodlarını temizleme (zamanı stilize edeceğiz)
        message = message_renderable or self.render_message(record)
        
        # Mesaj içeriğine özel stil uygulaması (emoji ve özel vurgular)
        if record.levelname == "INFO" and ("başarıyla" in str(message) or "✅" in str(message)):
            message = f"[green]{message}[/green]"
        elif record.levelname == "WARNING" and ("dikkat" in str(message) or "⚠️" in str(message)):
            message = f"[yellow]{message}[/yellow]"
            
        # Farklı log kaynakları için özel formatlar
        if "database" in record.name.lower():
            prefix = "[blue]DB[/blue]"
        elif "service" in record.name.lower():
            prefix = "[magenta]SRV[/magenta]"
        elif "handler" in record.name.lower():
            prefix = "[cyan]HDL[/cyan]"
        elif "utils" in record.name.lower():
            prefix = "[green]UTL[/green]"
        else:
            prefix = "[dim]LOG[/dim]"
            
        # Özel formatı hazırla
        return f"{time_format} {prefix} {level:<10} {module} → {message}"

def setup_logger(level=logging.INFO, log_dir="logs", console_only=False):
    """
    Loglama yapılandırmasını gerçekleştirir.
    
    Args:
        level: Log seviyesi (default: INFO)
        log_dir: Log dosyalarının kaydedileceği dizin
        console_only: Sadece konsola log yapılsın mı? (default: False)
    
    Returns:
        logging.Logger: Yapılandırılmış logger nesnesi
    """
    # Log dizini yoksa oluştur
    os.makedirs(log_dir, exist_ok=True)
    
    # Kök logger'ı yapılandır
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Eski handler'ları temizle
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Rich Konsol handler'ı yapılandır
    # Rich konsoluna zamanı doğrudan eklemiyoruz, özel formatımız var
    console_handler = CustomRichHandler(
        rich_tracebacks=True,
        show_time=False,
        show_level=False,  # Seviyeyi kendi formatımızda göstereceğiz
        show_path=False,   # Dosya yolunu göstermeyelim
        enable_link_path=False,
        markup=True,        # Rich markup'ı etkinleştir
        console=console     # Özel konsol nesnesi kullan
    )
    console_handler.setLevel(level)
    
    # Dosya handler'ını yapılandır (dosya boyutuna göre dönen)
    if not console_only:
        log_file = os.path.join(log_dir, "bot.log")
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,              # 5 yedek dosya
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        
        # Dosya formatını daha ayrıntılı yap
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        
        # Dosya handler'ını ekle
        root_logger.addHandler(file_handler)
    
    # Konsol handler'ını ekle
    root_logger.addHandler(console_handler)
    
    # Bazı modüllerin log seviyesini azalt
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    
    # Bilgilendirme mesajı
    logger = logging.getLogger("bot.utils.logger")
    logger.info(f"Loglama yapılandırması tamamlandı. Seviye: {logging.getLevelName(level)}")
    
    return logger
