#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Event Service - Servisler arası olay yönetimi ve iletişim için event bus
"""

import asyncio
import logging
import uuid
import time
import inspect
from typing import Dict, List, Callable, Any, Optional, Set, Tuple, Union
from functools import wraps

# Base modülünü import et
from bot.services.base_service import BaseService

# Log ayarları
logger = logging.getLogger(__name__)

class Event:
    """
    Event sınıfı, servisler arası iletişim için kullanılan olayları temsil eder
    """
    def __init__(self, 
                 event_type: str, 
                 source: str = None, 
                 target: str = None, 
                 data: Any = None,
                 timestamp: float = None,
                 event_id: str = None):
        """
        Event constructor
        
        Args:
            event_type: Olayın tipi (örn. 'user_joined', 'message_received')
            source: Olayı gönderen servis/bileşen adı
            target: Olayın hedeflendiği servis/bileşen adı (None ise tüm aboneler)
            data: Olayla birlikte gönderilen veri
            timestamp: Olayın oluşturulma zamanı (Unix timestamp)
            event_id: Olayın unique ID'si (None ise otomatik oluşturulur)
        """
        self.event_type = event_type
        self.source = source
        self.target = target
        self.data = data
        self.timestamp = timestamp or time.time()
        self.event_id = event_id or str(uuid.uuid4())
        self.processed = False
        self.processing_time = None
        
    def __str__(self):
        return f"Event[{self.event_id}] {self.event_type} from {self.source} to {self.target} at {self.timestamp}"
        
    def mark_processed(self):
        """Olayı işlenmiş olarak işaretle"""
        self.processed = True
        self.processing_time = time.time() - self.timestamp
        
    def is_processed(self):
        """Olayın işlenip işlenmediğini kontrol et"""
        return self.processed
        
    def to_dict(self):
        """Olayı sözlük yapısına dönüştür"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'source': self.source,
            'target': self.target,
            'data': self.data,
            'timestamp': self.timestamp,
            'processed': self.processed,
            'processing_time': self.processing_time
        }
        
    @classmethod
    def from_dict(cls, data: Dict):
        """Sözlükten olay oluştur"""
        event = cls(
            event_type=data['event_type'],
            source=data['source'],
            target=data['target'],
            data=data['data'],
            timestamp=data['timestamp'],
            event_id=data['event_id']
        )
        event.processed = data.get('processed', False)
        event.processing_time = data.get('processing_time', None)
        return event

class EventBus:
    """
    EventBus sınıfı, servisler arası iletişim için merkezi bir event yönetim sistemi sağlar
    Singleton pattern kullanır
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self._subscribers = {}  # event_type -> [callbacks]
        self._service_subscribers = {}  # service_name -> {event_type -> [callbacks]}
        self._event_history = {}  # event_type -> [events]
        self._lock = asyncio.Lock()
        self._event_queue = asyncio.Queue()
        self._processor_task = None
        self._running = False
        self._max_history_per_type = 100
        self._history_enabled = True
        self._initialized = True
        
    async def start(self):
        """Event bus'ı başlat"""
        if self._running:
            return
            
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("Event bus başlatıldı")
        
    async def stop(self):
        """Event bus'ı durdur"""
        if not self._running:
            return
            
        self._running = False
        if self._processor_task:
            try:
                self._processor_task.cancel()
                await asyncio.gather(self._processor_task, return_exceptions=True)
            except (asyncio.CancelledError, Exception) as e:
                logger.debug(f"Event processor task durdurulurken hata: {str(e)}")
        
        # Kuyruktaki tüm eventleri işle
        try:
            while not self._event_queue.empty():
                await self._event_queue.get()
                self._event_queue.task_done()
        except Exception as e:
            logger.error(f"Event kuyruğu temizlenirken hata: {str(e)}")
            
        logger.info("Event bus durduruldu")
        
    async def subscribe(self, event_type: str, callback: Callable, service_name: str = None):
        """
        Bir event tipine abone ol
        
        Args:
            event_type: Abone olunacak event tipi
            callback: Event alındığında çağrılacak fonksiyon
            service_name: Aboneliği yapan servis adı (opsiyonel)
        """
        async with self._lock:
            # Genel abonelikler
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            
            # Servis bazlı abonelikler
            if service_name:
                if service_name not in self._service_subscribers:
                    self._service_subscribers[service_name] = {}
                if event_type not in self._service_subscribers[service_name]:
                    self._service_subscribers[service_name][event_type] = []
                self._service_subscribers[service_name][event_type].append(callback)
                
            logger.debug(f"'{event_type}' event tipine yeni abonelik: {callback.__qualname__} ({service_name or 'anonim'})")
    
    async def unsubscribe(self, event_type: str, callback: Callable = None, service_name: str = None):
        """
        Bir event tipinden aboneliği kaldır
        
        Args:
            event_type: Abonelikten çıkılacak event tipi
            callback: Kaldırılacak callback (None ise tüm callbacks kaldırılır)
            service_name: Aboneliği kaldıran servis adı (None ise tüm servislerden)
        """
        async with self._lock:
            # Belirli bir callback kaldırılıyorsa
            if callback and event_type in self._subscribers:
                if callback in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(callback)
                    logger.debug(f"'{event_type}' event tipinden abonelik kaldırıldı: {callback.__qualname__}")
                
                # Servis bazlı aboneliklerden de kaldır
                if service_name and service_name in self._service_subscribers:
                    if event_type in self._service_subscribers[service_name]:
                        if callback in self._service_subscribers[service_name][event_type]:
                            self._service_subscribers[service_name][event_type].remove(callback)
                            
            # Bir servisin tüm aboneliklerini kaldır
            elif service_name and not callback:
                if service_name in self._service_subscribers:
                    for e_type, callbacks in self._service_subscribers[service_name].items():
                        if e_type in self._subscribers:
                            for cb in callbacks:
                                if cb in self._subscribers[e_type]:
                                    self._subscribers[e_type].remove(cb)
                    
                    # Servis abonelikleri temizle
                    self._service_subscribers.pop(service_name, None)
                    logger.debug(f"'{service_name}' servisinin tüm abonelikleri kaldırıldı")
                    
            # Bir event tipinin tüm aboneliklerini kaldır
            elif event_type and not callback and not service_name:
                self._subscribers.pop(event_type, None)
                
                # Servis aboneliklerinden de kaldır
                for service, events in self._service_subscribers.items():
                    events.pop(event_type, None)
                
                logger.debug(f"'{event_type}' event tipinin tüm abonelikleri kaldırıldı")
    
    async def publish(self, event: Event):
        """
        Bir event yayınla
        
        Args:
            event: Yayınlanacak event
        """
        if not self._running:
            logger.warning(f"Event bus çalışmıyor, event yayınlanamadı: {event}")
            return
            
        # Olayı kuyruğa ekle
        await self._event_queue.put(event)
        
        # Olayı geçmişe ekle
        if self._history_enabled:
            async with self._lock:
                if event.event_type not in self._event_history:
                    self._event_history[event.event_type] = []
                
                self._event_history[event.event_type].append(event)
                
                # Geçmişi sınırla
                if len(self._event_history[event.event_type]) > self._max_history_per_type:
                    self._event_history[event.event_type] = self._event_history[event.event_type][-self._max_history_per_type:]
    
    async def emit(self, event_type: str, data: Any = None, source: str = None, target: str = None):
        """
        Yeni bir event oluşturup yayınla (kolaylık metodu)
        
        Args:
            event_type: Olayın tipi
            data: Olayla birlikte gönderilecek veri
            source: Olayı gönderen servis
            target: Olayın hedeflendiği servis
        """
        event = Event(
            event_type=event_type,
            source=source,
            target=target,
            data=data
        )
        await self.publish(event)
        
    async def _process_events(self):
        """Event kuyruğunu işleyen arka plan görevi"""
        logger.debug("Event işleyici görev başlatıldı")
        
        while self._running:
            try:
                # Kuyruktan bir event al
                event = await self._event_queue.get()
                
                try:
                    # Eventi işle
                    await self._dispatch_event(event)
                except Exception as e:
                    logger.error(f"Event işlenirken hata: {str(e)} - Event: {event}")
                finally:
                    # İşlemi tamamlandı olarak işaretle
                    self._event_queue.task_done()
                    
            except asyncio.CancelledError:
                logger.debug("Event işleyici görev iptal edildi")
                break
            except Exception as e:
                logger.error(f"Event işleyici görevinde beklenmeyen hata: {str(e)}")
                await asyncio.sleep(1)  # Sonsuz döngüyü önle
        
        logger.debug("Event işleyici görev sonlandı")
        
    async def _dispatch_event(self, event: Event):
        """
        Bir eventi tüm abonelere dağıt
        
        Args:
            event: Dağıtılacak event
        """
        if event.event_type not in self._subscribers:
            logger.debug(f"'{event.event_type}' event tipine abone yok: {event}")
            event.mark_processed()
            return
            
        callbacks = self._subscribers[event.event_type].copy()
        
        if not callbacks:
            logger.debug(f"'{event.event_type}' event tipine abone yok: {event}")
            event.mark_processed()
            return
        
        # Eğer hedef belirtilmişse, sadece o hedefin callbacklerini çağır
        if event.target:
            filtered_callbacks = []
            
            if event.target in self._service_subscribers:
                if event.event_type in self._service_subscribers[event.target]:
                    filtered_callbacks = self._service_subscribers[event.target][event.event_type].copy()
                    
            if not filtered_callbacks:
                logger.debug(f"'{event.target}' hedefinde '{event.event_type}' event tipine abone yok: {event}")
                event.mark_processed()
                return
                
            callbacks = filtered_callbacks
                
        # Tüm callbackleri çağır
        for callback in callbacks:
            try:
                # Callback async mi?
                if inspect.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Event callback çağrılırken hata: {str(e)} - Event: {event}, Callback: {callback.__qualname__}")
                
        event.mark_processed()
        
    def get_event_history(self, event_type: str = None, limit: int = None) -> List[Event]:
        """
        Belirli bir event tipinin geçmişini döndür
        
        Args:
            event_type: Geçmişi istenilen event tipi (None ise tüm tipler)
            limit: Döndürülecek maksimum olay sayısı
            
        Returns:
            Event listesi
        """
        if not self._history_enabled:
            return []
            
        if event_type:
            events = self._event_history.get(event_type, []).copy()
            if limit:
                events = events[-limit:]
            return events
        else:
            events = []
            for e_type, e_list in self._event_history.items():
                events.extend(e_list)
            
            # Zaman damgasına göre sırala
            events.sort(key=lambda e: e.timestamp)
            
            if limit:
                events = events[-limit:]
            return events
            
    def clear_event_history(self, event_type: str = None):
        """
        Event geçmişini temizle
        
        Args:
            event_type: Temizlenecek event tipi (None ise tüm tipler)
        """
        if not self._history_enabled:
            return
            
        if event_type:
            self._event_history.pop(event_type, None)
        else:
            self._event_history.clear()
            
    def set_history_enabled(self, enabled: bool):
        """
        Event geçmişini etkinleştir/devre dışı bırak
        
        Args:
            enabled: Geçmişin etkin olup olmayacağı
        """
        self._history_enabled = enabled
        
        if not enabled:
            self._event_history.clear()
            
    def set_max_history_per_type(self, max_count: int):
        """
        Her event tipi için maksimum geçmiş sayısını ayarla
        
        Args:
            max_count: Her tip için maksimum geçmiş sayısı
        """
        self._max_history_per_type = max_count
        
        # Mevcut geçmişi sınırla
        if self._history_enabled:
            for event_type, events in self._event_history.items():
                if len(events) > max_count:
                    self._event_history[event_type] = events[-max_count:]

class EventService(BaseService):
    """
    Servisler arası iletişim ve event yönetimi için merkezi servis
    """
    
    def __init__(self, client=None, config=None, db=None, stop_event=None):
        """
        EventService constructor
        
        Args:
            client: Telegram istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            stop_event: Durdurma eventi
        """
        super().__init__("event", client, config, db, stop_event)
        self.event_bus = EventBus()
        
    async def initialize(self) -> bool:
        """
        Servisi başlat ve gerekli kaynakları yükle
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("EventService başlatılıyor...")
            
            # Event bus'ı başlat
            await self.event_bus.start()
            
            self.initialized = True
            logger.info("EventService başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"EventService başlatılırken hata: {str(e)}", exc_info=True)
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
                
        self.is_running = True
        logger.info("EventService başlatıldı")
        return True
        
    async def stop(self) -> None:
        """
        Servisi durdur
        
        Returns:
            None
        """
        self.is_running = False
        
        # Event bus'ı durdur
        await self.event_bus.stop()
        
        logger.info("EventService durduruldu")
        
    async def subscribe(self, event_type: str, callback: Callable, service_name: str = None):
        """
        Bir event tipine abone ol
        
        Args:
            event_type: Abone olunacak event tipi
            callback: Event alındığında çağrılacak fonksiyon
            service_name: Aboneliği yapan servis adı (opsiyonel)
        """
        await self.event_bus.subscribe(event_type, callback, service_name)
        
    async def unsubscribe(self, event_type: str, callback: Callable = None, service_name: str = None):
        """
        Bir event tipinden aboneliği kaldır
        
        Args:
            event_type: Abonelikten çıkılacak event tipi
            callback: Kaldırılacak callback (None ise tüm callbacks kaldırılır)
            service_name: Aboneliği kaldıran servis adı (None ise tüm servislerden)
        """
        await self.event_bus.unsubscribe(event_type, callback, service_name)
        
    async def publish(self, event: Event):
        """
        Bir event yayınla
        
        Args:
            event: Yayınlanacak event
        """
        await self.event_bus.publish(event)
        
    async def emit(self, event_type: str, data: Any = None, source: str = None, target: str = None):
        """
        Yeni bir event oluşturup yayınla
        
        Args:
            event_type: Olayın tipi
            data: Olayla birlikte gönderilecek veri
            source: Olayı gönderen servis
            target: Olayın hedeflendiği servis
        """
        await self.event_bus.emit(event_type, data, source, target)
        
    def get_event_history(self, event_type: str = None, limit: int = None) -> List[Event]:
        """
        Belirli bir event tipinin geçmişini döndür
        
        Args:
            event_type: Geçmişi istenilen event tipi (None ise tüm tipler)
            limit: Döndürülecek maksimum olay sayısı
            
        Returns:
            Event listesi
        """
        return self.event_bus.get_event_history(event_type, limit)
        
    def clear_event_history(self, event_type: str = None):
        """
        Event geçmişini temizle
        
        Args:
            event_type: Temizlenecek event tipi (None ise tüm tipler)
        """
        self.event_bus.clear_event_history(event_type)
        
    def set_history_enabled(self, enabled: bool):
        """
        Event geçmişini etkinleştir/devre dışı bırak
        
        Args:
            enabled: Geçmişin etkin olup olmayacağı
        """
        self.event_bus.set_history_enabled(enabled)
        
    def set_max_history_per_type(self, max_count: int):
        """
        Her event tipi için maksimum geçmiş sayısını ayarla
        
        Args:
            max_count: Her tip için maksimum geçmiş sayısı
        """
        self.event_bus.set_max_history_per_type(max_count)
        
# EventDecorator
def on_event(event_type: str, service_name: str = None):
    """
    Event'lere tepki veren metotlar için decorator
    
    Args:
        event_type: Abone olunacak event tipi
        service_name: Servis adı
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            if not hasattr(self, '_event_subscriptions'):
                self._event_subscriptions = []
                
            # Servis başlangıcında abone ol
            event_bus = EventBus()
            await event_bus.subscribe(event_type, func, service_name or getattr(self, 'service_name', None))
            
            # Aboneliği kaydet (daha sonra kaldırmak için)
            self._event_subscriptions.append((event_type, func))
            
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator 