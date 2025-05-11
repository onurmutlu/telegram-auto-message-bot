#!/usr/bin/env python3
"""
Telethon Session SQLite dosyalarının kilit sorunlarını çözen script.
"database is locked" hatalarını gidermek için kullanılır.
"""
import os
import sys
import time
import logging
import sqlite3
import subprocess
import shutil
from pathlib import Path

# Log formatını ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def fix_telethon_sessions():
    """
    Telethon session dosyalarını tarayıp, kilitlenme sorunlarını düzeltir.
    """
    logger.info("Telethon session dosyalarını düzeltme işlemi başlatılıyor...")
    
    # Session dosyalarını bul
    session_files = []
    
    # Ana dizinlerde ara
    session_dirs = ['runtime/sessions', 'session', '.']
    
    for session_dir in session_dirs:
        if os.path.exists(session_dir) and os.path.isdir(session_dir):
            for filename in os.listdir(session_dir):
                if filename.endswith('.session'):
                    session_path = os.path.join(session_dir, filename)
                    session_files.append(session_path)
    
    if not session_files:
        logger.error("Hiç session dosyası bulunamadı.")
        return
    
    logger.info(f"Toplam {len(session_files)} session dosyası bulundu: {session_files}")
    
    for session_file in session_files:
        logger.info(f"'{session_file}' dosyası işleniyor...")
        
        # 1. Dosya izinlerini kontrol et ve düzelt
        try:
            # Dosya izinlerini en geniş şekilde ayarla (okuma/yazma)
            os.chmod(session_file, 0o666)
            logger.info(f"Dosya izinleri düzeltildi: {session_file}")
        except Exception as e:
            logger.error(f"Dosya izinleri düzenlenirken hata: {str(e)}")
        
        # 2. Journal dosyasını kontrol et
        journal_file = f"{session_file}-journal"
        if os.path.exists(journal_file):
            try:
                # Journal dosyasının izinlerini de düzelt
                os.chmod(journal_file, 0o666)
                logger.info(f"Journal dosyası izinleri düzeltildi: {journal_file}")
            except Exception as e:
                logger.error(f"Journal dosyası izinleri düzenlenirken hata: {str(e)}")
        
        # 3. Lock dosyalarını kontrol et ve temizle
        lock_file = f"{session_file}-lock"
        shm_file = f"{session_file}-shm"
        wal_file = f"{session_file}-wal"
        
        for extra_file in [lock_file, shm_file, wal_file]:
            if os.path.exists(extra_file):
                try:
                    os.remove(extra_file)
                    logger.info(f"Fazlalık SQLite dosyası silindi: {extra_file}")
                except Exception as e:
                    logger.error(f"Fazlalık dosya silinirken hata: {str(e)}")
        
        # 4. Yedek dosya oluştur
        backup_file = f"{session_file}.backup"
        try:
            shutil.copy2(session_file, backup_file)
            logger.info(f"Yedek oluşturuldu: {backup_file}")
        except Exception as e:
            logger.error(f"Yedek oluşturulurken hata: {str(e)}")
            continue
        
        # 5. SQLite veritabanını integrity check ile kontrol et
        try:
            conn = sqlite3.connect(session_file)
            cursor = conn.cursor()
            
            # Veritabanı bütünlük kontrolü
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            
            if integrity_result == "ok":
                logger.info(f"Veritabanı bütünlüğü sağlam: {session_file}")
            else:
                logger.warning(f"Veritabanı bütünlük sorunu tespit edildi: {session_file}, sonuç: {integrity_result}")
                logger.info("Yedekten onarma denenecek...")
                conn.close()
                
                # Bozuk veritabanını yedekle
                broken_file = f"{session_file}.broken"
                shutil.move(session_file, broken_file)
                logger.info(f"Bozuk veritabanı yedeklendi: {broken_file}")
                
                # Yedekten geri yükle
                shutil.copy2(backup_file, session_file)
                logger.info(f"Veritabanı yedekten geri yüklendi: {session_file}")
                
                # Tekrar bağlan
                conn = sqlite3.connect(session_file)
                cursor = conn.cursor()
        except sqlite3.Error as e:
            logger.error(f"SQLite veritabanı işlenirken hata: {str(e)}")
            
            # Veritabanı açılamıyorsa, yedekten geri yükle
            broken_file = f"{session_file}.broken"
            try:
                # Bozuk veritabanını yedekle
                if os.path.exists(session_file):
                    shutil.move(session_file, broken_file)
                    logger.info(f"Bozuk veritabanı yedeklendi: {broken_file}")
                
                # Yedekten geri yükle
                shutil.copy2(backup_file, session_file)
                logger.info(f"Veritabanı yedekten geri yüklendi: {session_file}")
                
                # Tekrar bağlan
                conn = sqlite3.connect(session_file)
                cursor = conn.cursor()
            except Exception as e2:
                logger.error(f"Yedekten geri yükleme işlemi başarısız: {str(e2)}")
                continue
        
        # 6. Vacuum ile veritabanını optimize et
        try:
            cursor.execute("VACUUM")
            logger.info(f"Veritabanı optimize edildi: {session_file}")
        except sqlite3.Error as e:
            logger.error(f"Veritabanı optimize edilirken hata: {str(e)}")
        
        # 7. Wal modunu kapatmayı dene (kilitlenmeleri azaltabilir)
        try:
            cursor.execute("PRAGMA journal_mode=DELETE")
            journal_mode = cursor.fetchone()[0]
            logger.info(f"Journal modu değiştirildi: {journal_mode}")
        except sqlite3.Error as e:
            logger.error(f"Journal modu değiştirilirken hata: {str(e)}")
        
        # 8. Sync yaparak değişiklikleri diske kaydet
        try:
            cursor.execute("PRAGMA wal_checkpoint(FULL)")
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Checkpoint sırasında hata: {str(e)}")
        
        # Bağlantıyı kapat
        try:
            cursor.close()
            conn.close()
            logger.info(f"Veritabanı bağlantısı temiz şekilde kapatıldı: {session_file}")
        except Exception as e:
            logger.error(f"Veritabanı bağlantısı kapatılırken hata: {str(e)}")
    
    logger.info("Telethon session dosyalarını düzeltme işlemi tamamlandı.")

def fix_all_session_locks():
    """
    Telethon session dosyaları ile ilgili tüm işlemleri yapar
    ve sistemdeki kilitlenmiş SQLite işlemlerini sonlandırır.
    """
    logger.info("Telethon session kilit sorunları gideriliyor...")
    
    # 1. Telethon session dosyalarını düzelt
    fix_telethon_sessions()
    
    # 2. SQLite ile ilişkili süreçleri kontrol et ve gerekirse sonlandır
    try:
        if sys.platform == 'darwin' or sys.platform.startswith('linux'):
            # Unix-benzeri sistemlerde SQLite süreçlerini bul
            cmd = "ps aux | grep -i 'sqlite' | grep -v grep"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                logger.info("SQLite ile ilgili süreçler bulundu:")
                logger.info(result.stdout)
                
                # Kullanıcıdan onay iste
                response = input("Bu süreçleri sonlandırmak istiyor musunuz? (e/h): ")
                if response.lower() == 'e':
                    # Sonlandırma komutları
                    if sys.platform == 'darwin':
                        # macOS
                        kill_cmd = "killall -KILL sqlite3"
                    else:
                        # Linux
                        kill_cmd = "pkill -9 sqlite3"
                    
                    kill_result = subprocess.run(kill_cmd, shell=True, capture_output=True, text=True)
                    if kill_result.returncode == 0:
                        logger.info("SQLite süreçleri sonlandırıldı")
                    else:
                        logger.error(f"Süreçler sonlandırılırken hata: {kill_result.stderr}")
            else:
                logger.info("SQLite ile ilgili çalışan süreç bulunamadı")
        
        elif sys.platform == 'win32':
            # Windows'ta SQLite süreçlerini bul
            cmd = "tasklist | findstr sqlite"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                logger.info("SQLite ile ilgili süreçler bulundu:")
                logger.info(result.stdout)
                
                # Kullanıcıdan onay iste
                response = input("Bu süreçleri sonlandırmak istiyor musunuz? (e/h): ")
                if response.lower() == 'e':
                    # Windows'ta sonlandırma komutu
                    kill_cmd = "taskkill /F /IM sqlite3.exe"
                    kill_result = subprocess.run(kill_cmd, shell=True, capture_output=True, text=True)
                    if kill_result.returncode == 0:
                        logger.info("SQLite süreçleri sonlandırıldı")
                    else:
                        logger.error(f"Süreçler sonlandırılırken hata: {kill_result.stderr}")
            else:
                logger.info("SQLite ile ilgili çalışan süreç bulunamadı")
    except Exception as e:
        logger.error(f"Süreç kontrolü sırasında hata: {str(e)}")
    
    logger.info("Telethon session kilit sorunları giderme işlemi tamamlandı.")

if __name__ == "__main__":
    fix_all_session_locks() 