#!/usr/bin/env python3
import sys
import os
import subprocess
import logging
from pathlib import Path

# Ana proje dizinini Python path'ine ekle
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

def setup_logging():
    """Loglama yapılandırmasını ayarlar."""
    log_dir = project_root / "runtime" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "bot.log"),
            logging.StreamHandler()
        ]
    )

def upgrade_db():
    """Veritabanını günceller."""
    try:
        from bot.utils.db_setup import upgrade_database
        print("Veritabanı güncelleniyor...")
        upgrade_database()
    except Exception as e:
        print(f"Veritabanı güncellenirken hata: {e}")
        return False
    return True

def start_monitor_bot():
    """Monitor botunu başlatır."""
    try:
        import asyncio
        from debug_bot.telegram_monitor import main
        print("Debug bot başlatılıyor...")
        # Asenkron fonksiyonu doğru çağır
        asyncio.run(main())
    except Exception as e:
        print(f"Debug bot başlatılırken hata: {e}")
        return False
    return True

def start_main_bot():
    """Ana botu başlatır."""
    try:
        # Ana bot'un main modulüne bağlı olarak:
        # Hangisi varsa o çalışacak
        try:
            from bot.main import run
            print("Ana bot başlatılıyor...")
            run()
        except ModuleNotFoundError:
            try:
                from bot.main import start  # Replace with the correct module path
                start()
            except ModuleNotFoundError:
                print("Ana bot modülü bulunamadı.")
                return False
    except Exception as e:
        print(f"Ana bot başlatılırken hata: {e}")
        return False
    return True

@classmethod
def load_config(cls):  # self yerine cls parametresi (sınıf metodu)
    pass

if __name__ == "__main__":
    # Loglama yapılandırması
    setup_logging()
    
    # Veritabanını güncelle
    if not upgrade_db():
        print("Veritabanı güncellenemedi. Bot başlatılmıyor.")
        sys.exit(1)
    
    # Argümanları kontrol et
    if len(sys.argv) > 1:
        if sys.argv[1] == "monitor":
            start_monitor_bot()
        elif sys.argv[1] == "bot":
            start_main_bot()
        elif sys.argv[1] == "db":
            print("Veritabanı güncellendi.")
        else:
            print(f"Geçersiz argüman: {sys.argv[1]}")
    else:
        # Argüman yoksa hem ana bot hem de monitor bot başlat
        print("Tüm botlar başlatılıyor...")
        start_monitor_bot()
        start_main_bot()