import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# SQLite bağlantısı
sqlite_db_path = 'data/users.db'  # Eski SQLite veritabanınız
sqlite_conn = sqlite3.connect(sqlite_db_path)
sqlite_conn.row_factory = sqlite3.Row
sqlite_cursor = sqlite_conn.cursor()

# PostgreSQL bağlantısı
pg_conn = psycopg2.connect(os.getenv("DB_CONNECTION"))
pg_cursor = pg_conn.cursor()

# Grupları aktar
sqlite_cursor.execute("SELECT * FROM groups")
groups = sqlite_cursor.fetchall()

for group in groups:
    # PostgreSQL'e insert et
    pg_cursor.execute("""
        INSERT INTO groups 
        (group_id, name, join_date, last_message, message_count, member_count, 
        error_count, last_error, is_active, permanent_error, is_target, retry_after, 
        created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (group_id) DO NOTHING
    """, (
        group['group_id'], group['name'], group['join_date'], group['last_message'],
        group['message_count'], group['member_count'], group['error_count'],
        group['last_error'], group['is_active'], group['permanent_error'],
        group['is_target'], group['retry_after'], group['created_at'], group['updated_at']
    ))

# Commit
pg_conn.commit()

# Diğer tabloları da benzer şekilde aktarın...

# Bağlantıları kapat
sqlite_conn.close()
pg_conn.close()
