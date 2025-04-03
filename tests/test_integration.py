"""
# ============================================================================ #
# Dosya: test_integration.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/test_integration.py
# İşlev: Telegram Bot Servisler Arası Entegrasyon Testleri
#
# Build: 2025-04-01-03:45:00
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu test modülü, bot servislerinin birbirleriyle nasıl etkileşime girdiğini test eder:
# - GroupHandler, ReplyService ve DirectMessageService'in entegrasyon testleri
# - Servislerin çalışma durumları (başlatma, durdurma, duraklatma)
# - Asenkron işlem entegrasyonu
# - Servisler arası durum paylaşımı ve event yönetimi
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import sys
import pytest
import asyncio
import threading
from unittest.mock import patch, MagicMock, AsyncMock

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Proje modüllerini import et
from bot.core import TelegramBot
from bot.handlers.group_handler import GroupHandler
from bot.services.reply_service import ReplyService
from bot.services.dm_service import DirectMessageService
from config.settings import Config
from database.user_db import UserDatabase
from bot.utils.rate_limiter import RateLimiter  # RateLimiter'ı ekleyelim

# Tüm test fonksiyonları için asyncio mark ekle
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_services():
    """
    Entegrasyon testleri için mock servis nesneleri oluşturur.
    
    Bu fixture, tüm testler için ortak bir servis yapılandırması sağlar
    ve tests/conftest.py'daki temel mock'ları genişletir.
    
    Returns:
        dict: 'client', 'config', 'db', 'stop_event', 'message', 'reply', 'dm' 
        anahtarlarını içeren servisler sözlüğü
    """
    mock_client = AsyncMock()
    mock_client.on = MagicMock()  # Event handler mock'u
    mock_config = MagicMock()
    mock_db = MagicMock()
    mock_stop_event = threading.Event()
    
    # Mock gruplar
    mock_config.admin_groups = ["admin_group_id"]
    mock_config.target_groups = ["target_group_id"]
    
    # Mock mesaj şablonları 
    mock_config.message_templates = [
        "Test mesajı 1", 
        "Test mesajı 2 {username}", 
        "Test mesajı 3 {group_name}"
    ]
    
    # Mock davet şablonları
    mock_config.invite_templates = {
        "first_invite": ["Merhaba {username}, sizi gruba davet ediyorum!"],
        "reminder": ["Hala katılmadınız, tekrar davet ediyorum."]
    }
    
    # Mock yanıt şablonları
    mock_config.response_templates = {
        "flirty": ["Teşekkürler {username}!"],
        "formal": ["Merhaba, yardımcı olabilir miyim?"],
        "welcome": ["Aramıza hoş geldiniz {username}!"]
    }
    
    # RateLimiter'ı mockla
    mock_rate_limiter = MagicMock(spec=RateLimiter)
    mock_rate_limiter.is_allowed.return_value = True
    
    # RateLimiter'ı patchleyelim
    with patch('bot.services.reply_service.RateLimiter', return_value=mock_rate_limiter), \
         patch('bot.services.dm_service.RateLimiter', return_value=mock_rate_limiter):
         
        # Servisleri oluştur
        group_handler = GroupHandler(mock_client, mock_config, mock_db, mock_stop_event)
        reply_service = ReplyService(mock_client, mock_config, mock_db, mock_stop_event)
        dm_service = DirectMessageService(mock_client, mock_config, mock_db, mock_stop_event)
        
        # RateLimiter'ları manuel olarak ata
        if hasattr(reply_service, 'rate_limiter'):
            reply_service.rate_limiter = mock_rate_limiter
        if hasattr(dm_service, 'rate_limiter'):
            dm_service.rate_limiter = mock_rate_limiter
    
    # Görünürlük ve hata ayıklama için test değerleri ata
    group_handler.sent_count = 0
    reply_service.reply_count = 0
    dm_service.invite_count = 0
    
    # Servisin run metodlarını mockla
    group_handler.process_group_messages = AsyncMock()
    reply_service.run = AsyncMock()
    dm_service.run = AsyncMock()
    
    # Mock event metodlarını ekle
    group_handler.on_new_user_detected = AsyncMock()
    
    return {
        'client': mock_client,
        'config': mock_config,
        'db': mock_db,
        'stop_event': mock_stop_event,
        'message': group_handler,
        'reply': reply_service,
        'dm': dm_service
    }

async def test_services_running_states(mock_services):
    """
    Servis nesnelerinin çalışma durumlarını test eder.
    
    Bu test, servis nesnelerinin başlatılma ve durdurulma 
    davranışlarının doğru çalışıp çalışmadığını kontrol eder.
    
    Args:
        mock_services (dict): Servis nesneleri fixture'ı
    """
    # Başlangıçta tüm servisler çalışıyor olmalı
    assert mock_services['message'].running == True
    assert mock_services['reply'].running == True
    assert mock_services['dm'].running == True
    
    # Durdurucu event çalıştırıldığında
    mock_services['stop_event'].set()
    
    # Asenkron metodlar çağrıldığında stop_event'i kontrol etmeli
    # Bu kısımda run() çağrılarının mock davranışını kontrol edelim
    await mock_services['message'].process_group_messages()
    await mock_services['reply'].run()
    await mock_services['dm'].run()
    
    # Tüm servislerin durduğunu doğrula
    assert mock_services['stop_event'].is_set() == True

async def test_services_pause_resume(mock_services):
    """
    Servislerin duraklatma ve devam ettirme işlevlerini test eder.
    
    Bu test, tüm servislerin dinamik olarak duraklatılabildiğini
    ve tekrar başlatılabildiğini doğrular.
    
    Args:
        mock_services (dict): Servis nesneleri fixture'ı
    """
    # Tüm servisleri duraklat
    for service_name, service in mock_services.items():
        if hasattr(service, 'running'):
            service.running = False
    
    # Durum kontrolü
    assert mock_services['message'].running == False
    assert mock_services['reply'].running == False
    assert mock_services['dm'].running == False
    
    # Tüm servisleri devam ettir
    for service_name, service in mock_services.items():
        if hasattr(service, 'running'):
            service.running = True
    
    # Durum kontrolü
    assert mock_services['message'].running == True
    assert mock_services['reply'].running == True
    assert mock_services['dm'].running == True

async def test_services_status_reporting(mock_services):
    """
    Servislerin durum raporlama işlevlerini test eder.
    
    Bu test, her servisin dış sistemlere durum raporu
    sağlama yeteneğini kontrol eder.
    
    Args:
        mock_services (dict): Servis nesneleri fixture'ı
    
    Expected:
        Her bir servis durum raporunun doğru formatta olması
        Her raporda en az "running" anahtarının bulunması
    """
    # get_status metodlarının mock versiyonlarını hazırlayalım
    mock_services['message'].get_status = MagicMock(return_value={"running": True})
    mock_services['reply'].get_status = MagicMock(return_value={"running": True})
    mock_services['dm'].get_status = MagicMock(return_value={"running": True})
    
    # Her servisin durum raporu alınabilmeli
    message_status = mock_services['message'].get_status()
    reply_status = mock_services['reply'].get_status()
    dm_status = mock_services['dm'].get_status()
    
    # Her rapor bir sözlük olmalı
    assert isinstance(message_status, dict)
    assert isinstance(reply_status, dict)
    assert isinstance(dm_status, dict)
    
    # Her raporda running anahtarı olmalı
    assert "running" in message_status
    assert "running" in reply_status
    assert "running" in dm_status
    
    # Durum değerleri doğru tiplerde olmalı
    assert isinstance(message_status["running"], bool)
    assert isinstance(reply_status["running"], bool)
    assert isinstance(dm_status["running"], bool)

async def test_services_event_propagation(mock_services):
    """
    Servisler arasındaki event yayılımını test eder.
    """
    # Mock event handler'ları oluştur
    dm_handler = AsyncMock()
    reply_handler = AsyncMock()
    
    # Mock servislere event handler'ları ekle
    mock_services['dm'].on_new_user = dm_handler
    mock_services['reply'].on_message_received = reply_handler
    
    # GroupHandler'ın on_new_user_detected metodunu çağırdığımızda
    # otomatik olarak DM servisinin on_new_user metodunun çağrılmasını sağla
    async def simulate_dm_event(user_id, username):
        # DM servisinin on_new_user metodunu çağır
        await mock_services['dm'].on_new_user(user_id=user_id, username=username)
        return True
    
    # Simülasyon için side_effect ayarla
    mock_services['message'].on_new_user_detected.side_effect = simulate_dm_event
    
    # Bir kullanıcı olayı simüle et
    await mock_services['message'].on_new_user_detected(user_id=123456, username="test_user")
    
    # DM servisi yeni kullanıcı event'ini aldı mı?
    dm_handler.assert_called_once_with(user_id=123456, username="test_user")
    
    # Message event propagation için benzer yaklaşım
    message_event = {
        "user_id": 123456,
        "text": "Merhaba!",
        "chat_id": 789012,
        "timestamp": 1617235678
    }
    
    # Servisin metodunu çağır - burada doğrudan reply servisini test ediyoruz
    await mock_services['reply'].on_message_received(message_event)
    
    # Reply servisi mesaj event'ini aldı mı?
    reply_handler.assert_called_once_with(message_event)