#!/usr/bin/env python3
"""
Telethon oturum dosyasını kontrol eden yardımcı araç.
Bu araç oturum dosyasının yapısını kontrol eder ve
farklı Telethon sürümleri arasındaki şema uyumsuzluklarını tespit eder.
"""

import os
import sys
import sqlite3
import logging

# Ana dizini ekle
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def check_telethon_session(session_path):
    """
    Telethon oturum dosyasını kontrol eder.
    
    Args:
        session_path (str): Oturum dosyasının yolu
        
    Returns:
        dict: Kontrol sonuçları
    """
    result = {
        "exists": False,
        "valid": False,
        "corrupted": False,
        "version_mismatch": False,
        "schema": None,
        "expected_columns": 5,  # Telethon 1.40.0 için beklenen sütun sayısı
        "actual_columns": 0,
        "column_names": []
    }
    
    # Dosya var mı kontrol et
    if not os.path.exists(session_path):
        logger.warning(f"Oturum dosyası bulunamadı: {session_path}")
        return result
    
    result["exists"] = True
    
    # Dosya boyutunu kontrol et
    file_size = os.path.getsize(session_path)
    if file_size < 100:  # Minimum boyut kontrolü
        result["corrupted"] = True
        logger.warning(f"Oturum dosyası çok küçük: {file_size} bayt, muhtemelen bozuk")
        return result
    
    # İlk 100 baytı oku ve beklenilen SQLite magic number'ı içeriyor mu kontrol et
    try:
        with open(session_path, 'rb') as f:
            header = f.read(100)
            # SQLite magic number: 53 51 4c 69 74 65 ("SQLite" in ASCII)
            if not header.startswith(b'SQLite'):
                result["corrupted"] = True
                logger.warning("Oturum dosyası SQLite veritabanı değil, muhtemelen bozuk")
                return result
    except Exception as e:
        result["corrupted"] = True
        logger.warning(f"Oturum dosyası okuma hatası: {e}")
        return result
    
    # Telethon sürüm uyumluluğu kontrolü
    try:
        conn = sqlite3.connect(session_path)
        cursor = conn.cursor()
        
        # Tabloları kontrol et
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        logger.info(f"Oturum veritabanında {len(tables)} tablo bulundu: {', '.join(table_names)}")
        
        if "sessions" not in table_names:
            result["corrupted"] = True
            logger.warning("Oturum dosyasında 'sessions' tablosu bulunamadı")
            conn.close()
            return result
        
        # "sessions" tablosunun yapısını kontrol et
        cursor.execute("PRAGMA table_info(sessions)")
        columns = cursor.fetchall()
        
        # Sütun sayısını kontrol et
        column_count = len(columns)
        column_names = [col[1] for col in columns]
        
        result["actual_columns"] = column_count
        result["column_names"] = column_names
        
        # Şema bilgisi
        schema_info = []
        for col in columns:
            schema_info.append({
                "id": col[0],
                "name": col[1],
                "type": col[2],
                "notnull": col[3],
                "default": col[4],
                "pk": col[5]
            })
        
        result["schema"] = schema_info
        
        logger.info(f"'sessions' tablosunda {column_count} sütun bulundu: {', '.join(column_names)}")
        
        if column_count != result["expected_columns"]:
            result["version_mismatch"] = True
            logger.warning(f"Oturum dosyası sürüm uyumsuzluğu: {column_count} sütun ({result['expected_columns']} olması gerekiyor)")
            
            # Sütunları kontrol et ve hangi sürüme ait olduğunu tespit et
            if column_count == 4:
                logger.info("Oturum dosyası Telethon <1.22 sürümüne ait olabilir")
            
        else:
            result["valid"] = True
            logger.info("Oturum dosyası geçerli görünüyor")
        
        # Veri örneği kontrol et
        try:
            cursor.execute("SELECT * FROM sessions LIMIT 1")
            data = cursor.fetchone()
            if data:
                logger.info(f"'sessions' tablosunda veri bulundu")
            else:
                logger.warning("'sessions' tablosunda veri bulunamadı")
        except sqlite3.OperationalError as e:
            logger.warning(f"'sessions' tablosundan veri alınırken hata: {e}")
        
        conn.close()
        
    except sqlite3.OperationalError as e:
        result["corrupted"] = True
        logger.warning(f"SQLite hatası: {e}")
    except Exception as e:
        result["corrupted"] = True
        logger.warning(f"Oturum dosyası kontrolü sırasında beklenmeyen hata: {e}")
    
    return result

def fix_telethon_session(session_path):
    """
    Telethon oturum dosyasını düzeltmeyi dener.
    Şu anda sadece teşhis amaçlı kullanılır, otomatik düzeltme yapmaz.
    
    Args:
        session_path (str): Oturum dosyasının yolu
        
    Returns:
        dict: İşlem sonuçları
    """
    # Önce dosyayı kontrol et
    check_result = check_telethon_session(session_path)
    
    if not check_result["exists"]:
        return {
            "success": False,
            "message": "Oturum dosyası bulunamadı",
            "fix_needed": False
        }
    
    if check_result["corrupted"]:
        return {
            "success": False,
            "message": "Oturum dosyası bozuk, yeni bir oturum oluşturulmalı",
            "fix_needed": True,
            "fix_type": "create_new"
        }
    
    if check_result["version_mismatch"]:
        return {
            "success": False,
            "message": f"Sürüm uyumsuzluğu tespit edildi. Beklenen: {check_result['expected_columns']} sütun, Mevcut: {check_result['actual_columns']} sütun",
            "fix_needed": True,
            "fix_type": "schema_migration",
            "actual_schema": check_result["schema"],
            "actual_columns": check_result["actual_columns"],
            "expected_columns": check_result["expected_columns"]
        }
    
    return {
        "success": True,
        "message": "Oturum dosyası geçerli, düzeltme gerekmez",
        "fix_needed": False
    }

if __name__ == "__main__":
    # Örnek kullanım
    if len(sys.argv) < 2:
        print("Kullanım: python check_telethon_session.py [oturum_dosyası_yolu]")
        sys.exit(1)
    
    session_path = sys.argv[1]
    result = check_telethon_session(session_path)
    
    print("\n" + "="*50)
    print(" Telethon Oturum Dosyası Kontrol Sonuçları ")
    print("="*50)
    
    print(f"Dosya: {session_path}")
    print(f"Mevcut: {'Evet' if result['exists'] else 'Hayır'}")
    print(f"Geçerli: {'Evet' if result['valid'] else 'Hayır'}")
    print(f"Bozuk: {'Evet' if result['corrupted'] else 'Hayır'}")
    print(f"Sürüm uyumsuzluğu: {'Evet' if result['version_mismatch'] else 'Hayır'}")
    
    if result["exists"] and not result["corrupted"]:
        print(f"\nBeklenen sütun sayısı: {result['expected_columns']}")
        print(f"Mevcut sütun sayısı: {result['actual_columns']}")
        print(f"Mevcut sütunlar: {', '.join(result['column_names'])}")
    
    print("\nDÜZELTME TAVSİYESİ:")
    fix_result = fix_telethon_session(session_path)
    print(fix_result["message"])
    
    if fix_result["fix_needed"]:
        print("\nÖnerilen çözüm:")
        if fix_result["fix_type"] == "create_new":
            print("Yeni bir oturum dosyası oluşturulmalı ve yeniden kimlik doğrulaması yapılmalı.")
        elif fix_result["fix_type"] == "schema_migration":
            print("Telethon sürümünü değiştirme veya yeni bir oturum dosyası oluşturma gerekebilir.")
            
    print("\nİŞLEM TAMAMLANDI!")
    print("="*50)
