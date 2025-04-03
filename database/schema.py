# Veritabanı şema versiyonunu güncelleyin
DB_SCHEMA_VERSION = '2.0'

# Ekstra tablo tanımları ekleyin
TABLES = [
    # ...diğer tablolar...
    
    # Debug bot kullanıcıları için tablo
    """
    CREATE TABLE IF NOT EXISTS debug_bot_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        access_level TEXT DEFAULT 'basic',
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_developer BOOLEAN DEFAULT 0,
        is_superuser BOOLEAN DEFAULT 0
    )
    """,
    
    # Premium kullanıcı bilgileri için tablo
    """
    CREATE TABLE IF NOT EXISTS premium_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        license_key TEXT UNIQUE,
        license_type TEXT DEFAULT 'standard',
        api_id TEXT,
        api_hash TEXT,
        phone_number TEXT,
        activation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expiration_date TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """,
    
    # Sistem ayarları için tablo
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        description TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
]

# Veritabanı migrasyon betiği
MIGRATIONS = [
    # v1.0'dan v2.0'a migrasyon
    """
    -- v1.0'dan v2.0'a migrasyon
    
    -- Varolan users tablosunu yedekle
    CREATE TABLE IF NOT EXISTS users_backup AS SELECT * FROM users;
    
    -- Yeni tablolar için indeksler
    CREATE INDEX IF NOT EXISTS idx_debug_bot_users_user_id ON debug_bot_users(user_id);
    CREATE INDEX IF NOT EXISTS idx_premium_users_user_id ON premium_users(user_id);
    CREATE INDEX IF NOT EXISTS idx_premium_users_license_key ON premium_users(license_key);
    
    -- Varsayılan ayarlar ekle
    INSERT OR IGNORE INTO settings (key, value, description) VALUES 
    ('max_premium_users', '100', 'Maksimum premium kullanıcı sayısı'),
    ('license_validity_days', '365', 'Premium lisansların geçerlilik süresi (gün)'),
    ('debug_access_enabled', 'true', 'Debug bot erişiminin etkin olup olmadığı'),
    ('monitor_admin_ids', '', 'Virgülle ayrılmış monitor yönetici ID listesi');
    """
]