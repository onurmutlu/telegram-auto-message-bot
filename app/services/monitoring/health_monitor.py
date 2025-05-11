"""
# ============================================================================ #
# Dosya: health_monitor.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/monitoring/health_monitor.py
# İşlev: Servis sağlığı izleme ve metrik toplama sistemi
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import asyncio
import logging
import json
import time
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
import aiohttp
from enum import Enum
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class HealthStatus(str, Enum):
    """Servis sağlık durumu enum"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"
    UNKNOWN = "unknown"

class ServiceHealth:
    """Tek bir servisin sağlık durumu modeli"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.status = HealthStatus.UNKNOWN
        self.last_check = datetime.now()
        self.uptime = 0
        self.start_time = None
        self.error_count = 0
        self.last_error = None
        self.last_error_time = None
        self.consecutive_failures = 0
        self.metrics = {}
        self.details = {}
    
    def update(self, status: HealthStatus = None, **kwargs):
        """Sağlık durumunu günceller"""
        now = datetime.now()
        
        if status:
            # Durumu güncelle
            self.status = status
        
        # Start time yoksa ayarla
        if not self.start_time and status == HealthStatus.HEALTHY:
            self.start_time = now
        
        # Uptime hesapla
        if self.start_time:
            self.uptime = (now - self.start_time).total_seconds()
        
        # Error sayacı ve bilgisi
        if "error" in kwargs and kwargs["error"]:
            self.error_count += 1
            self.last_error = str(kwargs["error"])
            self.last_error_time = now
            self.consecutive_failures += 1
        elif status == HealthStatus.HEALTHY:
            self.consecutive_failures = 0
        
        # Son kontrol zamanı
        self.last_check = now
        
        # Ek metrikler
        if "metrics" in kwargs and kwargs["metrics"]:
            self.metrics.update(kwargs["metrics"])
        
        # Ek detaylar
        if "details" in kwargs and kwargs["details"]:
            self.details.update(kwargs["details"])
    
    def to_dict(self) -> Dict[str, Any]:
        """Dict formatına dönüştürür"""
        return {
            "service_name": self.service_name,
            "status": self.status,
            "last_check": self.last_check.isoformat(),
            "uptime_seconds": self.uptime,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "consecutive_failures": self.consecutive_failures,
            "metrics": self.metrics,
            "details": self.details
        }

class HealthMonitor(BaseService):
    """
    Servis sağlığı izleme ve metrik toplama sistemi.
    
    Bu servis:
    1. Tüm aktif servislerin sağlık durumunu düzenli olarak kontrol eder
    2. Metrikleri toplar ve kaydeder
    3. Sağlık API endpoint'leri sağlar
    4. Kritik servislerin durumunda değişiklik olduğunda uyarı gönderir
    """
    
    service_name = "health_monitor"
    default_interval = 30  # 30 saniyede bir kontrol et
    
    def __init__(self, **kwargs):
        """
        HealthMonitor servisi başlatıcısı
        
        Args:
            **kwargs: BaseService parametreleri
        """
        super().__init__(**kwargs)
        
        # Servis sağlık durumları
        self.service_health = {}
        
        # Kritik servisler listesi
        self.critical_services = set([
            "user", "group", "message", "reply_service", "direct_message"
        ])
        
        # Metrik depolama
        self.metrics_history = {}
        self.history_limit = 100  # Her metrik için saklanacak maksimum geçmiş değer sayısı
        
        # Webhook'lar
        self.alert_webhooks = []
        if hasattr(self, 'config') and self.config:
            # Config'den webhook URL'lerini al
            webhook_urls = self.config.get('ALERT_WEBHOOKS', '')
            if webhook_urls:
                self.alert_webhooks = [url.strip() for url in webhook_urls.split(',') if url.strip()]
        
        # API endpoint'i
        self.api_enabled = True
        self.api_host = "0.0.0.0"
        self.api_port = 8081
        self.api_task = None
        
        # İzleme ayarları
        self.check_interval = 30  # Saniye
        self.alert_threshold = 3  # Arka arkaya başarısız kontrol sayısı
        
        # Durum
        self.is_running = False
    
    async def _start(self) -> bool:
        """
        Health monitor servisini başlatır
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("Health Monitor servisi başlatılıyor...")
            
            # Tüm servisleri STARTING durumuna getir
            for service_name in self.services:
                if service_name != self.service_name:
                    self.service_health[service_name] = ServiceHealth(service_name)
                    self.service_health[service_name].update(status=HealthStatus.STARTING)
            
            # Kritik servislerin durumunu kontrol et
            await self._check_all_services()
            
            # API endpoint'i başlat (opsiyonel)
            if self.api_enabled:
                self.api_task = asyncio.create_task(self._start_api_server())
            
            self.is_running = True
            logger.info("Health Monitor servisi başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"Health Monitor başlatma hatası: {str(e)}")
            return False
    
    async def _stop(self) -> bool:
        """
        Health monitor servisini durdurur
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("Health Monitor servisi durduruluyor...")
            
            # API endpoint'ini durdur
            if self.api_task and not self.api_task.done():
                self.api_task.cancel()
            
            # Tüm servisleri STOPPING durumuna getir
            for service_name, health in self.service_health.items():
                health.update(status=HealthStatus.STOPPING)
            
            self.is_running = False
            logger.info("Health Monitor servisi durduruldu")
            return True
            
        except Exception as e:
            logger.error(f"Health Monitor durdurma hatası: {str(e)}")
            return False
    
    async def _update(self) -> None:
        """
        Periyodik sağlık kontrolü ve metrik toplama
        """
        try:
            # Tüm servislerin durumunu kontrol et
            await self._check_all_services()
            
            # Metrikleri kaydet
            self._record_metrics()
            
            # Uyarı gönder (gerekirse)
            await self._send_alerts()
            
        except Exception as e:
            logger.error(f"Health Monitor güncelleme hatası: {str(e)}")
    
    async def _check_all_services(self) -> None:
        """
        Tüm servislerin sağlık durumunu kontrol eder
        """
        for service_name, service in self.services.items():
            if service_name == self.service_name:
                continue  # Kendimizi kontrol etmeyelim
                
            try:
                # Servis nesnesini ve durumunu kontrol et
                if not service:
                    # Servis nesnesi yok
                    if service_name in self.service_health:
                        self.service_health[service_name].update(
                            status=HealthStatus.UNHEALTHY,
                            error="Servis nesnesi bulunamadı",
                            details={"reason": "missing_service_object"}
                        )
                    else:
                        # Yeni servis kaydı oluştur
                        self.service_health[service_name] = ServiceHealth(service_name)
                        self.service_health[service_name].update(
                            status=HealthStatus.UNHEALTHY,
                            error="Servis nesnesi bulunamadı", 
                            details={"reason": "missing_service_object"}
                        )
                    continue
                
                # Servis sağlık durumunu alın (get_status metodu varsa)
                if hasattr(service, 'get_status') and callable(service.get_status):
                    try:
                        status_data = await service.get_status()
                        
                        # Durumu analiz et
                        is_healthy = True
                        if "running" in status_data and not status_data["running"]:
                            is_healthy = False
                        
                        # Servis sağlık durumunu güncelle
                        if service_name not in self.service_health:
                            self.service_health[service_name] = ServiceHealth(service_name)
                        
                        # Metrikler
                        metrics = {}
                        for key, value in status_data.items():
                            if isinstance(value, (int, float)) and key not in ("running", "service"):
                                metrics[key] = value
                        
                        # Durumu güncelle
                        health_status = HealthStatus.HEALTHY if is_healthy else HealthStatus.DEGRADED
                        self.service_health[service_name].update(
                            status=health_status,
                            metrics=metrics,
                            details=status_data
                        )
                        
                    except Exception as e:
                        logger.warning(f"Servis durumu alınırken hata ({service_name}): {str(e)}")
                        if service_name not in self.service_health:
                            self.service_health[service_name] = ServiceHealth(service_name)
                        
                        self.service_health[service_name].update(
                            status=HealthStatus.DEGRADED,
                            error=f"Durum kontrolü hatası: {str(e)}",
                            details={"exception": str(e)}
                        )
                else:
                    # get_status metodu yok, sadece running özelliğine bakabiliriz
                    if hasattr(service, 'running'):
                        is_running = bool(service.running)
                        
                        if service_name not in self.service_health:
                            self.service_health[service_name] = ServiceHealth(service_name)
                        
                        health_status = HealthStatus.HEALTHY if is_running else HealthStatus.DEGRADED
                        self.service_health[service_name].update(
                            status=health_status,
                            details={"running": is_running}
                        )
                    else:
                        # Durum kontrolü yapılamıyor
                        if service_name not in self.service_health:
                            self.service_health[service_name] = ServiceHealth(service_name)
                        
                        self.service_health[service_name].update(
                            status=HealthStatus.UNKNOWN,
                            details={"reason": "no_status_method"}
                        )
            
            except Exception as e:
                # Genel hata
                logger.error(f"Servis sağlık kontrolü hatası ({service_name}): {str(e)}")
                if service_name not in self.service_health:
                    self.service_health[service_name] = ServiceHealth(service_name)
                
                self.service_health[service_name].update(
                    status=HealthStatus.DEGRADED,
                    error=f"Kontrol hatası: {str(e)}"
                )
    
    def _record_metrics(self) -> None:
        """
        Toplanan metrikleri kaydeder ve geçmişi günceller
        """
        current_time = datetime.now().isoformat()
        
        # Her servis için metrikleri kaydet
        for service_name, health in self.service_health.items():
            if not health.metrics:
                continue
            
            if service_name not in self.metrics_history:
                self.metrics_history[service_name] = {}
            
            # Her metrik için geçmiş değerleri güncelle
            for metric_name, value in health.metrics.items():
                metric_key = f"{service_name}.{metric_name}"
                
                if metric_key not in self.metrics_history:
                    self.metrics_history[metric_key] = []
                
                # Yeni değeri ekle
                self.metrics_history[metric_key].append({
                    "timestamp": current_time,
                    "value": value
                })
                
                # Limit aşıldıysa eski değerleri kaldır
                if len(self.metrics_history[metric_key]) > self.history_limit:
                    self.metrics_history[metric_key] = self.metrics_history[metric_key][-self.history_limit:]
    
    async def _send_alerts(self) -> None:
        """
        Kritik servis durumları için uyarı gönderir
        """
        critical_issues = []
        
        # Kritik servislerin durumunu kontrol et
        for service_name in self.critical_services:
            if service_name not in self.service_health:
                continue
            
            health = self.service_health[service_name]
            
            # UNHEALTHY durumunda veya çok sayıda ardışık hata varsa uyarı gönder
            if (health.status == HealthStatus.UNHEALTHY or 
                    health.consecutive_failures >= self.alert_threshold):
                critical_issues.append({
                    "service": service_name,
                    "status": health.status,
                    "error": health.last_error,
                    "consecutive_failures": health.consecutive_failures
                })
        
        # Kritik sorun varsa webhook'lara gönder
        if critical_issues and self.alert_webhooks:
            alert_data = {
                "timestamp": datetime.now().isoformat(),
                "service": "health_monitor",
                "event": "critical_service_issue",
                "issues": critical_issues
            }
            
            # Webhook'lara gönder
            for webhook_url in self.alert_webhooks:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            webhook_url, 
                            json=alert_data,
                            timeout=10
                        ) as response:
                            if response.status >= 400:
                                logger.warning(f"Webhook hatası ({webhook_url}): HTTP {response.status}")
                except Exception as e:
                    logger.error(f"Webhook gönderme hatası: {str(e)}")
    
    async def _start_api_server(self) -> None:
        """
        Sağlık ve metrik API'si için basit bir HTTP sunucusu başlatır
        """
        from aiohttp import web
        
        # API rotaları
        routes = web.RouteTableDef()
        
        @routes.get('/health')
        async def health_handler(request):
            """Tüm servislerin sağlık durumunu döndürür"""
            health_data = {
                "status": self._get_overall_status(),
                "timestamp": datetime.now().isoformat(),
                "services": {
                    name: health.to_dict() 
                    for name, health in self.service_health.items()
                }
            }
            return web.json_response(health_data)
        
        @routes.get('/health/{service}')
        async def service_health_handler(request):
            """Belirli bir servisin sağlık durumunu döndürür"""
            service_name = request.match_info['service']
            
            if service_name not in self.service_health:
                return web.json_response({"error": "Service not found"}, status=404)
            
            return web.json_response(self.service_health[service_name].to_dict())
        
        @routes.get('/metrics')
        async def metrics_handler(request):
            """Tüm metrikleri döndürür"""
            return web.json_response(self.metrics_history)
        
        @routes.get('/metrics/{service}')
        async def service_metrics_handler(request):
            """Belirli bir servisin metriklerini döndürür"""
            service_name = request.match_info['service']
            
            # Servis metriklerini filtrele
            service_metrics = {}
            for metric_key, values in self.metrics_history.items():
                if metric_key.startswith(f"{service_name}."):
                    service_metrics[metric_key] = values
            
            if not service_metrics:
                return web.json_response({"error": "No metrics found for service"}, status=404)
            
            return web.json_response(service_metrics)
        
        # Uygulama oluştur ve çalıştır
        app = web.Application()
        app.add_routes(routes)
        
        try:
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, self.api_host, self.api_port)
            
            logger.info(f"Health API sunucusu başlatılıyor: {self.api_host}:{self.api_port}")
            await site.start()
            
            # Servis durduğunda veya görev iptal edildiğinde temizle
            try:
                while self.is_running:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info("Health API sunucusu durduruluyor...")
            finally:
                await runner.cleanup()
                
        except Exception as e:
            logger.error(f"Health API sunucusu başlatma hatası: {str(e)}")
    
    def _get_overall_status(self) -> HealthStatus:
        """
        Sistemin genel sağlık durumunu belirler
        
        Returns:
            HealthStatus: Genel sağlık durumu
        """
        if not self.service_health:
            return HealthStatus.UNKNOWN
        
        # Kritik servis kontrolü
        critical_services_status = [
            self.service_health[name].status
            for name in self.critical_services
            if name in self.service_health
        ]
        
        # Herhangi bir kritik servis UNHEALTHY ise, genel durum UNHEALTHY
        if any(status == HealthStatus.UNHEALTHY for status in critical_services_status):
            return HealthStatus.UNHEALTHY
        
        # Herhangi bir kritik servis DEGRADED ise, genel durum DEGRADED
        if any(status == HealthStatus.DEGRADED for status in critical_services_status):
            return HealthStatus.DEGRADED
        
        # Tüm servisler HEALTHY ise, genel durum HEALTHY
        all_services_status = [health.status for health in self.service_health.values()]
        if all(status == HealthStatus.HEALTHY for status in all_services_status):
            return HealthStatus.HEALTHY
        
        # En az bir servis HEALTHY, diğerleri UNKNOWN veya STOPPING/STARTING
        if any(status == HealthStatus.HEALTHY for status in all_services_status):
            return HealthStatus.DEGRADED
        
        # Diğer durumlar
        return HealthStatus.UNKNOWN
    
    async def get_service_health(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Belirli bir servisin sağlık durumunu döndürür
        
        Args:
            service_name: Servis adı
            
        Returns:
            Optional[Dict[str, Any]]: Servis sağlık bilgileri
        """
        if service_name not in self.service_health:
            return None
        
        return self.service_health[service_name].to_dict()
    
    async def get_critical_services_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Kritik servislerin durumunu döndürür
        
        Returns:
            Dict[str, Dict[str, Any]]: Kritik servislerin sağlık bilgileri
        """
        return {
            name: self.service_health[name].to_dict()
            for name in self.critical_services
            if name in self.service_health
        }
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servis durum bilgilerini döndürür
        
        Returns:
            Dict[str, Any]: Durum bilgileri
        """
        return {
            'service': self.service_name,
            'running': self.is_running,
            'overall_status': self._get_overall_status(),
            'monitored_services': len(self.service_health),
            'critical_services': len(self.critical_services),
            'issues_count': sum(1 for h in self.service_health.values() if h.status != HealthStatus.HEALTHY),
            'api_enabled': self.api_enabled,
            'api_endpoint': f"{self.api_host}:{self.api_port}" if self.api_enabled else None
        }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servis istatistiklerini döndürür
        
        Returns:
            Dict[str, Any]: İstatistik bilgileri
        """
        services_by_status = {}
        for status in HealthStatus:
            services_by_status[status] = sum(1 for h in self.service_health.values() if h.status == status)
        
        return {
            'monitored_services': len(self.service_health),
            'metrics_count': sum(len(metrics) for metrics in self.metrics_history.values()),
            'services_by_status': services_by_status,
            'critical_services_healthy': sum(
                1 for name in self.critical_services 
                if name in self.service_health and self.service_health[name].status == HealthStatus.HEALTHY
            ),
            'last_check': datetime.now().isoformat()
        } 