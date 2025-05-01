#!/usr/bin/env python3
"""
Telethon Session SQLite dosyalarının kilit sorunlarını tamamen otomatik olarak çözen script.
"database is locked" hatalarını kullanıcı müdahalesi olmadan giderir.
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

def fix_telethon_sessions_auto():
    """
    Telethon session dosyalarını tarayıp, kilitlenme sorunlarını otomatik olarak düzeltir.
    """
    logger.info("Telethon session dosyalarını otomatik düzeltme işlemi başlatılıyor...")
    
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
    
    logger.info(f"Toplam {len(session_files)} session dosyası bulundu: {', '.join(session_files)}")
    
    # SQLite süreçlerini otomatik olarak sonlandır
    kill_sqlite_processes()
    
    for session_file in session_files:
        logger.info(f"'{session_file}' dosyası işleniyor...")
        
        # 1. Dosya izinlerini kontrol et ve düzelt
        try:
            # Dosya izinlerini en geniş şekilde ayarla (okuma/yazma)
            os.chmod(session_file, 0o666)
            logger.info(f"Dosya izinleri düzeltildi: {session_file}")
        except Exception as e:
            logger.error(f"Dosya izinleri düzenlenirken hata: {str(e)}")
        
        # 2. Journal, shm, wal dosyalarını kontrol et
        related_files = [
            f"{session_file}-journal",  # SQLite journal dosyası
            f"{session_file}-shm",      # SQLite shared memory dosyası
            f"{session_file}-wal",      # SQLite write-ahead log dosyası
            f"{session_file}-lock"      # Lock dosyası (genelde olmaz ama kontrol et)
        ]
        
        for related_file in related_files:
            if os.path.exists(related_file):
                try:
                    # İlişkili dosyanın izinlerini de düzelt
                    os.chmod(related_file, 0o666)
                    logger.info(f"İlişkili dosya izinleri düzeltildi: {related_file}")
                except Exception as e:
                    logger.error(f"İlişkili dosya izinleri düzenlenirken hata: {str(e)}")
        
        # 3. Yedek dosya oluştur
        timestamp = time.strftime("%Y%m%d%H%M%S")
        backup_file = f"{session_file}.backup_{timestamp}"
        try:
            shutil.copy2(session_file, backup_file)
            logger.info(f"Yedek oluşturuldu: {backup_file}")
        except Exception as e:
            logger.error(f"Yedek oluşturulurken hata: {str(e)}")
            continue
        
        # 4. SQLite veritabanına bağlanmayı dene
        try:
            # timeout değerini artırarak bağlanmayı dene
            conn = sqlite3.connect(session_file, timeout=30)
            cursor = conn.cursor()
            
            # Veritabanı bütünlük kontrolü
            try:
                cursor.execute("PRAGMA integrity_check")
                integrity_result = cursor.fetchone()[0]
                
                if integrity_result == "ok":
                    logger.info(f"Veritabanı bütünlüğü sağlam: {session_file}")
                else:
                    logger.warning(f"Veritabanı bütünlük sorunu tespit edildi: {session_file}, sonuç: {integrity_result}")
                    
                    # Veritabanını kapatmayı dene
                    try:
                        cursor.close()
                        conn.close()
                    except:
                        pass
                    
                    # Bozuk veritabanını yedekle
                    broken_file = f"{session_file}.broken_{timestamp}"
                    try:
                        shutil.move(session_file, broken_file)
                        logger.info(f"Bozuk veritabanı yedeklendi: {broken_file}")
                        
                        # Yedekten geri yükle
                        shutil.copy2(backup_file, session_file)
                        logger.info(f"Veritabanı yedekten geri yüklendi: {session_file}")
                        
                        # Tekrar bağlanmayı dene
                        conn = sqlite3.connect(session_file, timeout=30)
                        cursor = conn.cursor()
                    except Exception as e:
                        logger.error(f"Bozuk veritabanı işlenirken hata: {str(e)}")
                        continue
            except sqlite3.Error as e:
                logger.error(f"Bütünlük kontrolü yapılırken hata: {str(e)}")
            
            # Journal modu DELETE olarak ayarla (WAL yerine)
            try:
                cursor.execute("PRAGMA journal_mode=DELETE")
                journal_mode = cursor.fetchone()[0]
                logger.info(f"Journal modu '{journal_mode}' olarak ayarlandı")
            except sqlite3.Error as e:
                logger.error(f"Journal modu ayarlanırken hata: {str(e)}")
            
            # Busy timeout değerini ayarla
            try:
                cursor.execute("PRAGMA busy_timeout=5000")
                logger.info("Busy timeout 5000ms olarak ayarlandı")
            except sqlite3.Error as e:
                logger.error(f"Busy timeout ayarlanırken hata: {str(e)}")
            
            # Senkron modu ayarla
            try:
                cursor.execute("PRAGMA synchronous=NORMAL")
                logger.info("Senkron modu NORMAL olarak ayarlandı")
            except sqlite3.Error as e:
                logger.error(f"Senkron modu ayarlanırken hata: {str(e)}")
            
            # Veritabanını optimize et
            try:
                cursor.execute("VACUUM")
                logger.info("Veritabanı optimize edildi (VACUUM)")
            except sqlite3.Error as e:
                logger.error(f"VACUUM çalıştırılırken hata: {str(e)}")
            
            # Değişiklikleri kaydet ve bağlantıyı kapat
            try:
                conn.commit()
                cursor.close()
                conn.close()
                logger.info("Veritabanı bağlantısı temiz şekilde kapatıldı")
            except Exception as e:
                logger.error(f"Bağlantı kapatılırken hata: {str(e)}")
        
        except sqlite3.Error as e:
            logger.error(f"Veritabanına bağlanırken hata: {str(e)}")
            
            # Bağlantı kurulamıyorsa, yedekten geri yüklemeyi dene
            logger.warning("Veritabanına bağlanılamadı. Yedekten geri yükleme deneniyor...")
            
            # Eski dosyayı yeniden adlandır
            broken_file = f"{session_file}.broken_{timestamp}"
            try:
                if os.path.exists(session_file):
                    shutil.move(session_file, broken_file)
                    logger.info(f"Erişilemeyen veritabanı yedeklendi: {broken_file}")
                
                # Yedekten geri yükle
                shutil.copy2(backup_file, session_file)
                logger.info(f"Veritabanı yedekten geri yüklendi: {session_file}")
                
                # Dosya izinlerini de düzelt
                os.chmod(session_file, 0o666)
            except Exception as e2:
                logger.error(f"Yedekten geri yüklenirken hata: {str(e2)}")
        
        # 5. Dosya izinlerini bir kez daha kontrol et
        try:
            if os.path.exists(session_file):
                os.chmod(session_file, 0o666)
            
            # Journal dosyasını da kontrol et
            journal_file = f"{session_file}-journal"
            if os.path.exists(journal_file):
                os.chmod(journal_file, 0o666)
        except Exception as e:
            logger.error(f"Son dosya izinleri kontrolünde hata: {str(e)}")
    
    logger.info("Telethon session düzeltme işlemi tamamlandı")

def kill_sqlite_processes():
    """
    SQLite süreçlerini otomatik olarak tespit edip sonlandırır.
    """
    logger.info("SQLite süreçleri kontrol ediliyor...")
    
    try:
        if sys.platform == 'darwin':  # macOS
            # macOS'ta SQLite süreçlerini bul
            process_cmd = "ps aux | grep -i sqlite | grep -v grep"
            process_result = subprocess.run(process_cmd, shell=True, capture_output=True, text=True)
            
            if process_result.returncode == 0 and process_result.stdout.strip():
                logger.info("SQLite süreçleri bulundu:")
                logger.info(process_result.stdout)
                
                # Süreçleri sonlandır
                kill_cmd = "killall -9 sqlite3 2>/dev/null || true"
                subprocess.run(kill_cmd, shell=True)
                logger.info("SQLite süreçleri sonlandırıldı")
            else:
                logger.info("SQLite süreçleri bulunamadı")
            
            # Telethon/Python ile ilgili SQLite bağlantılarını da kontrol et
            process_cmd = "ps aux | grep -i python | grep -v grep"
            process_result = subprocess.run(process_cmd, shell=True, capture_output=True, text=True)
            
            if "main.py" in process_result.stdout:
                logger.info("Telegram botu çalışıyor. Bot durdurulacak...")
                stop_cmd = "pkill -f 'python main.py'"
                subprocess.run(stop_cmd, shell=True)
                logger.info("Telegram botu durduruldu")
                time.sleep(2)  # Sürecin düzgünce kapanması için bekle
        
        elif sys.platform.startswith('linux'):  # Linux
            # Linux'ta SQLite süreçlerini bul
            process_cmd = "ps aux | grep -i sqlite | grep -v grep"
            process_result = subprocess.run(process_cmd, shell=True, capture_output=True, text=True)
            
            if process_result.returncode == 0 and process_result.stdout.strip():
                logger.info("SQLite süreçleri bulundu:")
                logger.info(process_result.stdout)
                
                # Süreçleri sonlandır
                kill_cmd = "pkill -9 sqlite3 2>/dev/null || true"
                subprocess.run(kill_cmd, shell=True)
                logger.info("SQLite süreçleri sonlandırıldı")
            else:
                logger.info("SQLite süreçleri bulunamadı")
            
            # Telethon/Python süreçlerini kontrol et
            process_cmd = "ps aux | grep -i 'python main.py' | grep -v grep"
            process_result = subprocess.run(process_cmd, shell=True, capture_output=True, text=True)
            
            if process_result.stdout.strip():
                logger.info("Telegram botu çalışıyor. Bot durdurulacak...")
                stop_cmd = "pkill -f 'python main.py'"
                subprocess.run(stop_cmd, shell=True)
                logger.info("Telegram botu durduruldu")
                time.sleep(2)  # Sürecin düzgünce kapanması için bekle
        
        elif sys.platform == 'win32':  # Windows
            # Windows'ta SQLite süreçlerini bul
            process_cmd = "tasklist | findstr -i sqlite"
            process_result = subprocess.run(process_cmd, shell=True, capture_output=True, text=True)
            
            if process_result.returncode == 0 and process_result.stdout.strip():
                logger.info("SQLite süreçleri bulundu:")
                logger.info(process_result.stdout)
                
                # Süreçleri sonlandır
                kill_cmd = "taskkill /F /IM sqlite3.exe 2>nul"
                subprocess.run(kill_cmd, shell=True)
                logger.info("SQLite süreçleri sonlandırıldı")
            else:
                logger.info("SQLite süreçleri bulunamadı")
            
            # Telethon/Python süreçlerini kontrol et
            process_cmd = "tasklist | findstr -i python"
            process_result = subprocess.run(process_cmd, shell=True, capture_output=True, text=True)
            
            if "python.exe" in process_result.stdout:
                logger.info("Python süreçleri bulundu, bot süreçleri kontrol ediliyor...")
                process_cmd = "wmic process where \"commandline like '%main.py%'\" get processid"
                process_result = subprocess.run(process_cmd, shell=True, capture_output=True, text=True)
                
                if process_result.stdout.strip() and not "No Instance(s) Available" in process_result.stdout:
                    logger.info("Telegram botu çalışıyor. Bot durdurulacak...")
                    kill_cmd = "taskkill /F /FI \"WINDOWTITLE eq *main.py*\" 2>nul"
                    subprocess.run(kill_cmd, shell=True)
                    kill_cmd = "taskkill /F /FI \"IMAGENAME eq python.exe\" /FI \"WINDOWTITLE eq *main.py*\" 2>nul"
                    subprocess.run(kill_cmd, shell=True)
                    logger.info("Telegram botu durduruldu")
                    time.sleep(2)  # Sürecin düzgünce kapanması için bekle
    
    except Exception as e:
        logger.error(f"SQLite süreçleri kontrol edilirken hata: {str(e)}")

def main():
    """
    Ana fonksiyon - Tüm düzeltme sürecini çalıştırır
    """
    logger.info("Telethon Session SQLite düzeltme scripti başlatılıyor...")
    
    # 1. Öncelikle çalışan bot süreçlerini ve SQLite bağlantılarını kapat
    kill_sqlite_processes()
    
    # 2. Session dosyalarını düzelt
    fix_telethon_sessions_auto()
    
    # 3. Sistemi ve dosyaları senkronize et - Önbelleği diske yazma
    try:
        if sys.platform != 'win32':  # Unix benzeri sistemlerde sync komutu
            subprocess.run("sync", shell=True)
            logger.info("Sistem önbelleği diske yazıldı (sync)")
    except Exception as e:
        logger.error(f"Sync işlemi sırasında hata: {str(e)}")
    
    logger.info("Telethon Session SQLite düzeltme işlemi tamamlandı.")
    logger.info("Artık 'python main.py' komutu ile botu başlatabilirsiniz.")

if __name__ == "__main__":
    main() 