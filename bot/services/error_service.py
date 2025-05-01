#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Error Service - Uygulama hatalarını izleyen ve raporlayan servis
"""

import os
import sys
import asyncio
import logging
import traceback
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from sqlalchemy import func, select, and_, or_, desc, asc, text, update, insert
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from functools import wraps
import socket

from bot.services.base_service import BaseService
from bot.services.event_service import Event, on_event
from database.db_connection import get_db_pool

# Log ayarları
logger = logging.getLogger(__name__)

class ErrorRecord:
    """Hata kayıt sınıfı"""
    def __init__(self, error_type: str, message: str, source: str, 
                 details: Dict = None, traceback_info: str = None, 
                 severity: str = "ERROR", created_at: datetime = None,
                 category: str = "GENERAL"):
        self.error_id = int(time.time() * 1000)  # Unix timestamp milisaniye
        self.error_type = error_type
        self.message = message
        self.source = source
        self.details = details or {}
        self.traceback_info = traceback_info
        self.severity = severity  # DEBUG, INFO, WARNING, ERROR, CRITICAL
        self.created_at = created_at or datetime.now()
        self.resolved = False
        self.resolved_at = None
        self.resolution_info = None
        self.category = category  # Yeni: Hata kategorisi (DATABASE, NETWORK, TELEGRAM_API, vb.)
        
    def to_dict(self) -> Dict:
        """Sınıfı sözlük formatına dönüştürür"""
        return {
            'error_id': self.error_id,
            'error_type': self.error_type,
            'message': self.message,
            'source': self.source,
            'details': self.details,
            'traceback_info': self.traceback_info,
            'severity': self.severity,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_info': self.resolution_info,
            'category': self.category  # Yeni: Kategori bilgisi
        }
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'ErrorRecord':
        """Sözlükten ErrorRecord nesnesi oluşturur"""
        record = cls(
            error_type=data.get('error_type', 'UNKNOWN'),
            message=data.get('message', ''),
            source=data.get('source', ''),
            details=data.get('details', {}),
            traceback_info=data.get('traceback_info'),
            severity=data.get('severity', 'ERROR'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            category=data.get('category', 'GENERAL')  # Yeni: Kategori bilgisi
        )
        record.error_id = data.get('error_id', record.error_id)
        record.resolved = data.get('resolved', False)
        if data.get('resolved_at'):
            record.resolved_at = datetime.fromisoformat(data['resolved_at'])
        record.resolution_info = data.get('resolution_info')
        return record

class ErrorService(BaseService):
    """
    Hata izleme ve raporlama servisi - Uygulama hatalarını takip eder ve raporlar
    """
    
    def __init__(self, client=None, config=None, db=None, stop_event=None):
        """
        ErrorService constructor
        
        Args:
            client: Telegram istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            stop_event: Durdurma eventi
        """
        super().__init__("error", client, config, db, stop_event)
        self.db_pool = get_db_pool()
        self.errors = {}  # error_id -> ErrorRecord
        self.error_queue = asyncio.Queue()
        self.processing_task = None
        self.max_retained_errors = 1000
        self.error_log_path = "logs/errors"
        self.notify_critical = True
        self.notify_error = True
        self.alert_threshold = 5  # Belirli bir sürede bu sayıdan fazla hata olursa uyarı
        self.alert_window = 300  # Saniye cinsinden uyarı penceresi (5 dakika)
        self.hostname = socket.gethostname()
        
        # Yeni: Kategori bazlı eşikler
        self.category_thresholds = {
            "DATABASE": 3,       # Veritabanı hatalarında düşük eşik
            "TELEGRAM_API": 10,  # Telegram API hatalarında daha yüksek eşik
            "NETWORK": 5,        # Ağ hatalarında orta eşik
            "GENERAL": 5         # Genel hatalar için orta eşik
        }
        
        # Yeni: Kategori bazlı izleme pencereleri (saniye)
        self.category_windows = {
            "DATABASE": 600,      # Veritabanı hataları için 10 dakika
            "TELEGRAM_API": 300,  # Telegram API hataları için 5 dakika  
            "NETWORK": 300,       # Ağ hataları için 5 dakika
            "GENERAL": 300        # Genel hatalar için 5 dakika
        }
        
    async def initialize(self) -> bool:
        """
        Servisi başlat ve gerekli kaynakları yükle
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("ErrorService başlatılıyor...")
            
            # Log dizinini oluştur
            os.makedirs(self.error_log_path, exist_ok=True)
            
            # Yeni: Kategori bazlı log dizinleri oluştur
            for category in self.category_thresholds.keys():
                category_path = os.path.join(self.error_log_path, category.lower())
                os.makedirs(category_path, exist_ok=True)
            
            # Konfigürasyondan ayarları yükle (varsa)
            if self.config and 'error_service' in self.config:
                self.max_retained_errors = self.config['error_service'].get('max_retained_errors', 1000)
                self.error_log_path = self.config['error_service'].get('error_log_path', self.error_log_path)
                self.notify_critical = self.config['error_service'].get('notify_critical', True)
                self.notify_error = self.config['error_service'].get('notify_error', True)
                self.alert_threshold = self.config['error_service'].get('alert_threshold', 5)
                self.alert_window = self.config['error_service'].get('alert_window', 300)
                
                # Yeni: Kategori bazlı eşikleri konfigürasyondan yükle
                if 'category_thresholds' in self.config['error_service']:
                    self.category_thresholds.update(self.config['error_service']['category_thresholds'])
                
                # Yeni: Kategori bazlı izleme pencerelerini konfigürasyondan yükle
                if 'category_windows' in self.config['error_service']:
                    self.category_windows.update(self.config['error_service']['category_windows'])
            
            # Mevcut hata kayıtlarını yükle
            await self._load_error_records()
            
            self.initialized = True
            logger.info("ErrorService başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"ErrorService başlatılırken hata: {str(e)}", exc_info=True)
            return False
    
    async def start(self) -> bool:
        """
        Servisi başlat
        
        Returns:
            bool: Başarılı ise True
        """
        if not self.initialized:
            if not await self.initialize():
                return False
        
        try:
            # Hata işleme görevini başlat
            self.processing_task = asyncio.create_task(self._process_errors())
            
            # Python uncaught exception handler'ı yerleştir
            sys.excepthook = self._handle_uncaught_exception
            
            self.is_running = True
            logger.info("ErrorService çalışıyor")
            return True
            
        except Exception as e:
            logger.error(f"ErrorService başlatılırken hata: {str(e)}", exc_info=True)
            return False
    
    async def stop(self) -> None:
        """
        Servisi durdur
        
        Returns:
            None
        """
        # İşleme görevi çalışıyorsa durdur
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        # Tüm hata kayıtlarını kaydet
        await self._save_error_records()
        
        # Original excepthook'u geri getir
        sys.excepthook = sys.__excepthook__
            
        self.is_running = False
        logger.info("ErrorService durduruldu")
    
    def _handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        """
        İşlenmemiş Python istisnalarını yakalar
        
        Args:
            exc_type: İstisna tipi
            exc_value: İstisna değeri
            exc_traceback: İstisna stack trace
        """
        if issubclass(exc_type, KeyboardInterrupt):
            # KeyboardInterrupt (Ctrl+C) için özel düşünebiliriz
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
            
        # Traceback bilgisini string'e çevir
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_text = ''.join(tb_lines)
        
        # Hata kaydı oluştur
        error_record = ErrorRecord(
            error_type=exc_type.__name__,
            message=str(exc_value),
            source="UNCAUGHT_EXCEPTION",
            traceback_info=tb_text,
            severity="CRITICAL",
            details={
                'hostname': self.hostname,
                'pid': os.getpid()
            }
        )
        
        # Queue'ya ekle (senkron)
        asyncio.run_coroutine_threadsafe(
            self.error_queue.put(error_record), 
            asyncio.get_event_loop()
        )
        
        # Orijinal excepthook'u çağır
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        
    async def _process_errors(self):
        """
        Hata kuyruğunu işleyen arka plan görevi
        """
        try:
            while not self.stop_event.is_set():
                # Kuyruktan bir hata al
                error_record = await self.error_queue.get()
                
                try:
                    # Hatayı işle
                    await self._handle_error(error_record)
                except Exception as e:
                    logger.error(f"Hata işlenirken beklenmeyen hata: {str(e)}", exc_info=True)
                finally:
                    # İşlemi tamamlandı olarak işaretle
                    self.error_queue.task_done()
                    
        except asyncio.CancelledError:
            logger.info("Hata işleme görevi iptal edildi")
            raise
        except Exception as e:
            logger.error(f"Hata işleme görevinde beklenmeyen hata: {str(e)}", exc_info=True)
    
    async def _handle_error(self, error: ErrorRecord):
        """
        Bir hata kaydını işler
        
        Args:
            error: İşlenecek hata kaydı
        """
        try:
            # Hatayı kayıtlara ekle
            self.errors[error.error_id] = error
            
            # Eski kayıtları temizle (max_retained_errors sayısını geçmemek için)
            if len(self.errors) > self.max_retained_errors:
                # En eski kayıtlardan başlayarak temizle
                old_errors = sorted(
                    [e for e in self.errors.values() if not e.resolved],
                    key=lambda x: x.created_at
                )
                # Kaç kayıt temizleyeceğimizi hesapla
                to_remove = len(self.errors) - self.max_retained_errors
                # Temizle
                for e in old_errors[:to_remove]:
                    del self.errors[e.error_id]
            
            # Dosyaya kaydet
            self._log_error_to_file(error)
            
            # Hata olayını yayınla
            await self._emit_error_event(error)
            
            # Hata eşiğini kontrol et (kaynak ve kategori bazlı)
            is_threshold_exceeded = await self._check_error_threshold(error.source, error.category)
            
            # Eşik aşıldıysa uyarı gönder
            if is_threshold_exceeded:
                await self._emit_error_alert(error.source, error.category)
                
            logger.info(f"Hata işlendi: {error.error_id} - {error.error_type} ({error.category})")
            
        except Exception as e:
            logger.error(f"Hata işlenirken beklenmeyen hata: {str(e)}", exc_info=True)
    
    def _log_error_to_file(self, error: ErrorRecord):
        """
        Hatayı dosyaya kaydeder
        
        Args:
            error: Kaydedilecek hata
        """
        try:
            # Önce ana log dizinine kaydet
            timestamp = error.created_at.strftime("%Y%m%d-%H%M%S")
            filename = f"{timestamp}_{error.error_id}_{error.severity.lower()}.json"
            filepath = os.path.join(self.error_log_path, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(error.to_dict(), f, ensure_ascii=False, indent=2)
            
            # Yeni: Kategori bazlı dizine de kaydet
            category_path = os.path.join(self.error_log_path, error.category.lower())
            category_filepath = os.path.join(category_path, filename)
            
            with open(category_filepath, 'w', encoding='utf-8') as f:
                json.dump(error.to_dict(), f, ensure_ascii=False, indent=2)
                
            logger.debug(f"Hata dosyaya kaydedildi: {filepath} ve {category_filepath}")
            
        except Exception as e:
            logger.error(f"Hata dosyaya kaydedilirken beklenmeyen hata: {str(e)}")
    
    async def _load_error_records(self):
        """
        Mevcut hata kayıtlarını yükler
        """
        try:
            if not os.path.exists(self.error_log_path):
                return
                
            # Son 24 saatteki hataları yükle
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            files_to_check = [
                os.path.join(self.error_log_path, f"errors_{today}.json"),
                os.path.join(self.error_log_path, f"errors_{yesterday}.json")
            ]
            
            for file_path in files_to_check:
                if not os.path.exists(file_path):
                    continue
                    
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            error_dict = json.loads(line.strip())
                            error = ErrorRecord.from_dict(error_dict)
                            
                            # Son 24 saat içindeki hataları yükle
                            if error.created_at > datetime.now() - timedelta(days=1):
                                self.errors[error.error_id] = error
                                
                        except Exception as e:
                            logger.error(f"Hata kaydı yüklenirken beklenmeyen hata: {str(e)}")
                            
            logger.info(f"{len(self.errors)} hata kaydı belleğe yüklendi")
                
        except Exception as e:
            logger.error(f"Hata kayıtları yüklenirken beklenmeyen hata: {str(e)}", exc_info=True)
    
    async def _save_error_records(self):
        """
        Hata kayıtlarını dosyaya kaydeder
        """
        try:
            if not self.errors:
                return
                
            # Günlük log dosyası adı
            today = datetime.now().strftime('%Y-%m-%d')
            log_file = os.path.join(self.error_log_path, f"errors_{today}.json")
            
            # Hatayı JSON formatına dönüştür ve dosyaya yaz
            with open(log_file, 'w', encoding='utf-8') as f:
                for error in self.errors.values():
                    error_json = json.dumps(error.to_dict(), ensure_ascii=False, default=str)
                    f.write(error_json + '\n')
                    
            logger.info(f"{len(self.errors)} hata kaydı dosyaya kaydedildi")
                
        except Exception as e:
            logger.error(f"Hata kayıtları kaydedilirken beklenmeyen hata: {str(e)}", exc_info=True)
    
    async def _emit_error_event(self, error: ErrorRecord):
        """
        Bir hata olayını tetikler
        
        Args:
            error: Tetiklenecek hata
        """
        try:
            # Event tipini belirle
            event_type = f"error_{error.severity.lower()}"
            
            # Event bus'ı al
            from bot.services.event_service import EventBus
            event_bus = EventBus()
            
            # Event'i tetikle
            await event_bus.emit(
                event_type=event_type,
                data=error.to_dict(),
                source="error_service"
            )
            
            # Kritik hatalar ve normal hatalar için bildirim gönder (ayarlara göre)
            if (error.severity == "CRITICAL" and self.notify_critical) or \
               (error.severity == "ERROR" and self.notify_error):
                await event_bus.emit(
                    event_type="notification",
                    data={
                        "title": f"{error.severity} on {self.hostname}",
                        "message": f"{error.error_type}: {error.message}",
                        "source": error.source,
                        "level": error.severity.lower(),
                        "error_id": error.error_id
                    },
                    source="error_service"
                )
                
        except Exception as e:
            logger.error(f"Hata olayı tetiklenirken beklenmeyen hata: {str(e)}", exc_info=True)
    
    async def _check_error_threshold(self, source: str, category: str = "GENERAL") -> bool:
        """
        Belirli bir kaynak ve kategori için hata eşiğinin aşılıp aşılmadığını kontrol eder
        
        Args:
            source: Hata kaynağı
            category: Hata kategorisi
            
        Returns:
            bool: Eşik aşıldıysa True
        """
        # Kaynak ve kategori için son alert_window süresindeki hataları say
        threshold = self.category_thresholds.get(category, self.alert_threshold)
        window = self.category_windows.get(category, self.alert_window)
        
        now = datetime.now()
        window_start = now - timedelta(seconds=window)
        
        # Son window süresindeki hataları say
        error_count = sum(
            1 for e in self.errors.values()
            if e.source == source and e.category == category and e.created_at >= window_start
        )
        
        logger.debug(f"Hata eşiği kontrolü: {source} kaynağı, {category} kategorisi, {error_count}/{threshold} hata")
        
        # Eşik aşıldı mı?
        return error_count >= threshold
    
    async def _emit_error_alert(self, source: str, category: str = "GENERAL"):
        """
        Hata eşiği aşıldığında uyarı olayı yayınlar
        
        Args:
            source: Hata kaynağı
            category: Hata kategorisi
        """
        # Son alert_window süresindeki hataları listele
        threshold = self.category_thresholds.get(category, self.alert_threshold)
        window = self.category_windows.get(category, self.alert_window)
        
        now = datetime.now()
        window_start = now - timedelta(seconds=window)
        
        # Son window süresindeki hatalar
        recent_errors = [
            e for e in self.errors.values()
            if e.source == source and e.category == category and e.created_at >= window_start
        ]
        
        # Olayı yayınla
        event_data = {
            'source': source,
            'category': category,
            'threshold': threshold,
            'window_seconds': window,
            'error_count': len(recent_errors),
            'errors': [e.to_dict() for e in recent_errors[:10]],  # En fazla 10 hata detayı
            'timestamp': now.isoformat()
        }
        
        from bot.services.event_service import EventBus
        event_bus = EventBus()
        await event_bus.emit(
            event_type="error_threshold_exceeded",
            data=event_data,
            source="error_service"
        )
        
        logger.warning(
            f"Hata eşiği aşıldı: {source} kaynağı, {category} kategorisi, {len(recent_errors)}/{threshold} hata"
        )

    def categorize_error(self, error_type: str, message: str, traceback_info: str = None) -> str:
        """
        Hatayı kategorize eder ve uygun kategoriyi döndürür
        
        Args:
            error_type: Hata tipi
            message: Hata mesajı
            traceback_info: Hata traceback bilgisi
            
        Returns:
            str: Hata kategorisi (DATABASE, NETWORK, TELEGRAM_API, GENERAL, vb.)
        """
        # Veritabanı hataları
        if any(term in error_type.lower() for term in ['db', 'sql', 'database', 'postgres', 'sqlite']):
            return "DATABASE"
        elif any(term in message.lower() for term in ['db', 'database', 'sql', 'query', 'connection', 'transaction', 
                                                    'postgres', 'sqlite', 'sqlalchemy']):
            return "DATABASE"
            
        # Telegram API hataları  
        if any(term in error_type.lower() for term in ['flood', 'telegram', 'api', 'telethon', 'pyrogram']):
            return "TELEGRAM_API"
        elif any(term in message.lower() for term in ['flood', 'wait', 'telegram', 'api', 'telethon', 'pyrogram', 
                                                   'too many requests', 'retry after', 'ratelimit']):
            return "TELEGRAM_API"
            
        # Ağ hataları
        if any(term in error_type.lower() for term in ['connection', 'timeout', 'network', 'socket']):
            return "NETWORK"
        elif any(term in message.lower() for term in ['connection', 'timeout', 'network', 'socket', 'connect', 
                                                    'unavailable', 'unreachable']):
            return "NETWORK"
            
        # Traceback incelemesi (eğer varsa)
        if traceback_info:
            traceback_lower = traceback_info.lower()
            
            if any(term in traceback_lower for term in ['db', 'database', 'sql', 'query', 'connection']):
                return "DATABASE"
                
            if any(term in traceback_lower for term in ['telethon', 'pyrogram', 'telegram', 'api']):
                return "TELEGRAM_API"
                
            if any(term in traceback_lower for term in ['socket', 'http', 'connection', 'timeout']):
                return "NETWORK"
            
        # Diğer hata tipleri için özel kategoriler eklenebilir
        # Örneğin:
        # if 'outofmemory' in error_type.lower():
        #     return "SYSTEM"
            
        # Varsayılan kategori
        return "GENERAL"

    async def log_error(self, error_type: str, message: str, source: str, 
                    details: Dict = None, traceback_info: str = None, 
                    severity: str = "ERROR", category: str = None) -> int:
        """
        Yeni bir hata kaydı oluşturur
        
        Args:
            error_type: Hata tipi
            message: Hata mesajı
            source: Hata kaynağı
            details: Hata detayları (opsiyonel)
            traceback_info: Traceback bilgisi (opsiyonel)
            severity: Hata şiddeti (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            category: Hata kategorisi (opsiyonel, belirtilmezse otomatik kategorize edilir)
            
        Returns:
            int: Oluşturulan hatanın ID'si
        """
        # Kategori belirtilmemişse otomatik kategorize et
        if not category:
            category = self.categorize_error(error_type, message, traceback_info)
            
        error_record = ErrorRecord(
            error_type=error_type,
            message=message,
            source=source,
            details=details or {},
            traceback_info=traceback_info,
            severity=severity,
            category=category  # Yeni: Kategori bilgisi
        )
        
        # İşleme kuyruğuna ekle
        await self.error_queue.put(error_record)
        
        logger.debug(f"Hata kuyruğa eklendi: {error_record.error_id} - {error_type} ({category})")
        
        return error_record.error_id
    
    async def resolve_error(self, error_id: int, resolution_info: str = None) -> bool:
        """
        Bir hatayı çözüldü olarak işaretler
        
        Args:
            error_id: Çözülen hatanın ID'si
            resolution_info: Çözüm hakkında bilgi
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            if error_id not in self.errors:
                return False
                
            error = self.errors[error_id]
            error.resolved = True
            error.resolved_at = datetime.now()
            error.resolution_info = resolution_info
            
            # Dosyalara kaydet
            await self._save_error_records()
            
            return True
                
        except Exception as e:
            logger.error(f"Hata çözüldü olarak işaretlenirken beklenmeyen hata: {str(e)}", exc_info=True)
            return False
    
    async def get_errors(self, source: str = None, severity: str = None, 
                        include_resolved: bool = False, limit: int = 100, 
                        start_time: datetime = None, end_time: datetime = None) -> List[Dict]:
        """
        Hataları filtreli olarak döndürür
        
        Args:
            source: Hata kaynağı filtresi
            severity: Hata şiddeti filtresi
            include_resolved: Çözülmüş hataları da dahil et
            limit: Maksimum sonuç sayısı
            start_time: Başlangıç zamanı
            end_time: Bitiş zamanı
            
        Returns:
            List[Dict]: Bulunan hata kayıtları
        """
        try:
            # Filtreleri uygula
            filtered_errors = []
            
            for error in self.errors.values():
                # Çözülmüş hataları filtrele
                if not include_resolved and error.resolved:
                    continue
                    
                # Kaynağa göre filtrele
                if source and error.source != source:
                    continue
                    
                # Şiddete göre filtrele
                if severity and error.severity != severity:
                    continue
                    
                # Zamana göre filtrele
                if start_time and error.created_at < start_time:
                    continue
                    
                if end_time and error.created_at > end_time:
                    continue
                    
                filtered_errors.append(error.to_dict())
                
                # Limit kontrolü
                if len(filtered_errors) >= limit:
                    break
            
            # Oluşturulma zamanına göre sırala (en yeniden en eskiye)
            filtered_errors.sort(key=lambda x: x['created_at'], reverse=True)
            
            return filtered_errors
                
        except Exception as e:
            logger.error(f"Hatalar filtrelenirken beklenmeyen hata: {str(e)}", exc_info=True)
            return []
    
    async def get_error_count(self, source: str = None, severity: str = None,
                             include_resolved: bool = False, hours: int = 24) -> Dict:
        """
        Hata sayısını döndürür
        
        Args:
            source: Hata kaynağı filtresi
            severity: Hata şiddeti filtresi
            include_resolved: Çözülmüş hataları da dahil et
            hours: Son kaç saatteki hatalar (0 ise tümü)
            
        Returns:
            Dict: Hata sayıları
        """
        try:
            # Zaman filtresi
            start_time = None
            if hours > 0:
                start_time = datetime.now() - timedelta(hours=hours)
                
            # Hata sayılarını hesapla
            counts = {
                "total": 0,
                "by_source": {},
                "by_severity": {
                    "DEBUG": 0,
                    "INFO": 0,
                    "WARNING": 0,
                    "ERROR": 0,
                    "CRITICAL": 0
                },
                "by_resolved": {
                    "resolved": 0,
                    "unresolved": 0
                }
            }
            
            for error in self.errors.values():
                # Çözülmüş hataları filtrele
                if not include_resolved and error.resolved:
                    continue
                    
                # Kaynağa göre filtrele
                if source and error.source != source:
                    continue
                    
                # Şiddete göre filtrele
                if severity and error.severity != severity:
                    continue
                    
                # Zamana göre filtrele
                if start_time and error.created_at < start_time:
                    continue
                
                # Toplam sayı
                counts["total"] += 1
                
                # Kaynağa göre sayılar
                if error.source not in counts["by_source"]:
                    counts["by_source"][error.source] = 0
                counts["by_source"][error.source] += 1
                
                # Şiddete göre sayılar
                if error.severity in counts["by_severity"]:
                    counts["by_severity"][error.severity] += 1
                
                # Çözülmüş durumuna göre sayılar
                if error.resolved:
                    counts["by_resolved"]["resolved"] += 1
                else:
                    counts["by_resolved"]["unresolved"] += 1
            
            return counts
                
        except Exception as e:
            logger.error(f"Hata sayıları hesaplanırken beklenmeyen hata: {str(e)}", exc_info=True)
            return {"total": 0}

    async def get_errors_by_category(self, category: str, include_resolved: bool = False, 
                                limit: int = 100, hours: int = 24) -> List[Dict]:
        """
        Kategoriye göre hataları listeler
        
        Args:
            category: Hata kategorisi
            include_resolved: Çözülmüş hataları da dahil et
            limit: En fazla kaç hata döndürüleceği
            hours: Son kaç saatteki hatalar listelenecek
            
        Returns:
            List[Dict]: Hata kayıtları listesi
        """
        now = datetime.now()
        start_time = now - timedelta(hours=hours)
        
        # Filtreleme
        filtered_errors = [
            e.to_dict() for e in self.errors.values()
            if e.category == category and 
               e.created_at >= start_time and
               (include_resolved or not e.resolved)
        ]
        
        # Tarih sırasına göre sırala (en yeniler önce)
        sorted_errors = sorted(
            filtered_errors,
            key=lambda x: datetime.fromisoformat(x['created_at']),
            reverse=True
        )
        
        return sorted_errors[:limit]

    async def get_category_stats(self, hours: int = 24) -> Dict:
        """
        Kategori bazlı hata istatistiklerini döndürür
        
        Args:
            hours: Son kaç saatteki hatalar dahil edilecek
            
        Returns:
            Dict: Kategori bazlı hata istatistikleri
        """
        now = datetime.now()
        start_time = now - timedelta(hours=hours)
        
        # Kategorileri ve sayıları hesapla
        categories = {}
        
        for error in self.errors.values():
            if error.created_at >= start_time:
                category = error.category
                if category not in categories:
                    categories[category] = {
                        'total': 0,
                        'resolved': 0,
                        'by_severity': {
                            'DEBUG': 0,
                            'INFO': 0,
                            'WARNING': 0,
                            'ERROR': 0,
                            'CRITICAL': 0
                        }
                    }
                
                categories[category]['total'] += 1
                if error.resolved:
                    categories[category]['resolved'] += 1
                categories[category]['by_severity'][error.severity] += 1
        
        return {
            'timespan_hours': hours,
            'total_errors': sum(c['total'] for c in categories.values()),
            'categories': categories
        } 