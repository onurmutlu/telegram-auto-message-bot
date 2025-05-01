# Veritabanı şema versiyonunu güncelleyin
DB_SCHEMA_VERSION = '2.1'

from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, ForeignKey, MetaData, Text

metadata = MetaData()

groups = Table(
    'groups',
    metadata,
    Column('group_id', Integer, primary_key=True),
    Column('name', String),
    Column('join_date', DateTime),
    Column('last_message', DateTime),
    Column('message_count', Integer),
    Column('member_count', Integer),
    Column('error_count', Integer),
    Column('last_error', String),
    Column('is_active', Boolean),
    Column('permanent_error', Boolean),
    Column('is_target', Boolean),
    Column('is_admin', Boolean, default=False),
    Column('retry_after', DateTime),
    Column('created_at', DateTime),
    Column('updated_at', DateTime)
)

messages = Table(
    'messages',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.group_id')),
    Column('content', Text),
    Column('sent_at', DateTime),
    Column('status', String),
    Column('error', Text, nullable=True),
    Column('is_active', Boolean, default=True),
    Column('created_at', DateTime),
    Column('updated_at', DateTime)
)

mining_data = Table(
    'mining_data',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer),
    Column('username', String),
    Column('first_name', String),
    Column('last_name', String),
    Column('group_id', Integer),
    Column('group_name', String),
    Column('message_count', Integer, default=0),
    Column('first_seen', DateTime),
    Column('last_seen', DateTime),
    Column('is_active', Boolean, default=True),
    Column('created_at', DateTime),
    Column('updated_at', DateTime)
)

mining_logs = Table(
    'mining_logs',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('mining_id', Integer, ForeignKey('mining_data.id')),
    Column('action_type', String),
    Column('details', Text),
    Column('timestamp', DateTime),
    Column('success', Boolean),
    Column('error', Text, nullable=True),
    Column('created_at', DateTime)
)

debug_bot_users = Table(
    'debug_bot_users',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, unique=True),
    Column('username', String),
    Column('first_name', String),
    Column('last_name', String),
    Column('access_level', String),
    Column('first_seen', DateTime),
    Column('last_seen', DateTime),
    Column('is_developer', Boolean),
    Column('is_superuser', Boolean),
    Column('is_active', Boolean),
    Column('created_at', DateTime),
    Column('updated_at', DateTime)
)

user_group_relation = Table(
    'user_group_relation',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('debug_bot_users.user_id')),
    Column('group_id', Integer, ForeignKey('groups.group_id')),
    Column('joined_at', DateTime),
    Column('last_seen', DateTime),
    Column('is_active', Boolean),
    Column('created_at', DateTime),
    Column('updated_at', DateTime)
)

user_invites = Table(
    'user_invites',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('debug_bot_users.user_id')),
    Column('invite_link', String),
    Column('group_id', Integer, ForeignKey('groups.group_id'), nullable=True),
    Column('status', String),
    Column('invited_at', DateTime),
    Column('joined_at', DateTime, nullable=True),
    Column('is_active', Boolean),
    Column('created_at', DateTime),
    Column('updated_at', DateTime)
)

settings = Table(
    'settings',
    metadata,
    Column('key', String, primary_key=True),
    Column('value', String),
    Column('description', String),
    Column('updated_at', DateTime)
)

# Ekstra tablo tanımları ekleyin
TABLES = [
    # Gruplar tablosu
    """
    CREATE TABLE IF NOT EXISTS groups (
        id SERIAL PRIMARY KEY,
        group_id INTEGER NOT NULL UNIQUE,
        name TEXT,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_message TIMESTAMP,
        message_count INTEGER DEFAULT 0,
        member_count INTEGER DEFAULT 0,
        error_count INTEGER DEFAULT 0,
        last_error TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        permanent_error BOOLEAN DEFAULT FALSE,
        is_target BOOLEAN DEFAULT FALSE,
        is_admin BOOLEAN DEFAULT FALSE,
        retry_after TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # Mesajlar tablosu
    """
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
    )
    """,
    
    # Veri madenciliği tablosu
    """
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
    )
    """,
    
    # Veri madenciliği logları tablosu
    """
    CREATE TABLE IF NOT EXISTS mining_logs (
        id SERIAL PRIMARY KEY,
        mining_id INTEGER REFERENCES mining_data(id),
        action_type TEXT,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        success BOOLEAN,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # Debug bot kullanıcıları için tablo
    """
    CREATE TABLE IF NOT EXISTS debug_bot_users (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL UNIQUE,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        access_level TEXT DEFAULT 'basic',
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_developer BOOLEAN DEFAULT FALSE,
        is_superuser BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # Kullanıcı-grup ilişkileri için tablo
    """
    CREATE TABLE IF NOT EXISTS user_group_relation (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES debug_bot_users(user_id),
        group_id INTEGER NOT NULL REFERENCES groups(group_id),
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # Kullanıcı davetleri için tablo
    """
    CREATE TABLE IF NOT EXISTS user_invites (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES debug_bot_users(user_id),
        invite_link TEXT NOT NULL,
        group_id INTEGER REFERENCES groups(group_id),
        status TEXT DEFAULT 'pending',
        invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        joined_at TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    # v2.0'dan v2.1'e migrasyon
    """
    -- v2.0'dan v2.1'e migrasyon
    
    -- Grup tablosuna is_admin sütunu ekle
    ALTER TABLE groups ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
    
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
    
    -- Yeni tablolar için indeksler
    CREATE INDEX IF NOT EXISTS idx_debug_bot_users_user_id ON debug_bot_users(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_group_relation_user_id ON user_group_relation(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_group_relation_group_id ON user_group_relation(group_id);
    CREATE INDEX IF NOT EXISTS idx_user_invites_user_id ON user_invites(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_invites_group_id ON user_invites(group_id);
    CREATE INDEX IF NOT EXISTS idx_messages_group_id ON messages(group_id);
    CREATE INDEX IF NOT EXISTS idx_mining_data_user_id ON mining_data(user_id);
    CREATE INDEX IF NOT EXISTS idx_mining_data_group_id ON mining_data(group_id);
    CREATE INDEX IF NOT EXISTS idx_mining_logs_mining_id ON mining_logs(mining_id);
    
    -- Varsayılan ayarlar ekle
    INSERT INTO settings (key, value, description) VALUES 
    ('max_premium_users', '100', 'Maksimum premium kullanıcı sayısı'),
    ('license_validity_days', '365', 'Premium lisansların geçerlilik süresi (gün)'),
    ('debug_access_enabled', 'true', 'Debug bot erişiminin etkin olup olmadığı'),
    ('monitor_admin_ids', '', 'Virgülle ayrılmış monitor yönetici ID listesi')
    ON CONFLICT (key) DO NOTHING;
    """
]