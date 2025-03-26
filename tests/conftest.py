"""
Pytest fixtures ve ortak test yapılandırması
"""
import pytest
import os
import sys
import tempfile
from pathlib import Path
import sqlite3
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Proje modüllerini import et
from database.user_db import UserDatabase
from config.settings import Config

@pytest.fixture
def temp_db():
    """Geçici test veritabanı oluşturur"""
    # Geçici dosya oluştur
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    # Veritabanı bağlantısı
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Kullanıcı tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP,
        invited BOOLEAN DEFAULT 0,
        invite_time TIMESTAMP
    )
    ''')
    
    # Grup hataları tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS group_errors (
        group_id INTEGER PRIMARY KEY,
        group_title TEXT,
        error_reason TEXT,
        error_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        retry_after TIMESTAMP
    )
    ''')
    
    # İstatistikler tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS statistics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        messages_sent INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0,
        new_users INTEGER DEFAULT 0
    )
    ''')
    
    conn.commit()
    conn.close()
    os.close(db_fd)
    
    # Proje modüllerini import et
    from database.user_db import UserDatabase
    
    # Veritabanı nesnesi oluştur
    db = UserDatabase(db_path)
    
    yield db
    
    # Temizlik
    db.close_connection()
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def temp_config():
    """Geçici test yapılandırması oluşturur"""
    temp_dir = tempfile.mkdtemp()
    config_path = Path(temp_dir) / 'config.json'
    
    # Test yapılandırmasını oluştur
    config_data = {
        "session_file": str(Path(temp_dir) / "test_session"),
        "log_file": str(Path(temp_dir) / "test.log"),
        "log_level": "DEBUG",
        "debug_mode": True,
        "environment": "test"
    }
    
    # Yapılandırmayı dosyaya kaydet
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4)
    
    # Config nesnesi oluştur
    config = Config()
    for key, value in config_data.items():
        setattr(config, key, value)
    
    yield config, config_path
    
    # Temizlik
    if os.path.exists(config_path):
        os.remove(config_path)

@pytest.fixture
def mock_client():
    """Mock Telegram client nesnesi oluşturur"""
    client = AsyncMock()
    client.send_message = AsyncMock()
    client.start = AsyncMock()
    client.disconnect = AsyncMock()
    client.is_connected = MagicMock(return_value=True)
    
    # Mock entity döndürme
    async def get_entity(entity):
        mock_entity = MagicMock()
        if isinstance(entity, str) and entity.startswith('@'):
            mock_entity.id = hash(entity)
            mock_entity.username = entity[1:]
            mock_entity.title = f"Group {entity[1:]}"
        else:
            mock_entity.id = entity
            mock_entity.username = f"user_{entity}"
            mock_entity.title = f"Group {entity}"
        return mock_entity
        
    client.get_entity = get_entity
    
    # Mock me döndürme
    async def get_me():
        me = MagicMock()
        me.id = 123456789
        me.username = "test_bot"
        me.first_name = "Test Bot"
        return me
    
    client.get_me = get_me
    
    yield client

@pytest.fixture
def mock_db():
    """Mock veritabanı nesnesi oluşturur"""
    db = MagicMock()
    db.add_user = MagicMock(return_value=True)
    db.is_invited = MagicMock(return_value=False)
    db.mark_as_invited = MagicMock(return_value=True)
    db.get_database_stats = MagicMock(return_value={
        "total_users": 10,
        "invited_users": 5,
        "blocked_users": 1,
        "error_groups": 2
    })
    db.get_error_groups = MagicMock(return_value=[
        [12345, "Test Group", "Test Error", "2025-03-28 12:00:00", "2025-03-28 13:00:00"]
    ])
    db.clear_error_group = MagicMock(return_value=True)
    db.clear_all_error_groups = MagicMock(return_value=1)
    db.close_connection = MagicMock()
    
    yield db

@pytest.fixture
def test_data_directory():
    """Test veri dizini oluşturur"""
    # Geçici dizin oluştur
    temp_dir = tempfile.mkdtemp()
    data_dir = Path(temp_dir) / "data"
    os.makedirs(data_dir, exist_ok=True)
    
    # Test mesajları oluştur
    messages = [
        "Test message 1 #key1 #key2",
        "Test message 2 #tag1 #tag2",
        "Test message 3 with mention @username"
    ]
    
    # Mesajları dosyaya yaz
    messages_file = data_dir / "messages.json"
    with open(messages_file, 'w', encoding='utf-8') as f:
        json.dump(messages, f, indent=4)
    
    yield data_dir
    
    # Temizlik
    import shutil
    shutil.rmtree(temp_dir)