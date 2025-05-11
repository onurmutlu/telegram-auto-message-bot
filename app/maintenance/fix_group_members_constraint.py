#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fix_group_members_constraint.py - Group members tablosunda unique constraint sorununu çözer

Bu script, group_members tablosunda unique constraint olmadığı için ON CONFLICT kullanımında 
yaşanan hatayı düzeltir. Tablo şemasını güncelleyerek (user_id, group_id) için bir unique constraint ekler.

Kullanım:
    python fix_group_members_constraint.py

Komut satırı parametreleri:
    --check-only: Sadece kontrolü yapar, veritabanında değişiklik yapmaz
    --verbose: Ayrıntılı çıktı gösterir

Hata raporu: "there is no unique or exclusion constraint matching the ON CONFLICT specification"
"""

import os
import sys
import time
import logging
import argparse
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Kendi modüllerimizi import et
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.models import Base, GroupMember
from database.setup_db import get_db_url, add_unique_constraints

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_existing_constraints(engine):
    """
    Mevcut kısıtlamaları kontrol eder
    """
    inspector = inspect(engine)
    
    # Tabloların varlığını kontrol et
    tables = inspector.get_table_names()
    if 'group_members' not in tables:
        logger.error("'group_members' tablosu bulunamadı!")
        return False
    
    # Unique constraint var mı kontrol et
    constraints = inspector.get_unique_constraints('group_members')
    unique_columns = []
    
    for constraint in constraints:
        if 'user_id' in constraint['column_names'] and 'group_id' in constraint['column_names']:
            logger.info(f"Group members tablosunda (user_id, group_id) için unique constraint zaten mevcut: {constraint}")
            return True
    
    # Primary key kontrol et (tek başına group_id ve user_id PK olabilir mi?)
    primary_keys = inspector.get_pk_constraint('group_members')
    logger.info(f"Primary keys: {primary_keys}")
    
    # Tabloda tekrar eden veriler var mı?
    with engine.connect() as connection:
        result = connection.execute(text("""
            SELECT user_id, group_id, COUNT(*) 
            FROM group_members 
            GROUP BY user_id, group_id 
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        if duplicates:
            logger.warning(f"Tabloda {len(duplicates)} tekrar eden veri bulundu!")
            logger.warning("Unique constraint eklemeden önce bu verilerin temizlenmesi gerekiyor")
            for dup in duplicates[:5]:  # İlk 5 örneği göster
                logger.warning(f"  Tekrar eden veri: user_id={dup[0]}, group_id={dup[1]}, adet={dup[2]}")
            
            if len(duplicates) > 5:
                logger.warning(f"  ... ve {len(duplicates) - 5} veri daha")
                
            return False
    
    logger.info("Group members tablosunda unique constraint yok, eklenebilir.")
    return False

def fix_duplicate_data(engine):
    """
    Tekrar eden verileri temizler
    """
    try:
        logger.info("Tekrar eden veriler temizleniyor...")
        
        with engine.begin() as connection:
            # Tekrar eden verileri bul
            result = connection.execute(text("""
                SELECT user_id, group_id, COUNT(*), 
                       array_agg(id) as ids
                FROM group_members 
                GROUP BY user_id, group_id 
                HAVING COUNT(*) > 1
            """))
            duplicates = result.fetchall()
            
            if not duplicates:
                logger.info("Tekrar eden veri yok.")
                return True
            
            logger.info(f"{len(duplicates)} tekrar eden grup bulundu, temizleniyor...")
            cleaned = 0
            
            for dup in duplicates:
                user_id, group_id, count, ids = dup
                # İlk kayıt dışındakileri sil (en düşük ID'ye sahip olanı tut)
                ids_to_delete = sorted(ids)[1:]  # ID'leri sırala ve ilk elemanı koru
                
                for id_to_delete in ids_to_delete:
                    connection.execute(text(f"DELETE FROM group_members WHERE id = {id_to_delete}"))
                    cleaned += 1
            
            logger.info(f"{cleaned} tekrar eden kayıt temizlendi.")
            return True
            
    except Exception as e:
        logger.error(f"Tekrar eden veriler temizlenirken hata: {str(e)}")
        return False

def fix_constraint_issue(check_only=False):
    """
    Ana düzeltme fonksiyonu
    """
    try:
        logger.info("Group members constraint sorunu düzeltme işlemi başladı...")
        
        # Veritabanı bağlantısı oluştur
        db_url = get_db_url()
        engine = create_engine(db_url)
        
        # Mevcut kısıtlamaları kontrol et
        constraint_exists = check_existing_constraints(engine)
        
        if constraint_exists:
            logger.info("Unique constraint zaten mevcut, işlem gerekmiyor.")
            return True
        
        if check_only:
            logger.info("Sadece kontrol modu aktif, veritabanında değişiklik yapılmayacak.")
            return True
        
        # Tekrar eden verileri temizle
        if not fix_duplicate_data(engine):
            logger.error("Tekrar eden veriler temizlenemedi, işlem iptal ediliyor.")
            return False
        
        # Unique constraint ekle
        add_unique_constraints(engine)
        
        # Başarıyla tamamlandı mı kontrol et
        success = check_existing_constraints(engine)
        
        if success:
            logger.info("Unique constraint başarıyla eklendi!")
        else:
            logger.error("Unique constraint eklenemedi!")
        
        return success
        
    except Exception as e:
        logger.error(f"Constraint düzeltme işlemi sırasında hata: {str(e)}")
        return False

def main():
    """
    Ana fonksiyon
    """
    parser = argparse.ArgumentParser(description='Group members tablosunda unique constraint sorununu çözer')
    parser.add_argument('--check-only', action='store_true', help='Sadece kontrolü yapar, değişiklik yapmaz')
    parser.add_argument('--verbose', action='store_true', help='Ayrıntılı çıktı gösterir')
    args = parser.parse_args()
    
    # Verbose modunu ayarla
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    start_time = time.time()
    success = fix_constraint_issue(check_only=args.check_only)
    end_time = time.time()
    
    if success:
        logger.info(f"İşlem başarıyla tamamlandı! Geçen süre: {end_time - start_time:.2f} saniye")
        return 0
    else:
        logger.error("İşlem tamamlanamadı!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 