#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PostgreSQL veritabanı optimizasyon betiği

Bu betik, veritabanı performansını artırmak için aşağıdaki işlemleri gerçekleştirir:
1. Tüm tabloların analizi (ANALYZE)
2. Boş alanların temizlenmesi (VACUUM)
3. İndekslerin yeniden oluşturulması (REINDEX)
4. Veritabanı istatistiklerinin güncellenmesi
5. BigInt sütun dönüşümlerinin kontrolü
6. Unique constraint kontrolü
7. İndekslerin kontrolü ve optimizasyonu

Kullanım:
    python optimize_database.py [--vacuum-full] [--reindex-all] [--analyze-only] [--check-bigint] [--add-constraints] [--verbose]

"""

import os
import sys
import time
import argparse
import logging
import asyncio
from sqlalchemy import create_engine, text, inspect
from datetime import datetime, timedelta

# Proje kök dizinini import yoluna ekle
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.setup_db import get_db_url, check_and_fix_bigint_columns, add_unique_constraints, create_indexes

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"database_optimize_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

def get_table_sizes(engine):
    """
    Tüm tabloların boyutunu döndürür
    """
    logger.info("Tablo boyutları alınıyor...")
    
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT 
                relname as table_name,
                pg_size_pretty(pg_total_relation_size(c.oid)) as total_size,
                pg_size_pretty(pg_relation_size(c.oid)) as table_size,
                pg_size_pretty(pg_total_relation_size(c.oid) - pg_relation_size(c.oid)) as index_size,
                pg_total_relation_size(c.oid) as size_in_bytes
            FROM pg_class c
            LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE nspname = 'public'
            AND c.relkind = 'r'
            ORDER BY pg_total_relation_size(c.oid) DESC
        """))
        
        table_sizes = [dict(row) for row in result]
        
        # Toplam boyutu hesapla
        total_size_bytes = sum(row['size_in_bytes'] for row in table_sizes)
        
        # MB ve GB olarak toplam boyut
        total_size_mb = total_size_bytes / (1024 * 1024)
        total_size_gb = total_size_bytes / (1024 * 1024 * 1024)
        
        logger.info(f"Toplam veritabanı boyutu: {total_size_mb:.2f} MB ({total_size_gb:.4f} GB)")
        
        # Tablo boyutlarını yazdır
        logger.info("Tablo boyutları:")
        for row in table_sizes:
            logger.info(f"  {row['table_name']}: {row['total_size']} (Tablo: {row['table_size']}, İndeksler: {row['index_size']})")
            
        return table_sizes

def get_slow_queries(engine, min_time_ms=100, limit=20):
    """
    Yavaş sorguları döndürür (pg_stat_statements gerektirir)
    """
    logger.info(f"En yavaş {limit} sorgu alınıyor (min: {min_time_ms}ms)...")
    
    try:
        with engine.begin() as conn:
            # pg_stat_statements extension mevcut mu kontrol et
            result = conn.execute(text("""
                SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
            """))
            
            if not result.scalar():
                logger.warning("pg_stat_statements extension kurulu değil. Yavaş sorgular alınamıyor.")
                return []
            
            # Yavaş sorguları al
            result = conn.execute(text(f"""
                SELECT 
                    round(mean_exec_time) as avg_time_ms,
                    calls,
                    round(total_exec_time) as total_time_ms,
                    query
                FROM pg_stat_statements
                WHERE mean_exec_time > {min_time_ms}
                ORDER BY mean_exec_time DESC
                LIMIT {limit}
            """))
            
            slow_queries = [dict(row) for row in result]
            
            if slow_queries:
                logger.info(f"En yavaş {len(slow_queries)} sorgu:")
                for i, row in enumerate(slow_queries, 1):
                    logger.info(f"  #{i}: {row['avg_time_ms']}ms (çağrı: {row['calls']}, toplam: {row['total_time_ms']}ms)")
                    logger.info(f"      {row['query'][:100]}...")
            else:
                logger.info(f"Yavaş sorgu bulunamadı (min: {min_time_ms}ms)")
                
            return slow_queries
    except Exception as e:
        logger.error(f"Yavaş sorgular alınırken hata: {str(e)}")
        return []

def get_index_usage(engine):
    """
    İndeks kullanım istatistiklerini döndürür
    """
    logger.info("İndeks kullanım istatistikleri alınıyor...")
    
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT
                schemaname || '.' || relname as table_name,
                indexrelname as index_name,
                idx_scan as scan_count,
                pg_size_pretty(pg_relation_size(idxoid)) as index_size,
                pg_relation_size(idxoid) as size_in_bytes
            FROM pg_stat_user_indexes
            JOIN pg_index USING (indexrelid)
            ORDER BY idx_scan DESC NULLS LAST, pg_relation_size(indexrelid) DESC
        """))
        
        index_stats = [dict(row) for row in result]
        
        total_size_bytes = sum(row['size_in_bytes'] for row in index_stats)
        total_size_mb = total_size_bytes / (1024 * 1024)
        
        logger.info(f"Toplam indeks boyutu: {total_size_mb:.2f} MB")
        
        # En çok kullanılan indeksler
        most_used = [row for row in index_stats if row['scan_count'] > 0]
        if most_used:
            logger.info("En çok kullanılan indeksler:")
            for i, row in enumerate(most_used[:10], 1):
                logger.info(f"  #{i}: {row['index_name']} ({row['scan_count']} tarama, boyut: {row['index_size']})")
        
        # Hiç kullanılmayan indeksler
        unused = [row for row in index_stats if row['scan_count'] == 0]
        if unused:
            logger.info(f"Hiç kullanılmayan indeksler ({len(unused)}):")
            for i, row in enumerate(unused[:10], 1):
                logger.info(f"  #{i}: {row['index_name']} (boyut: {row['index_size']})")
            
            if len(unused) > 10:
                logger.info(f"  ... ve {len(unused) - 10} daha")
                
        return index_stats

def vacuum_database(engine, full=False, tables=None):
    """
    Veritabanında VACUUM işlemi gerçekleştirir
    
    Args:
        engine: SQLAlchemy engine
        full: VACUUM FULL yapılsın mı
        tables: Belirli tabloları vacuum yapmak için liste
    """
    try:
        # FULL kullanılacak mı
        vacuum_type = "FULL" if full else ""
        
        logger.info(f"VACUUM {vacuum_type} işlemi başlatılıyor...")
        start_time = time.time()
        
        with engine.begin() as conn:
            if tables:
                # Belirli tablolar için VACUUM
                for table in tables:
                    logger.info(f"VACUUM {vacuum_type} {table} tablosu için çalıştırılıyor...")
                    conn.execute(text(f"VACUUM {vacuum_type} {table}"))
            else:
                # Tüm veritabanı için VACUUM
                conn.execute(text(f"VACUUM {vacuum_type}"))
                
        elapsed = time.time() - start_time
        logger.info(f"VACUUM {vacuum_type} işlemi tamamlandı ({elapsed:.2f} saniye)")
        
    except Exception as e:
        logger.error(f"VACUUM işlemi sırasında hata: {str(e)}")

def analyze_database(engine, tables=None):
    """
    Veritabanında ANALYZE işlemi gerçekleştirir
    
    Args:
        engine: SQLAlchemy engine
        tables: Belirli tabloları analiz etmek için liste
    """
    try:
        logger.info("ANALYZE işlemi başlatılıyor...")
        start_time = time.time()
        
        with engine.begin() as conn:
            if tables:
                # Belirli tablolar için ANALYZE
                for table in tables:
                    logger.info(f"ANALYZE {table} tablosu için çalıştırılıyor...")
                    conn.execute(text(f"ANALYZE {table}"))
            else:
                # Tüm veritabanı için ANALYZE
                conn.execute(text("ANALYZE"))
                
        elapsed = time.time() - start_time
        logger.info(f"ANALYZE işlemi tamamlandı ({elapsed:.2f} saniye)")
        
    except Exception as e:
        logger.error(f"ANALYZE işlemi sırasında hata: {str(e)}")

def reindex_database(engine, tables=None):
    """
    Veritabanında REINDEX işlemi gerçekleştirir
    
    Args:
        engine: SQLAlchemy engine
        tables: Belirli tabloları reindex yapmak için liste
    """
    try:
        logger.info("REINDEX işlemi başlatılıyor...")
        start_time = time.time()
        
        with engine.begin() as conn:
            if tables:
                # Belirli tablolar için REINDEX
                for table in tables:
                    logger.info(f"REINDEX {table} tablosu için çalıştırılıyor...")
                    conn.execute(text(f"REINDEX TABLE {table}"))
            else:
                # İndeksleri ayrı ayrı reindex yap (SCHEMA kullanmak yerine)
                inspector = inspect(engine)
                table_names = inspector.get_table_names()
                
                for table in table_names:
                    logger.info(f"REINDEX {table} tablosu için çalıştırılıyor...")
                    conn.execute(text(f"REINDEX TABLE {table}"))
                
        elapsed = time.time() - start_time
        logger.info(f"REINDEX işlemi tamamlandı ({elapsed:.2f} saniye)")
        
    except Exception as e:
        logger.error(f"REINDEX işlemi sırasında hata: {str(e)}")

def optimize_database(engine, args):
    """
    Veritabanını optimize eder
    
    Args:
        engine: SQLAlchemy engine
        args: Komut satırı argümanları
    """
    logger.info("Veritabanı optimizasyonu başlatılıyor...")
    
    # Bilgi toplama
    get_table_sizes(engine)
    get_index_usage(engine)
    get_slow_queries(engine)
    
    # ANALYZE
    analyze_database(engine)
    
    # VACUUM
    if not args.analyze_only:
        vacuum_database(engine, full=args.vacuum_full)
    
    # REINDEX
    if args.reindex_all and not args.analyze_only:
        reindex_database(engine)
    
    # BigInt kontrolü
    if args.check_bigint:
        check_and_fix_bigint_columns(engine)
    
    # İndeks kontrolü
    create_indexes(engine)
    
    # Unique constraint kontrolü
    if args.add_constraints:
        add_unique_constraints(engine)
    
    # Son olarak tekrar veri topla
    logger.info("\nOptimizasyon sonrası veritabanı durumu:")
    get_table_sizes(engine)
    
    logger.info("Veritabanı optimizasyonu tamamlandı.")
    
def main():
    """Ana fonksiyon"""
    parser = argparse.ArgumentParser(description='PostgreSQL veritabanı optimizasyon betiği')
    parser.add_argument('--vacuum-full', action='store_true', help='VACUUM FULL çalıştır (daha uzun sürer ama daha etkilidir)')
    parser.add_argument('--reindex-all', action='store_true', help='Tüm indeksleri yeniden oluştur')
    parser.add_argument('--analyze-only', action='store_true', help='Sadece ANALYZE çalıştır, veritabanını değiştirme')
    parser.add_argument('--check-bigint', action='store_true', help='BigInt sütunları kontrol et ve dönüştür')
    parser.add_argument('--add-constraints', action='store_true', help='Unique constraint kontrolü yap')
    parser.add_argument('--verbose', action='store_true', help='Detaylı loglama')
    args = parser.parse_args()
    
    # Verbose mod
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Veritabanı bağlantısı
    db_url = get_db_url()
    logger.info(f"Veritabanı URL: {db_url}")
    
    # Engine oluştur
    engine = create_engine(db_url)
    
    # Veritabanını optimize et
    optimize_database(engine, args)
    
    # Engine'i kapat
    engine.dispose()
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 