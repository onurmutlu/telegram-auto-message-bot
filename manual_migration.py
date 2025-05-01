import psycopg2
import os
from urllib.parse import urlparse

# .env'den bağlantı bilgilerini al
from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')

# Bağlantı parametrelerini ayrıştır
url = urlparse(db_url)
db_name = url.path[1:]  # / işaretini kaldır
db_user = url.username
db_password = url.password
db_host = url.hostname
db_port = url.port or 5432

print(f'Bağlantı parametreleri: {db_host}:{db_port}/{db_name}')

# Bağlantı kur
conn = psycopg2.connect(
    dbname=db_name,
    user=db_user,
    password=db_password,
    host=db_host,
    port=db_port
)

cursor = conn.cursor()

# Migration SQL'i çalıştır
migration_sql = '''
-- Mesajlar tablosunu oluştur
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    group_id INTEGER REFERENCES groups(group_id),
    content TEXT,
    sent_at TIMESTAMP,
    status TEXT,
    error TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Veri madenciliği tablosunu oluştur
CREATE TABLE IF NOT EXISTS mining_data (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    group_id INTEGER,
    group_name TEXT,
    message_count INTEGER DEFAULT 0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Veri madenciliği logları tablosunu oluştur 
CREATE TABLE IF NOT EXISTS mining_logs (
    id SERIAL PRIMARY KEY,
    mining_id INTEGER REFERENCES mining_data(id),
    action_type TEXT,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- user_invites tablosunu oluştur
CREATE TABLE IF NOT EXISTS user_invites (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    invite_link TEXT NOT NULL,
    group_id INTEGER,
    status TEXT DEFAULT 'pending',
    invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    joined_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Yeni tablolar için indeksler
CREATE INDEX IF NOT EXISTS idx_messages_group_id ON messages(group_id);
CREATE INDEX IF NOT EXISTS idx_mining_data_user_id ON mining_data(user_id);
CREATE INDEX IF NOT EXISTS idx_mining_data_group_id ON mining_data(group_id);
CREATE INDEX IF NOT EXISTS idx_mining_logs_mining_id ON mining_logs(mining_id);
CREATE INDEX IF NOT EXISTS idx_user_invites_user_id ON user_invites(user_id);
CREATE INDEX IF NOT EXISTS idx_user_invites_group_id ON user_invites(group_id);
'''

try:
    cursor.execute(migration_sql)
    conn.commit()
    print('Migrasyon başarıyla çalıştırıldı')
except Exception as e:
    print(f'Hata: {str(e)}')
    conn.rollback()
finally:
    cursor.close()
    conn.close() 