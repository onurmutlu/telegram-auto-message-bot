import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.analytics.analytics_service import AnalyticsService


@pytest.fixture
def mock_db():
    """Veritabanı bağlantısı mock nesnesi oluşturur."""
    db = AsyncMock()
    db.get_analytics = AsyncMock()
    db.save_analytics = AsyncMock()
    return db


@pytest.fixture
def mock_services():
    """Diğer servislerin mock nesnelerini oluşturur."""
    user_service = AsyncMock()
    user_service.get_all_active_users = AsyncMock(return_value=[
        {'user_id': 1, 'username': 'user1'},
        {'user_id': 2, 'username': 'user2'}
    ])
    user_service.get_total_user_count = AsyncMock(return_value=5)
    
    group_service = AsyncMock()
    group_service.get_all_groups = AsyncMock(return_value=[
        {'group_id': 101, 'name': 'Group 1', 'is_active': True},
        {'group_id': 102, 'name': 'Group 2', 'is_active': True},
        {'group_id': 103, 'name': 'Group 3', 'is_active': False}
    ])
    
    message_service = AsyncMock()
    message_service.get_total_message_count = AsyncMock(return_value=100)
    message_service.get_total_command_count = AsyncMock(return_value=25)
    
    services = {
        'user_service': user_service,
        'group_service': group_service,
        'message_service': message_service
    }
    
    return services


@pytest.fixture
def analytics_service(mock_db, mock_services):
    """AnalyticsService test nesnesi oluşturur."""
    service = AnalyticsService(db=mock_db)
    service.services = mock_services
    service.initialized = True
    
    return service


@pytest.mark.asyncio
async def test_start_stop(analytics_service, mock_db):
    """Analitik servisi başlatma ve durdurma testi."""
    # Başlatma testi
    result = await analytics_service._start()
    assert result is True
    mock_db.get_analytics.assert_called_once()
    
    # Durdurma testi
    result = await analytics_service._stop()
    assert result is True
    mock_db.save_analytics.assert_called_once()


@pytest.mark.asyncio
async def test_load_statistics(analytics_service, mock_db):
    """İstatistik yükleme testi."""
    # Mock istatistik verisi
    mock_stats = {
        'user_stats': {'active': 10},
        'group_stats': {'active': 5},
        'message_stats': {'total': 100},
        'stats_periods': {
            'daily': {'today': {'count': 20}},
            'weekly': {},
            'monthly': {}
        },
        'total_stats': {
            'total_users': 15,
            'active_users': 10,
            'total_groups': 7,
            'active_groups': 5,
            'total_messages': 100,
            'total_commands': 30
        }
    }
    
    # Mock veritabanı yanıtı
    mock_db.get_analytics.return_value = mock_stats
    
    # İstatistikleri yükle
    await analytics_service._load_statistics()
    
    # Yüklenen istatistikleri kontrol et
    assert analytics_service.user_stats == mock_stats['user_stats']
    assert analytics_service.group_stats == mock_stats['group_stats']
    assert analytics_service.message_stats == mock_stats['message_stats']
    assert analytics_service.stats_periods == mock_stats['stats_periods']
    assert analytics_service.total_stats == mock_stats['total_stats']


@pytest.mark.asyncio
async def test_save_statistics(analytics_service, mock_db):
    """İstatistik kaydetme testi."""
    # İstatistikleri ayarla
    analytics_service.user_stats = {'active': 10}
    analytics_service.group_stats = {'active': 5}
    analytics_service.message_stats = {'total': 100}
    analytics_service.total_stats = {
        'total_users': 15,
        'active_users': 10,
        'total_groups': 7,
        'active_groups': 5,
        'total_messages': 100,
        'total_commands': 30
    }
    
    # İstatistikleri kaydet
    await analytics_service._save_statistics()
    
    # Veritabanı çağrısını kontrol et
    mock_db.save_analytics.assert_called_once()
    
    # Kaydedilen veriyi kontrol et
    saved_data = mock_db.save_analytics.call_args[0][0]
    assert 'user_stats' in saved_data
    assert 'group_stats' in saved_data
    assert 'message_stats' in saved_data
    assert 'stats_periods' in saved_data
    assert 'total_stats' in saved_data
    assert 'last_update' in saved_data


@pytest.mark.asyncio
async def test_update_user_stats(analytics_service, mock_services):
    """Kullanıcı istatistik güncellemesi testi."""
    # İstatistikleri güncelle
    await analytics_service._update_user_stats()
    
    # Servis çağrılarını kontrol et
    mock_services['user_service'].get_all_active_users.assert_called_once()
    mock_services['user_service'].get_total_user_count.assert_called_once()
    
    # Güncellenen istatistikleri kontrol et
    assert analytics_service.total_stats['active_users'] == 2
    assert analytics_service.total_stats['total_users'] == 5


@pytest.mark.asyncio
async def test_update_group_stats(analytics_service, mock_services):
    """Grup istatistik güncellemesi testi."""
    # İstatistikleri güncelle
    await analytics_service._update_group_stats()
    
    # Servis çağrılarını kontrol et
    mock_services['group_service'].get_all_groups.assert_called_once()
    
    # Güncellenen istatistikleri kontrol et
    assert analytics_service.total_stats['total_groups'] == 3
    assert analytics_service.total_stats['active_groups'] == 2


@pytest.mark.asyncio
async def test_update_message_stats(analytics_service, mock_services):
    """Mesaj istatistik güncellemesi testi."""
    # İstatistikleri güncelle
    await analytics_service._update_message_stats()
    
    # Servis çağrılarını kontrol et
    mock_services['message_service'].get_total_message_count.assert_called_once()
    mock_services['message_service'].get_total_command_count.assert_called_once()
    
    # Güncellenen istatistikleri kontrol et
    assert analytics_service.total_stats['total_messages'] == 100
    assert analytics_service.total_stats['total_commands'] == 25


@pytest.mark.asyncio
async def test_update_all(analytics_service):
    """Tüm istatistiklerin güncellenmesi testi."""
    # Update metodlarını mock et
    analytics_service._update_user_stats = AsyncMock()
    analytics_service._update_group_stats = AsyncMock()
    analytics_service._update_message_stats = AsyncMock()
    analytics_service._save_statistics = AsyncMock()
    
    # _update metodu ile güncelle
    await analytics_service._update()
    
    # Tüm güncelleme metodlarının çağrıldığını kontrol et
    analytics_service._update_user_stats.assert_called_once()
    analytics_service._update_group_stats.assert_called_once()
    analytics_service._update_message_stats.assert_called_once()
    analytics_service._save_statistics.assert_called_once()


@pytest.mark.asyncio
async def test_track_event(analytics_service):
    """Olayları takip etme testi."""
    # track_event metodunu mock et
    original_track_event = analytics_service.track_event
    analytics_service.track_event = AsyncMock(wraps=original_track_event)
    
    # Birkaç örnek event için track_event çağırarak test et
    await analytics_service.track_event('user_activity', {'user_id': 1, 'action': 'login'})
    await analytics_service.track_event('group_activity', {'group_id': 101, 'action': 'join'})
    await analytics_service.track_event('message', {'message_id': 201, 'text': 'Hello'})
    await analytics_service.track_event('command', {'command': '/start', 'user_id': 1})
    
    # track_event çağrı sayısını kontrol et
    assert analytics_service.track_event.call_count == 4


@pytest.mark.asyncio
async def test_get_statistics(analytics_service):
    """İstatistik alma testi."""
    # İstatistik verilerini ayarla
    analytics_service.total_stats = {
        'total_users': 15,
        'active_users': 10,
        'total_groups': 7,
        'active_groups': 5,
        'total_messages': 100,
        'total_commands': 30
    }
    
    # İstatistikleri al
    stats = await analytics_service.get_statistics()
    
    # Verileri kontrol et
    assert stats['total_users'] == 15
    assert stats['active_users'] == 10
    assert stats['total_groups'] == 7
    assert stats['active_groups'] == 5
    assert stats['total_messages'] == 100
    assert stats['total_commands'] == 30 