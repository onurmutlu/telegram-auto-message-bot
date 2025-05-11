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

# Tabloları listele
cursor.execute("""
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
""")

tables = [row[0] for row in cursor.fetchall()]
print(f"Bulunan tablolar: {tables}")

# Tüm tablolara yetki ver
grant_sql = ""
for table in tables:
    grant_sql += f"""
    GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user};
    """

try:
    cursor.execute(grant_sql)
    conn.commit()
    print('Yetkilendirme başarıyla yapıldı')
except Exception as e:
    print(f'Hata: {str(e)}')
    conn.rollback()
finally:
    cursor.close()
    conn.close() 