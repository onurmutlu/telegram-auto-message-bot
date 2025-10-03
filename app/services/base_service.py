#!/usr/bin/env python3
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)

class ConfigAdapter:
    """Yapılandırma adaptörü sınıfı."""
    
    @staticmethod
    def get_config(key: str, default: Any = None) -> Any:
        """Yapılandırma değerini al."""
        from app.core.config import settings
        return getattr(settings, key, default)

class BaseService(ABC):
    """
    Tüm servisler için temel sınıf.
    """
    
    def __init__(self, name: str = None, db: AsyncSession = None):
        self.service_name = name or self.__class__.__name__.lower()
        self.db = db
        self.running = False
        self.error_count = 0
        self.start_time = datetime.now()
        self.initialized = False
        self.config = {}
    
    async def initialize(self) -> bool:
        """Servisi başlatma işlemleri."""
        self.initialized = True
        # Yapılandırmaları yükle
        await self.load_config()
        return True
    
    async def start(self) -> None:
        """Servis çalışma döngüsü."""
        if not self.initialized:
            await self.initialize()
        
        self.running = True
        logger.info(f"{self.service_name} servisi başlatıldı.")
    
    async def stop(self) -> bool:
        """Servisi durdurma işlemleri."""
        self.running = False
        logger.info(f"{self.service_name} servisi durduruldu.")
        return True
    
    async def get_status(self) -> Dict[str, Any]:
        """Servisin durum bilgilerini döndürür."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            "name": self.service_name,
            "running": self.running,
            "initialized": self.initialized,
            "uptime": uptime,
            "error_count": self.error_count
        }
    
    async def load_config(self) -> Dict[str, Any]:
        """Veritabanından servis yapılandırmasını yükler."""
        if not self.db:
            return {}
        
        try:
            # Konfigürasyon tablosu yoksa oluştur
            create_table_query = text("""
                CREATE TABLE IF NOT EXISTS service_config (
                    id SERIAL PRIMARY KEY,
                    service_name VARCHAR(100) NOT NULL,
                    key VARCHAR(100) NOT NULL,
                    value TEXT,
                    type VARCHAR(20) NOT NULL DEFAULT 'string',
                    description TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(service_name, key)
                )
            """)
            await self.db.execute(create_table_query)
            await self.db.commit()
            
            # Servis yapılandırmasını yükle
            query = text("""
                SELECT key, value, type FROM service_config
                WHERE service_name = :service_name
            """)
            result = await self.db.execute(query, {"service_name": self.service_name})
            config_rows = result.fetchall()
            
            config = {}
            for row in config_rows:
                config[row.key] = self._convert_value(row.value, row.type)
            
            self.config = config
            logger.info(f"{self.service_name} için {len(config)} yapılandırma parametresi yüklendi.")
            return config
        except Exception as e:
            logger.error(f"{self.service_name} yapılandırması yüklenirken hata: {e}")
            return {}
    
    async def save_config(self, key: str, value: Any, value_type: str = None, description: str = None) -> bool:
        """Servis yapılandırmasını veritabanına kaydeder."""
        if not self.db:
            return False
        
        try:
            # Veri tipini belirle
            if value_type is None:
                if isinstance(value, bool):
                    value_type = "boolean"
                elif isinstance(value, int):
                    value_type = "integer"
                elif isinstance(value, float):
                    value_type = "float"
                elif isinstance(value, dict) or isinstance(value, list):
                    value_type = "json"
                else:
                    value_type = "string"
            
            # String'e dönüştür
            if value_type == "json":
                import json
                str_value = json.dumps(value)
            else:
                str_value = str(value)
            
            # Yapılandırmayı kaydet
            query = text("""
                INSERT INTO service_config (service_name, key, value, type, description, updated_at)
                VALUES (:service_name, :key, :value, :type, :description, NOW())
                ON CONFLICT (service_name, key) DO UPDATE
                SET value = :value, type = :type, updated_at = NOW()
            """)
            
            await self.db.execute(query, {
                "service_name": self.service_name,
                "key": key,
                "value": str_value,
                "type": value_type,
                "description": description
            })
            await self.db.commit()
            
            # Yerelde güncelle
            self.config[key] = value
            
            logger.info(f"{self.service_name} için '{key}' yapılandırması güncellendi.")
            return True
        except Exception as e:
            logger.error(f"{self.service_name} yapılandırması kaydedilirken hata: {e}")
            await self.db.rollback()
            return False
    
    def _convert_value(self, value: str, value_type: str) -> Any:
        """String değeri belirtilen tipe dönüştürür."""
        if value is None:
            return None
            
        try:
            if value_type == "integer":
                return int(value)
            elif value_type == "float":
                return float(value)
            elif value_type == "boolean":
                return value.lower() in ("true", "yes", "1")
            elif value_type == "json":
                import json
                return json.loads(value)
            else:
                return value
        except Exception:
            return value
    
    async def _start(self) -> bool:
        """
        Servis başlatma özel işlemleri.
        
        Alt sınıflar tarafından uygulanmalıdır.
        
        Returns:
            bool: Başlatma başarılı ise True
        """
        pass
    
    async def _stop(self) -> bool:
        """
        Servis durdurma özel işlemleri.
        
        Alt sınıflar tarafından uygulanmalıdır.
        
        Returns:
            bool: Durdurma başarılı ise True
        """
        pass
    
    async def _update(self) -> bool:
        """
        Servisin periyodik olarak çalıştıracağı iş.
        
        Alt sınıflar tarafından uygulanmalıdır.
        
        Returns:
            bool: İşlem başarılı ise True
        """
        pass 