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

# Önce user_invites tablosunu düşür
try:
    cursor.execute("DROP TABLE IF EXISTS user_invites CASCADE")
    conn.commit()
    print("user_invites tablosu başarıyla silindi")
except Exception as e:
    print(f"user_invites tablosu silinirken hata: {str(e)}")
    conn.rollback()

# Yeni user_invites tablosu oluştur
create_user_invites = """
CREATE TABLE IF NOT EXISTS user_invites (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    username TEXT,
    invite_link TEXT NOT NULL,
    group_id BIGINT,
    status TEXT DEFAULT 'pending',
    invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    joined_at TIMESTAMP,
    last_invite_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- İndeksler
CREATE INDEX IF NOT EXISTS idx_user_invites_user_id ON user_invites(user_id);
CREATE INDEX IF NOT EXISTS idx_user_invites_group_id ON user_invites(group_id);
"""

try:
    cursor.execute(create_user_invites)
    conn.commit()
    print("user_invites tablosu başarıyla oluşturuldu")
except Exception as e:
    print(f"user_invites tablosu oluşturulurken hata: {str(e)}")
    conn.rollback()

# Sequence sahipliğini düzelt
try:
    cursor.execute(f"ALTER SEQUENCE user_invites_id_seq OWNER TO {db_user}")
    conn.commit()
    print("Sequence sahipliği güncellendi")
except Exception as e:
    print(f"Sequence sahipliği güncellenirken hata: {str(e)}")
    conn.rollback()

# Yetkilendirme
try:
    cursor.execute(f"GRANT ALL PRIVILEGES ON TABLE user_invites TO {db_user}")
    cursor.execute(f"GRANT USAGE, SELECT ON SEQUENCE user_invites_id_seq TO {db_user}")
    conn.commit()
    print("user_invites tablosu için yetkiler verildi")
except Exception as e:
    print(f"Yetkilendirme yapılırken hata: {str(e)}")
    conn.rollback()

# Bağlantıyı kapat
cursor.close()
conn.close() 