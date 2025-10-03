"""
# ============================================================================ #
# Dosya: health_service.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/monitoring/health_service.py
# İşlev: Sistem ve servislerin sağlık durumunu izler ve raporlar.
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

import logging
import asyncio
import time
import psutil
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import os
import platform

from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_session
from app.services.base_service import BaseService
from app.services.service_manager import ServiceManager

logger = logging.getLogger(__name__)

class HealthService(BaseService):
    """
    Bot sağlık durumunu takip eden servis.
    
    Bu servis şunları yapar:
    - Bot ve sistem sağlık durumunu izler
    - Telegram API bağlantısını kontrol eder
    - Sistem kaynaklarını takip eder
    - Hata durumlarını raporlar
    """
    
    def __init__(self, client: TelegramClient, db=None):
        """Health servisini başlat."""
        super().__init__(name="health_service", db=db)
        self.client = client
        self.service_name = "health_service"
        self.start_time = time.time()
        self.connected = False
        self.api_ping = 0
        self.system_stats = {}
    
    async def run(self):
        """Servis ana döngüsü."""
        self.running = True
        logger.info("Health servisi çalışıyor...")
        
        try:
            # İlk çalıştırma
            await self._get_system_info()
            
            # Servis çalışırken aktif kal
            while self.running:
                # Client bağlantısı kontrol et
                if self.client:
                    self.connected = self.client.is_connected()
                    
                    # Bağlantı yoksa bağlan
                    if not self.connected and self.running:
                        try:
                            logger.info("Telegram bağlantısı kuruluyor...")
                            await self.client.connect()
                            self.connected = self.client.is_connected()
                            
                            if self.connected:
                                logger.info("Telegram bağlantısı yeniden kuruldu")
                        except Exception as e:
                            logger.error(f"Telegram bağlantısı kurulamadı: {e}")
                
                # Sistem bilgilerini güncelle
                await self._get_system_info()
                
                # 30 saniye bekle
                await asyncio.sleep(30)
                
        except asyncio.CancelledError:
            logger.info("Health servisi iptal edildi")
            self.running = False
        except Exception as e:
            logger.error(f"Health servisi çalışırken hata: {e}")
            self.running = False
    
    async def _get_system_info(self):
        """Sistem bilgilerini topla."""
        try:
            # Bellek kullanımı
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # CPU kullanımı
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Uptime
            uptime = time.time() - self.start_time
            
            # Sistem istatistiklerini güncelle
            self.system_stats = {
                "uptime": uptime,
                "memory_used_percent": memory.percent,
                "disk_used_percent": disk.percent,
                "cpu_percent": cpu_percent,
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "connected": self.connected,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Sistem bilgileri alınırken hata: {e}")
    
    async def get_status(self):
        """Servis durum bilgisini döndür."""
        status = await super().get_status()
        status.update({
            "connected": self.connected,
            "api_ping": self.api_ping,
            "uptime": time.time() - self.start_time,
            "system": self.system_stats
        })
        return status