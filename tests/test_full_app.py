"""
FastAPI Tam Uygulama Entegrasyon Testi

Bu modül, FastAPI uygulamasının tam bir işleyişini test eder:
1. API ayarlarının kaydedilmesi
2. Mesaj ekleme, görüntüleme, güncelleme ve silme işlemleri
3. Log erişimi ve doğrulama

Tüm bu adımlar tek bir akışta test edilir.
"""

import json
import os
import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# FastAPI uygulamasını içe aktar
from app.api.main import app, get_settings_path, get_logs_path

# Test sabitleri
TEST_SETTINGS = {
    "apiId": "12345678",
    "apiHash": "ad78ef9c1b23d456a7890b12c34d56e7",
    "botToken": "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ12345"
}

TEST_MESSAGE = {
    "content": "Test mesajı içeriği",
    "group_id": 123456789,
    "content_type": "text",
    "scheduled_time": "2025-12-31T23:59:59"
}

@pytest.fixture
def api_client():
    """FastAPI uygulamasını test etmek için bir TestClient sağlar."""
    return TestClient(app)

@pytest.fixture
def temp_files(tmp_path):
    """
    Geçici test dosyaları oluşturur ve temizler.
    
    Bu fixture, dosya sistemi işlemlerini izole etmek için kullanılır.
    Gerçek dosyaların yerine geçici dosyalar kullanılır.
    """
    # Geçici dosya yolları
    settings_path = tmp_path / "settings.json"
    logs_path = tmp_path / "logs.json"
    
    # Log dosyasını oluştur (boş bir log listesi ile)
    logs_path.write_text(json.dumps({"logs": []}))
    
    # get_settings_path ve get_logs_path işlevlerini monkeypatch ile değiştir
    with patch("app.api.main.get_settings_path", return_value=str(settings_path)), \
         patch("app.api.main.get_logs_path", return_value=str(logs_path)):
        
        yield {
            "settings_path": settings_path,
            "logs_path": logs_path
        }
    
    # Temizlik
    if settings_path.exists():
        os.remove(settings_path)
    if logs_path.exists():
        os.remove(logs_path)

@pytest.fixture
def db_session():
    """
    Veritabanı oturumu oluşturur ve test sonrası temizler.
    
    Bu fixture, test veritabanındaki CRUD işlemlerini izole etmek için kullanılır.
    """
    # Burada normalde bir test veritabanı bağlantısı oluşturulur
    # SQLAlchemy veya başka bir ORM için
    # Test için gerçek bir veritabanı mocklanabilir
    
    yield
    
    # Test sonrası temizlik işlemleri
    # Örneğin: truncate tables, rollback transaction vb.

@pytest.mark.asyncio
async def test_full_app_flow(api_client, temp_files, db_session):
    """
    Tam bir uygulama akışını test eder:
    1. Ayarları kaydetme
    2. Mesaj ekleme
    3. Mesajları listeleme
    4. Mesaj görüntüleme
    5. Mesaj güncelleme
    6. Mesaj silme
    7. Logları kontrol etme
    """
    # ----- 1. AYARLARI KAYDETME -----
    settings_response = api_client.post(
        "/api/save-settings",
        json=TEST_SETTINGS
    )
    
    # Yanıtı kontrol et
    assert settings_response.status_code == 200
    assert settings_response.json() == {"status": "success"}
    
    # Dosyayı kontrol et
    assert temp_files["settings_path"].exists()
    saved_settings = json.loads(temp_files["settings_path"].read_text())
    assert saved_settings == TEST_SETTINGS
    
    print("✓ Ayarlar başarıyla kaydedildi")
    
    # ----- 2. MESAJ EKLEME -----
    create_response = api_client.post(
        "/api/messages",
        json=TEST_MESSAGE
    )
    
    # Yanıtı kontrol et
    assert create_response.status_code == 200
    created_message = create_response.json()
    assert "id" in created_message
    assert created_message["content"] == TEST_MESSAGE["content"]
    
    # Mesaj ID'sini sakla
    message_id = created_message["id"]
    
    print(f"✓ Mesaj başarıyla oluşturuldu (ID: {message_id})")
    
    # ----- 3. MESAJLARI LİSTELEME -----
    list_response = api_client.get("/api/messages")
    
    # Yanıtı kontrol et
    assert list_response.status_code == 200
    messages = list_response.json()
    assert isinstance(messages, list)
    
    # Eklediğimiz mesajın listede olduğunu kontrol et
    assert any(msg["id"] == message_id for msg in messages)
    
    # Mesaj içeriğini kontrol et
    matching_message = next(msg for msg in messages if msg["id"] == message_id)
    assert matching_message["content"] == TEST_MESSAGE["content"]
    
    print("✓ Mesaj başarıyla listelendi")
    
    # ----- 4. TEK MESAJ GÖRÜNTÜLEME -----
    get_response = api_client.get(f"/api/messages/{message_id}")
    
    # Yanıtı kontrol et
    assert get_response.status_code == 200
    message = get_response.json()
    assert message["id"] == message_id
    assert message["content"] == TEST_MESSAGE["content"]
    
    print("✓ Tek mesaj başarıyla görüntülendi")
    
    # ----- 5. MESAJ GÜNCELLEME -----
    update_data = {
        "content": "Güncellenmiş test mesajı",
        "content_type": "updated_text"
    }
    
    update_response = api_client.put(
        f"/api/messages/{message_id}",
        json=update_data
    )
    
    # Yanıtı kontrol et
    assert update_response.status_code == 200
    updated_message = update_response.json()
    assert updated_message["id"] == message_id
    assert updated_message["content"] == update_data["content"]
    assert updated_message["content_type"] == update_data["content_type"]
    
    # Güncellenmiş mesajı kontrol et
    get_updated_response = api_client.get(f"/api/messages/{message_id}")
    assert get_updated_response.status_code == 200
    assert get_updated_response.json()["content"] == update_data["content"]
    
    print("✓ Mesaj başarıyla güncellendi")
    
    # ----- 6. MESAJ SİLME -----
    delete_response = api_client.delete(f"/api/messages/{message_id}")
    
    # Yanıtı kontrol et
    assert delete_response.status_code == 200
    
    # Mesajın silindiğini kontrol et
    get_deleted_response = api_client.get(f"/api/messages/{message_id}")
    assert get_deleted_response.status_code == 404  # Not Found
    
    print("✓ Mesaj başarıyla silindi")
    
    # ----- 7. MESAJ LİSTESİ TEKRAR KONTROL ET -----
    list_after_delete_response = api_client.get("/api/messages")
    assert list_after_delete_response.status_code == 200
    messages_after_delete = list_after_delete_response.json()
    
    # Silinen mesajın artık listede olmadığını kontrol et
    assert not any(msg["id"] == message_id for msg in messages_after_delete)
    
    print("✓ Mesaj listeden kaldırıldı")
    
    # ----- 8. LOGLARI KONTROL ET -----
    logs_response = api_client.get("/api/logs")
    
    # Yanıtı kontrol et
    assert logs_response.status_code == 200
    logs_data = logs_response.json()
    assert "logs" in logs_data
    logs = logs_data["logs"]
    
    # Log içeriklerini kontrol et (içerikler uygulamanıza göre değişecektir)
    log_texts = " ".join(logs)
    
    # Kritik anahtar kelimeleri kontrol et
    assert "settings" in log_texts.lower() or "ayarlar" in log_texts.lower(), "Log dosyasında ayarlar kaydı bulunamadı"
    assert "add" in log_texts.lower() or "ekle" in log_texts.lower() or "create" in log_texts.lower(), "Log dosyasında mesaj ekleme kaydı bulunamadı"
    assert "update" in log_texts.lower() or "güncelle" in log_texts.lower(), "Log dosyasında mesaj güncelleme kaydı bulunamadı"
    assert "delete" in log_texts.lower() or "sil" in log_texts.lower(), "Log dosyasında mesaj silme kaydı bulunamadı"
    
    print("✓ Log kayıtları başarıyla doğrulandı")
    
    # Tüm adımlar başarıyla tamamlandı
    print("\n✓ Tüm entegrasyon testi başarıyla tamamlandı!")

if __name__ == "__main__":
    # Test dosyası doğrudan çalıştırılırsa pytest ile çalıştır
    import sys
    sys.exit(pytest.main(["-xvs", __file__])) 