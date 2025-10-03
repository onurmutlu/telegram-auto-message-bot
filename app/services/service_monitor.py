import asyncio
import logging
import sys
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.core.config import settings
from app.services.service_manager import get_service_manager, ServiceManager

logger = logging.getLogger(__name__)

class ServiceMonitor:
    """
    Tüm servislerin durumunu izleyen ve yöneten CLI arayüzü.
    """
    
    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.service_manager = None
        self.status_interval = 10  # 10 saniyede bir durum güncelle
        self.running = False
        self.status_task = None
        self.status_file = "runtime/logs/service_status.json"
    
    async def initialize(self):
        """Servis izleyiciyi başlat"""
        logger.info("ServiceMonitor başlatılıyor...")
        
        # Servis yöneticisine bağlan
        self.service_manager = await get_service_manager()
        if not self.service_manager:
            logger.error("ServiceManager bulunamadı!")
            return False
        
        # Status dizinini oluştur
        os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
        
        return True
    
    async def start(self):
        """Servis izleme döngüsünü başlat"""
        if not self.service_manager:
            success = await self.initialize()
            if not success:
                logger.error("ServiceMonitor başlatılamadı!")
                return False
        
        logger.info("ServiceMonitor başlatıldı.")
        self.running = True
        
        # Ana izleme döngüsü
        self.status_task = asyncio.create_task(self._monitor_loop())
        
        return True
    
    async def stop(self):
        """Servis izleme döngüsünü durdur"""
        logger.info("ServiceMonitor durduruluyor...")
        self.running = False
        
        if self.status_task and not self.status_task.done():
            self.status_task.cancel()
            try:
                await self.status_task
            except asyncio.CancelledError:
                pass
        
        logger.info("ServiceMonitor durduruldu.")
        return True
    
    async def _monitor_loop(self):
        """Ana izleme döngüsü"""
        try:
            while self.running:
                # Tüm servislerin durumunu al
                all_status = await self.service_manager.get_all_services_status()
                
                # Durum bilgilerini işle ve kaydet
                await self._process_status(all_status)
                
                # Durum bilgilerini dosyaya kaydet (frontend için)
                self._save_status_file(all_status)
                
                # Belirlenen aralık kadar bekle
                await asyncio.sleep(self.status_interval)
                
        except asyncio.CancelledError:
            logger.info("Servis izleme döngüsü iptal edildi.")
        except Exception as e:
            logger.error(f"Servis izleme hatası: {e}")
    
    async def _process_status(self, status_data: Dict[str, Dict[str, Any]]):
        """Servis durum bilgilerini işler"""
        # Toplam servis sayımızı al
        total_services = len(status_data)
        active_services = sum(1 for s in status_data.values() if s.get("running", False))
        
        logger.info(f"Servis durumu: {active_services}/{total_services} aktif")
        
        # Sorunlu servisleri kontrol et
        problem_services = []
        for name, status in status_data.items():
            if not status.get("running", False) and name != "monitor":
                problem_services.append(name)
            
            # Hata sayısı belirli bir eşiği aşmış mı kontrol et
            error_count = status.get("error_count", 0)
            if error_count > 5:  # 5'ten fazla hata varsa uyarı ver
                logger.warning(f"{name} servisi çok sayıda hata ({error_count}) bildirdi!")
        
        # Sorunlu servisler varsa rapor et
        if problem_services:
            logger.warning(f"Çalışmayan servisler: {', '.join(problem_services)}")
            
            # Servis yeniden başlatma denemesi yapabilir
            if settings.AUTO_RESTART_SERVICES:
                for service_name in problem_services:
                    logger.info(f"{service_name} servisi yeniden başlatılıyor...")
                    try:
                        await self.service_manager.restart_service(service_name)
                    except Exception as e:
                        logger.error(f"{service_name} servisi yeniden başlatılamadı: {e}")
    
    def _save_status_file(self, status_data: Dict[str, Dict[str, Any]]):
        """Servis durum bilgilerini JSON dosyasına kaydeder"""
        try:
            # datetime nesnelerini string'e dönüştür
            clean_data = self._clean_status_for_json(status_data)
            
            with open(self.status_file, 'w') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "services": clean_data
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Durum dosyası kaydedilemedi: {e}")
    
    def _clean_status_for_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """JSON serialize edilemeyecek verileri temizler"""
        clean_data = {}
        
        for key, value in data.items():
            if isinstance(value, dict):
                clean_data[key] = self._clean_status_for_json(value)
            elif isinstance(value, datetime):
                clean_data[key] = value.isoformat()
            elif isinstance(value, (str, int, float, bool, type(None))):
                clean_data[key] = value
            else:
                try:
                    # Dönüştürülebilir mi kontrol et
                    json.dumps(value)
                    clean_data[key] = value
                except (TypeError, OverflowError):
                    # JSON'a dönüştürülemiyorsa string olarak kaydet
                    clean_data[key] = str(value)
        
        return clean_data
    
    async def get_service_details(self, service_name: str) -> Dict[str, Any]:
        """Belirli bir servisin detaylı durum bilgisini döndürür"""
        if not self.service_manager:
            await self.initialize()
        
        # Servis var mı kontrol et
        if service_name not in self.service_manager.services:
            return {"error": f"{service_name} servisi bulunamadı!"}
        
        try:
            # Servisin kendi durum bilgisini al
            service = self.service_manager.services[service_name]
            status = await service.get_status() if hasattr(service, 'get_status') else {}
            
            # Veritabanından ek bilgileri al
            query = text("""
                SELECT started_at, last_active, error_count, status,
                       created_at, updated_at
                FROM service_status
                WHERE service_name = :name
                ORDER BY id DESC
                LIMIT 1
            """)
            
            # Servis yapılandırma bilgilerini al
            config_query = text("""
                SELECT key, value, type, description, updated_at
                FROM service_config
                WHERE service_name = :name
                ORDER BY key
            """)
            
            result = await self.db.execute(query, {"name": service_name})
            db_status = result.fetchone()
            
            config_result = await self.db.execute(config_query, {"name": service_name})
            config_rows = config_result.fetchall()
            
            # Sonuçları birleştir
            details = {
                "name": service_name,
                "status": status,
                "db_status": {
                    "started_at": db_status.started_at.isoformat() if db_status and db_status.started_at else None,
                    "last_active": db_status.last_active.isoformat() if db_status and db_status.last_active else None,
                    "error_count": db_status.error_count if db_status else 0,
                    "status": db_status.status if db_status else "unknown",
                    "created_at": db_status.created_at.isoformat() if db_status and db_status.created_at else None,
                    "updated_at": db_status.updated_at.isoformat() if db_status and db_status.updated_at else None
                } if db_status else {},
                "config": {}
            }
            
            # Yapılandırma bilgilerini ekle
            for row in config_rows:
                details["config"][row.key] = {
                    "value": row.value,
                    "type": row.type,
                    "description": row.description,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None
                }
            
            return details
            
        except Exception as e:
            logger.error(f"Servis detayları alınamadı ({service_name}): {e}")
            return {"error": str(e)}
    
    async def restart_service(self, service_name: str) -> Dict[str, Any]:
        """Belirli bir servisi yeniden başlatır"""
        if not self.service_manager:
            await self.initialize()
        
        try:
            result = await self.service_manager.restart_service(service_name)
            if result:
                return {"success": True, "message": f"{service_name} servisi başarıyla yeniden başlatıldı."}
            else:
                return {"success": False, "message": f"{service_name} servisi yeniden başlatılamadı."}
        except Exception as e:
            logger.error(f"{service_name} servisi yeniden başlatılamadı: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_service_config(self, service_name: str, key: str, value: Any) -> Dict[str, Any]:
        """Servis yapılandırmasını günceller"""
        if not self.service_manager:
            await self.initialize()
        
        try:
            # Servis var mı kontrol et
            if service_name not in self.service_manager.services:
                return {"success": False, "error": f"{service_name} servisi bulunamadı!"}
            
            service = self.service_manager.services[service_name]
            
            # Servisin save_config metodu var mı kontrol et
            if hasattr(service, 'save_config') and callable(service.save_config):
                result = await service.save_config(key, value)
                if result:
                    return {"success": True, "message": f"{service_name} servisi için {key} yapılandırması güncellendi."}
                else:
                    return {"success": False, "message": f"{service_name} servisi için {key} yapılandırması güncellenemedi."}
            else:
                # Doğrudan veritabanına kaydet
                query = text("""
                    INSERT INTO service_config (service_name, key, value, updated_at)
                    VALUES (:service_name, :key, :value, NOW())
                    ON CONFLICT (service_name, key) DO UPDATE
                    SET value = :value, updated_at = NOW()
                """)
                
                await self.db.execute(query, {
                    "service_name": service_name,
                    "key": key,
                    "value": str(value)
                })
                await self.db.commit()
                
                return {"success": True, "message": f"{service_name} servisi için {key} yapılandırması güncellendi."}
                
        except Exception as e:
            logger.error(f"Servis yapılandırması güncellenemedi ({service_name}.{key}): {e}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}

# Tek bir ServiceMonitor örneği
_service_monitor = None

async def get_service_monitor(db=None) -> ServiceMonitor:
    """ServiceMonitor örneğini döndürür, yoksa yeni oluşturur."""
    global _service_monitor
    if _service_monitor is None:
        _service_monitor = ServiceMonitor(db=db)
        await _service_monitor.initialize()
    return _service_monitor 