#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Event Service Modülü

Bu modül, Telegram etkinliklerini işleyerek tanımlanan olaylara göre tepki verir.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable, Optional, Union, Set

from app.services.base_service import BaseService
from app.core.logger import get_logger

logger = get_logger(__name__)

class EventService(BaseService):
    """
    Telegram etkinliklerini dinleyip, tanımlanan olaylara göre tepki veren servis
    """
    
    def __init__(self, client=None, db=None, config=None):
        """
        Event servisini başlat
        
        Args:
            client: Telegram client nesnesi
            db: Veritabanı bağlantısı
            config: Yapılandırma değişkenleri
        """
        super().__init__(client, db, config)
        self.service_name = "event_service"
        self.default_interval = 60  # 1 dakikada bir çalıştır
        
        # Etkinlik ve işleyici eşleştirmeleri
        self.event_handlers = {}
        
        # Son etkinlik işleme zamanı
        self.last_processed = {}
        
        # Tüm etkinlikleri dinle
        self.listen_all = self.get_config("event_service.listen_all", False)
        
        # İşlenecek etkinlik türleri
        self.event_types = self.get_config("event_service.event_types", [
            "message", "edited_message", "new_chat_members", "left_chat_member", 
            "chat_title", "pinned_message", "user_status", "callback_query"
        ])
        
        # Devre dışı bırakılmış etkinlik türleri
        self.disabled_events = self.get_config("event_service.disabled_events", [])
        
        # Etkinlik arabelleği
        self.event_buffer = []
        self.buffer_size = self.get_config("event_service.buffer_size", 100)
        
        # Son etkinlik zamanı
        self.last_event_time = datetime.now()
        
        # Etkinlik işleme aralığı (saniye)
        self.process_interval = self.get_config("event_service.process_interval", 5)
    
    async def _start(self) -> bool:
        """
        Event servisini başlat ve etkinlik dinleyicilerini kaydet
        
        Returns:
            bool: Başlatma başarılı mı
        """
        self.log("Event servisi başlatılıyor...")
        
        # Client kontrol et
        if not self.client:
            self.log("Telegram client nesnesi bulunamadı.", level="error")
            return False
        
        # Temel etkinlik işleyicilerini ayarla
        self._setup_default_handlers()
        
        # Özel etkinlik işleyicilerini kaydet
        try:
            await self._register_event_handlers()
            self.log("Etkinlik işleyicileri kaydedildi", level="info")
        except Exception as e:
            self.log(f"Etkinlik işleyicileri kaydedilirken hata: {str(e)}", level="error")
            return False
        
        self.log("Event servisi başlatıldı", level="info")
        return True
    
    async def _stop(self) -> bool:
        """
        Event servisini durdur ve etkinlik dinleyicilerini temizle
        
        Returns:
            bool: Durdurma başarılı mı
        """
        self.log("Event servisi durduruluyor...")
        
        # Etkinlik işleyicilerini temizle
        try:
            self._clear_event_handlers()
            self.log("Etkinlik işleyicileri temizlendi", level="info")
        except Exception as e:
            self.log(f"Etkinlik işleyicileri temizlenirken hata: {str(e)}", level="error")
        
        # Arabelleği temizle
        self.event_buffer.clear()
        
        self.log("Event servisi durduruldu", level="info")
        return True
    
    async def _update(self) -> None:
        """Servis güncellemesi - Arabelleği işle"""
        # İşlenmeyen etkinlikler varsa işle
        if self.event_buffer:
            try:
                await self._process_event_buffer()
            except Exception as e:
                self.log(f"Etkinlik arabelleği işlenirken hata: {str(e)}", level="error")
    
    def _setup_default_handlers(self) -> None:
        """Temel etkinlik işleyicilerini ayarla"""
        if not self.client:
            return
            
        # Yeni mesaj etkinliği
        @self.client.on(events.NewMessage)
        async def on_new_message(event):
            await self._handle_event("message", event)
        
        # Düzenlenen mesaj etkinliği
        @self.client.on(events.MessageEdited)
        async def on_edited_message(event):
            await self._handle_event("edited_message", event)
        
        # Yeni sohbet üyesi etkinliği
        @self.client.on(events.ChatAction(func=lambda e: e.user_joined))
        async def on_user_joined(event):
            await self._handle_event("new_chat_members", event)
        
        # Sohbetten ayrılan üye etkinliği
        @self.client.on(events.ChatAction(func=lambda e: e.user_left))
        async def on_user_left(event):
            await self._handle_event("left_chat_member", event)
        
        # Sohbet başlığı değişikliği etkinliği
        @self.client.on(events.ChatAction(func=lambda e: e.new_title))
        async def on_chat_title_changed(event):
            await self._handle_event("chat_title", event)
        
        # Mesaj sabitleme etkinliği
        @self.client.on(events.ChatAction(func=lambda e: e.pin_message))
        async def on_message_pinned(event):
            await self._handle_event("pinned_message", event)
        
        # Geri çağrı sorgusu etkinliği
        @self.client.on(events.CallbackQuery)
        async def on_callback_query(event):
            await self._handle_event("callback_query", event)
    
    async def _register_event_handlers(self) -> None:
        """
        Veritabanından kayıtlı etkinlik işleyicilerini yükle
        """
        if not self.db:
            self.log("Veritabanı bağlantısı bulunamadı, etkinlik işleyicileri yüklenemedi", level="warning")
            return
        
        try:
            # Kayıtlı etkinlik işleyicilerini veritabanından al
            query = """
            SELECT id, event_type, pattern, is_active, handler_data, priority
            FROM event_handlers
            WHERE is_active = TRUE
            ORDER BY priority DESC
            """
            
            handlers = await self.db.fetchall(query)
            
            if not handlers:
                self.log("Kayıtlı etkinlik işleyicisi bulunamadı")
                return
            
            self.log(f"{len(handlers)} etkinlik işleyicisi bulundu")
            
            # Her işleyiciyi kaydet
            for handler in handlers:
                handler_id, event_type, pattern, is_active, handler_data, priority = handler
                
                if event_type in self.disabled_events:
                    continue
                
                if event_type not in self.event_handlers:
                    self.event_handlers[event_type] = []
                
                # İşleyiciyi ekle
                self.event_handlers[event_type].append({
                    "id": handler_id,
                    "pattern": pattern,
                    "data": handler_data,
                    "priority": priority
                })
                
                self.log(f"{event_type} için işleyici eklendi (ID: {handler_id})")
        
        except Exception as e:
            self.log(f"Etkinlik işleyicileri yüklenirken hata: {str(e)}", level="error")
            raise
    
    def _clear_event_handlers(self) -> None:
        """Tüm etkinlik işleyicilerini temizle"""
        self.event_handlers.clear()
    
    async def _handle_event(self, event_type: str, event: Any) -> None:
        """
        Bir etkinliği işle
        
        Args:
            event_type: Etkinlik türü (message, edited_message, vb.)
            event: Etkinlik nesnesi
        """
        # Etkinlik arabelleğine ekle
        self._buffer_event(event_type, event)
        
        # Arabellek işleme zamanı kontrolü
        current_time = datetime.now()
        time_since_last_event = (current_time - self.last_event_time).total_seconds()
        
        if time_since_last_event >= self.process_interval:
            self.last_event_time = current_time
            await self._process_event_buffer()
    
    def _buffer_event(self, event_type: str, event: Any) -> None:
        """
        Etkinliği arabellekte sakla
        
        Args:
            event_type: Etkinlik türü (message, edited_message, vb.)
            event: Etkinlik nesnesi
        """
        # Arabellek boyut kontrolü
        if len(self.event_buffer) >= self.buffer_size:
            # En eski etkinliği çıkar
            self.event_buffer.pop(0)
        
        # Etkinliği ekle
        self.event_buffer.append({
            "type": event_type,
            "event": event,
            "time": datetime.now()
        })
    
    async def _process_event_buffer(self) -> None:
        """Etkinlik arabelleğini işle"""
        if not self.event_buffer:
            return
        
        # Arabellekteki etkinlikleri kopyala ve arabellekten çıkar
        events_to_process = self.event_buffer.copy()
        self.event_buffer.clear()
        
        # Her etkinliği işle
        for event_data in events_to_process:
            event_type = event_data["type"]
            event = event_data["event"]
            
            # Etkinlik türü için işleyiciler bulunamadıysa ve tüm etkinlikleri dinlemiyorsak atla
            if event_type not in self.event_handlers and not self.listen_all:
                continue
            
            try:
                # Etkinlik türü için özel işleyici çağır
                if event_type in self.event_handlers:
                    for handler in self.event_handlers[event_type]:
                        await self._execute_handler(handler, event)
                
                # Etkinlik bilgilerini kaydet
                await self._log_event(event_type, event)
                
            except Exception as e:
                self.log(f"{event_type} etkinliği işlenirken hata: {str(e)}", level="error")
    
    async def _execute_handler(self, handler: Dict[str, Any], event: Any) -> None:
        """
        Belirli bir işleyiciyi çalıştır
        
        Args:
            handler: İşleyici bilgileri 
            event: Etkinlik nesnesi
        """
        handler_id = handler["id"]
        pattern = handler["pattern"]
        handler_data = handler["data"]
        
        try:
            # İşleyici fonksiyonunu al
            handler_func = self._get_handler_function(handler_data)
            
            if handler_func:
                # İşleyiciyi çalıştır
                await handler_func(event, pattern)
            else:
                self.log(f"İşleyici fonksiyonu bulunamadı (ID: {handler_id})", level="warning")
                
        except Exception as e:
            self.log(f"İşleyici çalıştırılırken hata (ID: {handler_id}): {str(e)}", level="error")
    
    def _get_handler_function(self, handler_data: str) -> Optional[Callable]:
        """
        İşleyici fonksiyonunu al
        
        Args:
            handler_data: İşleyici veri dizgisi
            
        Returns:
            Optional[Callable]: İşleyici fonksiyonu veya None
        """
        # Basit işleyiciler
        handlers = {
            "log": self._log_event_handler,
            "save": self._save_event_handler,
            "reply": self._reply_event_handler,
            "forward": self._forward_event_handler
        }
        
        # Temel işleyicileri kontrol et
        if handler_data in handlers:
            return handlers[handler_data]
        
        # Özel işleyici formatı: module.submodule.function
        if "." in handler_data:
            try:
                module_path, func_name = handler_data.rsplit(".", 1)
                module = __import__(module_path, fromlist=[func_name])
                return getattr(module, func_name, None)
            except (ImportError, AttributeError) as e:
                self.log(f"Özel işleyici yüklenirken hata: {str(e)}", level="error")
        
        return None
    
    async def _log_event(self, event_type: str, event: Any) -> None:
        """
        Etkinlik bilgilerini logla ve veritabanına kaydet
        
        Args:
            event_type: Etkinlik türü
            event: Etkinlik nesnesi
        """
        if not self.db:
            return
        
        try:
            # Etkinlik meta verileri
            event_meta = {
                "type": event_type,
                "chat_id": getattr(event.chat_id, "chat_id", None) if hasattr(event, "chat_id") else None,
                "user_id": getattr(event.sender_id, "sender_id", None) if hasattr(event, "sender_id") else None,
                "message_id": getattr(event, "id", None) if hasattr(event, "id") else None,
                "timestamp": datetime.now()
            }
            
            # Etkinliği veritabanına kaydet
            query = """
            INSERT INTO event_logs 
            (event_type, chat_id, user_id, message_id, event_data, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            params = (
                event_meta["type"],
                event_meta["chat_id"],
                event_meta["user_id"],
                event_meta["message_id"],
                str(event),
                event_meta["timestamp"]
            )
            
            await self.db.execute(query, params)
            
        except Exception as e:
            self.log(f"Etkinlik kaydedilirken hata: {str(e)}", level="error")
    
    # Temel işleyici fonksiyonları
    
    async def _log_event_handler(self, event: Any, pattern: str) -> None:
        """Etkinliği logla"""
        self.log(f"Etkinlik algılandı: {pattern}")
    
    async def _save_event_handler(self, event: Any, pattern: str) -> None:
        """Etkinliği veritabanına kaydet"""
        if not self.db:
            return
            
        try:
            # Etkinlik içeriğini kaydet
            query = """
            INSERT INTO saved_events 
            (event_pattern, chat_id, user_id, message_id, content, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            # Etkinlik bilgilerini çıkart
            chat_id = getattr(event.chat, "id", None) if hasattr(event, "chat") else None
            user_id = getattr(event.sender, "id", None) if hasattr(event, "sender") else None
            message_id = getattr(event, "id", None) if hasattr(event, "id") else None
            content = getattr(event.message, "text", str(event)) if hasattr(event, "message") else str(event)
            
            params = (
                pattern,
                chat_id,
                user_id,
                message_id,
                content,
                datetime.now()
            )
            
            await self.db.execute(query, params)
            
            self.log(f"Etkinlik kaydedildi: {pattern}")
            
        except Exception as e:
            self.log(f"Etkinlik kaydedilirken hata: {str(e)}", level="error")
    
    async def _reply_event_handler(self, event: Any, pattern: str) -> None:
        """Etkinliğe yanıt ver"""
        if not hasattr(event, "reply") or not callable(event.reply):
            return
            
        try:
            # Yanıt içeriğini al
            reply_text = f"Etkinlik algılandı: {pattern}"
            
            # Yanıt gönder
            await event.reply(reply_text)
            
            self.log(f"Etkinlik yanıtlandı: {pattern}")
            
        except Exception as e:
            self.log(f"Etkinlik yanıtlanırken hata: {str(e)}", level="error")
    
    async def _forward_event_handler(self, event: Any, pattern: str) -> None:
        """Etkinliği başka bir sohbete yönlendir"""
        if not hasattr(event, "forward_to") or not callable(event.forward_to):
            return
            
        try:
            # Hedef sohbet ID'sini al (pattern içinden)
            target_chat_id = None
            
            if ":" in pattern:
                _, target = pattern.split(":", 1)
                try:
                    target_chat_id = int(target.strip())
                except ValueError:
                    self.log(f"Geçersiz hedef sohbet ID'si: {target}", level="error")
                    return
            
            if not target_chat_id:
                self.log("Hedef sohbet ID'si belirtilmedi", level="error")
                return
                
            # Mesajı ilet
            await event.forward_to(target_chat_id)
            
            self.log(f"Etkinlik iletildi: {pattern} -> {target_chat_id}")
            
        except Exception as e:
            self.log(f"Etkinlik iletilirken hata: {str(e)}", level="error")
    
    # Servis yönetim fonksiyonları
    
    async def add_event_handler(self, event_type: str, pattern: str, handler_data: str, 
                               priority: int = 0) -> int:
        """
        Yeni bir etkinlik işleyicisi ekle
        
        Args:
            event_type: Etkinlik türü (message, edited_message, vb.)
            pattern: Eşleşme örüntüsü
            handler_data: İşleyici veri dizgisi
            priority: İşleyici önceliği (yüksek değer daha yüksek öncelik)
            
        Returns:
            int: Eklenen işleyici ID'si
        """
        if not self.db:
            raise Exception("Veritabanı bağlantısı bulunamadı")
            
        try:
            # İşleyiciyi veritabanına ekle
            query = """
            INSERT INTO event_handlers 
            (event_type, pattern, handler_data, is_active, priority, created_at, updated_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            
            now = datetime.now()
            params = (event_type, pattern, handler_data, True, priority, now, now)
            
            result = await self.db.fetchone(query, params)
            
            if not result or not result[0]:
                raise Exception("Etkinlik işleyicisi eklenirken hata oluştu")
                
            handler_id = result[0]
            
            # İşleyiciyi çalışma zamanı koleksiyonuna da ekle
            if event_type not in self.event_handlers:
                self.event_handlers[event_type] = []
                
            self.event_handlers[event_type].append({
                "id": handler_id,
                "pattern": pattern,
                "data": handler_data,
                "priority": priority
            })
            
            self.log(f"Yeni etkinlik işleyicisi eklendi: {event_type} (ID: {handler_id})")
            
            return handler_id
            
        except Exception as e:
            self.log(f"Etkinlik işleyicisi eklenirken hata: {str(e)}", level="error")
            raise
    
    async def remove_event_handler(self, handler_id: int) -> bool:
        """
        Bir etkinlik işleyicisini kaldır
        
        Args:
            handler_id: İşleyici ID'si
            
        Returns:
            bool: Kaldırma başarılı mı
        """
        if not self.db:
            raise Exception("Veritabanı bağlantısı bulunamadı")
            
        try:
            # İşleyiciyi veritabanından al
            query = "SELECT event_type FROM event_handlers WHERE id = %s"
            result = await self.db.fetchone(query, (handler_id,))
            
            if not result:
                raise ValueError(f"ID {handler_id} ile işleyici bulunamadı")
                
            event_type = result[0]
            
            # İşleyiciyi devre dışı bırak
            query = "UPDATE event_handlers SET is_active = FALSE, updated_at = %s WHERE id = %s"
            await self.db.execute(query, (datetime.now(), handler_id))
            
            # İşleyiciyi çalışma zamanı koleksiyonundan kaldır
            if event_type in self.event_handlers:
                self.event_handlers[event_type] = [
                    h for h in self.event_handlers[event_type] if h["id"] != handler_id
                ]
            
            self.log(f"Etkinlik işleyicisi kaldırıldı: {event_type} (ID: {handler_id})")
            
            return True
            
        except Exception as e:
            self.log(f"Etkinlik işleyicisi kaldırılırken hata: {str(e)}", level="error")
            raise
    
    async def get_event_handlers(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Etkinlik işleyicilerini getir
        
        Args:
            event_type: Belirli bir etkinlik türü için işleyicileri getir (opsiyonel)
            
        Returns:
            List[Dict[str, Any]]: İşleyici listesi
        """
        if not self.db:
            raise Exception("Veritabanı bağlantısı bulunamadı")
            
        try:
            # Sorgu oluştur
            if event_type:
                query = """
                SELECT id, event_type, pattern, is_active, handler_data, priority, created_at, updated_at
                FROM event_handlers
                WHERE event_type = %s
                ORDER BY priority DESC, created_at ASC
                """
                params = (event_type,)
            else:
                query = """
                SELECT id, event_type, pattern, is_active, handler_data, priority, created_at, updated_at
                FROM event_handlers
                ORDER BY event_type, priority DESC, created_at ASC
                """
                params = None
            
            # Sorguyu çalıştır
            rows = await self.db.fetchall(query, params)
            
            if not rows:
                return []
            
            # Sonuçları formatlayarak döndür
            handlers = []
            for row in rows:
                handler_id, event_type, pattern, is_active, handler_data, priority, created_at, updated_at = row
                
                handlers.append({
                    "id": handler_id,
                    "event_type": event_type,
                    "pattern": pattern,
                    "is_active": is_active,
                    "handler_data": handler_data,
                    "priority": priority,
                    "created_at": created_at,
                    "updated_at": updated_at
                })
            
            return handlers
            
        except Exception as e:
            self.log(f"Etkinlik işleyicileri alınırken hata: {str(e)}", level="error")
            raise
    
    async def get_events_log(self, limit: int = 100, 
                            event_type: Optional[str] = None, 
                            start_time: Optional[datetime] = None, 
                            end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Etkinlik günlüğünü getir
        
        Args:
            limit: Maksimum etkinlik sayısı
            event_type: Belirli bir etkinlik türü (opsiyonel)
            start_time: Başlangıç zamanı (opsiyonel)
            end_time: Bitiş zamanı (opsiyonel)
            
        Returns:
            List[Dict[str, Any]]: Etkinlik günlüğü
        """
        if not self.db:
            raise Exception("Veritabanı bağlantısı bulunamadı")
            
        try:
            # Sorgu parametreleri
            params = []
            conditions = []
            
            # Koşulları oluştur
            if event_type:
                conditions.append("event_type = %s")
                params.append(event_type)
                
            if start_time:
                conditions.append("created_at >= %s")
                params.append(start_time)
                
            if end_time:
                conditions.append("created_at <= %s")
                params.append(end_time)
            
            # Sorgu oluştur
            query = """
            SELECT id, event_type, chat_id, user_id, message_id, event_data, created_at
            FROM event_logs
            """
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            
            # Sorguyu çalıştır
            rows = await self.db.fetchall(query, tuple(params))
            
            if not rows:
                return []
            
            # Sonuçları formatlayarak döndür
            events = []
            for row in rows:
                event_id, event_type, chat_id, user_id, message_id, event_data, created_at = row
                
                events.append({
                    "id": event_id,
                    "event_type": event_type,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "message_id": message_id,
                    "event_data": event_data,
                    "created_at": created_at
                })
            
            return events
            
        except Exception as e:
            self.log(f"Etkinlik günlüğü alınırken hata: {str(e)}", level="error")
            raise 