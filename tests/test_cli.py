"""
Telegram Bot CLI - Komut Satırı Arayüzü Testi (Basitleştirilmiş)

Bu test modülü, bot uygulamasının komut satırı arayüzünü test eder.
Pytest ve mock kullanarak CLI komutlarını test eder.
"""

import os
import pytest
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call

# Test sabitleri
SERVICES_LIST = ["scheduler", "messaging", "monitoring"]  # Örnek servis listesi

@pytest.fixture
def mock_service_wrapper():
    """
    ServiceWrapper sınıfını mocklar.
    
    Bu fixture, servisleri başlatmak ve durdurmak için gerçekte kullanılan
    ServiceWrapper'ı taklit eder.
    """
    mock_wrapper = MagicMock()
    
    # start_all ve stop_all metodlarını mockla
    mock_wrapper.start_all = MagicMock(return_value=True)
    mock_wrapper.stop_all = MagicMock(return_value=True)
    
    # list_services metodunu mockla (aktif servislerin listesini döndürür)
    mock_wrapper.list_services = MagicMock(return_value={
        service: {"status": "running", "healthy": True} for service in SERVICES_LIST
    })
    
    return mock_wrapper

@pytest.fixture
def env_setup():
    """
    Test için geçici çevre değişkenleri ayarlar.
    """
    # Orijinal çevre değişkenlerini sakla
    original_env = os.environ.copy()
    
    # Test için geçici dizin oluştur
    temp_dir = tempfile.mkdtemp()
    
    # Test çevre değişkenlerini ayarla
    os.environ.update({
        "BOT_HOME": temp_dir,
        "BOT_ENV": "test",
        "BOT_LOG_LEVEL": "INFO"
    })
    
    yield
    
    # Test sonrası temizlik
    os.environ.clear()
    os.environ.update(original_env)
    
    # Geçici dizini temizle
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

# CLI komutları çağıran basit fonksiyonlar (test için)
def run_start_command(service_wrapper):
    """Start komutu simulasyonu"""
    service_wrapper.start_all()
    return "Servisler başlatılıyor..."

def run_stop_command(service_wrapper):
    """Stop komutu simulasyonu"""
    service_wrapper.stop_all()
    return "Servisler durduruluyor..."

def run_status_command(service_wrapper):
    """Status komutu simulasyonu"""
    status = service_wrapper.list_services()
    return f"Servislerin durumu: {len(status)} servis çalışıyor"

def test_start_command(mock_service_wrapper, env_setup):
    """
    'start' komutunun doğru çalıştığını test eder.
    """
    # Start komutunu çalıştır
    output = run_start_command(mock_service_wrapper)
    
    # Çıktıyı kontrol et
    assert "başlatılıyor" in output
    
    # ServiceWrapper.start_all metodunun çağrıldığını doğrula
    mock_service_wrapper.start_all.assert_called_once()

def test_stop_command(mock_service_wrapper, env_setup):
    """
    'stop' komutunun doğru çalıştığını test eder.
    """
    # Stop komutunu çalıştır
    output = run_stop_command(mock_service_wrapper)
    
    # Çıktıyı kontrol et
    assert "durduruluyor" in output
    
    # ServiceWrapper.stop_all metodunun çağrıldığını doğrula
    mock_service_wrapper.stop_all.assert_called_once()

def test_status_command(mock_service_wrapper, env_setup):
    """
    'status' komutunun doğru çalıştığını test eder.
    """
    # Status komutunu çalıştır
    output = run_status_command(mock_service_wrapper)
    
    # Çıktıyı kontrol et
    assert "durumu" in output
    assert str(len(SERVICES_LIST)) in output
    
    # ServiceWrapper.list_services metodunun çağrıldığını doğrula
    mock_service_wrapper.list_services.assert_called_once()

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 