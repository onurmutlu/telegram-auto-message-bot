"""
FastAPI backend API testleri

Bu modül, FastAPI backend endpoint'lerinin testlerini içerir:
- GET /api/logs
- POST /api/save-settings
- CRUD işlemleri: GET/POST/PUT/DELETE /api/messages
"""

import json
import os
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# FastAPI uygulamasını içe aktar 
# Not: Gerçek yolunuza göre ayarlayın
from app.api.main import app, get_settings_path, get_logs_path

# TestClient oluştur
client = TestClient(app)

@pytest.fixture
def temp_dir(tmp_path):
    """Test için geçici dizin oluşturur"""
    # Orijinal yolları sakla
    original_settings_path = get_settings_path()
    original_logs_path = get_logs_path()
    
    # Geçici test dizinleri
    settings_path = tmp_path / "settings.json"
    logs_path = tmp_path / "logs.json"
    
    # Mock'la
    with patch("app.api.main.get_settings_path", return_value=str(settings_path)), \
         patch("app.api.main.get_logs_path", return_value=str(logs_path)):
        yield {
            "settings_path": settings_path,
            "logs_path": logs_path
        }

class TestLogsEndpoint:
    """Logs endpoint testleri"""
    
    def test_get_logs_when_file_exists(self, temp_dir):
        """Log dosyası varsa, endpoint logs listesini döndürmelidir"""
        # Test log dosyasını hazırla
        logs_data = {"logs": ["Test log 1", "Test log 2", "Test log 3"]}
        with open(temp_dir["logs_path"], "w") as f:
            json.dump(logs_data, f)
        
        # API isteğini gönder
        response = client.get("/api/logs")
        
        # Sonuçları doğrula
        assert response.status_code == 200
        assert response.json() == logs_data
    
    def test_get_logs_when_file_not_exists(self, temp_dir):
        """Log dosyası yoksa, endpoint ["Henüz log yok."] döndürmelidir"""
        # Dosyanın olmadığından emin ol
        if os.path.exists(temp_dir["logs_path"]):
            os.remove(temp_dir["logs_path"])
            
        # API isteğini gönder
        response = client.get("/api/logs")
        
        # Sonuçları doğrula
        assert response.status_code == 200
        assert response.json() == {"logs": ["Henüz log yok."]}

class TestSettingsEndpoint:
    """Settings endpoint testleri"""
    
    def test_save_settings(self, temp_dir):
        """Ayarları kaydetme testi"""
        # Test verileri
        settings_data = {
            "apiId": "12345678",
            "apiHash": "testApiHash123456",
            "botToken": "123456:TEST-BOT-TOKEN"
        }
        
        # API isteğini gönder
        response = client.post(
            "/api/save-settings",
            json=settings_data
        )
        
        # HTTP yanıtını doğrula
        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        
        # Dosya içeriğini doğrula
        assert os.path.exists(temp_dir["settings_path"])
        with open(temp_dir["settings_path"], "r") as f:
            saved_data = json.load(f)
            assert saved_data == settings_data
    
    def test_save_settings_invalid_data(self):
        """Geçersiz ayarlar gönderildiğinde 422 hatası alınmalı"""
        # Eksik veri
        invalid_data = {
            "apiId": "12345678",
            # apiHash ve botToken eksik
        }
        
        # API isteğini gönder
        response = client.post(
            "/api/save-settings",
            json=invalid_data
        )
        
        # Doğrulama hatası alınmalı
        assert response.status_code == 422

class TestMessagesCRUD:
    """Mesaj CRUD işlemleri testleri"""
    
    @pytest.fixture
    def setup_message_db(self):
        """Mesaj işlemleri için DB hazırlama"""
        # Burada gerçek veritabanı yerine mock kullanabilirsiniz
        # Ya da test veritabanını temizleyebilirsiniz
        yield
    
    def test_crud_operations(self, setup_message_db):
        """Mesaj ekleme, listeleme, güncelleme ve silme testleri"""
        # 1. Önce mesaj listesinin boş olduğunu kontrol et
        response = client.get("/api/messages")
        assert response.status_code == 200
        initial_messages = response.json()
        initial_count = len(initial_messages)
        
        # 2. Yeni mesaj ekle
        new_message = {
            "content": "Test mesajı",
            "group_id": 123456789,
            "content_type": "text",
            "scheduled_time": "2025-06-15T14:30:00"
        }
        
        create_response = client.post(
            "/api/messages",
            json=new_message
        )
        assert create_response.status_code == 200
        created_message = create_response.json()
        message_id = created_message["id"]
        
        # 3. Mesajın listelendiğini kontrol et
        list_response = client.get("/api/messages")
        assert list_response.status_code == 200
        messages = list_response.json()
        assert len(messages) == initial_count + 1
        
        # 4. Belirli bir mesajı görüntüle
        get_response = client.get(f"/api/messages/{message_id}")
        assert get_response.status_code == 200
        assert get_response.json()["content"] == new_message["content"]
        
        # 5. Mesajı güncelle
        update_data = {
            "content": "Güncellenmiş test mesajı"
        }
        
        update_response = client.put(
            f"/api/messages/{message_id}",
            json=update_data
        )
        assert update_response.status_code == 200
        assert update_response.json()["content"] == update_data["content"]
        
        # 6. Güncelleme kontrolü
        after_update_response = client.get(f"/api/messages/{message_id}")
        assert after_update_response.status_code == 200
        assert after_update_response.json()["content"] == update_data["content"]
        
        # 7. Mesajı sil
        delete_response = client.delete(f"/api/messages/{message_id}")
        assert delete_response.status_code == 200
        
        # 8. Silme işlemini kontrol et
        after_delete_response = client.get(f"/api/messages/{message_id}")
        assert after_delete_response.status_code == 404  # Not Found beklenir
        
        # 9. Mesaj listesinin başlangıç sayısına döndüğünü kontrol et
        final_list_response = client.get("/api/messages")
        assert final_list_response.status_code == 200
        assert len(final_list_response.json()) == initial_count 