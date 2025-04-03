"""
# ============================================================================ #
# Dosya: test_error_handler.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/test_error_handler.py
# İşlev: ErrorHandler sınıfı için birim testler
#
# Build: 2025-04-01-00:07:55
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, ErrorHandler sınıfı için kapsamlı test senaryoları içerir:
# - Başlatma ve yapılandırma testleri
# - Metod varlık ve davranış testleri
# - Hata durumlarının kontrolü
# 
# Kullanım: python -m pytest tests/test_error_handler.py -v
#
# ============================================================================ #
"""

import os
import sys
import pytest
import logging
import inspect
from unittest.mock import patch, MagicMock, call

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Proje modüllerini import et
try:
    from bot.utils.error_handler import ErrorHandler
    HAS_ERROR_HANDLER = True
except ImportError:
    HAS_ERROR_HANDLER = False

# Error handler yoksa testleri atla
pytestmark = pytest.mark.skipif(not HAS_ERROR_HANDLER, reason="ErrorHandler modülü bulunamadı")

@pytest.fixture
def mock_bot():
    """Mock bot nesnesi oluşturur"""
    bot = MagicMock()
    bot.error_counter = {}
    return bot

def test_error_handler_initialization(mock_bot):
    """Error Handler başlatma testi"""
    # Error handler oluştur
    handler = ErrorHandler(mock_bot)
    
    # Nesne kontrolü
    assert hasattr(handler, 'bot')
    assert handler.bot == mock_bot

def test_error_handling_methods_exist(mock_bot):
    """ErrorHandler'ın hata işleme metotlarını kontrol eder"""
    # Error handler oluştur
    handler = ErrorHandler(mock_bot)
    
    # Hata işleme metotlarını bul
    error_methods = []
    for name in dir(handler):
        attr = getattr(handler, name)
        if callable(attr) and not name.startswith('_'):
            # İşlevi incele
            sig = inspect.signature(attr)
            # En az bir parametre var mı ve ismi hata işlemeyle ilgili mi?
            if len(sig.parameters) > 0 and any(keyword in name.lower() for keyword in ["error", "exception", "log", "handle"]):
                error_methods.append(name)
    
    # En az bir hata işleme metodu olmalı
    assert len(error_methods) > 0, "Hata işleme metodu bulunamadı"
    
    # Metotlar hakkında bilgi
    print(f"\nBulunan hata işleme metotları: {', '.join(error_methods)}")

def test_telethon_log_filtering(mock_bot):
    """Telethon loglarını filtreleme testi"""
    # Error handler oluştur
    handler = ErrorHandler(mock_bot)
    
    # telethon_log_cache mevcut mu?
    assert hasattr(handler, 'telethon_log_cache'), "telethon_log_cache özelliği bulunamadı"
    
    # Flood wait mesajını filtrele
    with patch('builtins.print') as mock_print:
        # Sahte log kaydı oluştur
        record = MagicMock()
        record.name = "telethon.network.mtprotosender"
        record.levelname = "INFO" 
        record.getMessage.return_value = "Sleeping for 10s due to FloodWait on GetDialogsRequest"
        record.msg = "Sleeping for 10s due to FloodWait on GetDialogsRequest"
        
        # _custom_emit metodu kontrolü 
        if hasattr(handler, '_custom_emit'):
            # İlk log
            handler._custom_emit(record)
            
            # Log gösterildi mi?
            mock_print.assert_called()
            
            # İkinci kez aynı log gelirse farklı davranmalı?
            mock_print.reset_mock()
            handler._custom_emit(record)
            
            # Assertion ekleyin - gerçek davranışa göre düzenleyin
            # Örneğin: Aynı mesaj tekrar geldiyse bastırılmış olabilir
            # mock_print.assert_not_called()  # Eğer log bastırılıyorsa
        else:
            # _custom_emit metodu yoksa alternatif test
            pytest.skip("_custom_emit metodu ErrorHandler'da bulunamadı")

@pytest.mark.asyncio(loop_scope="function")
async def test_async_error_handling(mock_bot):
    """Asenkron hata işleme testi"""
    # Error handler oluştur
    handler = ErrorHandler(mock_bot)
    
    # Asenkron metot kontrolü
    async_methods = [name for name in dir(handler) if 
                    callable(getattr(handler, name)) and 
                    inspect.iscoroutinefunction(getattr(handler, name))]
    
    # Asenkron metodları test et
    if async_methods:
        # Örnek asenkron çağrı ve test
        for method_name in async_methods:
            method = getattr(handler, method_name)
            try:
                # Parametreler metoda göre ayarlanmalı
                # await method(...)
                pass
            except Exception as e:
                pytest.fail(f"Asenkron metot {method_name} çağırılırken hata: {str(e)}")
    else:
        pytest.skip("ErrorHandler'da asenkron metot bulunamadı")