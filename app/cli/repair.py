"""
Veritabanı onarım komutları
"""
import os
import sys
import logging
import asyncio
import importlib
import subprocess
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session

logger = logging.getLogger(__name__)

async def repair_db():
    """Veritabanı onarımı yapar"""
    try:
        db = next(get_session())
        logger.info("Veritabanı onarım işlemi başlatılıyor...")
        
        # Tablolardaki kilitleri kontrol et ve temizle
        try:
            # Oturum temizliği
            db.rollback()
            
            # Aktif bağlantıları kontrol et
            check_connections_query = text("""
                SELECT pid, query_start, state, query 
                FROM pg_stat_activity 
                WHERE datname = current_database() 
                AND pid <> pg_backend_pid()
                AND state = 'idle in transaction'
            """)
            
            result = db.execute(check_connections_query)
            idle_connections = result.fetchall()
            
            if idle_connections:
                logger.warning(f"{len(idle_connections)} adet 'idle in transaction' bağlantısı tespit edildi.")
                
                # Her bir bağlantıyı sonlandır
                for conn in idle_connections:
                    try:
                        pid = conn.pid
                        terminate_query = text(f"""
                            SELECT pg_terminate_backend({pid})
                        """)
                        db.execute(terminate_query)
                        logger.info(f"Bağlantı sonlandırıldı: PID={pid}")
                    except Exception as e:
                        logger.error(f"Bağlantı sonlandırma hatası (PID={conn.pid}): {e}")
                
                db.commit()
                logger.info("Artık bağlantılar temizlendi.")
            else:
                logger.info("Artık bağlantı tespit edilmedi.")
            
            # Aktif kilitleri tespit et
            check_locks_query = text("""
                SELECT l.relation::regclass, l.mode, l.pid, a.query, a.query_start
                FROM pg_locks l
                JOIN pg_stat_activity a ON l.pid = a.pid
                WHERE l.granted AND l.relation IS NOT NULL
                AND a.datname = current_database()
                AND a.pid <> pg_backend_pid()
            """)
            
            result = db.execute(check_locks_query)
            locks = result.fetchall()
            
            if locks:
                logger.warning(f"{len(locks)} adet kilit tespit edildi.")
                
                # Kilitleri göster
                for lock in locks:
                    logger.info(f"Kilit: Tablo={lock.relation}, Mod={lock.mode}, PID={lock.pid}")
                
                # Kilitleyen prosesleri sonlandır
                for lock in locks:
                    try:
                        pid = lock.pid
                        terminate_query = text(f"""
                            SELECT pg_terminate_backend({pid})
                        """)
                        db.execute(terminate_query)
                        logger.info(f"Kilit kaldırıldı: PID={pid}, Tablo={lock.relation}")
                    except Exception as e:
                        logger.error(f"Kilit kaldırma hatası (PID={lock.pid}): {e}")
                
                db.commit()
                logger.info("Kilitler temizlendi.")
            else:
                logger.info("Aktif kilit tespit edilmedi.")
            
            logger.info("Veritabanı onarımı başarıyla tamamlandı.")
            return True, "Veritabanı onarımı başarıyla tamamlandı."
            
        except SQLAlchemyError as e:
            logger.error(f"Veritabanı onarımı sırasında hata: {e}")
            db.rollback()
            return False, f"Veritabanı hatası: {str(e)}"
        
    except Exception as e:
        logger.error(f"Veritabanı onarım işlemi sırasında hata: {e}")
        return False, f"Hata: {str(e)}"

def run_repair():
    """CLI için repair çalıştırıcı"""
    result, message = asyncio.run(repair_db())
    
    if result:
        print("\033[92m" + message + "\033[0m")  # Yeşil
    else:
        print("\033[91m" + message + "\033[0m")  # Kırmızı
    
    return result 