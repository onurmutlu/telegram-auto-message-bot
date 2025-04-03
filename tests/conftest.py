"""
# ============================================================================ #
# Dosya: conftest.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/conftest.py
# İşlev: Pytest test ortamı yapılandırması ve fixture tanımları.
#
# Build: 2025-04-01
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, test ortamı için gerekli tüm fixture'ları içerir:
# - Mock servisler (GroupService, ReplyService, DirectMessageService)
# - Test yapılandırması (Config) ve veritabanı (UserDatabase)
# - Log yapılandırması ve test raporlama araçları
# - Asenkron test desteği ve pytest hook'ları
#
# ============================================================================ #
"""
import os
import sys
import tempfile
import threading
import logging
from datetime import datetime
from pathlib import Path
import sqlite3
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
# Projenin kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Proje modüllerini import et
from bot.handlers.message_handler import MessageHandler
from bot.handlers.group_handler import GroupHandler
from bot.services.reply_service import ReplyService
from bot.services.dm_service import DirectMessageService
from bot.services.group_service import GroupService
from database.user_db import UserDatabase
from config.settings import Config
from bot.core import TelegramBot

# Log dizini oluşturma
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Her test çalışması için benzersiz log dosyası adı
TEST_LOG_FILE = LOG_DIR / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

def setup_logging():
    """Test loglama yapılandırmasını ayarlar."""
    # Root logger'ı yapılandır
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Mevcut handler'ları temizle
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Format tanımla
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Dosya handler
    file_handler = logging.FileHandler(TEST_LOG_FILE, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    # Konsol handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # pytest logger
    test_logger = logging.getLogger("pytest")
    test_logger.setLevel(logging.INFO)

    return root_logger, test_logger

@pytest.fixture(scope="session", autouse=True)
def configure_test_logging():
    """Test oturumu için loglama yapılandırması."""
    # Loglama yapılandırmasını ayarla
    root_logger, test_logger = setup_logging()

    test_logger.info(f"Test oturumu başlatıldı: {datetime.now()}")
    test_logger.info(f"Test log dosyası: {TEST_LOG_FILE}")

    yield

    test_logger.info(f"Test oturumu tamamlandı: {datetime.now()}")

# pytest_asyncio tarafından sağlanan event_loop fixture'ı kullanılmalı
# Kendi event_loop fixture'ımızı tanımlamıyoruz

@pytest.hookimpl(hookwrapper=True)
def pytest_terminal_summary(terminalreporter):
    """Test özeti için hook."""
    outcome = yield

    logger = logging.getLogger("pytest")
    stats = terminalreporter.stats

    summary = []
    summary.append("=" * 60)
    summary.append("TEST SONUÇLARI ÖZETİ")
    summary.append("=" * 60)
    summary.append(f"Geçen testler: {len(stats.get('passed', []))}")
    summary.append(f"Başarısız testler: {len(stats.get('failed', []))}")
    summary.append(f"Atlanan testler: {len(stats.get('skipped', []))}")
    summary.append(f"Hatalı testler: {len(stats.get('error', []))}")

    try:
        # Süreyi hesapla
        current_time = datetime.now()
        start_time = getattr(terminalreporter, '_sessionstarttime', current_time)
        if isinstance(start_time, float):
            import time
            start_time = datetime.fromtimestamp(start_time)
        duration = current_time - start_time
        summary.append(f"Toplam süre: {duration.total_seconds():.2f} saniye")
    except Exception as e:
        summary.append(f"Süre hesaplanamadı: {e}")

    # Tek bir log çağrısıyla tüm özeti yaz
    logger.info("\n".join(summary))

@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report):
    """Test sonuçlarını logla."""
    logger = logging.getLogger("pytest")

    if report.when == "call":
        if report.passed:
            logger.info(f"[PASS] {report.nodeid}")
        elif report.failed:
            logger.error(f"[FAIL] {report.nodeid}")
        elif report.skipped:
            logger.warning(f"[SKIP] {report.nodeid} - {report.longrepr}")

@pytest.fixture
def temp_db():
    """Geçici test veritabanı oluşturur."""
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
        invite_time TIMESTAMP,
        active_status INTEGER DEFAULT 1
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
        new_users INTEGER DEFAULT 0,
        replies_sent INTEGER DEFAULT 0,
        invites_sent INTEGER DEFAULT 0
    )
    ''')

    # Grup aktivite tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS group_activity (
        group_id INTEGER PRIMARY KEY,
        group_title TEXT,
        last_activity TIMESTAMP,
        message_count INTEGER DEFAULT 0,
        message_frequency REAL DEFAULT 0.0,
        last_message_time TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()
    os.close(db_fd)

    # Veritabanı nesnesi oluştur
    db = UserDatabase(db_path)

    yield db

    # Temizlik
    db.close_connection()
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def temp_config():
    """Geçici test yapılandırması oluşturur."""
    temp_dir = tempfile.mkdtemp()

    # Geçici dizin yapısı oluştur
    data_dir = Path(temp_dir) / 'data'
    runtime_dir = Path(temp_dir) / 'runtime'
    sessions_dir = runtime_dir / 'sessions'
    logs_dir = runtime_dir / 'logs'

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(sessions_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    # Test mesajlarını oluştur
    messages = [
        "Test message 1",
        "Test message 2",
        "Test message 3"
    ]

    # Davet şablonlarını oluştur
    invites = {
        "first_invite": [
            "Test invite 1",
            "Test invite 2"
        ],
        "redirect_messages": [
            "Test redirect 1",
            "Test redirect 2"
        ]
    }

    # Yanıt şablonlarını oluştur
    responses = {
        "flirty": [
            "Test response 1",
            "Test response 2",
            "Test response 3"
        ]
    }

    # JSON dosyalarını oluştur
    messages_file = data_dir / "messages.json"
    invites_file = data_dir / "invites.json"
    responses_file = data_dir / "responses.json"

    with open(messages_file, 'w', encoding='utf-8') as f:
        json.dump(messages, f, indent=4)

    with open(invites_file, 'w', encoding='utf-8') as f:
        json.dump(invites, f, indent=4)

    with open(responses_file, 'w', encoding='utf-8') as f:
        json.dump(responses, f, indent=4)

    # Config nesnesi oluştur
    config = Config()

    # Test yapılandırma değerlerini ayarla
    config.BASE_DIR = Path(temp_dir)
    config.DATA_DIR = data_dir
    config.RUNTIME_DIR = runtime_dir
    config.SESSION_DIR = sessions_dir
    config.LOGS_DIR = logs_dir
    config.LOG_FILE_PATH = logs_dir / "test.log"
    config.SESSION_PATH = sessions_dir / "test_session"
    config.MESSAGE_TEMPLATES_PATH = messages_file
    config.INVITE_TEMPLATES_PATH = invites_file
    config.RESPONSE_TEMPLATES_PATH = responses_file

    # Config için şablonları yükle
    config.message_templates = messages
    config.invite_templates = invites
    config.response_templates = responses

    yield config

    # Temizlik
    try:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    except:
        pass

@pytest.fixture
def mock_client():
    """Test için mock Telegram client nesnesi."""
    client = AsyncMock()
    client.on = MagicMock()
    
    # Mesaj gönderme işlevleri
    client.send_message = AsyncMock()
    client.edit_message = AsyncMock()
    client.delete_messages = AsyncMock()
    
    # Grup işlevleri
    client.get_entity = AsyncMock()
    client.get_participants = AsyncMock(return_value=[])
    
    return client

@pytest.fixture
def mock_db():
    """Mock veritabanı nesnesi oluşturur."""
    db = MagicMock()
    db.add_user = MagicMock(return_value=True)
    db.is_invited = MagicMock(return_value=False)
    db.mark_as_invited = MagicMock(return_value=True)
    db.get_database_stats = MagicMock(return_value={
        "total_users": 10,
        "invited_users": 5,
        "blocked_users": 1,
        "error_groups": 2,
        "active_users": 8
    })
    db.get_error_groups = MagicMock(return_value=[
        [12345, "Test Group", "Test Error", "2025-03-28 12:00:00", "2025-03-28 13:00:00"]
    ])
    db.clear_error_group = MagicMock(return_value=True)
    db.clear_all_error_groups = MagicMock(return_value=1)
    db.get_user_count = MagicMock(return_value=10)
    db.get_active_user_count = MagicMock(return_value=8)
    db.close_connection = MagicMock()

    return db

@pytest.fixture
def stop_event():
    """Test için durdurma eventi oluşturur."""
    event = threading.Event()
    yield event
    # Test sonrası eventi temizle
    event.clear()

@pytest.fixture
def mock_config():
    """Config mock nesnesi."""
    config = MagicMock()

    # Test şablonları ayarla
    config.message_templates = [
        "Test mesaj 1",
        "Test mesaj 2",
        "Test mesaj 3"
    ]

    # Davet şablonları
    config.invite_templates = {
        "first_invite": [
            "Test davet 1", 
            "Test davet 2"
        ],
        "redirect_messages": [
            "Test yönlendirme 1", 
            "Test yönlendirme 2"
        ]
    }

    # Yanıt şablonları
    config.response_templates = {
        "flirty": [
            "Test yanıt 1",
            "Test yanıt 2",
            "Test yanıt 3"
        ]
    }

    # Diğer gerekli config özellikleri
    config.admin_groups = ["https://t.me/admin_group1", "https://t.me/admin_group2"]
    config.target_groups = ["https://t.me/target_group1", "https://t.me/target_group2"]
    config.get_setting = MagicMock(return_value=True)
    
    # Debug modu
    config.debug = False

    return config

@pytest.fixture
def mock_message():
    """Telegram mesaj mock nesnesi."""
    message = MagicMock()
    message.id = 12345
    message.sender_id = 67890
    message.chat_id = -1001234567890
    message.text = "Test mesajı"
    message.reply = AsyncMock()

    # Gönderici bilgisi
    sender = MagicMock()
    sender.id = 67890
    sender.username = "test_user"
    message.sender = sender

    return message

@pytest.fixture
def mock_event():
    """Mock Telegram olay nesnesi oluşturur."""
    event = MagicMock()

    # Genel özellikler
    event.id = 12345
    event.chat_id = -1001234567890
    event.text = "Test message content"
    event.raw_text = "Test message content"
    event.is_group = True

    # Gönderen
    sender = MagicMock()
    sender.id = 987654321
    sender.username = "test_user"
    sender.first_name = "Test User"
    event.sender = sender
    event.sender_id = sender.id

    # Yanıt işlevleri
    event.reply = AsyncMock()
    event.respond = AsyncMock()
    event.edit = AsyncMock()
    event.delete = AsyncMock()

    # Yanıt kontrolü
    event.is_reply = False

    async def get_reply_message():
        replied = MagicMock()
        replied.sender_id = 123456789  # Bot ID
        replied.text = "Original bot message"
        return replied

    event.get_reply_message = get_reply_message

    return event

@pytest.fixture
def test_config():
    """Test ortamı için Config nesnesi oluşturur."""
    # Geçici dosya yolları için temp dizini oluştur
    with tempfile.TemporaryDirectory() as temp_dir:
        # Config nesnesini oluştur
        config = Config()

        # Geçici yolları ayarla
        temp_path = Path(temp_dir)
        config.RUNTIME_DIR = temp_path / 'runtime'
        config.SESSION_DIR = config.RUNTIME_DIR / 'sessions'
        config.DATABASE_DIR = config.RUNTIME_DIR / 'database'
        config.LOGS_DIR = config.RUNTIME_DIR / 'logs'
        config.DATABASE_PATH = config.DATABASE_DIR / 'test_users.db'
        config.SESSION_PATH = config.SESSION_DIR / 'test_session'
        config.LOG_FILE_PATH = config.LOGS_DIR / 'test.log'

        # Gerekli dizinleri oluştur
        os.makedirs(config.SESSION_DIR, exist_ok=True)
        os.makedirs(config.DATABASE_DIR, exist_ok=True)
        os.makedirs(config.LOGS_DIR, exist_ok=True)

        # Test şablonları ayarla
        config.message_templates = [
            "Test mesaj 1",
            "Test mesaj 2",
            "Test mesaj 3"
        ]

        config.invite_templates = {
            "first_invite": [
                "Test invite 1",
                "Test invite 2"
            ],
            "redirect_messages": [
                "Test yönlendirme 1",
                "Test yönlendirme 2"
            ]
        }

        config.response_templates = {
            "flirty": [
                "Test yanıt 1",
                "Test yanıt 2",
                "Test yanıt 3"
            ]
        }

        # Debug modu ayarla
        config.debug_mode = False

        yield config

        # Temizlik işlemleri
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

@pytest.fixture
def test_db(test_config):
    """Test ortamı için veritabanı nesnesi oluşturur."""
    # Veritabanını başlat
    db = UserDatabase(db_path=test_config.DATABASE_PATH)

    # Test verisini ekle
    db.add_user(123456, "test_user1")
    db.add_user(654321, "test_user2")
    db.add_user(789012, "test_user3")

    yield db

    # Temizlik işlemleri
    db.close()
    try:
        os.remove(test_config.DATABASE_PATH)
    except:
        pass

@pytest.fixture
def mock_group_handler(mock_client, mock_config, mock_db, stop_event):
    """GroupHandler için mock sınıf oluştur"""
    handler = MagicMock()
    handler.bot = mock_client
    handler.config = mock_config
    handler.db = mock_db
    handler.stop_event = stop_event
    handler.running = True
    handler.get_status.return_value = {
        'running': True,
        'last_run': datetime.now(),
        'messages_sent': 0,
        'messages_failed': 0,
        'active_groups': 5,
        'current_interval': 900
    }
    return handler

@pytest.fixture
def mock_message_service(mock_client, mock_config, mock_db, stop_event):
    """MessageService için mock sınıf oluştur"""
    service = MagicMock()
    service.client = mock_client
    service.config = mock_config
    service.db = mock_db
    service.stop_event = stop_event
    service.running = True
    service.messages_sent = 0
    service.messages_failed = 0
    service.last_run = datetime.now()
    
    # Asenkron metodlar için AsyncMock kullan
    service.analyze_group_activity = AsyncMock()
    service.send_message_to_group = AsyncMock(return_value=True)
    service.run = AsyncMock()
    
    # Normal metodlar
    service._analyze_group_activity = MagicMock(return_value=900)
    service._choose_message = MagicMock(return_value="Test mesajı")
    service.get_status = MagicMock(return_value={
        'running': True,
        'last_run': datetime.now(),
        'messages_sent': 0,
        'messages_failed': 0,
        'active_groups': 5,
        'current_interval': 900
    })
    
    return service

@pytest.fixture
def mock_reply_service(mock_client, mock_config, mock_db, stop_event):
    """ReplyService mock nesnesi."""
    service = MagicMock(spec=ReplyService)
    service.client = mock_client
    service.config = mock_config
    service.db = mock_db
    service.stop_event = stop_event
    service.running = True
    service.replies_sent = 0
    
    # Asenkron metodlar
    service.process_message = AsyncMock()
    service._send_response = AsyncMock()
    service.run = AsyncMock()
    
    # Normal metodlar
    service._choose_response_template = MagicMock(return_value="Test yanıt")
    service.get_status = MagicMock(return_value={
        'running': True,
        'last_activity': datetime.now(),
        'replies_sent': 0,
    })
    
    return service

@pytest.fixture
def mock_dm_service(mock_client, mock_config, mock_db, stop_event):
    """DirectMessageService mock nesnesi."""
    # RateLimiter'ı mockla
    with patch('bot.utils.rate_limiter.RateLimiter') as mock_rate_limiter_class:
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.is_allowed.return_value = True
        mock_rate_limiter_class.return_value = mock_rate_limiter
        
        # DirectMessageService örneği oluştur
        service = DirectMessageService(mock_client, mock_config, mock_db, stop_event)
        
        # Eksik özellikleri ekle
        service.replied_users = set()
        service.group_links = ["test_group1", "test_group2"]
        service.processed_dms = 0
        service.invites_sent = 0
        service.last_activity = datetime.now()
        
        # Test için process_message metodu ekle (bu metod gerçekte sınıfta yok)
        async def process_message(event):
            """Test için mesaj işleme metodu"""
            if not service.running:
                return False
                
            await service._send_invite(event)
            return True
        
        service.process_message = process_message
        service._send_invite = AsyncMock()
        
        return service

@pytest.fixture
def mock_bot(mock_client, mock_db, mock_config):
    """Mock bot nesnesi oluşturur."""
    bot = TelegramBot(
        api_id="123456",
        api_hash="test_hash",
        phone="1234567890",
        group_links=["https://t.me/test1", "https://t.me/test2"],
        user_db=mock_db,
        config=mock_config,
        admin_groups=["admin_group1", "admin_group2"],
        target_groups=["target_group3", "target_group4"]
    )
    bot.client = mock_client
    bot.messages = ["Test message 1", "Test message 2"]
    bot.invite_templates = {"first_invite": ["Test invite"]}
    bot.response_templates = {"flirty": ["Test response"]}
    bot.is_running = True

    return bot