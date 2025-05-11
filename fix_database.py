#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Veritabanı bağlantısı temizleme script'i.
Bu script, veritabanındaki bozuk/tamamlanmamış işlemleri temizler.
"""

import os
import sys
import psycopg2
import logging
from dotenv import load_dotenv

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fix_database")

# .env dosyasını yükle
load_dotenv()

def main():
    """Ana fonksiyon"""
    logger.info("Veritabanı bağlantısı temizleme aracı başlatılıyor...")
    
    # Veritabanı bağlantı parametreleri
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "telegram_bot")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    
    try:
        # Veritabanı bağlantısı
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password
        )
        
        # Otomatik commit'i kapat
        conn.autocommit = False
        
        # Cursor oluştur
        cur = conn.cursor()
        
        logger.info(f"Veritabanına bağlandı: {db_host}:{db_port}/{db_name}")
        
        # Aktif bağlantıları listele
        cur.execute("""
            SELECT pid, 
                   usename, 
                   application_name,
                   client_addr, 
                   state, 
                   query
            FROM pg_stat_activity 
            WHERE datname = %s
        """, (db_name,))
        
        connections = cur.fetchall()
        
        logger.info(f"Toplam {len(connections)} aktif bağlantı bulundu")
        
        # Aktif bağlantıları göster
        for conn_info in connections:
            pid, user, app_name, addr, state, query = conn_info
            logger.info(f"PID: {pid}, User: {user}, App: {app_name}, State: {state}")
            if query and len(query) > 100:
                query = query[:100] + "..."
            logger.info(f"  Query: {query}")
        
        # İdleme durumunda kalan işlemleri sonlandır
        cur.execute("""
            SELECT pid, 
                   usename,
                   state,
                   age(clock_timestamp(), xact_start) as xact_age
            FROM pg_stat_activity 
            WHERE datname = %s
            AND state = 'idle in transaction'
            AND age(clock_timestamp(), xact_start) > interval '5 minutes'
        """, (db_name,))
        
        idle_txns = cur.fetchall()
        
        if idle_txns:
            logger.info(f"{len(idle_txns)} uzun süren boşta işlem bulundu")
            for txn in idle_txns:
                pid, user, state, age = txn
                logger.info(f"PID: {pid}, User: {user}, State: {state}, Age: {age}")
                
                # İşlemi sonlandır
                try:
                    logger.info(f"PID {pid} işlemi sonlandırılıyor...")
                    cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
                    logger.info(f"PID {pid} işlemi sonlandırıldı")
                except Exception as e:
                    logger.error(f"PID {pid} işlemi sonlandırılırken hata oluştu: {str(e)}")
        else:
            logger.info("Boşta kalan işlem bulunamadı")
        
        # Toplam bağlantı sayısı
        cur.execute("""
            SELECT count(*) FROM pg_stat_activity WHERE datname = %s
        """, (db_name,))
        
        total_conn = cur.fetchone()[0]
        logger.info(f"Toplam bağlantı sayısı: {total_conn}")
        
        # Veritabanı istatistiklerini temizle
        logger.info("Veritabanı istatistiklerini sıfırlama...")
        cur.execute("SELECT pg_stat_reset()")
        
        # Değişiklikleri kaydet
        conn.commit()
        logger.info("İşlemler başarıyla tamamlandı")
        
        # İptal edilen işlemleri sıfırla
        logger.info("İptal edilmiş işlemleri temizleme...")
        cur.execute("ROLLBACK")
        conn.commit()
        
        # Tabloların analizini yap
        logger.info("Tabloların analizi yapılıyor...")
        # VACUUM transaction içinde çalışamaz, autocommit'i açıyoruz
        conn.autocommit = True
        cur.execute("VACUUM ANALYZE")
        
    except Exception as e:
        logger.error(f"Veritabanı işlemi sırasında hata oluştu: {str(e)}", exc_info=True)
        
    finally:
        # Bağlantıyı kapat
        try:
            if conn:
                conn.close()
                logger.info("Veritabanı bağlantısı kapatıldı")
        except:
            pass
    
    logger.info("Veritabanı bağlantısı temizleme aracı tamamlandı")
    
if __name__ == "__main__":
    main() 