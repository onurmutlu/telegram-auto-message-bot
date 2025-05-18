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

from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_session
from app.services.base import BaseService
from app.services.service_manager import ServiceManager

logger = logging.getLogger(__name__)

class HealthService(BaseService):
    """
    Sistem ve servislerin sağlık durumunu izleyen servis.
    - Sistemin genel durumunu izler (CPU, RAM, disk kullanımı)
    - Servislerin çalışma durumunu kontrol eder
    - Veritabanı bağlantısını test eder
    - Telegram bağlantısını kontrol eder
    - İstatistikleri toplar ve raporlar
    """
    
    service_name = "health_service"
    default_interval = 300  # 5 dakika
    
    def __init__(self, client: TelegramClient = None, service_manager: ServiceManager = None, db: AsyncSession = None):
        """
        HealthService başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            service_manager: Servis yöneticisi
            db: Veritabanı oturumu
        """
        super().__init__(name="health_service")
        self.client = client
        self.service_manager = service_manager
        self.db = db
        self.status_history = []  # Son durumları sakla
        self.running = False
        self.initialized = False
        self.last_check_time = None
        self.health_data = {
            "system": {},
            "services": {},
            "database": {},
            "telegram": {}
        }
    
    async def initialize(self) -> bool:
        """Servisi başlat."""
        self.db = self.db or next(get_session())
        self.initialized = True
        self.last_check_time = datetime.now()
        logger.info("Health monitoring service initialized")
        return True
    
    async def start_monitoring(self):
        """Düzenli sağlık kontrolü döngüsünü başlat."""
        logger.info("Starting health monitoring loop")
        self.running = True
        
        while self.running:
            try:
                # Sağlık durumunu kontrol et
                await self._check_health()
                
                # Sağlık durumunu raporla
                await self._report_health()
                
                # Belirlenen aralıkta bekle
                try:
                    interval_str = os.environ.get("HEALTH_CHECK_INTERVAL", str(self.default_interval))
                    # Yorum satırını veya boşlukları temizle
                    interval_str = interval_str.split('#')[0].strip()
                    interval = int(interval_str)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid HEALTH_CHECK_INTERVAL value: {interval_str}, using default: {self.default_interval}")
                    interval = self.default_interval
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {str(e)}", exc_info=True)
                await asyncio.sleep(60)  # Hata durumunda 1 dakika bekle
    
    async def _check_health(self):
        """Tüm sistemin sağlık durumunu kontrol et."""
        logger.debug("Checking system health")
        self.last_check_time = datetime.now()
        
        try:
            # Sistem sağlık durumu
            self.health_data["system"] = await self._check_system_health()
            
            # Servis sağlık durumu
            self.health_data["services"] = await self._check_services_health()
            
            # Veritabanı sağlık durumu
            self.health_data["database"] = await self._check_database_health()
            
            # Telegram bağlantı durumu
            self.health_data["telegram"] = await self._check_telegram_health()
            
            # Sonuçları history'e ekle (sadece son 10 kontrolü tut)
            self.status_history.append({
                "timestamp": self.last_check_time.isoformat(),
                "data": self.health_data
            })
            
            if len(self.status_history) > 10:
                self.status_history.pop(0)
                
            # Sorunlu durumlarda tepki ver
            await self._react_to_health_issues()
                
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", exc_info=True)
            self.health_data["status"] = "error"
            self.health_data["error"] = str(e)
    
    async def _react_to_health_issues(self):
        """Sağlık sorunlarına otomatik tepki ver."""
        try:
            # Veritabanı bağlantısı sorunları
            db_status = self.health_data["database"].get("status")
            if db_status != "healthy":
                logger.warning("Database connection issues detected, attempting to reconnect")
                try:
                    # Veritabanını yeniden bağla
                    if self.db:
                        try:
                            self.db.rollback()  # Önce rollback yapalım
                        except:
                            pass
                        try:
                            self.db.close()
                        except:
                            pass
                    self.db = next(get_session())
                    # Test et
                    query_result = self.db.execute(text("SELECT 1 as result"))
                    result = query_result.fetchone()
                    if result and result.result == 1:
                        logger.info("Database reconnection successful")
                except Exception as db_error:
                    logger.error(f"Database reconnection failed: {str(db_error)}")
            
            # Telegram bağlantı sorunları
            tg_status = self.health_data["telegram"].get("status")
            if tg_status != "healthy" and tg_status != "disabled" and self.client:
                logger.warning("Telegram bağlantı sorunları tespit edildi, yeniden bağlanmaya çalışılıyor")
                try:
                    # Önce bağlantıyı kapat
                    try:
                        if self.client.is_connected():
                            await self.client.disconnect()
                            await asyncio.sleep(2)
                    except:
                        pass
                    
                    # Bağlantıyı yeniden kur
                    await self.client.connect()
                    # Bağlantı sonrası kısa bir bekleme
                    await asyncio.sleep(3)
                    
                    # Bağlantıyı kontrol et
                    if self.client.is_connected():
                        logger.info("Telegram bağlantısı yeniden kuruldu")
                        
                        # Oturum durumunu kontrol et
                        try:
                            is_authorized = await self.client.is_user_authorized()
                            auth_status = "açık" if is_authorized else "kapalı"
                            logger.info(f"Telegram oturum durumu: {auth_status}")
                            
                            # Ping testi
                            if is_authorized:
                                me = await self.client.get_me()
                                if me:
                                    logger.info(f"Telegram ping başarılı, kullanıcı: {me.first_name}")
                                else:
                                    logger.warning("Telegram get_me() başarısız")
                        except Exception as auth_error:
                            logger.error(f"Oturum kontrolü sırasında hata: {auth_error}")
                    else:
                        logger.error("Telegram bağlantısı yeniden kurulamadı")
                        
                except Exception as tg_error:
                    logger.error(f"Telegram yeniden bağlantı hatası: {str(tg_error)}")
                    
                # Telegram sağlık durumunu hemen güncelle
                self.health_data["telegram"] = await self._check_telegram_health()
                    
        except Exception as e:
            logger.error(f"Error during health issue reactions: {str(e)}")
    
    async def _check_system_health(self) -> Dict[str, Any]:
        """Sistem kaynaklarının sağlık durumunu kontrol et."""
        try:
            # CPU kullanımı
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # RAM kullanımı
            memory = psutil.virtual_memory()
            ram_usage = memory.percent
            ram_available = memory.available / 1024 / 1024  # MB
            
            # Disk kullanımı
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent
            disk_free = disk.free / 1024 / 1024 / 1024  # GB
            
            # Çalışma süresi
            uptime = time.time() - psutil.boot_time()
            
            return {
                "cpu_usage": cpu_usage,
                "ram_usage": ram_usage,
                "ram_available_mb": round(ram_available, 2),
                "disk_usage": disk_usage,
                "disk_free_gb": round(disk_free, 2),
                "uptime_seconds": uptime,
                "status": "healthy" if cpu_usage < 90 and ram_usage < 90 and disk_usage < 90 else "warning"
            }
        except Exception as e:
            logger.error(f"Error checking system health: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _check_services_health(self) -> Dict[str, Any]:
        """Tüm servislerin sağlık durumunu kontrol et."""
        services_status = {}
        
        # Service Manager varsa servis durumlarını al
        if self.service_manager:
            for name, service in self.service_manager.services.items():
                try:
                    # Servisin durumunu getir
                    if hasattr(service, 'get_status') and callable(service.get_status):
                        status = await service.get_status()
                        services_status[name] = status
                    else:
                        # Basit durum kontrolü
                        services_status[name] = {
                            "running": getattr(service, "running", False),
                            "initialized": getattr(service, "initialized", False)
                        }
                except Exception as e:
                    logger.error(f"Error checking service '{name}': {str(e)}")
                    services_status[name] = {
                        "status": "error",
                        "error": str(e)
                    }
        
        return {
            "services_count": len(services_status),
            "services": services_status,
            "status": "healthy" if all(s.get("running", False) for s in services_status.values()) else "warning"
        }
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Veritabanı sağlık durumunu kontrol et."""
        if not self.db:
            return {
                "connected": False,
                "status": "error",
                "error": "No database connection available"
            }
            
        try:
            # Basit bir sorgu ile veritabanı bağlantısını test et
            start_time = time.time()
            
            # Rollback yaparak önceki transaction hataları temizle
            try:
                self.db.rollback()
            except:
                pass
                
            query_result = self.db.execute(text("SELECT 1 as result"))
            result = query_result.fetchone()
            query_time = time.time() - start_time
            
            if result and result.result == 1:
                # Veritabanı boyutu kontrolü
                try:
                    # PostgreSQL veritabanı boyutu
                    size_query = text("""
                        SELECT pg_database_size(current_database()) / 1024 / 1024 as size_mb,
                               current_database() as db_name
                    """)
                    size_result = self.db.execute(size_query)
                    db_info = size_result.fetchone()
                    if db_info:
                        size_mb = db_info.size_mb
                        db_name = db_info.db_name
                    else:
                        size_mb = 0
                        db_name = "unknown"
                except Exception as size_error:
                    logger.debug(f"Error getting database size: {str(size_error)}")
                    size_mb = 0
                    db_name = "unknown"
                
                return {
                    "connected": True,
                    "query_time_ms": round(query_time * 1000, 2),
                    "size_mb": size_mb if size_mb else 0,
                    "db_name": db_name,
                    "status": "healthy"
                }
            else:
                return {
                    "connected": False,
                    "status": "error",
                    "error": "Database query returned unexpected result"
                }
        except Exception as e:
            logger.error(f"Error checking database health: {str(e)}", exc_info=True)
            return {
                "connected": False,
                "status": "error",
                "error": str(e)
            }
    
    async def _check_telegram_health(self) -> Dict[str, Any]:
        """Telegram bağlantısı sağlık durumunu kontrol et."""
        if not self.client:
            return {
                "connected": False,
                "status": "disabled",
                "error": "Telegram client is disabled in minimal mode"
            }
        
        try:
            # Client bağlı mı kontrol et
            is_connected = self.client.is_connected()
            connection_status = "connected" if is_connected else "disconnected"
            
            # Bağlı değilse bağlan
            reconnect_attempt = 0
            max_reconnect_attempts = 2
            
            while not is_connected and reconnect_attempt < max_reconnect_attempts:
                reconnect_attempt += 1
                try:
                    logger.info(f"Health check: Telegram bağlantısı kuruluyor... (Deneme {reconnect_attempt}/{max_reconnect_attempts})")
                    await self.client.connect()
                    # Bağlantı sonrası kısa bir bekleme
                    await asyncio.sleep(2)
                    is_connected = self.client.is_connected()
                    connection_status = "reconnected" if is_connected else "connection_failed"
                    if is_connected:
                        logger.info("Health check: Telegram bağlantısı başarıyla kuruldu!")
                        break
                except Exception as conn_error:
                    logger.error(f"Health check: Telegram bağlantı hatası (Deneme {reconnect_attempt}/{max_reconnect_attempts}): {conn_error}")
                    await asyncio.sleep(3)
            
            # Mevcut oturum bilgisi
            is_authorized = False
            auth_status = "unknown"
            try:
                if is_connected:
                    is_authorized = await self.client.is_user_authorized()
                    auth_status = "authorized" if is_authorized else "unauthorized"
                    logger.info(f"Health check: Yetkilendirme durumu: {auth_status}")
                else:
                    auth_status = "connection_failed"
                    logger.warning("Health check: Bağlantı kurulamadığı için yetkilendirme kontrolü yapılamadı.")
            except Exception as auth_error:
                logger.error(f"Health check: Telegram yetkilendirme hatası: {auth_error}")
                auth_status = "auth_error"
                # Yetkilendirme hatası bağlantı hatası olabilir, yeniden bağlanmayı dene
                if is_connected:
                    try:
                        logger.info("Health check: Yetkilendirme hatası nedeniyle yeniden bağlanılıyor...")
                        await self.client.disconnect()
                        await asyncio.sleep(2)
                        await self.client.connect()
                        await asyncio.sleep(2)
                        is_connected = self.client.is_connected()
                        if is_connected:
                            is_authorized = await self.client.is_user_authorized()
                            auth_status = "authorized" if is_authorized else "unauthorized"
                            logger.info(f"Health check: Yeniden bağlantı sonrası yetkilendirme durumu: {auth_status}")
                    except Exception as reconnect_err:
                        logger.error(f"Health check: Yeniden bağlantı hatası: {reconnect_err}")
            
            # Ping testi 
            ping_success = False
            user_info = None
            ping_ms = None
            
            try:
                if is_connected and is_authorized:
                    ping_attempt = 0
                    max_ping_attempts = 2
                    while ping_attempt < max_ping_attempts:
                        ping_attempt += 1
                        try:
                            start_time = time.time()
                            me = await self.client.get_me()
                            ping_ms = round((time.time() - start_time) * 1000, 2)
                            
                            if me:
                                ping_success = True
                                user_info = {
                                    "user_id": me.id,
                                    "username": me.username if hasattr(me, 'username') else None,
                                    "first_name": me.first_name if hasattr(me, 'first_name') else "Unknown"
                                }
                                logger.info(f"Health check: Telegram ping başarılı: {ping_ms}ms, Kullanıcı: {user_info['first_name']}")
                                break
                            else:
                                logger.warning(f"Health check: get_me() None döndürdü (Deneme {ping_attempt}/{max_ping_attempts}).")
                                await asyncio.sleep(2)
                        except Exception as ping_attempt_err:
                            logger.error(f"Health check: Ping hatası (Deneme {ping_attempt}/{max_ping_attempts}): {ping_attempt_err}")
                            await asyncio.sleep(2)
                    
                    if not ping_success:
                        logger.warning("Health check: Tüm ping denemeleri başarısız.")
            except Exception as ping_error:
                logger.error(f"Health check: Telegram ping işlemi sırasında beklenmedik hata: {ping_error}")
            
            # Genel sağlık durumu belirleme
            health_status = "healthy"
            if not is_connected:
                health_status = "error"
                error_message = "Bağlantı kurulamadı"
            elif not is_authorized:
                health_status = "warning"
                error_message = "Oturum açılmadı"
            elif not ping_success:
                health_status = "warning"
                error_message = "Ping başarısız"
            else:
                error_message = None
            
            # Sonuçları dön
            result = {
                "connected": is_connected,
                "connection_status": connection_status,
                "authorized": is_authorized,
                "auth_status": auth_status,
                "status": health_status
            }
            
            # Hata mesajı varsa ekle
            if error_message:
                result["error"] = error_message
            
            # Ping bilgileri başarılıysa ekle
            if ping_success:
                result["ping_ms"] = ping_ms
                result.update(user_info)
            
            return result
                
        except Exception as e:
            logger.error(f"Health check: Telegram sağlık kontrolü sırasında beklenmedik hata: {str(e)}", exc_info=True)
            return {
                "connected": False,
                "status": "error",
                "error": str(e)
            }
    
    async def _report_health(self):
        """Sağlık durumunu raporla."""
        # Genel sistem durumunu belirle
        is_system_healthy = self.health_data["system"].get("status") == "healthy"
        is_db_healthy = self.health_data["database"].get("status") == "healthy"
        is_telegram_healthy = self.health_data["telegram"].get("status") == "healthy"
        
        # Tüm servislerin durumu
        services_status = self.health_data["services"].get("status", "unknown")
        
        # Genel durum
        overall_status = "healthy" if (is_system_healthy and is_db_healthy and is_telegram_healthy and services_status == "healthy") else "warning"
        
        # Log olarak rapor et
        if overall_status == "healthy":
            logger.info("System health check: OK")
        else:
            logger.warning(f"System health check: {overall_status.upper()}")
            
            # Sorunlu kısımları detaylı logla
            if not is_system_healthy:
                logger.warning(f"System resources issues: CPU {self.health_data['system'].get('cpu_usage')}%, RAM {self.health_data['system'].get('ram_usage')}%")
            
            if not is_db_healthy:
                logger.warning(f"Database issues: {self.health_data['database'].get('error', 'Unknown error')}")
            
            if not is_telegram_healthy:
                logger.warning(f"Telegram issues: {self.health_data['telegram'].get('error', 'Unknown error')}")
            
            if services_status != "healthy":
                problematic_services = [name for name, data in self.health_data["services"].get("services", {}).items() 
                                        if not data.get("running", False)]
                logger.warning(f"Problematic services: {', '.join(problematic_services)}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Servis durumunu al."""
        return {
            "name": self.service_name,
            "running": self.running,
            "initialized": self.initialized,
            "last_check": self.last_check_time.isoformat() if self.last_check_time else None,
            "health_status": {
                "system": self.health_data["system"].get("status", "unknown"),
                "database": self.health_data["database"].get("status", "unknown"),
                "telegram": self.health_data["telegram"].get("status", "unknown"),
                "services": self.health_data["services"].get("status", "unknown")
            }
        }
    
    async def get_detailed_status(self) -> Dict[str, Any]:
        """Detaylı durum raporu al."""
        return {
            "current": self.health_data,
            "history": self.status_history,
            "last_update": self.last_check_time.isoformat() if self.last_check_time else None
        }
    
    async def cleanup(self):
        """Servis kapatılırken temizlik işleri."""
        self.running = False
        logger.info("Health monitoring service stopped")
    
    async def _start(self) -> bool:
        """BaseService için başlatma metodu"""
        return await self.initialize()
    
    async def _stop(self) -> bool:
        """BaseService için durdurma metodu"""
        try:
            self.initialized = False
            self.running = False
            await self.cleanup()
            return True
        except Exception as e:
            logger.error(f"HealthService durdurma hatası: {e}")
            return False
    
    async def _update(self) -> bool:
        """Periyodik güncelleme metodu"""
        await self._check_health()
        return True

    async def force_connect(self) -> Dict[str, Any]:
        """Telegram bağlantısını zorla yenileme ve test etme."""
        if not self.client:
            return {
                "connected": False,
                "status": "disabled",
                "error": "Telegram client is not initialized"
            }
        
        logger.info("Telegram bağlantısı zorla yenileniyor...")
        
        try:
            # İşlemden önce bağlantıyı kapat (temiz başlangıç)
            if self.client.is_connected():
                await self.client.disconnect()
                await asyncio.sleep(2)
            
            # Sistem bilgilerini al
            from app.core.config import settings
            import platform
            
            # Benzersiz bir oturum adı oluştur (eski oturum dosyalarıyla çakışmasını önlemek için)
            original_session_name = settings.SESSION_NAME
            device_info = f"Python {platform.python_version()} on {platform.system()} {platform.release()}"
            
            # Oturum dosyası dizini kontrolü ve oluşturma
            import pathlib
            if not hasattr(settings, 'SESSIONS_DIR'):
                # SESSIONS_DIR tanımlı değilse otomatik tanımla
                BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent
                settings.SESSIONS_DIR = BASE_DIR / "app" / "sessions"
                # Dizinin var olduğundan emin ol
                settings.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
                logger.info(f"SESSIONS_DIR otomatik tanımlandı: {settings.SESSIONS_DIR}")
            
            # Oturum dosyasını kontrol et
            session_path = settings.SESSIONS_DIR / f"{original_session_name}.session"
            
            # Telethon sürüm uyumluluğu kontrolü
            try:
                import sqlite3
                import os
                import shutil
                
                if os.path.exists(session_path):
                    # Dosya boyutunu kontrol et
                    file_size = os.path.getsize(session_path)
                    if file_size < 100:
                        logger.warning(f"Oturum dosyası çok küçük: {file_size} bayt, muhtemelen bozuk")
                        # Yedekle ve sil
                        backup_path = f"{session_path}.backup.{int(time.time())}"
                        shutil.copy2(session_path, backup_path)
                        logger.info(f"Bozuk oturum dosyası yedeklendi: {backup_path}")
                        os.remove(session_path)
                        logger.info(f"Bozuk oturum dosyası silindi")
                    else:
                        # Oturum dosyasının SQLite şemasını kontrol et
                        try:
                            conn = sqlite3.connect(session_path)
                            cursor = conn.cursor()
                            
                            # sessions tablosunun yapısını kontrol et
                            cursor.execute("PRAGMA table_info(sessions)")
                            columns = cursor.fetchall()
                            
                            # Sütun sayısını kontrol et
                            column_count = len(columns)
                            column_names = [col[1] for col in columns]
                            
                            logger.info(f"Oturum tablosunda {column_count} sütun bulundu: {', '.join(column_names)}")
                            
                            # Eğer 5 sütun yerine 4 sütun varsa (eski Telethon) yeni oturum oluştur
                            if column_count != 5:
                                logger.warning(f"Oturum dosyası sürüm uyumsuzluğu tespit edildi: {column_count} sütun (5 olması gerekiyor)")
                                
                                # Yedekle
                                backup_path = f"{session_path}.v{column_count}_backup.{int(time.time())}"
                                conn.close()
                                shutil.copy2(session_path, backup_path)
                                logger.info(f"Eski format oturum dosyası yedeklendi: {backup_path}")
                                
                                # Sil
                                os.remove(session_path)
                                logger.info(f"Eski format oturum dosyası silindi")
                            
                            else:
                                # Bağlantı kapat
                                conn.close()
                                
                        except sqlite3.OperationalError as e:
                            logger.warning(f"Oturum dosyası SQLite hatası: {e}")
                            if "no such table" in str(e).lower():
                                # Oturum dosyası bozuk olabilir, yedekle ve sil
                                backup_path = f"{session_path}.corrupted.{int(time.time())}"
                                shutil.copy2(session_path, backup_path)
                                logger.info(f"Bozuk oturum dosyası yedeklendi: {backup_path}")
                                os.remove(session_path)
                                logger.info(f"Bozuk oturum dosyası silindi")
                        except Exception as schema_err:
                            logger.error(f"Oturum dosyası şema kontrolü hatası: {schema_err}")
            except Exception as check_err:
                logger.error(f"Oturum dosyası kontrolü hatası: {check_err}")
            
            # Aşırı yeniden deneme için client'ı yeniden oluştur
            from telethon import TelegramClient
            
            # Daha güçlü bağlantı için client yeniden oluştur (isteğe bağlı)
            try:
                logger.info("Güçlü bağlantı için TelegramClient yeniden oluşturuluyor...")
                # API_ID ve API_HASH değerlerini al
                api_id = settings.API_ID
                api_hash = settings.API_HASH
                
                # API_HASH'i düzgün şekilde işle
                if hasattr(api_hash, 'get_secret_value'):
                    api_hash_value = api_hash.get_secret_value()
                else:
                    api_hash_value = api_hash
                
                # Telethon sürümünü al
                import telethon
                logger.info(f"Kullanılan Telethon sürümü: {telethon.__version__}")
                
                # Temiz client oluştur
                old_client = self.client
                self.client = TelegramClient(
                    original_session_name,
                    api_id,
                    api_hash_value,
                    proxy=None,
                    connection_retries=int(settings.TG_CONNECTION_RETRIES),
                    device_model=device_info,
                    system_version=platform.release(),
                    app_version='1.0',
                    lang_code='tr',
                    system_lang_code='tr'
                )
                logger.info("TelegramClient yeniden oluşturuldu.")
            except Exception as recreate_err:
                logger.error(f"TelegramClient yeniden oluşturma hatası: {recreate_err}")
                # Eski client'ı kullanmaya devam et
                self.client = old_client
            
            # Yeniden bağlan
            connect_attempt = 0
            max_connect_attempts = 5  # Maximum deneme sayısını artırdık
            
            while connect_attempt < max_connect_attempts:
                connect_attempt += 1
                try:
                    logger.info(f"Telegram'a yeniden bağlanılıyor (Deneme {connect_attempt}/{max_connect_attempts})...")
                    await self.client.connect()
                    await asyncio.sleep(3)  # Bağlantı kurulduktan sonra bekle
                    
                    if self.client.is_connected():
                        logger.info("Telegram bağlantısı başarıyla kuruldu!")
                        
                        # Oturum durumunu kontrol et
                        try:
                            is_authorized = await self.client.is_user_authorized()
                            auth_status = "authorized" if is_authorized else "unauthorized"
                            logger.info(f"Oturum durumu: {auth_status}")
                            
                            if is_authorized:
                                # Ping testi
                                start_time = time.time()
                                me = await self.client.get_me()
                                ping_ms = round((time.time() - start_time) * 1000, 2)
                                
                                if me:
                                    logger.info(f"Kullanıcı bilgileri: {me.first_name} (ID: {me.id})")
                                    logger.info(f"Ping: {ping_ms}ms")
                                    
                                    # BOT_USERNAME'i ayarla
                                    try:
                                        username = me.username if hasattr(me, 'username') and me.username else ""
                                        settings.BOT_USERNAME = username
                                        logger.info(f"BOT_USERNAME ayarlandı: {username}")
                                    except Exception as username_err:
                                        logger.warning(f"BOT_USERNAME ayarlanamadı: {username_err}")
                                    
                                    return {
                                        "connected": True,
                                        "authorized": True,
                                        "user_id": me.id,
                                        "first_name": me.first_name,
                                        "username": me.username if hasattr(me, 'username') else None,
                                        "ping_ms": ping_ms,
                                        "status": "healthy"
                                    }
                                else:
                                    logger.warning("Kullanıcı bilgileri alınamadı")
                            else:
                                logger.warning("Oturum yetkilendirilmemiş, yeniden yetkilendirme gerekli.")
                                return {
                                    "connected": True,
                                    "authorized": False,
                                    "status": "unauthorized",
                                    "message": "Oturum yetkilendirilmemiş, yeniden yetkilendirme gerekli."
                                }
                                
                        except Exception as auth_err:
                            logger.error(f"Yetkilendirme kontrolü hatası: {auth_err}")
                    else:
                        logger.warning(f"Bağlantı kurulamadı, tekrar deneniyor...")
                        await asyncio.sleep(3)
                        
                except Exception as conn_error:
                    logger.error(f"Bağlantı hatası (Deneme {connect_attempt}/{max_connect_attempts}): {conn_error}")
                    
                    # Telethon oturum hatası kontrolü
                    if "table sessions has 4 columns but 5 values were supplied" in str(conn_error) or "table sessions has 5 columns but 4 values were supplied" in str(conn_error):
                        logger.warning("Telethon sürüm uyumsuzluğu tespit edildi, oturum dosyası yeniden oluşturuluyor...")
                        
                        # Oturum dosyasını sil
                        try:
                            import os
                            
                            # Oturum dosyası dizini kontrolü
                            import pathlib
                            if not hasattr(settings, 'SESSIONS_DIR'):
                                # SESSIONS_DIR tanımlı değilse otomatik tanımla
                                BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent
                                settings.SESSIONS_DIR = BASE_DIR / "app" / "sessions"
                                settings.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
                                logger.info(f"SESSIONS_DIR otomatik tanımlandı: {settings.SESSIONS_DIR}")
                                
                            session_path = settings.SESSIONS_DIR / f"{original_session_name}.session"
                            if os.path.exists(session_path):
                                # Yedekle
                                import shutil
                                backup_path = f"{session_path}.version_mismatch.{int(time.time())}"
                                shutil.copy2(session_path, backup_path)
                                logger.info(f"Eski format oturum dosyası yedeklendi: {backup_path}")
                                
                                # Sil
                                os.remove(session_path)
                                logger.info(f"Eski format oturum dosyası silindi")
                        except Exception as del_err:
                            logger.error(f"Oturum dosyası silme hatası: {del_err}")
                        
                        # Daha fazla deneme yapma, yeni oturum oluşturulacak
                        break
                    
                    await asyncio.sleep(5)  # Daha uzun bekleme süresi
            
            # Tüm denemeler başarısız oldu
            return {
                "connected": False,
                "status": "error",
                "error": "Maksimum bağlantı denemesi aşıldı"
            }
                
        except Exception as e:
            logger.error(f"Telegram bağlantısı yenileme hatası: {str(e)}", exc_info=True)
            return {
                "connected": False,
                "status": "error",
                "error": str(e)
            }