import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.user_service import UserService, UserStatus


@pytest.fixture
def mock_db():
    """Veritabanı bağlantısı mock nesnesi oluşturur."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetchone = AsyncMock()
    db.fetchall = AsyncMock()
    return db


@pytest.fixture
def user_service(mock_db):
    """UserService test nesnesi oluşturur."""
    service = UserService(db=mock_db)
    service.initialized = True
    
    return service


@pytest.mark.asyncio
async def test_service_start_stop(user_service, mock_db):
    """UserService başlatma ve durdurma testleri."""
    # Servisi sıfırla
    user_service.initialized = False
    
    # Başlatma testi
    result = await user_service._start()
    assert result is True
    assert user_service.initialized is True
    
    # DB olmadan başlatma testi
    user_service.db = None
    user_service.initialized = False
    result = await user_service._start()
    assert result is False
    
    # Durdurma testi
    user_service.db = mock_db
    user_service.initialized = True
    result = await user_service._stop()
    assert result is True
    assert user_service.initialized is False


@pytest.mark.asyncio
async def test_user_exists(user_service, mock_db):
    """Kullanıcı var mı kontrolü testi."""
    # Kullanıcı var durumu
    mock_db.fetchone.return_value = (1,)
    exists = await user_service.user_exists(12345)
    assert exists is True
    mock_db.fetchone.assert_called_with("SELECT COUNT(*) FROM users WHERE user_id = %s", (12345,))
    
    # Kullanıcı yok durumu
    mock_db.fetchone.return_value = (0,)
    exists = await user_service.user_exists(67890)
    assert exists is False
    
    # Hata durumu
    mock_db.fetchone.side_effect = Exception("Test hatası")
    exists = await user_service.user_exists(12345)
    assert exists is False
    
    # Temizleme
    mock_db.fetchone.side_effect = None


@pytest.mark.asyncio
async def test_check_user_status(user_service, mock_db):
    """Kullanıcı durumu kontrolü testi."""
    # Aktif kullanıcı
    mock_db.fetchone.return_value = (UserStatus.ACTIVE.value, True)
    status = await user_service.check_user_status(12345)
    assert status == UserStatus.ACTIVE
    
    # Engellenmiş kullanıcı
    mock_db.fetchone.return_value = (UserStatus.BLOCKED.value, True)
    status = await user_service.check_user_status(12345)
    assert status == UserStatus.BLOCKED
    
    # Pasif kullanıcı
    mock_db.fetchone.return_value = (UserStatus.ACTIVE.value, False)
    status = await user_service.check_user_status(12345)
    assert status == UserStatus.INACTIVE
    
    # Kullanıcı bulunamadı
    mock_db.fetchone.return_value = None
    status = await user_service.check_user_status(12345)
    assert status == UserStatus.NOT_FOUND
    
    # Hata durumu
    mock_db.fetchone.side_effect = Exception("Test hatası")
    status = await user_service.check_user_status(12345)
    assert status == UserStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_add_user(user_service, mock_db):
    """Kullanıcı ekleme testi."""
    # User var mı kontrolünü yapay olarak False yap
    user_service.user_exists = AsyncMock(return_value=False)
    
    # Kullanıcı ekle
    await user_service.add_user(12345, "test_user", "+905551234567")
    
    # DB'ye ekleme yapıldı mı kontrol et
    mock_db.execute.assert_called_once()
    # Çağrı parametrelerini kontrol et (SQL sorgusu ve parametreler)
    args, kwargs = mock_db.execute.call_args
    sql_query, params = args
    assert "INSERT INTO users" in sql_query
    assert params[0] == 12345  # user_id
    assert params[1] == "test_user"  # username
    assert params[2] == "+905551234567"  # phone
    assert params[3] == UserStatus.ACTIVE.value  # status
    assert params[4] is True  # is_active
    
    # Kullanıcı zaten var durumu
    mock_db.execute.reset_mock()
    user_service.user_exists = AsyncMock(return_value=True)
    await user_service.add_user(12345, "test_user", "+905551234567")
    
    # DB'ye ekleme yapılmadı kontrol et
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_activate_user(user_service, mock_db):
    """Kullanıcı aktifleştirme testi."""
    # Kullanıcıyı aktifleştir
    await user_service.activate_user(12345)
    
    # DB'de güncelleme yapıldı mı kontrol et
    mock_db.execute.assert_called_once()
    # Çağrı parametrelerini kontrol et
    args, kwargs = mock_db.execute.call_args
    sql_query, params = args
    assert "UPDATE users" in sql_query
    assert params[0] == UserStatus.ACTIVE.value
    assert params[1] == 12345


@pytest.mark.asyncio
async def test_process_user_new(user_service):
    """Yeni kullanıcı işleme testi."""
    # Mock fonksiyonları ayarla
    user_service.check_user_status = AsyncMock(return_value=UserStatus.NOT_FOUND)
    user_service.add_user = AsyncMock()
    
    # Yeni kullanıcı işle
    await user_service.process_user(12345, "test_user", "+905551234567")
    
    # Kullanıcı durumu kontrol edildi mi?
    user_service.check_user_status.assert_called_once_with(12345)
    
    # Kullanıcı eklendi mi?
    assert user_service.add_user.call_count == 2  # İlk kontrol ve sonra ekleme


@pytest.mark.asyncio
async def test_process_user_inactive(user_service):
    """Pasif kullanıcı işleme testi."""
    # Mock fonksiyonları ayarla
    user_service.check_user_status = AsyncMock(return_value=UserStatus.INACTIVE)
    user_service.add_user = AsyncMock()
    user_service.activate_user = AsyncMock()
    
    # Pasif kullanıcı işle
    await user_service.process_user(12345, "test_user", "+905551234567")
    
    # Kullanıcı durumu kontrol edildi mi?
    user_service.check_user_status.assert_called_once_with(12345)
    
    # Kullanıcı aktifleştirildi mi?
    user_service.activate_user.assert_called_once_with(12345)


@pytest.mark.asyncio
async def test_process_user_blocked(user_service):
    """Engellenmiş kullanıcı işleme testi."""
    # Mock fonksiyonları ayarla
    user_service.check_user_status = AsyncMock(return_value=UserStatus.BLOCKED)
    user_service.add_user = AsyncMock()
    user_service.activate_user = AsyncMock()
    
    # Engellenmiş kullanıcı işle
    await user_service.process_user(12345, "test_user", "+905551234567")
    
    # Kullanıcı durumu kontrol edildi mi?
    user_service.check_user_status.assert_called_once_with(12345)
    
    # Kullanıcı aktifleştirilmedi ve eklenmedi kontrol et
    user_service.activate_user.assert_not_called()
    assert user_service.add_user.call_count == 1  # Sadece ilk kontrol 