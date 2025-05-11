#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analytics ve Error servislerinin gelişmiş testleri
"""

import asyncio
import unittest
import os
import json
import logging
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Sistemi hazırla
from config_helper import ConfigAdapter, ConfigDict
from app.services.analytics_service import AnalyticsService
from app.services.error_service import ErrorService, ErrorRecord, ErrorCategory

# Logging yapılandırması
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockDatabase:
    """Test için sahte veritabanı sınıfı"""
    
    def __init__(self):
        """Sahte veritabanı ve gerekli metodlar"""
        self.messages = {}
        self.users = {}
        self.groups = {}
        self.settings = {}
        self.error_records = []
        
    async def get_messages_stats(self, **kwargs):
        """Mesaj istatistiklerini döndürür"""
        return {
            "total": 1500,
            "active_groups": 10,
            "media_messages": 300,
            "text_messages": 1200,
        }
        
    async def get_group_stats(self, **kwargs):
        """Grup istatistiklerini döndürür"""
        return {
            "total_groups": 25,
            "active_groups": 15,
            "growing_groups": 5,
            "inactive_groups": 5,
        }
        
    async def get_user_stats(self, **kwargs):
        """Kullanıcı istatistiklerini döndürür"""
        return {
            "total_users": 500,
            "active_users": 200,
            "new_users": 50,
            "inactive_users": 250,
        }
        
    async def get_top_groups(self, **kwargs):
        """En aktif grupları döndürür"""
        return [
            {"group_id": 1001, "name": "Test Grup 1", "message_count": 350},
            {"group_id": 1002, "name": "Test Grup 2", "message_count": 250},
            {"group_id": 1003, "name": "Test Grup 3", "message_count": 150},
        ]
        
    async def get_error_records(self, **kwargs):
        """Hata kayıtlarını döndürür"""
        return self.error_records
        
    async def save_error(self, **kwargs):
        """Hata kaydı oluşturur"""
        error_id = f"ERR-{len(self.error_records) + 1}"
        timestamp = datetime.now()
        error = {
            "error_id": error_id,
            "error_type": kwargs.get("error_type", "UnknownError"),
            "message": kwargs.get("message", ""),
            "source": kwargs.get("source", "unknown"),
            "severity": kwargs.get("severity", "ERROR"),
            "category": kwargs.get("category", "GENERAL"),
            "stack_trace": kwargs.get("stack_trace", ""),
            "metadata": kwargs.get("metadata", {}),
            "timestamp": timestamp,
            "resolved": False,
            "resolution_info": None,
            "resolution_timestamp": None
        }
        self.error_records.append(error)
        return error_id
        
    async def resolve_error(self, error_id, resolution_info=None):
        """Hatayı çözüldü olarak işaretler"""
        for error in self.error_records:
            if error["error_id"] == error_id:
                error["resolved"] = True
                error["resolution_info"] = resolution_info
                error["resolution_timestamp"] = datetime.now()
                return True
        return False
        
    async def connect(self, *args, **kwargs):
        """Bağlantı başlatma taklidi"""
        return True
        
    async def disconnect(self, *args, **kwargs):
        """Bağlantı kapatma taklidi"""
        return True
        
    async def execute(self, *args, **kwargs):
        """Sorgu çalıştırma taklidi"""
        return []
        
    async def fetch(self, *args, **kwargs):
        """Veri çekme taklidi"""
        return []
        

class TestServicesEnhanced(unittest.TestCase):
    """Analytics ve Error servislerinin gelişmiş testleri"""
    
    def setUp(self):
        """Test ortamını hazırla"""
        # Geçici dizinler oluştur
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.temp_dir, "logs")
        self.error_logs_dir = os.path.join(self.logs_dir, "errors")
        self.data_dir = os.path.join(self.temp_dir, "data")
        
        # Dizinleri oluştur
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.error_logs_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Mock veritabanı
        self.db = MockDatabase()
        
        # Yapılandırma nesnesi
        self.config = {
            'analytics': {
                'update_interval': 1800,
                'max_retained_reports': 30
            },
            'error_service': {
                'max_retained_errors': 1000,
                'error_log_path': self.error_logs_dir,
                'notify_critical': True,
                'notify_error': True,
                'alert_threshold': 5,
                'alert_window': 300,
                'category_thresholds': {
                    'DATABASE': 3, 
                    'TELEGRAM_API': 10,
                    'NETWORK': 5,
                    'GENERAL': 5
                },
                'category_windows': {
                    'DATABASE': 600,
                    'TELEGRAM_API': 300,
                    'NETWORK': 300,
                    'GENERAL': 300
                }
            }
        }
        
        # Stop event
        self.stop_event = asyncio.Event()
        
        # Analytics servisi
        self.analytics_service = AnalyticsService(
            service_name="analytics",
            client=None,
            config=self.config,
            db=self.db,
            stop_event=self.stop_event
        )
        
        # Error servisi
        self.error_service = ErrorService(
            service_name="error",
            client=None,
            config=self.config,
            db=self.db,
            stop_event=self.stop_event
        )
        
    def tearDown(self):
        """Test ortamını temizle"""
        # Geçici dizinleri temizle
        shutil.rmtree(self.temp_dir)
        
    async def _test_analytics_initialize(self):
        """Analytics servisinin başlatılmasını test eder"""
        # Servisi başlat
        result = await self.analytics_service.initialize()
        
        # Sonuçları doğrula
        self.assertTrue(result)
        self.assertTrue(self.analytics_service.initialized)
        self.assertEqual(self.analytics_service.update_interval, 1800)
        
        return result
        
    async def _test_analytics_generate_report(self):
        """Rapor oluşturma işlevini test eder"""
        # Servisi başlat
        await self.analytics_service.initialize()
        
        # Rapor oluştur
        report = await self.analytics_service.generate_weekly_report()
        
        # Sonuçları doğrula
        self.assertIsNotNone(report)
        self.assertIn("date", report)
        self.assertIn("period", report)
        self.assertIn("total_groups", report)
        self.assertIn("total_messages", report)
        self.assertIn("groups", report)
        
        # Grupları kontrol et
        self.assertEqual(len(report["groups"]), 3)  # Mock DB'den 3 grup almalıyız
        
        return report
        
    async def _test_analytics_export_csv(self):
        """CSV dışa aktarma işlevini test eder"""
        # Servisi başlat
        await self.analytics_service.initialize()
        
        # Test verisi oluştur
        test_data = [
            {"group_id": 1001, "name": "Test Grup 1", "message_count": 350, "active_users": 120, "engagement_rate": 22.5},
            {"group_id": 1002, "name": "Test Grup 2", "message_count": 250, "active_users": 80, "engagement_rate": 18.2},
            {"group_id": 1003, "name": "Test Grup 3", "message_count": 150, "active_users": 45, "engagement_rate": 15.8}
        ]
        
        # Dışa aktar
        export_path = os.path.join(self.data_dir, "test_export.csv")
        result = await self.analytics_service.export_to_csv(test_data, export_path)
        
        # Sonuçları doğrula
        self.assertTrue(result)
        self.assertTrue(os.path.exists(export_path))
        
        # CSV içeriğini kontrol et
        with open(export_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("group_id", content)
            self.assertIn("name", content)
            self.assertIn("message_count", content)
            self.assertIn("Test Grup 1", content)
            
        return export_path
        
    async def _test_error_initialize(self):
        """Error servisinin başlatılmasını test eder"""
        # Servisi başlat
        result = await self.error_service.initialize()
        
        # Sonuçları doğrula
        self.assertTrue(result)
        self.assertTrue(self.error_service.initialized)
        self.assertEqual(self.error_service.error_log_path, self.error_logs_dir)
        
        # Kategori dizinlerini kontrol et
        for category in ["database", "network", "telegram_api", "general"]:
            category_path = os.path.join(self.error_logs_dir, category)
            self.assertTrue(os.path.exists(category_path))
            
        return result
        
    async def _test_error_logging(self):
        """Hata loglama işlevini test eder"""
        # Servisi başlat
        await self.error_service.initialize()
        
        # Farklı türlerde hatalar oluştur
        db_error_id = await self.error_service.log_error(
            error_type="ConnectionError",
            message="Test veritabanı bağlantı hatası",
            source="test_services",
            severity="ERROR",
            category="DATABASE"
        )
        
        api_error_id = await self.error_service.log_error(
            error_type="APIError",
            message="Test Telegram API hatası",
            source="test_services",
            severity="CRITICAL",
            category="TELEGRAM_API"
        )
        
        # Sonuçları doğrula
        self.assertIsNotNone(db_error_id)
        self.assertIsNotNone(api_error_id)
        
        # Hata log dosyalarını kontrol et
        db_log_path = os.path.join(self.error_logs_dir, "database")
        api_log_path = os.path.join(self.error_logs_dir, "telegram_api")
        
        db_files = os.listdir(db_log_path)
        api_files = os.listdir(api_log_path)
        
        self.assertTrue(len(db_files) > 0)
        self.assertTrue(len(api_files) > 0)
        
        return {"db_error_id": db_error_id, "api_error_id": api_error_id}
        
    async def _test_error_resolution(self):
        """Hata çözme işlevini test eder"""
        # Servisi başlat
        await self.error_service.initialize()
        
        # Test hatası oluştur
        error_id = await self.error_service.log_error(
            error_type="TestError",
            message="Çözülecek test hatası",
            source="test_services",
            severity="WARNING",
            category="GENERAL"
        )
        
        # Hatayı çöz
        resolved = await self.error_service.resolve_error(
            error_id=error_id,
            resolution_info="Test tarafından çözüldü"
        )
        
        # Sonuçları doğrula
        self.assertTrue(resolved)
        
        # Çözülen hatayı kontrol et
        for error in self.db.error_records:
            if error["error_id"] == error_id:
                self.assertTrue(error["resolved"])
                self.assertEqual(error["resolution_info"], "Test tarafından çözüldü")
                self.assertIsNotNone(error["resolution_timestamp"])
                
        return error_id
        
    async def _test_error_category_stats(self):
        """Kategori bazlı hata istatistiklerini test eder"""
        # Servisi başlat
        await self.error_service.initialize()
        
        # Farklı kategorilerde hatalar oluştur
        for i in range(3):
            await self.error_service.log_error(
                error_type=f"DBError{i}",
                message=f"Veritabanı hatası {i}",
                source="test_services",
                severity="ERROR",
                category="DATABASE"
            )
            
        for i in range(2):
            await self.error_service.log_error(
                error_type=f"NetError{i}",
                message=f"Ağ hatası {i}",
                source="test_services",
                severity="WARNING",
                category="NETWORK"
            )
            
        for i in range(4):
            await self.error_service.log_error(
                error_type=f"APIError{i}",
                message=f"API hatası {i}",
                source="test_services",
                severity="CRITICAL" if i == 0 else "ERROR",
                category="TELEGRAM_API"
            )
            
        # Kategori istatistikleri al
        stats = await self.error_service.get_category_stats(hours=24)
        
        # Sonuçları doğrula
        self.assertIsNotNone(stats)
        self.assertIn("DATABASE", stats)
        self.assertIn("NETWORK", stats)
        self.assertIn("TELEGRAM_API", stats)
        
        # Sayıları kontrol et
        self.assertEqual(stats["DATABASE"], 3)
        self.assertEqual(stats["NETWORK"], 2)
        self.assertEqual(stats["TELEGRAM_API"], 4)
        
        return stats
    
    def test_all(self):
        """Tüm testleri çalıştırır"""
        loop = asyncio.get_event_loop()
        
        # Analytics testleri
        loop.run_until_complete(self._test_analytics_initialize())
        loop.run_until_complete(self._test_analytics_generate_report())
        loop.run_until_complete(self._test_analytics_export_csv())
        
        # Error testleri
        loop.run_until_complete(self._test_error_initialize())
        loop.run_until_complete(self._test_error_logging())
        loop.run_until_complete(self._test_error_resolution())
        loop.run_until_complete(self._test_error_category_stats())
        
        print("Tüm testler başarıyla tamamlandı!")
        

if __name__ == "__main__":
    unittest.main() 