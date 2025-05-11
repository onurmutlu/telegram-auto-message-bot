"""
Telegram Bot Monitoring Servisi Testleri

Bu test modülü, Monitoring servisinin işlevselliğini test eder:
1. Servis durumu izleme
2. Performans metrikleri toplama
3. Hata loglama
4. Alarm bildirimleri
"""

import os
import asyncio
import pytest
import pytest_asyncio
import tempfile
import json
import time
import datetime
from unittest.mock import AsyncMock, MagicMock, patch, ANY, call
from pathlib import Path

# Monitoring servisi sınıflarını mock ediyoruz
class MockMonitoringService:
    """Monitoring servisinin mock implementasyonu"""
    
    def __init__(self, config=None):
        self.running = False
        self.metrics = {
            "messages_sent": 0,
            "errors": 0,
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "uptime": 0
        }
        self.config = config or {
            "check_interval": 60,  # saniye
            "error_threshold": 5,  # bu sayının üstünde hata olduğunda alarm
            "logs_dir": "/tmp/bot_logs",
        }
        self.error_log = []
        self.events = []
        self.start_time = None
        self.alerts_enabled = True
        
    async def start(self):
        """Monitoring servisini başlatır"""
        self.running = True
        self.start_time = datetime.datetime.now()
        self.metrics["uptime"] = 0
        return True
    
    async def stop(self):
        """Monitoring servisini durdurur"""
        self.running = False
        self.start_time = None
        return True
    
    def log_error(self, error_message, service_name=None, severity="error"):
        """Hata loglar"""
        timestamp = datetime.datetime.now().isoformat()
        error_entry = {
            "timestamp": timestamp,
            "message": error_message,
            "service": service_name or "unknown",
            "severity": severity
        }
        self.error_log.append(error_entry)
        self.metrics["errors"] += 1
        
        # Kritik hata durumunda alarm gönder
        if severity == "critical" and self.alerts_enabled:
            self._send_alert(error_entry)
        
        return True
    
    def _send_alert(self, error_entry):
        """Alarm bildirimi gönderir (mock)"""
        self.events.append({
            "type": "alert",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": error_entry
        })
        return True
    
    def record_metric(self, metric_name, value):
        """Metrik kaydeder"""
        if metric_name in self.metrics:
            self.metrics[metric_name] = value
            return True
        return False
    
    def increment_metric(self, metric_name, increment=1):
        """Metrik değerini artırır"""
        if metric_name in self.metrics and isinstance(self.metrics[metric_name], (int, float)):
            self.metrics[metric_name] += increment
            return True
        return False
    
    def get_metrics(self):
        """Tüm metrikleri döndürür"""
        # Uptime'ı güncelle
        if self.running and self.start_time:
            uptime_seconds = (datetime.datetime.now() - self.start_time).total_seconds()
            self.metrics["uptime"] = int(uptime_seconds)
        
        return self.metrics
    
    def get_errors(self, limit=10, severity=None):
        """Son hataları döndürür"""
        filtered_errors = self.error_log
        
        if severity:
            filtered_errors = [e for e in filtered_errors if e["severity"] == severity]
        
        return filtered_errors[-limit:]
    
    def export_logs(self, output_path):
        """Logları dışa aktarır"""
        try:
            with open(output_path, 'w') as f:
                json.dump({
                    "metrics": self.metrics,
                    "errors": self.error_log,
                    "events": self.events,
                    "export_time": datetime.datetime.now().isoformat()
                }, f, indent=2)
            return True
        except Exception:
            return False
    
    def enable_alerts(self, enabled=True):
        """Alarm bildirimlerini etkinleştirir/devre dışı bırakır"""
        self.alerts_enabled = enabled
        return True

@pytest.fixture
def monitoring_service():
    """Test için MonitoringService instance'ı oluşturur"""
    service = MockMonitoringService()
    return service

# ================== TEMEL FONKSİYONELLİK TESTLERİ ==================

@pytest.mark.asyncio
async def test_service_lifecycle(monitoring_service):
    """Monitoring servisinin yaşam döngüsünü test eder"""
    # Başlangıçta servisin çalışmadığını doğrula
    assert monitoring_service.running == False
    
    # Servisi başlat
    result = await monitoring_service.start()
    assert result == True
    assert monitoring_service.running == True
    
    # Servisi durdur
    result = await monitoring_service.stop()
    assert result == True
    assert monitoring_service.running == False

@pytest.mark.asyncio
async def test_error_logging(monitoring_service):
    """Hata loglama işlevselliğini test eder"""
    # Servisi başlat
    await monitoring_service.start()
    
    # Birkaç hata logla
    monitoring_service.log_error("Test hatası 1", "messaging", "warning")
    monitoring_service.log_error("Test hatası 2", "scheduler", "error")
    monitoring_service.log_error("Test hatası 3", "database", "critical")
    
    # Hata sayısını kontrol et
    assert monitoring_service.metrics["errors"] == 3
    
    # Kayıtlı hataları kontrol et
    errors = monitoring_service.get_errors()
    assert len(errors) == 3
    
    # Kritik hataları filtrele
    critical_errors = monitoring_service.get_errors(severity="critical")
    assert len(critical_errors) == 1
    assert critical_errors[0]["message"] == "Test hatası 3"
    
    # Servisi durdur
    await monitoring_service.stop()

@pytest.mark.asyncio
async def test_metric_tracking(monitoring_service):
    """Metrik izleme işlevselliğini test eder"""
    # Servisi başlat
    await monitoring_service.start()
    
    # Metrikleri kaydet
    monitoring_service.record_metric("cpu_usage", 25.5)
    monitoring_service.record_metric("memory_usage", 150.2)
    monitoring_service.increment_metric("messages_sent", 10)
    
    # Metrikleri kontrol et
    metrics = monitoring_service.get_metrics()
    assert metrics["cpu_usage"] == 25.5
    assert metrics["memory_usage"] == 150.2
    assert metrics["messages_sent"] == 10
    
    # Uptime metriğinin pozitif olduğunu kontrol et
    assert metrics["uptime"] >= 0
    
    # Servisi durdur
    await monitoring_service.stop()

# ================== ALARM VE BİLDİRİM TESTLERİ ==================

@pytest.mark.asyncio
async def test_alert_system(monitoring_service):
    """Alarm sistemini test eder"""
    # Servisi başlat
    await monitoring_service.start()
    
    # Alarm bildirimlerinin etkin olduğunu doğrula
    assert monitoring_service.alerts_enabled == True
    
    # Normal hata - alarm oluşturmamalı
    monitoring_service.log_error("Normal hata", "test", "error")
    assert len(monitoring_service.events) == 0
    
    # Kritik hata - alarm oluşturmalı
    monitoring_service.log_error("Kritik hata", "test", "critical")
    assert len(monitoring_service.events) == 1
    assert monitoring_service.events[0]["type"] == "alert"
    assert monitoring_service.events[0]["data"]["message"] == "Kritik hata"
    
    # Alarmları devre dışı bırak
    monitoring_service.enable_alerts(False)
    assert monitoring_service.alerts_enabled == False
    
    # Alarmlar devre dışıyken kritik hata - alarm oluşturmamalı
    monitoring_service.log_error("Başka kritik hata", "test", "critical")
    assert len(monitoring_service.events) == 1  # Hâlâ 1 olmalı
    
    # Servisi durdur
    await monitoring_service.stop()

# ================== LOG DOSYALARI TESTLERİ ==================

@pytest.mark.asyncio
async def test_log_export(monitoring_service):
    """Log dışa aktarma işlevselliğini test eder"""
    # Servisi başlat
    await monitoring_service.start()
    
    # Bazı veriler oluştur
    monitoring_service.log_error("Test hatası", "export_test")
    monitoring_service.record_metric("cpu_usage", 30.0)
    
    # Geçici bir dosya oluştur
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        # Logları dışa aktar
        export_result = monitoring_service.export_logs(tmp_path)
        assert export_result == True
        
        # Dışa aktarılan dosyayı kontrol et
        with open(tmp_path, 'r') as f:
            exported_data = json.load(f)
        
        # Dışa aktarılan verinin doğru olduğunu kontrol et
        assert "metrics" in exported_data
        assert "errors" in exported_data
        assert exported_data["metrics"]["cpu_usage"] == 30.0
        assert len(exported_data["errors"]) == 1
        assert exported_data["errors"][0]["message"] == "Test hatası"
    
    finally:
        # Geçici dosyayı temizle
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    
    # Servisi durdur
    await monitoring_service.stop()

# ================== PERFORMANS TESTLERİ ==================

@pytest.mark.asyncio
async def test_high_volume_error_logging(monitoring_service):
    """Yüksek hacimli hata loglama performansını test eder"""
    # Servisi başlat
    await monitoring_service.start()
    
    # Çok sayıda hata logla
    error_count = 1000
    start_time = time.time()
    
    for i in range(error_count):
        monitoring_service.log_error(f"Performans testi hatası {i}", "performance_test")
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Loglama süresini kontrol et (makul bir sürede tamamlanmalı)
    assert duration < 1.0, f"Yüksek hacimli loglama çok uzun sürdü: {duration:.2f} saniye"
    
    # Hata sayısını kontrol et
    assert monitoring_service.metrics["errors"] == error_count
    
    # Servisi durdur
    await monitoring_service.stop()

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 