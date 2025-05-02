"""
# ============================================================================ #
# Dosya: group_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/group_service.py
# İşlev: Telegram bot için grup yönetimi servisi.
#
# Amaç: Bu modül, grup keşfi, mesaj gönderimi, aktivite takibi ve
#       etkileşim yönetimi için gerekli fonksiyonları sağlar.
#
# Build: 2025-04-10-20:30:00
# Versiyon: v3.5.0
# ============================================================================ #
"""

import os
import re
import json
import time
import random
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Any, Optional, Union
from pathlib import Path
import traceback

from telethon import TelegramClient, functions, types, errors
from telethon.tl.functions.channels import GetFullChannelRequest, JoinChannelRequest, GetParticipantsRequest
from telethon.tl.functions.messages import GetDialogsRequest, ImportChatInviteRequest
from telethon.tl.types import InputPeerEmpty, InputPeerChannel, Channel, ChannelFull, User, PeerChannel, ChannelParticipantsRecent, ChannelParticipantsAdmins
from telethon.errors import FloodWaitError, ChannelPrivateError, UserBannedInChannelError, ChatAdminRequiredError

# Custom imports
from bot.services.base_service import BaseService
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter
from database.models import Group

# Setup logger
logger = logging.getLogger(__name__)

class GroupService(BaseService):
    """
    Telegram grupları için servis sınıfı.
    Bu sınıf, grup keşfi, mesaj gönderimi, aktivite takibi ve
    etkileşim yönetimi için gerekli fonksiyonları sağlar.
    """
    
    def __init__(self, client, config, db, stop_event=None):
        """
        GroupService sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            stop_event: Durdurma eventi (opsiyonel)
        """
        super().__init__("group", client, config, db, stop_event)
        
        # Grup verileri
        self.groups = {}
        self.active_groups = set()
        self.admin_groups = set()
        self.message_templates = {}
        self.group_stats = {}
        self.stats = {
            'total_groups': 0,
            'last_update': None
        }
        
        logger.info("GroupService başlatıldı")
    
    async def initialize(self):
        """
        Servisi başlatır ve gerekli kaynakları yükler.
        """
        try:
            logger.info("GroupService başlatılıyor...")
            
            # Her adımı ayrı olarak ele alıp, bir hata olursa diğer adımlara devam edelim
            try:
                await self.load_groups()
            except Exception as e:
                logger.error(f"Gruplar yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir set ile devam et
                self.groups = {}
                self.active_groups = set()
            
            try:
                await self.load_admin_groups()
            except Exception as e:
                logger.error(f"Admin grupları yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir set ile devam et
                self.admin_groups = set()
            
            try:
                await self.load_message_templates()
            except Exception as e:
                logger.error(f"Mesaj şablonları yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir dict ile devam et
                self.message_templates = {}
            
            try:
                await self.load_group_stats()
            except Exception as e:
                logger.error(f"Grup istatistikleri yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir dict ile devam et
                self.group_stats = {}
            
            # Başarıyla tamamlandı
            self.initialized = True
            logger.info("GroupService başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"GroupService başlatılırken genel hata: {str(e)}", exc_info=True)
            # Yine de True döndürelim, servisin diğer servislere bağlı olduğu durumlarda bile çalışması için
            self.initialized = True
            return True
    
    async def start(self) -> bool:
        """
        Servisi başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        if not self.initialized:
            await self.initialize()
            
        self.is_running = True
        self.start_time = datetime.now()
        logger.info(f"{self.service_name} servisi başlatıldı.")
        return True
    
    async def stop(self) -> None:
        """
        Servisi güvenli bir şekilde durdurur.
        
        Returns:
            None
        """
        # Önce durum değişkenini güncelle
        self.is_running = False
        
        # Durdurma sinyalini ayarla (varsa)
        if hasattr(self, 'stop_event') and self.stop_event:
            self.stop_event.set()
            
        # Diğer durdurma sinyallerini de kontrol et
        if hasattr(self, 'shutdown_event'):
            self.shutdown_event.set()
        
        # Çalışan görevleri iptal et
        try:
            service_tasks = [task for task in asyncio.all_tasks() 
                        if (task.get_name().startswith(f"{self.name}_task_") or
                            task.get_name().startswith(f"{self.service_name}_task_")) and 
                        not task.done() and not task.cancelled()]
                        
            for task in service_tasks:
                task.cancel()
                
            # Kısa bir süre bekle
            try:
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                pass
                
            # İptal edilen görevlerin tamamlanmasını kontrol et
            if service_tasks:
                await asyncio.wait(service_tasks, timeout=2.0)
        except Exception as e:
            logger.error(f"{self.service_name} görevleri iptal edilirken hata: {str(e)}")
            
        logger.info(f"{self.service_name} servisi durduruldu.")
        
    async def load_groups(self):
        """
        Grupları veritabanından yükler.
        """
        try:
            logger.info("Gruplar yükleniyor...")
            # Önce veritabanı bağlantısını kontrol et ve gerekirse yeniden bağlan
            if not self.db.connected or not self.db.cursor:
                await self.db.connect()
                if not self.db.cursor:
                    logger.error("Veritabanı bağlantısı kurulamadı, DB cursor null")
                    return False
                
            # Sütun adlarını açıkça belirterek veri çek
            query = """
            SELECT id, group_id, name, join_date, last_message, message_count, member_count, 
                  error_count, last_error, is_active, permanent_error, is_target, retry_after, is_admin
            FROM groups 
            WHERE is_active = TRUE
            """
            rows = await self.db.fetchall(query)
            
            if not rows:
                logger.warning("Aktif grup bulunamadı veya veritabanında grup tablosu yok.")
                return False
                
            for row in rows:
                if len(row) < 4:  # En azından id, group_id, name ve join_date olmalı
                    logger.warning(f"Grup verisi yeterli sütun içermiyor: {row}")
                    continue
                
                # Sütun indekslerini daha güvenli bir şekilde kullan
                group_id = row[1]  # group_id her zaman 2. sütun (indeks 1)
                
                self.groups[group_id] = {
                    "name": row[2] if len(row) > 2 else "Bilinmeyen Grup",
                    "join_date": row[3] if len(row) > 3 else None,
                    "last_message": row[4] if len(row) > 4 else None,
                    "message_count": row[5] if len(row) > 5 else 0,
                    "member_count": row[6] if len(row) > 6 else 0,
                    "error_count": row[7] if len(row) > 7 else 0,
                    "last_error": row[8] if len(row) > 8 else None,
                    "is_active": row[9] if len(row) > 9 else True,
                    "permanent_error": row[10] if len(row) > 10 else False,
                    "is_target": row[11] if len(row) > 11 else False,
                    "retry_after": row[12] if len(row) > 12 else None,
                    "is_admin": row[13] if len(row) > 13 else False
                }
                self.active_groups.add(group_id)
            
            logger.info(f"{len(self.groups)} grup yüklendi")
            return True
        except Exception as e:
            logger.error(f"Gruplar yüklenirken hata: {str(e)}", exc_info=True)
            return False
    
    async def load_admin_groups(self):
        """
        Admin gruplarını veritabanından yükler.
        """
        try:
            logger.info("Admin grupları yükleniyor...")
            
            # Önce veritabanı bağlantısını kontrol et ve gerekirse yeniden bağlan
            if not self.db.connected or not self.db.cursor:
                await self.db.connect()
                if not self.db.cursor:
                    logger.error("Veritabanı bağlantısı kurulamadı, DB cursor null")
                    return False
            
            # Açık sütun adlarını kullanarak sorgu
            query = """
            SELECT group_id 
            FROM groups 
            WHERE is_admin = TRUE AND is_active = TRUE
            """
            rows = await self.db.fetchall(query)
            
            if not rows:
                logger.warning("Admin grup bulunamadı veya veritabanında grup tablosu yok.")
                return False
            
            self.admin_groups = set()
            for row in rows:
                if row and len(row) > 0:
                    self.admin_groups.add(row[0])
            
            logger.info(f"{len(self.admin_groups)} admin grubu yüklendi")
            return True
        except Exception as e:
            logger.error(f"Admin grupları yüklenirken hata: {str(e)}", exc_info=True)
            return False
    
    async def load_message_templates(self):
        """
        Mesaj şablonlarını veritabanından yükler.
        """
        try:
            logger.info("Mesaj şablonları yükleniyor...")
            
            # Veritabanı bağlantısını kontrol et
            if not self.db.connected or not self.db.cursor:
                await self.db.connect()
                if not self.db.cursor:
                    logger.error("Veritabanı bağlantısı kurulamadı, DB cursor null")
                    return
            
            query = "SELECT id, content, category, language FROM message_templates WHERE is_active = TRUE"
            rows = await self.db.fetchall(query)
            
            if not rows:
                logger.warning("Aktif mesaj şablonu bulunamadı.")
                return
            
            for row in rows:
                if len(row) >= 4:
                    template_id = row[0]
                    self.message_templates[template_id] = {
                        "content": row[1],
                        "category": row[2],
                        "language": row[3]
                    }
            
            logger.info(f"{len(self.message_templates)} mesaj şablonu yüklendi")
        except Exception as e:
            logger.error(f"Mesaj şablonları yüklenirken hata: {str(e)}", exc_info=True)
            # Hata durumunda varsayılan şablonlarla devam et
            self.message_templates = {}
    
    async def load_group_stats(self):
        """
        Grup istatistiklerini veritabanından yükler.
        """
        try:
            logger.info("Grup istatistikleri yükleniyor...")
            
            # Veritabanı bağlantısını kontrol et
            if not self.db.connected or not self.db.cursor:
                await self.db.connect()
                if not self.db.cursor:
                    logger.error("Veritabanı bağlantısı kurulamadı, DB cursor null")
                    return
            
            query = """
                SELECT group_id, COUNT(*) as message_count, 
                       MAX(sent_at) as last_message
                FROM messages
                GROUP BY group_id
            """
            rows = await self.db.fetchall(query)
            
            if not rows:
                logger.warning("Grup istatistiği bulunamadı.")
                return
            
            for row in rows:
                if len(row) >= 3:
                    group_id = row[0]
                    self.group_stats[group_id] = {
                        "message_count": row[1],
                        "last_message": row[2]
                    }
            
            logger.info(f"{len(self.group_stats)} grup istatistiği yüklendi")
        except Exception as e:
            logger.error(f"Grup istatistikleri yüklenirken hata: {str(e)}", exc_info=True)
            # Hata durumunda boş istatistiklerle devam et
            self.group_stats = {}
        
    async def get_group(self, group_id):
        """Grup bilgilerini getirir"""
        return self.groups.get(group_id)
        
    async def is_group_active(self, group_id):
        """Grubun aktif olup olmadığını kontrol eder"""
        return group_id in self.active_groups
        
    async def is_admin_group(self, group_id):
        """Grubun admin grubu olup olmadığını kontrol eder"""
        return group_id in self.admin_groups
        
    async def get_group_stats(self, group_id):
        """Grup istatistiklerini getirir"""
        return self.group_stats.get(group_id, {
            'message_count': 0,
            'last_message': None
        })
        
    async def get_message_template(self, group_type):
        """Grup tipine göre rastgele bir mesaj şablonu getirir"""
        templates = self.message_templates.get(group_type, [])
        if not templates:
            return None
        return random.choice(templates)

    async def add_group(self, group_id, name, is_admin=False):
        """Yeni grup ekler"""
        try:
            group = {
                'group_id': group_id,
                'name': name,
                'is_admin': is_admin,
                'is_active': True,
                'join_date': datetime.now(),
                'last_message': None,
                'message_count': 0,
                'member_count': 0,
                'error_count': 0,
                'last_error': None,
                'permanent_error': False,
                'is_target': False,
                'retry_after': None
            }
            
            # Veritabanı bağlantısını kontrol et
            if not self.db.connected or not self.db.conn or not self.db.cursor:
                try:
                    await self.db.connect()
                except Exception as db_error:
                    logger.error(f"Veritabanı bağlantısı kurulamadı: {str(db_error)}")
                    # Bağlantı kurulamazsa, grubu sadece bellekte tut
                    self.groups[group_id] = group
                    self.active_groups.add(group_id)
                    if is_admin:
                        self.admin_groups.add(group_id)
                    logger.warning(f"Grup sadece bellekte eklendi (DB bağlantı hatası): {group_id} - {name}")
                    return True
            
            # Bağlantı başarılıysa
            if self.db.connected and self.db.cursor:
                try:
                    # SQL sorgusunu ve parametrelerini hazırla
                    query = """
                        INSERT INTO groups (group_id, name, is_admin, is_active, join_date) 
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (group_id) DO UPDATE SET 
                        name = EXCLUDED.name, is_admin = EXCLUDED.is_admin, is_active = EXCLUDED.is_active
                    """
                    params = (group_id, name, is_admin, True, group['join_date'])
                    
                    # Execute sorgusu
                    self.db.cursor.execute(query, params)
                    self.db.conn.commit()
                except Exception as db_error:
                    logger.error(f"Grup veritabanına eklenirken hata: {str(db_error)}")
                    # Hata oluşursa, groups tablosunda yetki sorunu olabilir, yine de bellekte tut
            
            # Her durumda, grup bellekte tutulur
            self.groups[group_id] = group
            self.active_groups.add(group_id)
            if is_admin:
                self.admin_groups.add(group_id)
                
            logger.info(f"Grup eklendi: {group_id} - {name}")
            return True
            
        except Exception as e:
            logger.error(f"Grup eklenirken hata: {str(e)}")
            # Kritik hata durumunda bile, grubu bellekte tutmaya çalış
            try:
                self.groups[group_id] = {
                    'group_id': group_id,
                    'name': name,
                    'is_admin': is_admin,
                    'is_active': True,
                    'join_date': datetime.now()
                }
                self.active_groups.add(group_id)
                if is_admin:
                    self.admin_groups.add(group_id)
                logger.warning(f"Grup sadece bellekte eklendi (kritik hata sonrası): {group_id} - {name}")
            except:
                pass
            return False
            
    async def remove_group(self, group_id):
        """Grubu kaldırır"""
        try:
            # SQL sorgusu
            query = "DELETE FROM groups WHERE group_id = %s"
            
            # Execute sorgusu
            self.db.cursor.execute(query, (group_id,))
            self.db.conn.commit()
            
            if group_id in self.groups:
                del self.groups[group_id]
            self.active_groups.discard(group_id)
            self.admin_groups.discard(group_id)
            
            logger.info(f"Grup kaldırıldı: {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"Grup kaldırılırken hata: {str(e)}")
            return False
            
    async def send_message(self, group_id, template_type, category=None, **kwargs):
        """Gruba mesaj gönderir"""
        try:
            if not self.is_running:
                logger.error("Grup servisi çalışmıyor")
                return False
                
            if group_id not in self.groups:
                logger.error(f"Grup bulunamadı: {group_id}")
                return False
                
            if not self.message_service:
                logger.error("Mesaj servisi bağlı değil")
                return False
                
            return await self.message_service.send_message(group_id, template_type, category, **kwargs)
            
        except Exception as e:
            logger.error(f"Mesaj gönderilirken hata: {str(e)}")
            return False
            
    def set_message_service(self, message_service):
        """Mesaj servisini ayarlar"""
        self.message_service = message_service
        
    async def get_target_groups(self):
        """
        Hedef grupların listesini döndürür.
        Grup işleyicisi tarafından kullanılır.
        
        Returns:
            list: Hedef grup listesi
        """
        try:
            groups_list = []
            
            # Veritabanı bağlantısını kontrol et
            if not self.db.connected:
                await self.db.connect()
                
            # Aktif grupları al
            query = """
                SELECT group_id, name, member_count, is_active, last_message, join_date
                FROM groups 
                WHERE is_active = TRUE
                ORDER BY member_count DESC
            """
            rows = await self.db.fetchall(query)
            
            if not rows:
                logger.warning("Hedef grup bulunamadı.")
                return []
            
            for row in rows:
                group_id = row[0]
                groups_list.append({
                    'group_id': group_id,
                    'name': row[1],
                    'member_count': row[2] or 0,
                    'is_active': bool(row[3]),
                    'last_message': row[4],
                    'join_date': row[5]
                })
            
            logger.info(f"{len(groups_list)} hedef grup bulundu.")
            return groups_list
            
        except Exception as e:
            logger.error(f"Hedef gruplar alınırken hata: {str(e)}")
            return []

    async def discover_groups(self, limit=100, offset_date=None):
        """
        Telegram diyaloglarından grupları keşfeder ve veritabanına kaydeder.
        
        Args:
            limit (int): Keşfedilecek maksimum grup sayısı
            offset_date (datetime): Bu tarihten önce oluşturulan grupları keşfet
            
        Returns:
            list: Keşfedilen grupların listesi
        """
        try:
            logger.info(f"Grup keşfi başlatılıyor... (limit: {limit})")
            
            # Keşfedilen grupların listesi
            discovered_groups = []
            
            # GetDialogsRequest ile tüm diyalogları al - daha agresif limit kullan
            result = await self.client(GetDialogsRequest(
                offset_date=offset_date,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=limit * 2,  # Daha fazla dialog almak için limit 2 katına çıkarıldı
                hash=0
            ))
            
            chats = result.chats
            
            # Grupları filtrele
            for chat in chats:
                # Sadece gruplar ve süper gruplar
                if hasattr(chat, 'title') and (
                    isinstance(chat, types.Chat) or 
                    isinstance(chat, types.Channel) and chat.megagroup
                ):
                    group_id = -chat.id  # Grup ID'leri negatif olmalı
                    
                    # Veritabanına kaydet veya mevcut grubu güncelle
                    if group_id not in self.groups:
                        await self.add_group(
                            group_id=group_id,
                            name=chat.title,
                            is_admin=False
                        )
                        discovered_groups.append({
                            'id': group_id,
                            'title': chat.title,
                            'is_new': True
                        })
                    else:
                        # Mevcut grupları da güncelle
                        await self._update_group_details(
                            group_id=group_id,
                            name=chat.title
                        )
                        discovered_groups.append({
                            'id': group_id,
                            'title': chat.title,
                            'is_new': False
                        })
            
            logger.info(f"{len(discovered_groups)} grup keşfedildi. {sum(1 for g in discovered_groups if g['is_new'])} yeni grup.")
            return discovered_groups
            
        except Exception as e:
            logger.error(f"Grup keşfi hatası: {str(e)}", exc_info=True)
            return []
    
    async def _update_group_details(self, group_id, name):
        """
        Mevcut grupların bilgilerini günceller.
        
        Args:
            group_id: Güncellenecek grup ID'si
            name: Grup adı
        """
        try:
            # Önce veritabanı bağlantısını kontrol et
            if not self.db.connected or not self.db.cursor:
                await self.db.connect()
                
            # Grup detaylarını güncelle
            query = """
            UPDATE groups SET 
                name = %s,
                updated_at = NOW(),
                last_active = NOW(),
                is_active = TRUE
            WHERE group_id = %s
            """
            
            await self.db.execute(query, (name, group_id))
            
            # Eğer grubu lokal hafızada tutuyorsak orada da güncelle
            if group_id in self.groups:
                self.groups[group_id]["name"] = name
                self.groups[group_id]["is_active"] = True
                # Aktif gruplar listesinde yoksa ekle
                if group_id not in self.active_groups:
                    self.active_groups.add(group_id)
        except Exception as e:
            logger.error(f"Grup detayları güncellenirken hata: {str(e)}")