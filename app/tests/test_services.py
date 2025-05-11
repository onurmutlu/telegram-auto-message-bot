import asyncio
import logging
from datetime import datetime

from app.db.session import get_session
from app.services.base_service import BaseService
from app.services.group_service import GroupService
from app.services.user_service import UserService
from app.services.messaging.announcement_service import AnnouncementService
from app.services.messaging.dm_service import DirectMessageService
from app.services.message_service import MessageService
from app.core.logger import get_logger

logger = get_logger(__name__)

# Test verileri
TEST_CONFIG = {
    "telegram": {
        "api_id": 12345,
        "api_hash": "dummy_hash",
        "phone": "+900000000000"
    },
    "services": {
        "user_service": {
            "enabled": True,
            "interval": 60
        },
        "group_service": {
            "enabled": True,
            "interval": 120
        },
        "message_service": {
            "enabled": True,
            "interval": 30
        },
        "announcement_service": {
            "enabled": True,
            "interval": 300,
            "cooldown": 3600
        },
        "dm_service": {
            "enabled": True,
            "interval": 120,
            "rate_limit": 10
        }
    }
}

async def test_base_service():
    """BaseService testleri."""
    print("\n-- BaseService Testleri --")
    
    # Mock veritabanı ve istemci
    mock_db = {}
    mock_client = None
    
    # BaseService örneği oluştur
    service = BaseService(client=mock_client, db=mock_db, config=TEST_CONFIG)
    
    # Servis adını kontrol et
    service_name = service.get_service_name()
    print(f"Servis adı: {service_name}")
    assert service_name == "base_service", f"Servis adı hatası: {service_name}"
    
    # Interval değerini kontrol et
    interval = service.get_interval()
    print(f"Aralık: {interval}")
    assert interval == 300, f"Aralık değeri hatası: {interval}"
    
    # Config değerini kontrol et
    config_value = service.get_config("services.user_service.interval", 0)
    print(f"Config değeri: {config_value}")
    assert config_value == 60, f"Config değeri hatası: {config_value}"
    
    # Varsayılan değerli config kontrolü
    default_value = service.get_config("nonexistent.key", "default")
    print(f"Varsayılan değer: {default_value}")
    assert default_value == "default", f"Varsayılan değer hatası: {default_value}"
    
    # Başlatma testi
    started = await service.start()
    print(f"Başlatma sonucu: {started}")
    
    # Durdurma testi
    stopped = await service.stop()
    print(f"Durdurma sonucu: {stopped}")
    
    # Güncelleme testi
    await service.update()
    print("Güncelleme tamamlandı")
    
    print("BaseService testleri başarılı!")
    return True

async def test_user_service():
    """UserService testleri."""
    print("\n-- UserService Testleri --")
    
    # Mock veritabanı ve istemci
    mock_db = {}
    mock_client = None
    
    # UserService örneği oluştur
    service = UserService(client=mock_client, db=mock_db, config=TEST_CONFIG)
    
    # Servis adını kontrol et
    service_name = service.get_service_name()
    print(f"Servis adı: {service_name}")
    assert service_name == "user_service", f"Servis adı hatası: {service_name}"
    
    # Interval değerini kontrol et
    interval = service.get_interval()
    print(f"Aralık: {interval}")
    assert interval == 60, f"Aralık değeri hatası: {interval}"
    
    print("UserService testleri başarılı!")
    return True

async def test_group_service():
    """GroupService testleri."""
    print("\n-- GroupService Testleri --")
    
    # Mock veritabanı ve istemci
    mock_db = {}
    mock_client = None
    
    # GroupService örneği oluştur
    service = GroupService(client=mock_client, db=mock_db, config=TEST_CONFIG)
    
    # Servis adını kontrol et
    service_name = service.get_service_name()
    print(f"Servis adı: {service_name}")
    assert service_name == "group_service", f"Servis adı hatası: {service_name}"
    
    # Interval değerini kontrol et
    interval = service.get_interval()
    print(f"Aralık: {interval}")
    assert interval == 120, f"Aralık değeri hatası: {interval}"
    
    print("GroupService testleri başarılı!")
    return True

async def test_message_service():
    """MessageService testleri."""
    print("\n-- MessageService Testleri --")
    
    # Mock veritabanı ve istemci
    mock_db = {}
    mock_client = None
    
    # MessageService örneği oluştur
    service = MessageService(client=mock_client, db=mock_db, config=TEST_CONFIG)
    
    # Servis adını kontrol et
    service_name = service.get_service_name()
    print(f"Servis adı: {service_name}")
    assert service_name == "message_service", f"Servis adı hatası: {service_name}"
    
    # Interval değerini kontrol et
    interval = service.get_interval()
    print(f"Aralık: {interval}")
    assert interval == 30, f"Aralık değeri hatası: {interval}"
    
    print("MessageService testleri başarılı!")
    return True

async def test_announcement_service():
    """AnnouncementService testleri."""
    print("\n-- AnnouncementService Testleri --")
    
    # Mock veritabanı ve istemci
    mock_db = {}
    mock_client = None
    
    # AnnouncementService örneği oluştur
    service = AnnouncementService(client=mock_client, db=mock_db, config=TEST_CONFIG)
    
    # Servis adını kontrol et
    service_name = service.get_service_name()
    print(f"Servis adı: {service_name}")
    assert service_name == "announcement_service", f"Servis adı hatası: {service_name}"
    
    # Interval değerini kontrol et
    interval = service.get_interval()
    print(f"Aralık: {interval}")
    assert interval == 300, f"Aralık değeri hatası: {interval}"
    
    print("AnnouncementService testleri başarılı!")
    return True

async def test_dm_service():
    """DirectMessageService testleri."""
    print("\n-- DirectMessageService Testleri --")
    
    # Mock veritabanı ve istemci
    mock_db = {}
    mock_client = None
    
    # DirectMessageService örneği oluştur
    service = DirectMessageService(client=mock_client, db=mock_db, config=TEST_CONFIG)
    
    # Servis adını kontrol et
    service_name = service.get_service_name()
    print(f"Servis adı: {service_name}")
    assert service_name == "dm_service", f"Servis adı hatası: {service_name}"
    
    # Interval değerini kontrol et
    interval = service.get_interval()
    print(f"Aralık: {interval}")
    assert interval == 120, f"Aralık değeri hatası: {interval}"
    
    print("DirectMessageService testleri başarılı!")
    return True

async def run_all_tests():
    """Tüm testleri çalıştırır."""
    print("\n===== SERVİS TESTLERİ =====")
    
    # Temel servis testi
    await test_base_service()
    
    # Spesifik servis testleri
    await test_user_service()
    await test_group_service()
    await test_message_service()
    await test_announcement_service()
    await test_dm_service()
    
    print("\n===== TÜM TESTLER BAŞARIYLA TAMAMLANDI =====")

if __name__ == "__main__":
    # Log seviyesini ayarla
    logging.basicConfig(level=logging.INFO)
    
    # Event loop al
    loop = asyncio.get_event_loop()
    
    try:
        # Testleri çalıştır
        loop.run_until_complete(run_all_tests())
    except Exception as e:
        logger.error(f"Test sırasında hata: {str(e)}")
        raise
    finally:
        # Event loop'u kapat
        loop.close() 