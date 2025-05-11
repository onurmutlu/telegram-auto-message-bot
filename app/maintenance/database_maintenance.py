"""
Veritabanı Bakım Araçları

Veritabanı bakım, onarım ve optimizasyon işlemleri için yardımcı araçlar.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

from app.core.logger import get_logger
from app.db.session import get_session

logger = get_logger(__name__)

async def fix_db_locks(db_path: Optional[str] = None, verbose: bool = False) -> Tuple[bool, int]:
    """
    Veritabanı kilitlerini temizler.
    
    Args:
        db_path: Veritabanı dosya yolu (None ise varsayılan)
        verbose: Ayrıntılı log çıktısı
        
    Returns:
        Tuple[bool, int]: (başarılı mı, düzeltilen kilit sayısı)
    """
    try:
        logger.info("Veritabanı kilitleri temizleniyor...")
        
        if verbose:
            logger.info(f"Kullanılan veritabanı: {db_path or 'varsayılan'}")
            
        # Veritabanı bağlantısı al
        session = next(get_session())
        
        # Kilitleri temizle
        try:
            # PostgreSQL için kilit temizleme sorgusu
            result = session.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND state = 'idle';")
            affected = result.rowcount
            
            # Commit yaparak değişiklikleri uygula
            session.commit()
            
            if verbose:
                logger.info(f"Toplam {affected} kilit temizlendi")
                
            return True, affected
            
        except Exception as e:
            # Hata durumunda rollback yap
            session.rollback()
            logger.error(f"Kilit temizleme hatası: {str(e)}")
            return False, 0
            
        finally:
            # Her durumda oturumu kapat
            session.close()
            
    except Exception as e:
        logger.exception(f"Veritabanı kilit temizleme işlemi başarısız: {str(e)}")
        return False, 0

async def fix_permissions(schema: str = "public", verbose: bool = False) -> Tuple[bool, int]:
    """
    Veritabanı izinlerini düzeltir.
    
    Args:
        schema: Şema adı
        verbose: Ayrıntılı log çıktısı
        
    Returns:
        Tuple[bool, int]: (başarılı mı, düzeltilen tablo sayısı)
    """
    try:
        logger.info(f"Veritabanı izinleri düzeltiliyor: {schema} şeması...")
        
        # Veritabanı bağlantısı al
        session = next(get_session())
        fixed_count = 0
        
        try:
            # Tüm tabloları listele
            result = session.execute(f"SELECT tablename FROM pg_tables WHERE schemaname = '{schema}';")
            tables = [row[0] for row in result.fetchall()]
            
            if verbose:
                logger.info(f"Toplam {len(tables)} tablo bulundu")
                
            # Her tablo için izinleri düzelt
            for table in tables:
                try:
                    # Tablo izinlerini ayarla
                    session.execute(f"GRANT ALL PRIVILEGES ON TABLE {schema}.{table} TO current_user;")
                    fixed_count += 1
                    
                    if verbose:
                        logger.info(f"Tablo izinleri düzeltildi: {table}")
                        
                except Exception as e:
                    logger.error(f"Tablo izinleri düzeltilemedi: {table} - {str(e)}")
                    
            # Commit yaparak değişiklikleri uygula
            session.commit()
            
            logger.info(f"Toplam {fixed_count}/{len(tables)} tablo izni düzeltildi")
            return True, fixed_count
            
        except Exception as e:
            # Hata durumunda rollback yap
            session.rollback()
            logger.error(f"İzin düzeltme hatası: {str(e)}")
            return False, fixed_count
            
        finally:
            # Her durumda oturumu kapat
            session.close()
            
    except Exception as e:
        logger.exception(f"Veritabanı izin düzeltme işlemi başarısız: {str(e)}")
        return False, 0

async def optimize_database(vacuum: bool = True, analyze: bool = True, verbose: bool = False) -> bool:
    """
    Veritabanını optimize eder.
    
    Args:
        vacuum: VACUUM işlemi yapılsın mı
        analyze: ANALYZE işlemi yapılsın mı
        verbose: Ayrıntılı log çıktısı
        
    Returns:
        bool: Başarılı ise True
    """
    try:
        logger.info("Veritabanı optimizasyonu başlatılıyor...")
        
        # Veritabanı bağlantısı al
        session = next(get_session())
        
        try:
            # VACUUM işlemi
            if vacuum:
                if verbose:
                    logger.info("VACUUM işlemi başlatılıyor...")
                    
                # VACUUM ANALYZE işlemi
                if analyze:
                    session.execute("VACUUM ANALYZE;")
                    if verbose:
                        logger.info("VACUUM ANALYZE işlemi tamamlandı")
                else:
                    session.execute("VACUUM;")
                    if verbose:
                        logger.info("VACUUM işlemi tamamlandı")
                        
            # Sadece ANALYZE işlemi
            elif analyze:
                if verbose:
                    logger.info("ANALYZE işlemi başlatılıyor...")
                    
                session.execute("ANALYZE;")
                
                if verbose:
                    logger.info("ANALYZE işlemi tamamlandı")
                    
            # Commit yaparak değişiklikleri uygula
            session.commit()
            
            logger.info("Veritabanı optimizasyonu tamamlandı")
            return True
            
        except Exception as e:
            # Hata durumunda rollback yap
            session.rollback()
            logger.error(f"Optimizasyon hatası: {str(e)}")
            return False
            
        finally:
            # Her durumda oturumu kapat
            session.close()
            
    except Exception as e:
        logger.exception(f"Veritabanı optimizasyon işlemi başarısız: {str(e)}")
        return False

async def run_all_maintenance(verbose: bool = False) -> Dict[str, Any]:
    """
    Tüm bakım işlemlerini çalıştırır.
    
    Args:
        verbose: Ayrıntılı log çıktısı
        
    Returns:
        Dict[str, Any]: Sonuç raporu
    """
    logger.info("Tüm bakım işlemleri başlatılıyor...")
    
    results = {
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "steps": {},
        "success": False
    }
    
    # Veritabanı kilitlerini temizle
    success, count = await fix_db_locks(verbose=verbose)
    results["steps"]["fix_db_locks"] = {
        "success": success,
        "count": count
    }
    
    # Veritabanı izinlerini düzelt
    success, count = await fix_permissions(verbose=verbose)
    results["steps"]["fix_permissions"] = {
        "success": success,
        "count": count
    }
    
    # Veritabanını optimize et
    success = await optimize_database(verbose=verbose)
    results["steps"]["optimize_database"] = {
        "success": success
    }
    
    # Sonuç raporu
    results["end_time"] = datetime.now().isoformat()
    results["success"] = all(step["success"] for step in results["steps"].values())
    
    if results["success"]:
        logger.info("Tüm bakım işlemleri başarıyla tamamlandı")
    else:
        logger.warning("Bazı bakım işlemleri başarısız oldu")
        
    return results

# Komut satırından çalıştırılırsa
if __name__ == "__main__":
    import argparse
    
    # Argümanları ayarla
    parser = argparse.ArgumentParser(description="Veritabanı bakım araçları")
    parser.add_argument("--fix-locks", action="store_true", help="Veritabanı kilitlerini temizle")
    parser.add_argument("--fix-permissions", action="store_true", help="Veritabanı izinlerini düzelt")
    parser.add_argument("--optimize", action="store_true", help="Veritabanını optimize et")
    parser.add_argument("--all", action="store_true", help="Tüm bakım işlemlerini çalıştır")
    parser.add_argument("--verbose", action="store_true", help="Ayrıntılı log çıktısı")
    
    # Argümanları ayrıştır
    args = parser.parse_args()
    
    # Asenkron çalıştırma fonksiyonu
    async def main():
        if args.all:
            await run_all_maintenance(verbose=args.verbose)
        else:
            if args.fix_locks:
                await fix_db_locks(verbose=args.verbose)
            if args.fix_permissions:
                await fix_permissions(verbose=args.verbose)
            if args.optimize:
                await optimize_database(verbose=args.verbose)
                
    # Asenkron işlevi çalıştır
    asyncio.run(main()) 