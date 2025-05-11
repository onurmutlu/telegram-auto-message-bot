#!/usr/bin/env python3
"""
Telegram botundaki tüm veritabanı ve oturum sorunlarını tek seferde düzeltmek için kullanılan yardımcı script.
Bu script, aşağıdaki düzeltme scriptlerini sırayla çalıştırır:

1. fix_telethon_session_auto.py - Telethon oturum dosyalarındaki kilitleme sorunlarını düzeltir
2. setup_db.py - PostgreSQL veritabanı şemasını oluşturur/günceller
3. fix_data_mining.py - Data mining tablosundaki user_id kolonunu düzeltir
4. fix_mining_tables.py - Veri madenciliği tablolarını düzeltir

Kullanım:
    python fix_all.py [--skip-session] [--skip-db] [--skip-mining]
    
Parametreler:
    --skip-session: Telethon oturum düzeltmeyi atla
    --skip-db: Veritabanı şeması oluşturmayı atla
    --skip-mining: Veri madenciliği düzeltmelerini atla
"""

import os
import sys
import argparse
import logging
import subprocess
import time

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_script(script_path, description):
    """Belirtilen scripti çalıştırır ve sonucu döndürür"""
    logger.info(f"📋 {description} çalıştırılıyor...")
    
    try:
        start_time = time.time()
        result = subprocess.run([sys.executable, script_path], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               universal_newlines=True,
                               check=True)
        end_time = time.time()
        
        # Çıktıyı yazdır
        if result.stdout:
            for line in result.stdout.splitlines():
                logger.info(f"  {line}")
        
        logger.info(f"✅ {description} başarıyla tamamlandı ({end_time - start_time:.2f} saniye)")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ {description} çalıştırılırken hata oluştu:")
        if e.stdout:
            for line in e.stdout.splitlines():
                logger.info(f"  {line}")
        if e.stderr:
            for line in e.stderr.splitlines():
                logger.error(f"  {line}")
        return False
    except Exception as e:
        logger.error(f"❌ {description} çalıştırılırken beklenmedik hata: {str(e)}")
        return False

def main():
    """Ana fonksiyon"""
    parser = argparse.ArgumentParser(description='Tüm düzeltme scriptlerini çalıştır')
    parser.add_argument('--skip-session', action='store_true', help='Telethon oturum düzeltmeyi atla')
    parser.add_argument('--skip-db', action='store_true', help='Veritabanı şeması oluşturmayı atla')
    parser.add_argument('--skip-mining', action='store_true', help='Veri madenciliği düzeltmelerini atla')
    args = parser.parse_args()
    
    logger.info("🚀 Telegram Bot Düzeltme İşlemleri Başlatılıyor...")
    
    # Proje kök dizinini bul
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Script dosya yolları
    script_paths = {
        "telethon_session": os.path.join(project_root, "scripts", "fix_telethon_session_auto.py"),
        "setup_db": os.path.join(project_root, "database", "setup_db.py"),
        "data_mining": os.path.join(project_root, "scripts", "fix_data_mining.py"),
        "mining_tables": os.path.join(project_root, "scripts", "fix_mining_tables.py")
    }
    
    # Çalıştırma sırası ve açıklamaları
    scripts = [
        {"key": "telethon_session", "desc": "Telethon oturum düzeltme", "skip": args.skip_session},
        {"key": "setup_db", "desc": "Veritabanı şeması oluşturma", "skip": args.skip_db},
        {"key": "data_mining", "desc": "Data mining user_id düzeltme", "skip": args.skip_mining},
        {"key": "mining_tables", "desc": "Veri madenciliği tabloları düzeltme", "skip": args.skip_mining}
    ]
    
    # Scriptleri sırayla çalıştır
    success_count = 0
    total_count = 0
    
    for script in scripts:
        if script["skip"]:
            logger.info(f"🔄 {script['desc']} atlanıyor (--skip parametresi)")
            continue
        
        script_path = script_paths[script["key"]]
        total_count += 1
        
        # Script dosyasının varlığını kontrol et
        if not os.path.exists(script_path):
            logger.error(f"❌ {script_path} dosyası bulunamadı!")
            continue
        
        # Scripti çalıştır
        if run_script(script_path, script["desc"]):
            success_count += 1
    
    # Özet
    if total_count > 0:
        if success_count == total_count:
            logger.info(f"🎉 Tüm düzeltme işlemleri başarıyla tamamlandı! ({success_count}/{total_count})")
        else:
            logger.warning(f"⚠️ Düzeltme işlemleri tamamlandı, ancak bazı hatalar oluştu. ({success_count}/{total_count} başarılı)")
    else:
        logger.info("ℹ️ Hiçbir düzeltme işlemi çalıştırılmadı (tüm işlemler atlandı)")

if __name__ == "__main__":
    main() 