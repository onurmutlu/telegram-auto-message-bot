"""
Logger testleri
"""
import os
import sys
import pytest
import logging
import tempfile
from pathlib import Path

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Proje modüllerini import et
try:
    from bot.utils.logger_setup import setup_logger, configure_console_logger
except ImportError:
    # Logger modulü henüz oluşturulmadı ise atlayalım
    pytestmark = pytest.mark.skip(reason="Logger modülü henüz oluşturulmadı")

def test_logger_file_creation():
    """Logger dosyası oluşturma testi"""
    # Geçici log dosyası
    with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as temp:
        log_file = temp.name
    
    # Logger oluştur
    try:
        setup_logger(log_file=log_file, level=logging.DEBUG)
        
        # Test logu yaz
        logger = logging.getLogger("test_logger")
        logger.info("Test log message")
        
        # Log dosyasını kontrol et
        assert os.path.exists(log_file)
        
        # İçeriği kontrol et
        with open(log_file, 'r') as f:
            content = f.read()
            assert "Test log message" in content
    except NameError:
        # setup_logger fonksiyonu henüz yok
        pytest.skip("Logger setup fonksiyonu bulunamadı")
    finally:
        # Temizlik
        if os.path.exists(log_file):
            os.remove(log_file)

def test_logger_levels():
    """Logger seviyesi testi"""
    # Root logger'ı yedekle
    original_level = logging.getLogger().level
    original_handlers = logging.getLogger().handlers.copy()
    
    try:
        # Logger oluştur
        setup_logger(level=logging.ERROR)
        
        # Seviyeyi kontrol et
        assert logging.getLogger().level == logging.ERROR
        
        # DEBUG mesajı loglanıyor mu? (loglanmamalı)
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as temp:
            log_file = temp.name
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            logging.getLogger().addHandler(file_handler)
            
            # DEBUG logu yaz
            logging.debug("This should NOT be in the log")
            
            # Kontrol et
            with open(log_file, 'r') as f:
                content = f.read()
                assert "This should NOT be in the log" not in content
                
            # ERROR logu yaz
            logging.error("This should be in the log")
            
            # Kontrol et
            with open(log_file, 'r') as f:
                content = f.read()
                assert "This should be in the log" in content
    except NameError:
        # setup_logger fonksiyonu henüz yok
        pytest.skip("Logger setup fonksiyonu bulunamadı")
    finally:
        # Root logger'ı geri yükle
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        root_logger.setLevel(original_level)
        for handler in original_handlers:
            root_logger.addHandler(handler)
            
        # Temizlik
        if os.path.exists(log_file):
            os.remove(log_file)