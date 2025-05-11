#!/usr/bin/env python3
"""
PostgreSQL veritabanındaki kilit (lock) sorunlarını çözen script.
Özellikle "database is locked" hatalarını ele alır ve mevcut bağlantıları yönetir.
"""
import os
import sys
import time
import logging
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

# Log formatını ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# .env dosyasından ayarları yükle
load_dotenv()

# Veritabanı bağlantı bilgilerini al
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')

# Bağlantı parametrelerini ayrıştır
url = urlparse(db_url)
db_name = url.path[1:]  # / işaretini kaldır
db_user = url.username or 'postgres'
db_password = url.password or 'postgres'
db_host = url.hostname or 'localhost'
db_port = url.port or 5432

logger.info(f"Veritabanı: {db_host}:{db_port}/{db_name} (Kullanıcı: {db_user})")

def fix_db_locks():
    """
    Veritabanındaki kilitlenme sorunlarını çöz ve kalan bağlantıları temizle.
    """
    try:
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
        
        logger.info("Veritabanına bağlandı")
        
        # 1. İlk olarak superuser yetkisi ver
        try:
            cursor.execute(f"ALTER ROLE {db_user} WITH SUPERUSER;")
            logger.info(f"{db_user} kullanıcısına superuser yetkisi verildi")
        except Exception as e:
            logger.error(f"Superuser yetkisi verilirken hata: {str(e)}")
        
        # 2. Veritabanı üzerindeki aktif bağlantıları ve kilitleri elde et
        logger.info("Aktif bağlantılar ve kilitler kontrol ediliyor...")
        cursor.execute("""
        SELECT pid, 
               usename, 
               application_name, 
               client_addr, 
               backend_start, 
               state, 
               wait_event_type,
               query
        FROM pg_stat_activity 
        WHERE datname = current_database() 
          AND pid <> pg_backend_pid()
          AND state != 'idle'
        ORDER BY backend_start DESC;
        """)
        
        active_connections = cursor.fetchall()
        logger.info(f"Toplam {len(active_connections)} aktif bağlantı bulundu")
        
        # 3. Aktif sorguları ve kilitleri göster
        for conn_info in active_connections:
            pid, username, app_name, client_addr, start_time, state, wait_type, query = conn_info
            logger.info(f"PID: {pid}, Kullanıcı: {username}, Durum: {state}, Başlangıç: {start_time}")
            logger.info(f"  Sorgu: {query[:100]}...")  # İlk 100 karakteri göster
        
        # 4. Kilit durumunu kontrol et
        cursor.execute("""
        SELECT bl.pid AS blocked_pid, 
               a.usename AS blocked_user, 
               a.query AS blocked_query,
               kl.pid AS blocking_pid, 
               ka.usename AS blocking_user, 
               ka.query AS blocking_query,
               now() - a.query_start AS blocked_duration
        FROM pg_catalog.pg_locks bl
        JOIN pg_catalog.pg_stat_activity a ON bl.pid = a.pid
        JOIN pg_catalog.pg_locks kl ON bl.transactionid = kl.transactionid AND bl.pid != kl.pid
        JOIN pg_catalog.pg_stat_activity ka ON kl.pid = ka.pid
        WHERE NOT bl.granted;
        """)
        
        locks = cursor.fetchall()
        if locks:
            logger.info(f"Toplam {len(locks)} kilitlenmiş sorgu bulundu")
            
            for lock_info in locks:
                blocked_pid, blocked_user, blocked_query, blocking_pid, blocking_user, blocking_query, duration = lock_info
                logger.info(f"Kilitlenmiş PID: {blocked_pid}, Kullanıcı: {blocked_user}, Süre: {duration}")
                logger.info(f"  Bekleyen sorgu: {blocked_query[:100]}...")
                logger.info(f"Kilitleyen PID: {blocking_pid}, Kullanıcı: {blocking_user}")
                logger.info(f"  Kilitleyen sorgu: {blocking_query[:100]}...")
                
                # Kilitleyen sorguyu sonlandır
                logger.info(f"PID {blocking_pid} numaralı sorgu sonlandırılıyor...")
                try:
                    cursor.execute(f"SELECT pg_terminate_backend({blocking_pid});")
                    logger.info(f"PID {blocking_pid} sonlandırıldı")
                    time.sleep(1)  # İşlemin tamamlanması için kısa bir bekleme
                except Exception as e:
                    logger.error(f"Sorgu sonlandırılırken hata: {str(e)}")
        else:
            logger.info("Kilitlenmiş sorgu bulunamadı")
        
        # 5. Uzun süren tüm sorguları sonlandır (isteğe bağlı)
        cursor.execute("""
        SELECT pid, 
               usename, 
               now() - query_start AS duration, 
               query
        FROM pg_stat_activity 
        WHERE query_start IS NOT NULL 
          AND state != 'idle'
          AND now() - query_start > interval '30 seconds'
          AND pid <> pg_backend_pid();
        """)
        
        long_queries = cursor.fetchall()
        if long_queries:
            logger.info(f"Toplam {len(long_queries)} uzun süren sorgu bulundu")
            
            for query_info in long_queries:
                pid, username, duration, query = query_info
                logger.info(f"Uzun süren sorgu (PID: {pid}, Kullanıcı: {username}, Süre: {duration})")
                logger.info(f"  Sorgu: {query[:100]}...")
                
                # İsteğe bağlı olarak uzun süren sorguyu sonlandır
                # (Dikkat: Bu, aktif sorguları kesebilir!)
                response = input(f"PID {pid} numaralı sorguyu sonlandırmak istiyor musunuz? (e/h): ")
                if response.lower() == 'e':
                    try:
                        cursor.execute(f"SELECT pg_terminate_backend({pid});")
                        logger.info(f"PID {pid} sonlandırıldı")
                    except Exception as e:
                        logger.error(f"Sorgu sonlandırılırken hata: {str(e)}")
        else:
            logger.info("Uzun süren sorgu bulunamadı")
        
        # 6. Boşta kalan (idle) bağlantıları temizle
        cursor.execute("""
        SELECT pid, 
               usename, 
               application_name, 
               state, 
               now() - state_change AS idle_duration
        FROM pg_stat_activity 
        WHERE state = 'idle'
          AND now() - state_change > interval '10 minutes'
          AND pid <> pg_backend_pid();
        """)
        
        idle_connections = cursor.fetchall()
        if idle_connections:
            logger.info(f"Toplam {len(idle_connections)} boşta kalan bağlantı bulundu")
            
            for conn_info in idle_connections:
                pid, username, app_name, state, idle_duration = conn_info
                logger.info(f"Boşta kalan bağlantı (PID: {pid}, Kullanıcı: {username}, Süre: {idle_duration})")
                
                # Boşta kalan bağlantıyı sonlandır
                try:
                    cursor.execute(f"SELECT pg_terminate_backend({pid});")
                    logger.info(f"PID {pid} sonlandırıldı")
                except Exception as e:
                    logger.error(f"Bağlantı sonlandırılırken hata: {str(e)}")
        else:
            logger.info("Boşta kalan bağlantı bulunamadı")
        
        # 7. İstatistikleri sıfırla
        try:
            logger.info("Veritabanı istatistikleri sıfırlanıyor...")
            cursor.execute("SELECT pg_stat_reset();")
            logger.info("Veritabanı istatistikleri sıfırlandı")
        except Exception as e:
            logger.error(f"İstatistikler sıfırlanırken hata: {str(e)}")
        
        # 8. Telethon session veritabanını düzeltmek için SQLite dosyasının yetkilerini düzelt
        try:
            session_files = [
                'runtime/sessions/bot_session.session',
                'session/bot_session.session'
            ]
            
            for session_file in session_files:
                if os.path.exists(session_file):
                    logger.info(f"Telethon session dosyası bulundu: {session_file}")
                    # Unix sistemlerde dosya izinlerini ayarla
                    try:
                        os.chmod(session_file, 0o666)
                        logger.info(f"Session dosyası yetkileri düzeltildi: {session_file}")
                    except Exception as e:
                        logger.error(f"Session dosyası yetkileri düzeltilirken hata: {str(e)}")
        except Exception as e:
            logger.error(f"Session dosyası işlemlerinde hata: {str(e)}")
        
        # 9. Vacuum işlemi (veritabanı optimizasyonu)
        try:
            logger.info("Veritabanı optimizasyonu (VACUUM) yapılıyor...")
            # Vacuum işlemi bir işlem (transaction) içinde çalıştırılamaz
            old_isolation_level = conn.isolation_level
            conn.set_isolation_level(0)  # ISOLATION_LEVEL_AUTOCOMMIT
            cursor.execute("VACUUM ANALYZE;")  # Bu komut tüm tabloları optimize eder
            conn.set_isolation_level(old_isolation_level)
            logger.info("Veritabanı optimizasyonu tamamlandı")
        except Exception as e:
            logger.error(f"Veritabanı optimizasyonu sırasında hata: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("Veritabanı kilitleri düzeltme işlemi tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_db_locks() 