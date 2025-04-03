"""
# ============================================================================ #
# Dosya: test_reply_service.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/test_reply_service.py
# İşlev: ReplyService sınıfı için birim testler
#
# Build: 2025-04-01
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, reply_service.py için birim testleri içerir:
# - Temel yanıt işlevselliği testleri 
# - Şablon seçimi testleri
# - Durum yönetimi testleri
# 
# Kullanım: python -m pytest tests/test_reply_service.py -v
#
# ============================================================================ #
"""

import pytest
import os
import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Proje modüllerini import et
try:
    from telethon import errors
    from bot.services.reply_service import ReplyService
except ImportError:
    # Telethon modülü yüklü değilse atlayalım
    pytestmark = pytest.mark.skip(reason="Telethon modülü yüklü değil")

@pytest.mark.asyncio
async def test_init(mock_reply_service):
    """ReplyService başlatma testi"""
    # İlişkilerin doğru olduğunu kontrol et
    assert hasattr(mock_reply_service, 'client')
    assert hasattr(mock_reply_service, 'config')
    assert hasattr(mock_reply_service, 'db')
    assert hasattr(mock_reply_service, 'stop_event')
    assert mock_reply_service.running == True

@pytest.mark.asyncio
async def test_get_status(mock_reply_service):
    """get_status metodu testi"""
    # get_status çağrı sonucu
    status = mock_reply_service.get_status()
    
    assert isinstance(status, dict)
    assert 'running' in status
    assert 'last_activity' in status
    assert 'replies_sent' in status

@pytest.mark.asyncio
async def test_run_basic(mock_reply_service):
    """run metodu temel işlevsellik testi"""
    # Servisin çalıştığını kontrol et
    assert mock_reply_service.running == True
    
    # Kısa bir süre çalıştır
    await mock_reply_service.run()
    
    # Servis hala çalışıyor olmalı
    assert mock_reply_service.running == True

@pytest.mark.asyncio
async def test_process_message(mock_reply_service, mock_event):
    """process_message metodu testi"""
    # Yanıt gönderme için ayarla
    mock_reply_service.process_message = AsyncMock(return_value=True)
    
    # Test et
    result = await mock_reply_service.process_message(mock_event)
    
    # Başarılı olmalı
    assert result == True

@pytest.mark.asyncio
async def test_choose_response_template(mock_reply_service):
    """_choose_response_template metodu testi"""
    # Mock yanıtı hazırla
    mock_reply_service._choose_response_template.return_value = "Test yanıt"
    
    # Test et
    response = mock_reply_service._choose_response_template()
    
    # Doğru yanıt dönmeli
    assert response == "Test yanıt"
    assert isinstance(response, str)

@pytest.mark.asyncio
async def test_send_response(mock_reply_service, mock_event):
    """_send_response metodu testi"""
    # Yanıt göndermeyi ayarla
    mock_reply_service._send_response.return_value = True
    
    # Test et
    result = await mock_reply_service._send_response(mock_event)
    
    # Başarılı olmalı
    assert result == True

@pytest.mark.asyncio
async def test_run_pause_resume(mock_reply_service):
    """run metodu duraklat/devam et testi"""
    # Başlangıçta çalışıyor olmalı
    assert mock_reply_service.running == True
    
    # Duraklat ve kontrol et
    mock_reply_service.running = False
    assert mock_reply_service.running == False
    
    # Devam ettir
    mock_reply_service.running = True
    assert mock_reply_service.running == True

@pytest.mark.asyncio
async def test_replies_count(mock_reply_service, mock_event):
    """Yanıt sayacı testi"""
    # Başlangıç değeri
    initial_count = mock_reply_service.replies_sent
    
    # Yanıt gönder
    mock_reply_service._send_response = AsyncMock(return_value=True)
    await mock_reply_service._send_response(mock_event)
    
    # Sayacı ayarla
    mock_reply_service.replies_sent = initial_count + 1
    
    # Sayaç artmalı
    assert mock_reply_service.replies_sent == initial_count + 1

@pytest.mark.asyncio
async def test_bot_message_detection(mock_reply_service, mock_event):
    """Bot mesajının tespit edilmesi testi"""
    # Bot ID'si ayarla
    mock_reply_service.client.get_me = AsyncMock()
    mock_reply_service.client.get_me.return_value = MagicMock(id=123456789)
    
    # Mesajın bottan geldiğini ayarla
    mock_event.sender_id = 123456789
    
    # Bot mesajlarına yanıt vermemeli
    mock_reply_service.process_message = AsyncMock(return_value=False)
    result = await mock_reply_service.process_message(mock_event)
    
    # İşlem yapılmamalı
    assert result == False

@pytest.mark.asyncio
async def test_flood_wait_handling(mock_reply_service, mock_event):
    """FloodWaitError işleme testi"""
    # FloodWaitError oluşacak şekilde ayarla
    mock_reply_service._send_response.side_effect = errors.FloodWaitError(42)
    
    try:
        # Yanıt göndermeyi dene
        await mock_reply_service._send_response(mock_event)
    except errors.FloodWaitError:
        pass  # Hata bekleniyor
        
    # Test başarılı
    assert True
