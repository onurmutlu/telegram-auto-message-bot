#!/usr/bin/env python3
"""
Telegram botu için kapsamlı bakım ve sorun giderme scripti.
Veritabanı yetkilerini düzeltir, veritabanı kilit sorunlarını çözer,
eksik tabloları oluşturur ve genel bakım işlemlerini gerçekleştirir.
"""
import os
import sys
import time
import argparse
import logging
import subprocess

# Log formatını ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_script(script_name, description=None):
    """
    Belirtilen scripti çalıştırır ve sonucunu döndürür

    Args:
        script_name: Çalıştırılacak Python script dosyası
        description: İşlem açıklaması (None ise script adı kullanılır)
    
    Returns:
        bool: Script başarılı çalıştıysa True, aksi halde False
    """
    desc = description or f"{script_name} scripti çalıştırılıyor"
    logger.info(f"[BAŞLAT] {desc}...")
    
    try:
        result = subprocess.run(['python', script_name], 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE,
                                text=True)
        
        if result.returncode == 0:
            logger.info(f"[BAŞARILI] {script_name} başarıyla çalıştırıldı")
            return True
        else:
            logger.error(f"[HATA] {script_name} çalıştırılırken hata oluştu: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"[HATA] {script_name} çalışırken istisna oluştu: {str(e)}")
        return False

def fix_all():
    """
    Tüm bakım ve düzeltme işlemlerini sırayla çalıştırır
    """
    logger.info("=== TELEGRAM BOT KAPSAMLI BAKIM İŞLEMİ BAŞLATILIYOR ===")
    
    # 1. Önce veritabanı kilitlerini temizle
    run_script('fix_db_locks_auto.py', "Veritabanı kilitleri temizleniyor")
    
    # 2. Telethon session kilit sorunlarını gider
    run_script('fix_telethon_session_auto.py', "Telethon session SQLite sorunları gideriliyor")
    
    # 3. Veritabanı sahipliğini düzelt
    run_script('fix_db_ownership.py', "Veritabanı sahipliği düzeltiliyor") 
    
    # 4. PostgreSQL tablolarının özel yetkilendirmelerini yap
    run_script('fix_pg_specific_tables.py', "PostgreSQL tablolarına özel yetkiler veriliyor")
    
    # 5. Eksik kolonları ve indeksleri düzelt
    run_script('fix_user_ids.py', "Eksik kolonlar ve indeksler düzeltiliyor")
    
    # 6. Tüm tablolara tam yetki ver
    run_script('fix_all_permissions.py', "Tüm tablolara tam yetki veriliyor")
    
    # 7. Özellikle sorunlu tabloları ayrıca düzelt
    run_script('fix_specific_table_permissions.py', "Özel sorunlu tablolar düzeltiliyor")
    
    # 8. Eksik tabloları oluştur
    run_script('create_missing_tables.py', "Eksik tablolar oluşturuluyor")
    
    # 9. Settings ve config tablolarını düzelt
    run_script('fix_settings_and_backup.py', "Settings ve backup izinleri düzeltiliyor")
    
    # 10. Grup tablolarını düzelt
    run_script('fix_groups_table.py', "Groups tablosu düzeltiliyor")
    run_script('fix_group_tables.py', "User-group ilişki tabloları düzeltiliyor")
    
    # 11. Yedekleme yetkilerini düzelt
    run_script('fix_yedekleme.py', "Veritabanı yedekleme izinleri düzeltiliyor")
    
    # 12. Son olarak tekrar veritabanı kilitlerini temizle ve optimize et
    run_script('fix_db_locks_auto.py', "Son veritabanı optimizasyonu yapılıyor")
    
    logger.info("=== BAKIM İŞLEMİ TAMAMLANDI ===")
    logger.info("Bot artık çalıştırılabilir: python main.py")

def fix_minimal():
    """
    Sadece temel sorunları çözen hızlı bir bakım yapar
    """
    logger.info("=== HIZLI BAKIM İŞLEMİ BAŞLATILIYOR ===")
    
    # 1. Veritabanı kilitlerini temizle
    run_script('fix_db_locks_auto.py', "Veritabanı kilitleri temizleniyor")
    
    # 2. Telethon session sorunlarını düzelt
    run_script('fix_telethon_session_auto.py', "Telethon session SQLite sorunları gideriliyor")
    
    # 3. PostgreSQL tablolarının özel yetkilendirmelerini yap
    run_script('fix_pg_specific_tables.py', "PostgreSQL tablolarına özel yetkiler veriliyor")
    
    # 4. Eksik kolonları ve indeksleri düzelt
    run_script('fix_user_ids.py', "Eksik kolonlar ve indeksler düzeltiliyor")
    
    # 5. Sorunlu tabloları düzelt
    run_script('fix_specific_table_permissions.py', "Sorunlu tablolar düzeltiliyor")
    
    logger.info("=== HIZLI BAKIM İŞLEMİ TAMAMLANDI ===")
    logger.info("Bot artık çalıştırılabilir: python main.py")

def fix_telethon_only():
    """
    Sadece Telethon session sorunlarını giderir
    """
    logger.info("=== TELETHON SESSION BAKIM İŞLEMİ BAŞLATILIYOR ===")
    
    # SQLite işlemleri ve session dosyalarını düzelt
    run_script('fix_telethon_session_auto.py', "Telethon session SQLite sorunları gideriliyor")
    
    logger.info("=== TELETHON SESSION BAKIM İŞLEMİ TAMAMLANDI ===")
    logger.info("Bot artık çalıştırılabilir: python main.py")

def fix_postgresql_only():
    """
    Sadece PostgreSQL veritabanı sorunlarını giderir
    """
    logger.info("=== POSTGRESQL BAKIM İŞLEMİ BAŞLATILIYOR ===")
    
    # 1. PostgreSQL tablolarının özel yetkilendirmelerini yap
    run_script('fix_pg_specific_tables.py', "PostgreSQL tablolarına özel yetkiler veriliyor")
    
    # 2. Eksik kolonları ve indeksleri düzelt
    run_script('fix_user_ids.py', "Eksik kolonlar ve indeksler düzeltiliyor")
    
    # 3. Tüm tablolara tam yetki ver
    run_script('fix_all_permissions.py', "Tüm tablolara tam yetki veriliyor")
    
    logger.info("=== POSTGRESQL BAKIM İŞLEMİ TAMAMLANDI ===")
    logger.info("Bot artık çalıştırılabilir: python main.py")

def fix_schema_only():
    """
    Sadece veritabanı şema sorunlarını düzeltir (tablolar, kolonlar, indeksler)
    """
    logger.info("=== VERİTABANI ŞEMA BAKIM İŞLEMİ BAŞLATILIYOR ===")
    
    # Eksik kolonları ve indeksleri düzelt
    run_script('fix_user_ids.py', "Eksik kolonlar ve indeksler düzeltiliyor")
    
    logger.info("=== VERİTABANI ŞEMA BAKIM İŞLEMİ TAMAMLANDI ===")
    logger.info("Bot artık çalıştırılabilir: python main.py")

def test_bot_access():
    """
    Botun temel veritabanı erişimini test eder
    """
    logger.info("=== BOT VERİTABANI ERİŞİMİ TESTİ BAŞLATILIYOR ===")
    
    try:
        import psycopg2
        import os
        from dotenv import load_dotenv
        from urllib.parse import urlparse
        
        # .env dosyasından ayarları yükle
        load_dotenv()
        
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')
        url = urlparse(db_url)
        db_name = url.path[1:]
        db_user = url.username or 'postgres'
        db_password = url.password or 'postgres'
        db_host = url.hostname or 'localhost'
        db_port = url.port or 5432
        
        # Veritabanına bağlan
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        logger.info("✓ Veritabanı bağlantısı başarılı")
        
        # Önemli tabloları kontrol et
        problem_tables = [
            'settings', 'config', 'user_groups', 'groups', 'debug_bot_users'
        ]
        
        for table in problem_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                logger.info(f"✓ {table} tablosu erişilebilir (kayıt sayısı: {count})")
            except Exception as e:
                logger.error(f"✗ {table} tablosu erişiminde hata: {str(e)}")
        
        # SQLite session dosyasını kontrol et
        session_files = [
            'runtime/sessions/bot_session.session',
            'session/bot_session.session'
        ]
        
        for session_file in session_files:
            if os.path.exists(session_file):
                if os.access(session_file, os.R_OK | os.W_OK):
                    logger.info(f"✓ {session_file} dosyası okunabilir ve yazılabilir")
                else:
                    logger.error(f"✗ {session_file} dosyası erişim izinleri eksik")
                    
                    # Yetkileri düzeltmeye çalış
                    try:
                        os.chmod(session_file, 0o666)
                        logger.info(f"  Session dosyası yetkileri düzeltildi: {session_file}")
                    except Exception as e:
                        logger.error(f"  Session dosyası yetkileri düzeltilirken hata: {str(e)}")
        
        # Veritabanı yedekleme testi
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            cmd = [
                'pg_dump',
                f'--host={db_host}',
                f'--port={db_port}',
                f'--username={db_user}',
                f'--dbname={db_name}',
                '--no-password',
                '--schema-only',
                '--section=pre-data'
            ]
            
            logger.info("Pg_dump test ediliyor...")
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                logger.info("✓ Veritabanı yedekleme testi başarılı")
            else:
                logger.error(f"✗ Veritabanı yedekleme testi başarısız: {result.stderr}")
        except Exception as e:
            logger.error(f"✗ Veritabanı yedekleme testi hatası: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Bot veritabanı erişim testi hatası: {str(e)}")
    
    logger.info("=== ERİŞİM TESTİ TAMAMLANDI ===")

def check_system():
    """
    Sistem durumunu kontrol eder ve özet bilgi verir
    """
    logger.info("=== SİSTEM DURUM KONTROLÜ BAŞLATILIYOR ===")
    
    # Gerekli kütüphaneleri kontrol et
    try:
        import psycopg2
        logger.info("✓ psycopg2 kütüphanesi yüklü")
    except ImportError:
        logger.error("✗ psycopg2 kütüphanesi eksik")
    
    try:
        import telethon
        logger.info(f"✓ telethon kütüphanesi yüklü (sürüm: {telethon.__version__})")
    except ImportError:
        logger.error("✗ telethon kütüphanesi eksik")
    
    # Python sürümünü kontrol et
    python_version = sys.version.split(' ')[0]
    logger.info(f"✓ Python sürümü: {python_version}")
    
    # İşletim sistemi bilgisi
    import platform
    logger.info(f"✓ İşletim sistemi: {platform.system()} {platform.release()}")
    
    # PostgreSQL varlığını kontrol et
    try:
        result = subprocess.run(['pg_dump', '--version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True)
        if result.returncode == 0:
            logger.info(f"✓ PostgreSQL araçları yüklü: {result.stdout.strip()}")
        else:
            logger.error("✗ PostgreSQL araçları yüklenemedi")
    except Exception:
        logger.error("✗ PostgreSQL araçları bulunamadı")
    
    # .env dosyasını kontrol et
    if os.path.exists('.env'):
        logger.info("✓ .env dosyası mevcut")
    else:
        logger.error("✗ .env dosyası bulunamadı")
    
    # Dizinleri kontrol et
    directories = ['data', 'logs', 'session', 'runtime', 'runtime/logs', 'runtime/sessions']
    for directory in directories:
        if os.path.exists(directory) and os.path.isdir(directory):
            logger.info(f"✓ {directory} dizini mevcut")
        else:
            logger.error(f"✗ {directory} dizini bulunamadı")
    
    logger.info("=== SİSTEM KONTROL TAMAMLANDI ===")

def parse_arguments():
    """
    Komut satırı argümanlarını işler
    """
    parser = argparse.ArgumentParser(description='Telegram Bot Bakım Aracı')
    
    parser.add_argument('--all', action='store_true', 
                        help='Tüm bakım işlemlerini çalıştır')
    
    parser.add_argument('--minimal', action='store_true', 
                        help='Sadece temel sorunları çözen hızlı bakım yap')
    
    parser.add_argument('--test', action='store_true', 
                        help='Bot veritabanı erişimini test et')
    
    parser.add_argument('--check', action='store_true', 
                        help='Sistem durumunu kontrol et')
    
    parser.add_argument('--session', action='store_true',
                        help='Sadece Telethon session sorunlarını gider')
    
    parser.add_argument('--postgresql', action='store_true',
                        help='Sadece PostgreSQL veritabanı sorunlarını gider')
    
    parser.add_argument('--schema', action='store_true',
                        help='Sadece veritabanı şema sorunlarını düzelt')
    
    args = parser.parse_args()
    
    # Hiçbir argüman verilmemişse yardım göster
    if not any(vars(args).values()):
        parser.print_help()
        
    return args

if __name__ == "__main__":
    args = parse_arguments()
    
    if args.all:
        fix_all()
    
    if args.minimal:
        fix_minimal()
    
    if args.test:
        test_bot_access()
    
    if args.check:
        check_system()
        
    if args.session:
        fix_telethon_only()
        
    if args.postgresql:
        fix_postgresql_only()
        
    if args.schema:
        fix_schema_only() 