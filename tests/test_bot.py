"""
# ============================================================================ #
# Dosya: test_bot.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/test_bot.py
# İşlev: Telegram Bot Ana Sınıf Birim Testleri
# Amaç: TelegramBot sınıfının ve temel işlevlerinin birim testlerini içerir.
#       Bu testler, botun başlatılması, Telegram'a bağlanması, güvenli kapatılması,
#       çalışma süresinin hesaplanması ve olay işleyicilerinin doğru çalışmasını kapsar.
#
# Build: 2025-04-01-03:50:00
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu test modülü, Telegram Bot'un çekirdek işlevlerini test eder:
# - TelegramBot sınıfının başlatılması ve yapılandırılması
# - Bot'un Telegram'a bağlanma ve yetkilendirme süreci
# - Güvenli bot kapatma mekanizması
# - Çalışma süresi hesaplama ve raporlama
# - Sinyal işleme ve exception yönetimi
#
# Test edilen bileşenler:
# - bot.core.TelegramBot - Ana bot sınıfı
# - TelegramClient ile entegrasyon
# - Bot yapılandırma ve veritabanı arayüzü
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import sys
import pytest
import asyncio
import tempfile
import logging
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock, call

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Proje modüllerini import et
from main import TelegramBot
from database.user_db import UserDatabase
from config.settings import Config

# Tüm test fonksiyonları için asyncio mark ekle
pytestmark = pytest.mark.asyncio

logging.basicConfig(level=logging.DEBUG)

async def test_bot_initialization(mock_client, mock_db):
    logging.debug("Starting test_bot_initialization")
    """
    TelegramBot sınıfının doğru başlatılmasını test eder.
    
    Bu test aşağıdakileri doğrular:
    - Bot nesnesi doğru parametrelerle oluşturulabilir
    - Özellikler ve değişkenler doğru atanmıştır
    - Şablon koleksiyonları doğru tipte başlatılmıştır
    
    Args:
        mock_client: TelegramClient'ın mock versiyonu
        mock_db: Veritabanının mock versiyonu
    """
    # Bot nesnesi oluştur
    with patch('bot.core.TelegramClient', return_value=mock_client):
        with patch('bot.core.Config') as mock_config:
            # Config için session_path instance'ı ayarla
            config_instance = mock_config.return_value
            config_instance.SESSION_PATH = "test_session"
            
            # Test veri yapıları
            test_admin_groups = ["test_group1", "test_group2"]
            test_target_groups = ["test_group3", "test_group4"]
            test_group_links = ["link1", "link2"]
            
            bot = TelegramBot(
                api_id="123",
                api_hash="test_hash",
                phone="123456789",
                admin_groups=test_admin_groups,
                target_groups=test_target_groups,
                group_links=test_group_links,
                user_db=mock_db,
                config=config_instance
            )
            
            # Bot temel değişkenleri kontrolü
            assert bot.api_id == "123"
            assert bot.api_hash == "test_hash"
            assert bot.phone == "123456789"
            assert bot.is_running == False
            assert bot.admin_groups == test_admin_groups
            assert bot.target_groups == test_target_groups
            assert bot.group_links == test_group_links
            
            # Şablon koleksiyonlarının başlatılması
            assert isinstance(bot.messages, list)
            assert isinstance(bot.invite_templates, dict)
            assert isinstance(bot.response_templates, dict)
            
            # Veritabanı referansı kontrolü
            assert bot.db == mock_db
    logging.debug("Completed test_bot_initialization")

# test_bot_start metodu düzeltme

async def test_bot_start(mock_client, mock_db):
    """
    Bot başlatma işlevinin doğru çalışmasını test eder.
    """
    logging.debug("Starting test_bot_start")
    # Mock connect ve is_user_authorized döndürsün
    mock_client.connect = AsyncMock()
    mock_client.is_user_authorized = AsyncMock(return_value=True)
    
    # Asenkron işlemlerin doğru tamamlanması için
    mock_client.add_event_handler = MagicMock()  # Event handler'ı mockla
    mock_client.iter_dialogs = AsyncMock(return_value=[])  # iter_dialogs'u boş liste döndürecek şekilde mockla
    
    with patch('bot.core.TelegramClient', return_value=mock_client):
        with patch('bot.core.Config') as mock_config:
            # Config için session_path instance'ı ayarla
            config_instance = mock_config.return_value
            config_instance.SESSION_PATH = "test_session"
            
            # Test veri yapıları
            test_admin_groups = ["test_group1"]
            test_target_groups = ["test_group2"]
            test_group_links = ["link1", "link2"]
            
            bot = TelegramBot(
                api_id="123",
                api_hash="test_hash",
                phone="123456789",
                admin_groups=test_admin_groups,
                target_groups=test_target_groups,
                group_links=test_group_links,
                user_db=mock_db,
                config=config_instance
            )
            
            # Sonsuz döngüyü önlemek için interruptible_sleep metodunu mockla
            bot.interruptible_sleep = AsyncMock()
            
            # start metodunun içindeki tüm uzun süreli asenkron işlemleri mockla
            with patch.object(bot, '_register_event_handlers'), \
                 patch('bot.core.threading.Thread'):
                
                # Bot'u başlat
                start_time = datetime.now()
                logging.debug("Calling bot.start()")
                await bot.start(interactive=False)  # Servisleri başlatma, timeout'u önlemek için
                logging.debug("bot.start() returned")
                
                # Bağlantı kuruldu mu?
                mock_client.connect.assert_called_once()
                logging.debug("mock_client.connect.assert_called_once() passed")
                
                # Yetkilendirme kontrol edildi mi?
                mock_client.is_user_authorized.assert_called_once()
                logging.debug("mock_client.is_user_authorized.assert_called_once() passed")
                
                # Bot çalışıyor mu?
                assert bot.is_running == True
                logging.debug("assert bot.is_running == True passed")
                
                # Bot'un başlatma zamanı kaydedilmiş mi?
                assert bot._start_time > 0
                assert abs(bot._start_time - start_time.timestamp()) < 5  # 5 saniye tolerans
                logging.debug("assert bot._start_time checks passed")
    logging.debug("Completed test_bot_start")

async def test_bot_shutdown(mock_client, mock_db):
    """
    Bot'un güvenli kapatma işlevinin doğru çalışmasını test eder.
    
    Bu test aşağıdakileri doğrular:
    - _safe_shutdown() metodu client bağlantısını düzgün şekilde kapatır
    - Bot'un durumu doğru şekilde güncellenir
    - Veritabanı bağlantıları düzgün şekilde kapatılır
    
    Args:
        mock_client: TelegramClient'ın mock versiyonu
        mock_db: Veritabanının mock versiyonu
    """
    # Mock disconnect 
    mock_client.disconnect = AsyncMock()
    mock_db.close = MagicMock()
    
    with patch('bot.core.TelegramClient', return_value=mock_client):
        with patch('bot.core.Config') as mock_config:
            # Config için session_path instance'ı ayarla
            config_instance = mock_config.return_value
            config_instance.SESSION_PATH = "test_session"
            
            bot = TelegramBot(
                api_id="123",
                api_hash="test_hash",
                phone="123456789",
                admin_groups=["test_group1"],
                target_groups=["test_group2"],
                group_links=["link1", "link2"],
                user_db=mock_db,
                config=config_instance
            )
            bot.client = mock_client
            
            # Bot'u çalışır duruma getir
            bot.is_running = True
            
            # Bot'u kapat
            await bot._safe_shutdown()
            
            # Bot durdu mu?
            assert bot.is_running == False
            
            # Client disconnect çağrıldı mı?
            mock_client.disconnect.assert_called_once()
            
            # Veritabanı bağlantısı kapandı mı?
            mock_db.close.assert_called_once()

async def test_bot_uptime(mock_client, mock_db):
    """
    Bot çalışma süresi hesaplama işlevlerini test eder.
    
    Bu test aşağıdakileri doğrular:
    - _calculate_uptime() metodu doğru sayısal değer döndürür
    - _format_uptime() metodu uygun formatlanmış string döndürür
    - Zaman hesaplamaları doğru yapılır
    
    Args:
        mock_client: TelegramClient'ın mock versiyonu
        mock_db: Veritabanının mock versiyonu
    """
    with patch('bot.core.TelegramClient', return_value=mock_client):
        with patch('bot.core.Config') as mock_config:
            # Config için session_path instance'ı ayarla
            config_instance = mock_config.return_value
            config_instance.SESSION_PATH = "test_session"
            
            bot = TelegramBot(
                api_id="123",
                api_hash="test_hash",
                phone="123456789",
                admin_groups=["test_group1"],
                target_groups=["test_group2"],
                group_links=["link1", "link2"],
                user_db=mock_db,
                config=config_instance
            )
            
            # Bot başlangıç zamanını elle ayarla (1 saat önce)
            bot._start_time = datetime.now().timestamp() - 3600
            
            # Çalışma süresi string olarak alınabilir mi?
            uptime_str = bot._format_uptime()
            assert isinstance(uptime_str, str)
            assert "1s" in uptime_str  # 1 saat
            assert "0d" in uptime_str  # 0 dakika (tam 1 saat)
            
            # Çalışma süresi sayısal olarak alınabilir mi?
            uptime = bot._calculate_uptime()
            assert isinstance(uptime, float)
            assert abs(uptime - 3600) < 5  # 3600 saniye (1 saat) civarında olmalı, 5 saniyelik tolerans

# test_bot_unauthorized_login metodunu düzelt
async def test_bot_unauthorized_login(mock_client, mock_db):
    """
    Yetkilendirilmemiş bot oturumu durumunu test eder.
    """
    # Mockları doğru şekilde yapılandır
    mock_client.connect = AsyncMock()
    mock_client.is_user_authorized = AsyncMock(return_value=False)
    mock_client.send_code_request = AsyncMock()
    
    # Doğrudan client.connect() testini yapın - Telethon mocklaması gerekmez
    bot = None
    
    with patch('bot.core.TelegramClient') as mock_telethon:
        mock_telethon.return_value = mock_client
        
        with patch('bot.core.Config') as mock_config:
            config_instance = mock_config.return_value
            config_instance.SESSION_PATH = "test_session"
            
            bot = TelegramBot(
                api_id="123",
                api_hash="test_hash",
                phone="123456789",
                admin_groups=["test_group1"],
                target_groups=["test_group2"],
                group_links=["link1", "link2"],
                user_db=mock_db,
                config=config_instance
            )
    
    # Şimdi client doğru şekilde mocklanmış olmalı
    try:
        await bot.start(interactive=False)
    except Exception:
        # Yetkilendirme hatası bekleniyor
        pass
    
    # Bot'un metodlarını test et
    mock_client.connect.assert_called_once()
    mock_client.is_user_authorized.assert_called_once()
    assert bot.is_running == False

# test_bot_event_handlers metodunu şu şekilde değiştirin:
async def test_bot_event_handlers(mock_client, mock_db):
    """
    Bot'un olay işleyicilerini doğru kaydetmesini test eder.
    """
    # Capture add_event_handler çağrıları
    add_handler_calls = []
    
    # add_event_handler metodunu override et ve çağrı bilgilerini kaydet
    def mock_add_handler(callback, event):
        # Çağrıyı yakala
        add_handler_calls.append((callback, event))
        return None  # Bu metod bir değer döndürmez
    
    # Mock client'a metodu ekle
    mock_client.add_event_handler = mock_add_handler
    
    with patch('bot.core.TelegramClient', return_value=mock_client), \
         patch('bot.core.events.NewMessage') as mock_new_message:
        
        # NewMessage'ı mockla ve pattern'ı sakla 
        def fake_new_message(pattern=None, **kwargs):
            handler = MagicMock()
            handler.pattern = pattern  # Doğrudan pattern'ı saklayalım
            return handler
            
        mock_new_message.side_effect = fake_new_message
        
        # Bot'u oluştur
        with patch('bot.core.Config') as mock_config:
            config_instance = mock_config.return_value
            config_instance.SESSION_PATH = "test_session"
            
            bot = TelegramBot(
                api_id="123",
                api_hash="test_hash",
                phone="123456789",
                admin_groups=["test_group1"],
                target_groups=["test_group2"],
                group_links=["link1", "link2"],
                user_db=mock_db,
                config=config_instance
            )
            
            # Gerekli metodları ekle
            bot.start_command = AsyncMock()
            bot.help_command = AsyncMock()
            bot.status_command = AsyncMock()
            bot.on_private_message = AsyncMock()
            bot.on_group_message = AsyncMock()
            bot._is_private_chat = lambda event: event.is_private
            bot._is_group_chat = lambda event: not event.is_private
            
            # Client'ı ayarla
            bot.client = mock_client
            
            # Olay işleyicilerini kaydet
            bot._register_event_handlers()
            
            # Pattern'ları kontrol et - çağrılan event handler'ları incele
            patterns = []
            for _, event in add_handler_calls:
                if hasattr(event, 'pattern'):
                    patterns.append(event.pattern)
            
            # En az 3 işleyici kaydedilmiş olmalı
            assert len(add_handler_calls) >= 3
            
            # Start, help ve status için pattern'lar var mı?
            pattern_strings = [str(p) for p in patterns if p is not None]
            assert any('/start' in p for p in pattern_strings), f"'/start' pattern'ı bulunamadı. Pattern'lar: {pattern_strings}"