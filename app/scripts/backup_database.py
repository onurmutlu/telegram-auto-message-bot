#!/usr/bin/env python3
"""
# ============================================================================ #
# Dosya: backup_database.py
# Yol: /Users/siyahkare/code/telegram-bot/app/scripts/backup_database.py
# İşlev: PostgreSQL veritabanını otomatik olarak yedekler
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

import asyncio
import os
import sys
import subprocess
import argparse
import logging
import time
from datetime import datetime, timedelta
import gzip
import shutil

# Proje kök dizinini Python yoluna ekle
project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_dir)

from app.core.config import settings
from app.core.logger import setup_logger

# Loglama yapılandırması
logger = setup_logger("backup_database", log_level=logging.INFO)

# Yedekleme klasörü
BACKUP_DIR = os.path.join(project_dir, "runtime", "database", "backups")

# En fazla saklanacak yedek sayısı (daha eskiler silinecek)
MAX_BACKUPS = 10

async def create_backup(db_host=None, db_port=None, db_user=None, db_password=None, db_name=None, backup_file=None):
    """
    PostgreSQL veritabanının yedeğini oluşturur.
    
    Args:
        db_host: Veritabanı sunucusu
        db_port: Veritabanı portu
        db_user: Veritabanı kullanıcısı
        db_password: Veritabanı şifresi
        db_name: Veritabanı adı
        backup_file: Yedek dosyasının adı (None ise otomatik oluşturulur)
        
    Returns:
        bool: Yedekleme başarılı ise True
    """
    try:
        # .env değerlerini veya varsayılanları kullan
        db_host = db_host or os.getenv("DB_HOST", "localhost")
        db_port = db_port or os.getenv("DB_PORT", "5432")
        db_user = db_user or os.getenv("DB_USER", "postgres")
        db_password = db_password or os.getenv("DB_PASSWORD", "postgres")
        db_name = db_name or os.getenv("DB_NAME", "telegram_bot")
        
        # Yedekleme dizini oluştur
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Zaman damgalı dosya adı oluştur
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_file or os.path.join(BACKUP_DIR, f"postgres_telegram_bot_{timestamp}.sql")
        
        logger.info(f"Veritabanı yedeği oluşturuluyor: {backup_file}")
        
        # pg_dump komutunu oluştur
        cmd = [
            "pg_dump",
            f"--host={db_host}",
            f"--port={db_port}",
            f"--username={db_user}",
            f"--dbname={db_name}",
            "--format=plain",
            f"--file={backup_file}"
        ]
        
        # Şifreyi çevre değişkeni olarak ayarla
        env = os.environ.copy()
        env["PGPASSWORD"] = db_password
        
        # Komutu çalıştır
        start_time = time.time()
        process = subprocess.run(cmd, env=env, check=True, capture_output=True)
        
        if process.returncode == 0:
            # Başarılı - dosyayı sıkıştır
            end_time = time.time()
            duration = end_time - start_time
            
            logger.info(f"Veritabanı yedeği oluşturuldu ({duration:.2f}s), sıkıştırılıyor: {backup_file}")
            
            with open(backup_file, 'rb') as f_in:
                with gzip.open(f"{backup_file}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Orijinal sıkıştırılmamış dosyayı sil
            os.remove(backup_file)
            
            logger.info(f"Veritabanı yedeği sıkıştırıldı: {backup_file}.gz")
            return f"{backup_file}.gz"
        else:
            logger.error(f"Veritabanı yedeği oluşturulamadı: {process.stderr.decode()}")
            return None
            
    except subprocess.CalledProcessError as e:
        logger.error(f"pg_dump hatası: {e.stderr.decode() if e.stderr else str(e)}")
        return None
    except Exception as e:
        logger.error(f"Yedekleme hatası: {str(e)}")
        return None

async def clean_old_backups():
    """
    Eski yedekleri temizler, sadece MAX_BACKUPS sayıda yedek kalır.
    """
    try:
        # Yedek dosyalarını listele ve sırala
        backup_files = []
        for filename in os.listdir(BACKUP_DIR):
            if filename.startswith("postgres_telegram_bot_") and filename.endswith(".sql.gz"):
                filepath = os.path.join(BACKUP_DIR, filename)
                backup_files.append({
                    "path": filepath,
                    "name": filename,
                    "time": os.path.getmtime(filepath)
                })
        
        # Zaman damgasına göre sırala (eskiden yeniye)
        backup_files.sort(key=lambda x: x["time"])
        
        # Eski yedekleri sil (en yeni MAX_BACKUPS sayıda dosya hariç)
        if len(backup_files) > MAX_BACKUPS:
            files_to_delete = backup_files[:-MAX_BACKUPS]
            for file_info in files_to_delete:
                logger.info(f"Eski yedek siliniyor: {file_info['name']}")
                os.remove(file_info["path"])
            
            logger.info(f"{len(files_to_delete)} eski yedek silindi")
        else:
            logger.info(f"Silinecek eski yedek yok (toplam {len(backup_files)} yedek var)")
            
    except Exception as e:
        logger.error(f"Eski yedekleri temizleme hatası: {str(e)}")

async def backup_and_rotate():
    """
    Veritabanını yedekler ve eski yedekleri temizler.
    """
    backup_file = await create_backup()
    if backup_file:
        await clean_old_backups()
        return True
    return False

async def main():
    """Ana fonksiyon."""
    parser = argparse.ArgumentParser(description="PostgreSQL veritabanı yedekleme aracı")
    
    parser.add_argument("--host", help="Veritabanı sunucusu")
    parser.add_argument("--port", help="Veritabanı portu")
    parser.add_argument("--user", help="Veritabanı kullanıcısı")
    parser.add_argument("--password", help="Veritabanı şifresi")
    parser.add_argument("--dbname", help="Veritabanı adı")
    parser.add_argument("--file", help="Yedek dosyasının adı")
    parser.add_argument("--max-backups", type=int, help="Saklanacak maksimum yedek sayısı")
    parser.add_argument("--clean-only", action="store_true", help="Sadece eski yedekleri temizle")
    
    args = parser.parse_args()
    
    # Maksimum yedek sayısını güncelle
    global MAX_BACKUPS
    if args.max_backups:
        MAX_BACKUPS = args.max_backups
    
    if args.clean_only:
        # Sadece eski yedekleri temizle
        await clean_old_backups()
    else:
        # Yedek oluştur ve eski yedekleri temizle
        backup_file = await create_backup(
            db_host=args.host,
            db_port=args.port,
            db_user=args.user,
            db_password=args.password,
            db_name=args.dbname,
            backup_file=args.file
        )
        
        if backup_file:
            logger.info(f"Veritabanı yedeği başarıyla oluşturuldu: {backup_file}")
            await clean_old_backups()
        else:
            logger.error("Veritabanı yedeği oluşturulamadı")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 