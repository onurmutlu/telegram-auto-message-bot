import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from sqlmodel import Session, select
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_session
from app.models.message import Message, MessageStatus, MessageType
from app.models.group import Group
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class MessageService(BaseService):
    """
    Mesaj gönderme ve planlama servisi.
    
    Zamanlanan mesajları kontrol eder ve gönderim için işler.
    """
    
    service_name = "message_service"
    default_interval = 30  # 30 saniyede bir kontrol et
    
    def __init__(self, name='message_service', client=None, db=None, config=None, stop_event=None, *args, **kwargs):
        super().__init__(name=name)
        self.client = client
        self.db = db
        self.config = config
        self.stop_event = stop_event
        # Config'den ayarları al
        self.bot_enabled = getattr(settings, 'BOT_ENABLED', True)
        self.debug_mode = getattr(settings, 'DEBUG', False)
        self.batch_size = getattr(settings, 'MESSAGE_BATCH_SIZE', 50)
        self.batch_interval = getattr(settings, 'MESSAGE_BATCH_INTERVAL', 30)
        self.initialized = False
        self.running = False  # Servis çalışma durumu
        logger.info(f"MessageService başlatıldı. Bot aktif: {self.bot_enabled}")
    
    async def update(self):
        """Periyodik olarak çalışacak ana metod"""
        try:
            logger.debug("MessageService update fonksiyonu çalışıyor")
            await self.check_scheduled_messages()
        except Exception as e:
            logger.error(f"Mesaj servisi hatası: {e}", exc_info=True)
    
    async def schedule_message(
        self, 
        content: str, 
        group_id: int, 
        scheduled_for: Optional[datetime] = None,
        message_type: MessageType = MessageType.TEXT,
        media_path: Optional[str] = None,
        **kwargs
    ) -> Optional[Message]:
        """
        Yeni bir mesaj planlar
        
        Args:
            content: Mesaj içeriği
            group_id: Hedef grup ID'si
            scheduled_for: Gönderim zamanı (None ise hemen gönderilir)
            message_type: Mesaj tipi (TEXT, PHOTO vb.)
            media_path: Medya için dosya yolu
            **kwargs: Ek parametreler
        
        Returns:
            Oluşturulan mesaj objesi
        """
        try:
            logger.debug(f"Yeni mesaj planlanıyor: {content[:50]}... Grup: {group_id}, Zaman: {scheduled_for}")
            
            # Mesaj tipi ve durumunu normalize et
            normalized_type = MessageType.normalize(message_type)
            normalized_status = MessageStatus.SCHEDULED if scheduled_for else MessageStatus.PENDING
            
            # Mesaj oluştur
            message = Message(
                content=content,
                group_id=group_id,
                message_type=normalized_type.value,
                status=normalized_status.value,
                scheduled_for=scheduled_for,
                **kwargs
            )
            
            # Veri tabanına kaydet
            session = next(get_session())
            session.add(message)
            session.commit()
            session.refresh(message)
            
            logger.info(f"Mesaj planlandı: ID={message.id}, Grup={group_id}, Zaman={scheduled_for}")
            
            # Hemen gönderilecekse doğrudan göndermeyi başlat
            if not scheduled_for:
                # Async olarak başlat ve sonucu bekleme
                asyncio.create_task(self.send_message(message.id))
            
            return message
        except Exception as e:
            logger.error(f"Mesaj planlama hatası: {e}", exc_info=True)
            return None
    
    async def check_scheduled_messages(self):
        """Zamanlanmış mesajları kontrol et ve gönderme zamanı gelenleri işle"""
        try:
            now = datetime.utcnow()
            logger.debug(f"Zamanlanmış mesajlar kontrol ediliyor: {now}")
            
            session = next(get_session())
            
            # Hem büyük harf hem küçük harf status değerlerini kontrol et
            query = text("""
                SELECT id, group_id, content, status, scheduled_for, message_type
                FROM messages
                WHERE (UPPER(status) = :status_upper) AND scheduled_for <= :now
                ORDER BY scheduled_for
                LIMIT :limit
            """)
            
            results = session.execute(
                query, 
                {
                    "status_upper": MessageStatus.SCHEDULED.value.upper(), 
                    "now": now, 
                    "limit": self.batch_size
                }
            ).all()
            
            if not results:
                logger.debug("Gönderilecek zamanlanmış mesaj bulunamadı.")
                return
                
            logger.info(f"{len(results)} adet zamanlanmış mesaj gönderilecek")
            
            # Her bir mesajı göndermeyi başlat
            for row in results:
                message_id = row[0]
                logger.debug(f"Mesaj {message_id} gönderiliyor: Grup={row[1]}")
                # Async olarak başlat ve sonucu bekleme
                asyncio.create_task(self.send_message(message_id))
                
        except Exception as e:
            logger.error(f"Zamanlanmış mesaj işleme hatası: {e}", exc_info=True)
    
    async def send_message(self, message_id: int) -> bool:
        """
        Mesajı gönderir
        
        Args:
            message_id: Gönderilecek mesajın ID'si
            
        Returns:
            bool: Başarı durumu
        """
        session = None
        try:
            logger.debug(f"send_message çağrıldı: message_id={message_id}")
            session = next(get_session())
            
            # Mesajı veritabanından al
            message_query = text("""
                SELECT id, group_id, content, status, message_type, media_path, reply_to_message_id, scheduled_for
                FROM messages
                WHERE id = :message_id
            """)
            message_result = session.execute(message_query, {"message_id": message_id}).first()
            
            if not message_result:
                logger.error(f"Mesaj bulunamadı: ID={message_id}")
                return False
                
            message_id = message_result[0]
            group_id = message_result[1]
            content = message_result[2]
            status = message_result[3]
            message_type = message_result[4]
            media_path = message_result[5]
            reply_to_message_id = message_result[6]
            scheduled_for = message_result[7]
            
            # Grubu veritabanından al - doğrudan SQL ile çekelim
            group_query = text("""
                SELECT group_id, name, is_active 
                FROM groups 
                WHERE group_id = :group_id
            """)
            group_result = session.execute(group_query, {"group_id": group_id}).first()
            
            if not group_result:
                logger.info(f"Grup veritabanında bulunamadı: ID={group_id}. Otomatik olarak oluşturulacak.")
                
                # Grubu bulamadıysak, Telegram API ile bilgilerini almaya çalışalım
                try:
                    from app.core.unified.client import get_client
                    client = await get_client()
                    if not client:
                        logger.error("Telegram client bağlantısı alınamadı")
                        return False
                        
                    # Grup bilgilerini almaya çalış
                    try:
                        entity = await client.get_entity(group_id)
                        if entity:
                            group_name = getattr(entity, 'title', f"Grup {group_id}")
                            logger.info(f"Telegram'dan grup bilgileri alındı: {group_name} ({group_id})")
                            
                            # Grubu veritabanına ekle
                            new_group_query = text("""
                                INSERT INTO groups (group_id, name, is_active, created_at, updated_at)
                                VALUES (:group_id, :name, TRUE, NOW(), NOW())
                                ON CONFLICT (group_id) DO UPDATE
                                SET name = EXCLUDED.name, is_active = TRUE, updated_at = NOW()
                                RETURNING group_id, name, is_active
                            """)
                            
                            new_group_result = session.execute(
                                new_group_query, 
                                {"group_id": group_id, "name": group_name}
                            ).first()
                            
                            session.commit()
                            
                            if new_group_result:
                                logger.info(f"Grup veritabanına eklendi: {group_name} ({group_id})")
                                target_group_id = new_group_result[0]
                                group_name = new_group_result[1]
                                group_is_active = new_group_result[2]
                            else:
                                logger.error(f"Grup eklenemedi: {group_id}")
                                # Mesajı başarısız olarak işaretle
                                update_query = text("""
                                    UPDATE messages
                                    SET status = :status, error = :error
                                    WHERE id = :message_id
                                """)
                                session.execute(
                                    update_query, 
                                    {"status": MessageStatus.FAILED.value, "error": "Grup bulunamadı ve eklenemedi", "message_id": message_id}
                                )
                                session.commit()
                                return False
                        else:
                            logger.error(f"Telegram'dan grup bilgisi alınamadı: {group_id}")
                            # Mesajı başarısız olarak işaretle
                            update_query = text("""
                                UPDATE messages
                                SET status = :status, error = :error
                                WHERE id = :message_id
                            """)
                            session.execute(
                                update_query, 
                                {"status": MessageStatus.FAILED.value, "error": "Grup Telegram'da bulunamadı", "message_id": message_id}
                            )
                            session.commit()
                            return False
                    except Exception as get_entity_error:
                        logger.error(f"Grup bilgileri alınırken hata: {str(get_entity_error)}")
                        
                        # Varsayılan grup bilgileri ile devam et
                        group_name = f"Grup {group_id}"
                        
                        # Grubu veritabanına ekle
                        new_group_query = text("""
                            INSERT INTO groups (group_id, name, is_active, created_at, updated_at)
                            VALUES (:group_id, :name, TRUE, NOW(), NOW())
                            ON CONFLICT (group_id) DO UPDATE
                            SET name = EXCLUDED.name, is_active = TRUE, updated_at = NOW()
                            RETURNING group_id, name, is_active
                        """)
                        
                        new_group_result = session.execute(
                            new_group_query, 
                            {"group_id": group_id, "name": group_name}
                        ).first()
                        
                        session.commit()
                        
                        if new_group_result:
                            logger.info(f"Varsayılan bilgilerle grup veritabanına eklendi: {group_name} ({group_id})")
                            target_group_id = new_group_result[0]
                            group_name = new_group_result[1]
                            group_is_active = new_group_result[2]
                        else:
                            logger.error(f"Grup eklenemedi: {group_id}")
                            # Mesajı başarısız olarak işaretle
                            update_query = text("""
                                UPDATE messages
                                SET status = :status, error = :error
                                WHERE id = :message_id
                            """)
                            session.execute(
                                update_query, 
                                {"status": MessageStatus.FAILED.value, "error": "Grup bulunamadı ve eklenemedi", "message_id": message_id}
                            )
                            session.commit()
                            return False
                except Exception as e:
                    logger.error(f"Grup otomatik oluşturma hatası: {str(e)}")
                    # Mesajı başarısız olarak işaretle
                    update_query = text("""
                        UPDATE messages
                        SET status = :status, error = :error
                        WHERE id = :message_id
                    """)
                    session.execute(
                        update_query, 
                        {"status": MessageStatus.FAILED.value, "error": f"Grup bulunamadı: {str(e)}", "message_id": message_id}
                    )
                    session.commit()
                    return False
            else:
                target_group_id = group_result[0]
                group_name = group_result[1] or "Adsız Grup"
                group_is_active = group_result[2] if len(group_result) > 2 else True
            
            # Grup aktif değilse mesajı işleme
            if not group_is_active:
                logger.warning(f"Grup aktif değil: {group_name} ({target_group_id}), mesaj gönderilmiyor")
                update_query = text("""
                    UPDATE messages
                    SET status = :status, error = :error
                    WHERE id = :message_id
                """)
                session.execute(
                    update_query, 
                    {"status": MessageStatus.FAILED.value, "error": "Grup aktif değil", "message_id": message_id}
                )
                session.commit()
                return False
            
            # Bot aktif değilse sadece güncelle
            if not self.bot_enabled:
                logger.warning("Bot devre dışı olduğundan mesaj gerçekten gönderilmiyor")
                update_query = text("""
                    UPDATE messages
                    SET status = :status, sent_at = :sent_at
                    WHERE id = :message_id
                """)
                session.execute(
                    update_query, 
                    {"status": MessageStatus.SENT.value, "sent_at": datetime.utcnow(), "message_id": message_id}
                )
                session.commit()
                return True
            
            # Mesajın durumunu güncelle
            update_query = text("""
                UPDATE messages
                SET status = :status
                WHERE id = :message_id
            """)
            session.execute(
                update_query, 
                {"status": MessageStatus.PENDING.value, "message_id": message_id}
            )
            session.commit()
            
            # Debug modunda gerçek gönderim yapma, sadece log göster
            if self.debug_mode:
                logger.debug(f"DEBUG MODU: Mesaj gönderildi (simülasyon): {content[:50]}... -> Grup: {group_name}")
                # Mesajı başarılı olarak işaretle
                update_query = text("""
                    UPDATE messages
                    SET status = :status, sent_at = :sent_at
                    WHERE id = :message_id
                """)
                session.execute(
                    update_query, 
                    {"status": MessageStatus.SENT.value, "sent_at": datetime.utcnow(), "message_id": message_id}
                )
                session.commit()
                return True
            
            # Gönderim için Telegram Client'a ihtiyaç var
            from app.core.unified.client import get_client
            
            client = await get_client()
            if not client:
                logger.error("Telegram client bağlantısı alınamadı")
                update_query = text("""
                    UPDATE messages
                    SET status = :status, error = :error
                    WHERE id = :message_id
                """)
                session.execute(
                    update_query, 
                    {"status": MessageStatus.FAILED.value, "error": "Telegram client bağlantısı yok", "message_id": message_id}
                )
                session.commit()
                return False
                
            logger.debug(f"Mesaj gönderiliyor: {content[:50]}... -> Grup: {group_name}")
            
            # Mesaj tipine göre gönderme işlemini yap
            try:
                # Mesaj tipini normalize et (büyük/küçük harf duyarsız)
                normalized_type = MessageType.normalize(message_type)
                
                if normalized_type == MessageType.TEXT:
                    await client.send_message(
                        target_group_id, 
                        content,
                        reply_to=reply_to_message_id
                    )
                elif normalized_type == MessageType.PHOTO:
                    await client.send_file(
                        target_group_id,
                        media_path,
                        caption=content,
                        reply_to=reply_to_message_id
                    )
                elif normalized_type == MessageType.VIDEO:
                    await client.send_file(
                        target_group_id,
                        media_path,
                        caption=content,
                        reply_to=reply_to_message_id,
                        attributes=[{"ATTR_TYPES": ["video"]}]
                    )
                elif normalized_type == MessageType.DOCUMENT:
                    await client.send_file(
                        target_group_id,
                        media_path,
                        caption=content,
                        reply_to=reply_to_message_id,
                        force_document=True
                    )
                else:
                    logger.warning(f"Desteklenmeyen mesaj tipi: {message_type}, TEXT olarak gönderiliyor")
                    await client.send_message(
                        target_group_id, 
                        content,
                        reply_to=reply_to_message_id
                    )
                    
                # Mesajı başarılı olarak işaretle
                update_query = text("""
                    UPDATE messages
                    SET status = :status, sent_at = :sent_at, error = NULL
                    WHERE id = :message_id
                """)
                session.execute(
                    update_query, 
                    {"status": MessageStatus.SENT.value, "sent_at": datetime.utcnow(), "message_id": message_id}
                )
                
                # Grup istatistiklerini güncelle
                group_update_query = text("""
                    UPDATE groups 
                    SET message_count = COALESCE(message_count, 0) + 1, 
                        last_message = :now 
                    WHERE group_id = :group_id
                """)
                session.execute(group_update_query, {"now": datetime.utcnow(), "group_id": target_group_id})
                
                session.commit()
                
                logger.info(f"Mesaj başarıyla gönderildi: ID={message_id}, Grup={group_name}")
                return True
                
            except Exception as send_error:
                logger.error(f"Mesaj gönderme hatası: {send_error}", exc_info=True)
                
                # Mesajı başarısız olarak işaretle
                update_query = text("""
                    UPDATE messages
                    SET status = :status, error = :error
                    WHERE id = :message_id
                """)
                session.execute(
                    update_query, 
                    {"status": MessageStatus.FAILED.value, "error": str(send_error), "message_id": message_id}
                )
                
                # Grup hata sayısını artır
                group_error_query = text("""
                    UPDATE groups 
                    SET error_count = COALESCE(error_count, 0) + 1,
                        last_error = :error
                    WHERE group_id = :group_id
                """)
                session.execute(group_error_query, {"error": str(send_error), "group_id": target_group_id})
                
                session.commit()
                
                return False
                
        except Exception as e:
            logger.error(f"Mesaj gönderme işleminde beklenmeyen hata: {e}", exc_info=True)
            
            # Veritabanı işlemini tamamlamaya çalış
            if session:
                try:
                    update_query = text("""
                        UPDATE messages
                        SET status = :status, error = :error
                        WHERE id = :message_id
                    """)
                    session.execute(
                        update_query, 
                        {"status": MessageStatus.FAILED.value, "error": f"İşlem hatası: {str(e)}", "message_id": message_id}
                    )
                    session.commit()
                except Exception as db_error:
                    logger.error(f"Veritabanı güncelleme hatası: {db_error}")
            
            return False
    
    async def initialize(self) -> bool:
        """
        Mesaj servisini başlatır.
        
        Returns:
            bool: Başarılıysa True
        """
        try:
            logger.info("Mesaj servisi başlatılıyor")
            
            # Telegram istemcisi kontrolü
            from app.core.unified.client import get_client
            self.client = await get_client()
            
            self.initialized = True
            logger.info(f"Mesaj servisi başlatıldı (batch_size: {self.batch_size}, batch_interval: {self.batch_interval}s)")
            return True
        except Exception as e:
            logger.exception(f"Mesaj servisi başlatma hatası: {str(e)}")
            return False
    
    async def start(self) -> bool:
        """Servisi başlatır"""
        if self.initialized:
            self.running = True
            return True
        success = await self.initialize()
        if success:
            self.running = True
        return success
    
    # BaseService'den gelen soyut metotları uygula
    async def _start(self) -> bool:
        """
        BaseService için start metodu
        
        Returns:
            bool: Başarılıysa True
        """
        return await self.initialize()
            
    async def _stop(self) -> bool:
        """
        BaseService için stop metodu
        
        Returns:
            bool: Başarılıysa True
        """
        try:
            logger.info("Mesaj servisi durduruluyor")
            self.initialized = False
            self.running = False
            logger.info("Mesaj servisi durduruldu")
            return True
        except Exception as e:
            logger.exception(f"Mesaj servisi durdurma hatası: {str(e)}")
            return False
            
    async def _update(self) -> None:
        """
        BaseService için periyodik güncelleme metodu
        """
        try:
            logger.debug("MessageService güncelleniyor")
            await self.check_scheduled_messages()
        except Exception as e:
            logger.error(f"Mesaj servisi güncelleme hatası: {e}", exc_info=True)
            
    async def stop(self) -> bool:
        """
        Mesaj servisini durdurur.
        
        Returns:
            bool: Başarılıysa True
        """
        try:
            logger.info("Mesaj servisi durduruluyor")
            
            # Telegram istemcisini kapatma
            # İstemci başka servisler tarafından da kullanılıyor olabilir
            # Bu nedenle burada kapatmıyoruz
            
            self.initialized = False
            self.running = False
            logger.info("Mesaj servisi durduruldu")
            return True
        except Exception as e:
            logger.exception(f"Mesaj servisi durdurma hatası: {str(e)}")
            return False
            
    async def run(self) -> None:
        """Servis ana döngüsü"""
        logger.info("MessageService döngüsü başladı")
        
        try:
            self.running = True
            while not getattr(self, 'stop_event', None) or not self.stop_event.is_set():
                try:
                    if not self.initialized:
                        logger.warning("MessageService henüz başlatılmadı, güncelleme atlanıyor")
                        await asyncio.sleep(5)
                        continue
                    
                    # Zamanlanmış mesajları kontrol et
                    await self.check_scheduled_messages()
                    
                    # Bir sonraki kontrole kadar bekle
                    await asyncio.sleep(self.batch_interval)
                except asyncio.CancelledError:
                    logger.info("MessageService döngüsü iptal edildi")
                    break
                except Exception as e:
                    logger.exception(f"Mesaj servisi döngüsünde hata: {str(e)}")
                    await asyncio.sleep(5)  # Hata durumunda kısa beklet
        except asyncio.CancelledError:
            logger.info("MessageService döngüsü iptal edildi")
        except Exception as e:
            logger.exception(f"MessageService döngüsünde kritik hata: {str(e)}")
        finally:
            self.running = False
            logger.info("MessageService döngüsü sonlandı")
            
    async def cancel_scheduled_message(self, message_id: int) -> bool:
        """
        Planlanmış mesajı iptal eder.
        
        Args:
            message_id: İptal edilecek mesaj ID'si
            
        Returns:
            bool: İptal işlemi başarılıysa True
        """
        # Veritabanı oturumu al
        session = next(get_session())
        try:
            # Mesajı al
            message = session.get(Message, message_id)
            if not message:
                logger.error(f"Mesaj bulunamadı: {message_id}")
                return False
                
            # Mesaj planlanmış mı kontrol et - UPPER kullan
            message_status_upper = message.status.upper() if message.status else ""
            if message_status_upper != MessageStatus.SCHEDULED.value.upper():
                logger.error(f"Mesaj planlanmış durumda değil: {message_id}, durum: {message.status}")
                return False
                
            # Mesajı sil
            session.delete(message)
            session.commit()
            
            logger.info(f"Planlanmış mesaj iptal edildi: {message_id}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.exception(f"Mesaj iptal etme hatası: {str(e)}")
            return False
        finally:
            session.close()
            
    async def get_scheduled_messages(self, group_id: Optional[int] = None) -> List[Message]:
        """
        Planlanmış mesajları getirir.
        
        Args:
            group_id: Belirli bir grubun mesajlarını almak için grup ID'si
            
        Returns:
            List[Message]: Planlanmış mesajlar
        """
        # Veritabanı oturumu al
        session = next(get_session())
        try:
            # UPPER ile karşılaştırma yaparak büyük-küçük harf farkını yok et
            query = text("""
                SELECT * FROM messages
                WHERE UPPER(status) = :status
                ORDER BY scheduled_for
            """)
            
            params = {"status": MessageStatus.SCHEDULED.value.upper()}
            
            # Eğer grup_id varsa, o gruba ait mesajları filtrele
            if group_id:
                query = text("""
                    SELECT * FROM messages
                    WHERE UPPER(status) = :status AND group_id = :group_id
                    ORDER BY scheduled_for
                """)
                params["group_id"] = group_id
                
            results = session.execute(query, params).all()
            
            # Sonuçları Message nesnelerine dönüştür
            messages = []
            for row in results:
                message = Message()
                for i, column in enumerate(session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'messages'")).scalars().all()):
                    if i < len(row):
                        setattr(message, column, row[i])
                messages.append(message)
                
            return messages
            
        except Exception as e:
            logger.exception(f"Planlanmış mesajları getirme hatası: {str(e)}")
            return []
        finally:
            session.close()
            
    async def get_status(self) -> Dict[str, Any]:
        """Servis durum bilgisini döndürür"""
        return {
            "name": self.service_name,
            "running": self.running,
            "initialized": self.initialized,
            "batch_size": self.batch_size,
            "batch_interval": self.batch_interval,
            "client_connected": bool(self.client and getattr(self.client, 'is_connected', lambda: False)())
        } 