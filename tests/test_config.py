"""
Konfigürasyon testleri
"""

import os
import sys
import pytest
import json
from pathlib import Path

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Proje modüllerini import et
from config.settings import Config

def test_config_initialization():
    """Config başlatma testi"""
    # Config nesnesi oluştur
    config = Config()

    # Önemli özellikler var mı?
    assert hasattr(config, 'env')
    assert hasattr(config, 'debug')
    assert config.debug is False  # Varsayılan değerin doğru olduğundan emin olun

    # Şablon sözlükleri doğru şekilde başlatılmış mı?
    assert isinstance(config.message_templates, list)  # Bu satırı kontrol edin
    assert isinstance(config.invite_templates, dict)
    assert 'first_invite' in config.invite_templates
    assert 'redirect_messages' in config.invite_templates
    assert isinstance(config.response_templates, dict)
    assert 'flirty' in config.response_templates

def test_config_directory_paths():
    """Config dizin yolları testi"""
    # Config sınıfı üzerinden yol sabitlerine erişim
    assert os.path.isabs(Config.BASE_DIR)
    assert str(Config.RUNTIME_DIR).endswith('runtime')
    assert str(Config.SESSION_DIR).endswith('sessions')
    assert str(Config.DATABASE_DIR).endswith('database')
    assert str(Config.LOGS_DIR).endswith('logs')
    
    # Veritabanı ve oturum dosya yolları
    assert str(Config.DATABASE_PATH).endswith('users.db')
    assert str(Config.SESSION_PATH).endswith('member_session')
    assert str(Config.LOG_FILE_PATH).endswith('bot.log')

def test_config_create_directories(tmpdir):
    """Dizin oluşturma testi"""
    # Config nesnesi oluştur
    config = Config()

    # Geçici bir dizine yapılandırma oluşturma
    original_runtime_dir = config.RUNTIME_DIR
    original_session_dir = config.SESSION_DIR
    original_database_dir = config.DATABASE_DIR
    original_logs_dir = config.LOGS_DIR
    
    try:
        # Geçici dizinlerle güncelle
        test_runtime_dir = Path(tmpdir) / 'runtime'
        config.RUNTIME_DIR = test_runtime_dir
        config.SESSION_DIR = test_runtime_dir / 'sessions'
        config.DATABASE_DIR = test_runtime_dir / 'database'
        config.LOGS_DIR = test_runtime_dir / 'logs'
        
        # Dizinleri oluştur
        config.create_directories()
        
        # Dizinler oluşturuldu mu?
        assert os.path.exists(test_runtime_dir)
        assert os.path.exists(config.SESSION_DIR)
        assert os.path.exists(config.DATABASE_DIR)
        assert os.path.exists(config.LOGS_DIR)
        assert os.path.exists(config.DATABASE_DIR / 'backups')
        
    finally:
        # Orijinal değerlere geri dön
        config.RUNTIME_DIR = original_runtime_dir
        config.SESSION_DIR = original_session_dir
        config.DATABASE_DIR = original_database_dir
        config.LOGS_DIR = original_logs_dir

def test_config_load_message_templates():
    """Mesaj şablonları yükleme testi"""
    # Config nesnesi oluştur
    config = Config()

    # Mesajları yükle
    result = config.load_message_templates()

    # Sonucu kontrol et
    assert isinstance(result, list)
    assert len(result) > 0

def test_config_load_invite_templates():
    """Davet şablonları yükleme testi"""
    # Geçici config dosyası oluştur
    import tempfile
    temp_dir = tempfile.mkdtemp()
    invites_path = os.path.join(temp_dir, 'invites.json')

    # Test davetleri
    test_invites = {
        "first_invite": ["Test davet 1", "Test davet 2"],
        "invites": ["Test davet 1", "Test davet 2"],
        "invites_outro": ["Test outro"],
        "redirect_messages": ["Test yönlendirme"]
    }

    try:
        # Davetleri dosyaya yaz
        with open(invites_path, 'w', encoding='utf-8') as f:
            json.dump(test_invites, f)

        # Config oluştur
        config = Config()

        # Orijinal yolu yedekle
        original_path = config.INVITE_TEMPLATES_PATH

        # Test yolunu ayarla
        config.INVITE_TEMPLATES_PATH = invites_path

        # Davetleri yükle
        result = config.load_invite_templates()

        # Sonucu kontrol et
        assert "first_invite" in result  # Bu satırı kontrol edin
        assert "invites" in result
        assert "invites_outro" in result
        assert "redirect_messages" in result
        assert result["invites"] == test_invites["invites"]

    finally:
        # Orijinal yolu geri yükle
        config.INVITE_TEMPLATES_PATH = original_path

def test_config_load_response_templates():
    """Yanıt şablonları yükleme testi"""
    # Config nesnesi oluştur
    config = Config()

    # Yanıtları yükle
    result = config.load_response_templates()

    # Sonucu kontrol et
    assert isinstance(result, dict)
    assert "flirty" in result
    assert len(result["flirty"]) > 0