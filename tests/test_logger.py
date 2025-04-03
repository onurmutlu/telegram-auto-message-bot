"""
# ============================================================================ #
# Dosya: test_logger.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/test_logger.py
# İşlev: Telegram bot bileşeni
#
# Build: 2025-04-01-00:07:55
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu test modülü, logger için birim testleri içerir:
# - Temel işlevsellik testleri
# - Sınır koşulları ve hata durumları
# - Mock nesnelerle izolasyon
# 
# Kullanım: python -m pytest tests/test_logger.py -v
#
# ============================================================================ #
"""

import os
import sys
import pytest
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Proje modüllerini import et
try:
    from bot.utils.logger_setup import setup_logger, configure_service_logger
except ImportError:
    # Logger modulü henüz oluşturulmadı ise atlayalım
    pytestmark = pytest.mark.skip(reason="Logger modülü henüz oluşturulmadı")

def test_logger_file_creation():
    """Logger dosyası oluşturma testi"""
    # Geçici log dosyası için
    temp_dir = tempfile.mkdtemp()
    log_file = os.path.join(temp_dir, "test.log")
    
    # Mock config 
    mock_config = MagicMock()
    mock_config.LOG_FILE_PATH = log_file
    
    try:
        # Logger'ı yapılandır
        logger = setup_logger(mock_config)
        
        # Log dosyası oluşturuldu mu?
        assert os.path.exists(log_file)
        
        # Temel log mesajı yaz
        logger.info("Test log message")
        
        # Log dosyası içeriğinde bu mesaj var mı?
        with open(log_file, 'r') as f:
            content = f.read()
            assert "Test log message" in content
            
    finally:
        # Temizlik
        if os.path.exists(log_file):
            os.remove(log_file)
        os.rmdir(temp_dir)

def test_logger_levels():
    """Logger seviyesi testi"""
    # Geçici log dosyası için
    temp_dir = tempfile.mkdtemp()
    log_file = os.path.join(temp_dir, "test.log")
    
    # Mock config
    mock_config = MagicMock()
    mock_config.LOG_FILE_PATH = log_file
    
    try:
        # INFO seviyesi ile yapılandır
        info_logger = setup_logger(mock_config, level=logging.INFO)
        
        # Log seviyeleri doğru çalışıyor mu?
        # DEBUG seviyesindeki mesaj yazılmamalı
        info_logger.debug("DEBUG message should not be in console")
        info_logger.info("INFO message should be in log")
        
        # Log dosyasındaki içerik
        with open(log_file, 'r') as f:
            content = f.read()
            # DEBUG seviyesi dosyaya girmeli (handler'lar farklı seviyede)
            assert "DEBUG message" in content
            assert "INFO message" in content
            
        # DEBUG seviyesi ile yapılandır
        os.remove(log_file)  # Önceki log dosyasını sil
        debug_logger = setup_logger(mock_config, level=logging.DEBUG)
        
        # Şimdi DEBUG de yazılmalı
        debug_logger.debug("This DEBUG should be visible")
        
        # Log dosyasındaki içerik
        with open(log_file, 'r') as f:
            content = f.read()
            assert "This DEBUG should be visible" in content
            
    finally:
        # Temizlik
        if os.path.exists(log_file):
            os.remove(log_file)
        os.rmdir(temp_dir)

def test_service_logger():
    """Servis logger testi"""
    # Geçici log dosyası için
    temp_dir = tempfile.mkdtemp()
    log_file = os.path.join(temp_dir, "test.log")
    
    # Mock config
    mock_config = MagicMock()
    mock_config.LOG_FILE_PATH = log_file
    
    try:
        # Ana logger'ı yapılandır
        main_logger = setup_logger(mock_config)
        
        # Servis logger'ı oluştur
        service_logger = configure_service_logger("message_service")
        
        # Servis logger adı doğru mu?
        assert service_logger.name == "service.message_service"
        
        # Log mesajları
        service_logger.info("Service log test")
        
        # Log dosyasında bu mesaj var mı?
        with open(log_file, 'r') as f:
            content = f.read()
            assert "Service log test" in content
            
    finally:
        # Temizlik
        if os.path.exists(log_file):
            os.remove(log_file)
        os.rmdir(temp_dir)

def test_telethon_log_filtering():
    """Telethon log seviyelerini kontrol et"""
    # Geçici log dosyası için
    temp_dir = tempfile.mkdtemp()
    log_file = os.path.join(temp_dir, "test.log")
    
    # Mock config
    mock_config = MagicMock()
    mock_config.LOG_FILE_PATH = log_file
    
    try:
        # Logger'ı yapılandır
        logger = setup_logger(mock_config)
        
        # Telethon logger'ının seviyesi WARNING olmalı
        telethon_logger = logging.getLogger('telethon')
        assert telethon_logger.level == logging.WARNING
            
    finally:
        # Temizlik
        if os.path.exists(log_file):
            os.remove(log_file)
        os.rmdir(temp_dir)