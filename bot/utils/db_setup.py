def upgrade_database():
    """
    Veritabanı şemasını en son versiyona yükseltir.
    """
    from database.schema import TABLES, MIGRATIONS, DB_SCHEMA_VERSION
    import sqlite3
    import os
    
    db_path = os.environ.get('DB_PATH', 'runtime/database/users.db')
    
    # Veritabanı dizininin varlığını kontrol et
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    # Veritabanı bağlantısı oluştur
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # Şema versiyonu tablosu
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Mevcut şema versiyonunu kontrol et
        cursor = conn.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
        row = cursor.fetchone()
        current_version = row['version'] if row else '0.0'
        
        print(f"Mevcut veritabanı şema versiyonu: {current_version}")
        print(f"Hedef veritabanı şema versiyonu: {DB_SCHEMA_VERSION}")
        
        # Eğer güncel değilse tabloları oluştur ve migrasyonları uygula
        if current_version != DB_SCHEMA_VERSION:
            print("Veritabanı şeması güncelleniyor...")
            
            # Tabloları oluştur
            for table_sql in TABLES:
                conn.execute(table_sql)
                
            # Migrasyonları uygula
            for migration_sql in MIGRATIONS:
                conn.executescript(migration_sql)
                
            # Şema versiyonunu güncelle
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (DB_SCHEMA_VERSION,))
            conn.commit()
            
            print(f"Veritabanı başarıyla {DB_SCHEMA_VERSION} versiyonuna güncellendi.")
        else:
            print("Veritabanı şeması zaten güncel.")
            
    except Exception as e:
        print(f"Veritabanı güncellenirken hata: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade_database()