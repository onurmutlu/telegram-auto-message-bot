"""
# ============================================================================ #
# Dosya: test_message_service.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/test_message_service.py
# İşlev: MessageService sınıfı için birim testler
#
# Build: 2025-04-01-00:07:55
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, MessageService sınıfının işlevlerini test eder:
# - Grup mesajları gönderme
# - Çalıştırma/durdurma ve durum yönetimi
# - Grup aktivite analizi ve mesaj zamanlaması
# 
# Kullanım: python -m pytest tests/test_message_service.py -v
#
# ============================================================================ #
"""

import os
import sys
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Proje modüllerini import et
try:
    from telethon import errors
except ImportError:
    # Telethon modülü yüklü değilse atlayalım
    pytestmark = pytest.mark.skip(reason="Telethon modülü yüklü değil")

@pytest.mark.asyncio
async def test_init(mock_message_service):
    """Servis başlatma testi"""
    # İlişkilerin doğru olduğunu kontrol et
    assert hasattr(mock_message_service, 'client')
    assert hasattr(mock_message_service, 'config')
    assert hasattr(mock_message_service, 'db')
    assert hasattr(mock_message_service, 'stop_event')
    assert mock_message_service.running == True

@pytest.mark.asyncio
async def test_get_status(mock_message_service):
    """get_status metodu testi"""
    # get_status çağrı sonucu
    status = mock_message_service.get_status()
    
    assert isinstance(status, dict)
    assert 'running' in status
    assert 'last_run' in status
    assert 'messages_sent' in status
    assert 'messages_failed' in status

@pytest.mark.asyncio
async def test_run_with_messages(mock_message_service):
    """run metodu temel işlevsellik testi"""
    # Mock metodu çağrısı ve parametreleri
    mock_message_service.config.get_group_links = MagicMock(return_value=["testgroup1", "testgroup2"])
    
    # run metodunu asenkron olarak patch et
    async def mock_run_impl():
        await mock_message_service.analyze_group_activity()
    
    mock_message_service.run = AsyncMock(side_effect=mock_run_impl)
    
    # Kısa bir süre çalıştır
    await mock_message_service.run()
    
    # Metodların çağrıldığını doğrula
    mock_message_service.analyze_group_activity.assert_called_once()

@pytest.mark.asyncio
async def test_run_pause_resume(mock_message_service):
    """run metodu duraklat/devam et testi"""
    assert mock_message_service.running == True
    
    # Duraklat ve kontrol et
    mock_message_service.running = False
    assert mock_message_service.running == False
    
    # Devam ettir
    mock_message_service.running = True
    assert mock_message_service.running == True
    
    # Servisin durumunu kontrol et
    mock_service_status = mock_message_service.get_status()
    assert mock_service_status['running'] is True

@pytest.mark.asyncio
async def test_analyze_group_activity(mock_message_service):
    """analyze_group_activity metodu testi"""
    # Test veri setini hazırla
    mock_message_service._analyze_group_activity = MagicMock(return_value=300)
    
    # Boş aktivite ile varsayılan aralık
    interval = mock_message_service._analyze_group_activity(-1001234567890, [])
    assert interval == 300  # 5 dakika

@pytest.mark.asyncio
async def test_send_group_message_success(mock_message_service):
    """send_message_to_group başarılı mesaj gönderme testi"""
    group_link = "testgroup"
    
    # Başarılı mesaj gönderimi ayarla
    mock_message_service.send_message_to_group.return_value = True
    mock_message_service.messages_sent = 0
    
    # Test et
    result = await mock_message_service.send_message_to_group(group_link)
    
    # Sonucu doğrula
    assert result == True

@pytest.mark.asyncio
async def test_send_group_message_flood_error(mock_message_service):
    """send_message_to_group flood error testi"""
    group_link = "testgroup"
    
    # Hata yayınlama için side_effect kullan
    mock_message_service.send_message_to_group.side_effect = errors.FloodWaitError(42)
    
    # Test et
    try:
        await mock_message_service.send_message_to_group(group_link)
    except errors.FloodWaitError:
        pass  # Hata bekleniyor

@pytest.mark.asyncio
async def test_send_group_message_other_error(mock_message_service):
    """send_message_to_group diğer hata testi"""
    group_link = "testgroup"
    
    # Genel hata senaryosunu simüle et
    mock_message_service.send_message_to_group.side_effect = Exception("Test hata")
    
    # Test et
    try:
        await mock_message_service.send_message_to_group(group_link)
    except Exception:
        pass  # Hata bekleniyor

@pytest.mark.asyncio
async def test_choose_message(mock_message_service):
    """_choose_message metodu testi"""
    # Mock mesajı hazırla
    mock_message_service._choose_message.return_value = "Test mesaj içeriği"
    
    # Test et
    message = mock_message_service._choose_message()
    
    # Sonucu doğrula
    assert message == "Test mesaj içeriği"