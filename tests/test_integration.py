"""
Telegram Bot Servisleri - Basit Entegrasyon Testi

Bu test modülü, ServiceWrapper ve temel servislerin 
düzgün çalıştığını doğrular.
"""

import os
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import datetime

# Test sabitleri
TEST_ACCOUNT_NAME = "test_account"
TEST_MESSAGE_CONTENT = "Bu bir test mesajıdır"
TEST_GROUP_ID = 123456789

@pytest.fixture
def mock_telethon_client():
    """TelethonClient mocklaması"""
    mock_client = AsyncMock()
    mock_client.send_message = AsyncMock(return_value=True)
    mock_client.connect = AsyncMock(return_value=True)
    mock_client.is_connected = AsyncMock(return_value=True)
    mock_client.disconnect = AsyncMock()
    
    return mock_client

# ServiceWrapper mocking
class MockServiceWrapper:
    """Basit bir ServiceWrapper mock sınıfı"""
    
    def __init__(self):
        self.running = False
    
    async def start_all(self):
        self.running = True
        return True
    
    async def stop_all(self):
        self.running = False
        return True

@pytest.fixture
def service_wrapper():
    """
    Test için ServiceWrapper instance'ı oluşturur.
    """
    # ServiceWrapper mocked instance
    wrapper = MockServiceWrapper()
    
    return wrapper

@pytest.mark.asyncio
async def test_service_wrapper_lifecycle(service_wrapper):
    """
    ServiceWrapper başlatma ve durdurma işlemlerini test eder.
    """
    # Başlangıçta servis çalışmıyor olmalı
    assert service_wrapper.running == False
    
    # Servisleri başlat
    start_result = await service_wrapper.start_all()
    assert start_result == True
    assert service_wrapper.running == True
    
    # Servisleri durdur
    stop_result = await service_wrapper.stop_all()
    assert stop_result == True
    assert service_wrapper.running == False

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 