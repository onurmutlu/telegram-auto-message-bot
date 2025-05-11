"""
FastAPI endpoint'leri için birim testleri

Bu modül, FastAPI backend API endpoint'lerinin birim testlerini içerir.
"""

import json
import os
from pathlib import Path
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, mock_open

# FastAPI uygulamasını içe aktar
from app.api.main import app  # Dosya yolunuzu doğru şekilde ayarlayın

# TestClient oluştur
client = TestClient(app)

# Sabit değişkenler
TEST_SETTINGS_PATH = "settings.json"
TEST_SETTINGS_DATA = {
    "apiId": "12345678",
    "apiHash": "a1b2c3d4e5f6g7h8i9j0",
    "botToken": "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
}

class TestLogsEndpoint:
    """Logs endpoint'i için testler"""
    
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_get_logs_when_file_exists(self, mock_file, mock_exists):
        """Log dosyası varsa, logs endpoint'i log listesini döndürmelidir"""
        # Dosyanın var olduğunu simüle et
        mock_exists.return_value = True
        
        # Sahte log verilerini ayarla
        mock_file.return_value.read.return_value = json.dumps({
            "logs": ["Log 1", "Log 2", "Log 3"]
        })
        
        # API çağrısını yap
        response = client.get("/api/logs")
        
        # Sonuçları doğrula
        assert response.status_code == 200
        assert response.json() == {"logs": ["Log 1", "Log 2", "Log 3"]}
        
    @patch("os.path.exists")
    def test_get_logs_when_file_not_exists(self, mock_exists):
        """Log dosyası yoksa, logs endpoint'i ["Henüz log yok."] döndürmelidir"""
        # Dosyanın var olmadığını simüle et
        mock_exists.return_value = False
        
        # API çağrısını yap
        response = client.get("/api/logs")
        
        # Sonuçları doğrula
        assert response.status_code == 200
        assert response.json() == ["Henüz log yok."]

class TestSettingsEndpoint:
    """Ayarlar endpoint'i için testler"""
    
    @pytest.fixture
    def setup_settings_file(self):
        """Test için settings.json dosyasını oluştur ve test sonrası temizle"""
        # Test öncesi dosyayı temizle
        if os.path.exists(TEST_SETTINGS_PATH):
            os.remove(TEST_SETTINGS_PATH)
        
        yield
        
        # Test sonrası dosyayı temizle
        if os.path.exists(TEST_SETTINGS_PATH):
            os.remove(TEST_SETTINGS_PATH)
    
    def test_save_settings_success(self, setup_settings_file):
        """Geçerli ayarlar gönderildiğinde, settings endpoint'i dosyayı kaydetmeli ve 200 döndürmeli"""
        # API çağrısını yap
        response = client.post(
            "/api/save-settings",
            json=TEST_SETTINGS_DATA
        )
        
        # HTTP yanıtını doğrula
        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        
        # Dosyanın doğru şekilde oluşturulduğunu doğrula
        assert os.path.exists(TEST_SETTINGS_PATH)
        
        # Dosya içeriğini doğrula
        with open(TEST_SETTINGS_PATH, "r") as f:
            saved_data = json.load(f)
            assert saved_data == TEST_SETTINGS_DATA
    
    def test_save_settings_invalid_data(self):
        """Geçersiz ayarlar gönderildiğinde, settings endpoint'i 422 hatası döndürmeli"""
        # Eksik alanlar içeren geçersiz veri
        invalid_data = {
            "apiId": "12345678",
            # apiHash ve botToken eksik
        }
        
        # API çağrısını yap
        response = client.post(
            "/api/save-settings",
            json=invalid_data
        )
        
        # Doğrulama hatası alınmalı
        assert response.status_code == 422  # Unprocessable Entity 