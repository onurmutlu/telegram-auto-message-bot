"""
# ============================================================================ #
# Dosya: group_service.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/group_service.py
# İşlev: Telegram bot için grup yönetimi servisi.
#
# Amaç: Bu modül, grup keşfi, mesaj gönderimi, aktivite takibi ve
#       etkileşim yönetimi için gerekli fonksiyonları sağlar.
#
# Build: 2025-05-15-10:00:00
# Versiyon: v3.6.0
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
from sqlalchemy import text

# Custom imports
from app.services.base_service import BaseService
from app.utils.adaptive_rate_limiter import AdaptiveRateLimiter
from app.db.session import get_session

# Setup logger
logger = logging.getLogger(__name__)

class GroupService(BaseService):
    """
    Telegram grupları için servis sınıfı.
    Bu sınıf, grup keşfi, mesaj gönderimi, aktivite takibi ve
    etkileşim yönetimi için gerekli fonksiyonları sağlar.
    """
    
    service_name = "group_service"
    default_interval = 60  # 60 saniyede bir kontrol et
    
    def __init__(self, **kwargs):
        """
        GroupService sınıfının başlatıcısı.
        """
        super().__init__(**kwargs)
        
        # Grup verileri
        self.groups = {}
        self.active_groups = set()
        self.admin_groups = set()
        self.message_templates = {}
        self.group_stats = {}
        self.stats = {
            'total_groups': 0,
            'active_groups': 0,
            'admin_groups': 0,
            'last_update': None
        }
        
        self.initialized = False
        self.message_service = None
        self.logger.info("GroupService oluşturuldu")
    
    async def _start(self) -> bool:
        """
        Servisi başlatır ve gerekli kaynakları yükler.
        
        Returns:
            bool: Başlatma başarılıysa True
        """
        try:
            self.logger.info("GroupService başlatılıyor...")
            
            # Her adımı ayrı olarak ele alıp, bir hata olursa diğer adımlara devam edelim
            try:
                await self.load_groups()
            except Exception as e:
                self.logger.error(f"Gruplar yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir set ile devam et
                self.groups = {}
                self.active_groups = set()
            
            try:
                await self.load_admin_groups()
            except Exception as e:
                self.logger.error(f"Admin grupları yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir set ile devam et
                self.admin_groups = set()
            
            try:
                await self.load_message_templates()
            except Exception as e:
                self.logger.error(f"Mesaj şablonları yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir dict ile devam et
                self.message_templates = {}
            
            try:
                await self.load_group_stats()
            except Exception as e:
                self.logger.error(f"Grup istatistikleri yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir dict ile devam et
                self.group_stats = {}
            
            # Başarıyla tamamlandı
            self.initialized = True
            
            # İstatistikleri güncelle
            self.stats['total_groups'] = len(self.groups)
            self.stats['active_groups'] = len(self.active_groups)
            self.stats['admin_groups'] = len(self.admin_groups)
            self.stats['last_update'] = datetime.now()
            
            self.logger.info(f"GroupService başlatıldı. Toplam {self.stats['total_groups']} grup, " 
                             f"{self.stats['active_groups']} aktif, {self.stats['admin_groups']} admin.")
            return True
            
        except Exception as e:
            self.logger.error(f"GroupService başlatılırken genel hata: {str(e)}", exc_info=True)
            return False
    
    async def _stop(self) -> bool:
        """
        Servisi güvenli bir şekilde durdurur.
        
        Returns:
            bool: Durdurma başarılıysa True
        """
        try:
            self.logger.info("GroupService durduruluyor...")
            
            # Çalışan görevleri iptal et
            try:
                service_tasks = [task for task in asyncio.all_tasks() 
                            if (task.get_name().startswith(f"{self.get_service_name()}_task_")) and 
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
                self.logger.error(f"{self.get_service_name()} görevleri iptal edilirken hata: {str(e)}")
                
            self.initialized = False
            self.logger.info("GroupService durduruldu")
            return True
        except Exception as e:
            self.logger.error(f"GroupService durdurulurken hata: {str(e)}", exc_info=True)
            return False
    
    async def _update(self) -> None:
        """
        Düzenli aralıklarla çağrılan güncelleme metodu.
        Grup listesini ve istatistiklerini günceller.
        """
        try:
            if not self.initialized:
                self.logger.warning("GroupService henüz başlatılmadı, güncelleme atlanıyor")
                return
                
            self.logger.debug("GroupService güncelleniyor...")
            
            # Aktif grupları yenile
            await self.load_groups()
            
            # Grup istatistiklerini güncelle
            await self.load_group_stats()
            
            # İstatistikleri güncelle
            self.stats['total_groups'] = len(self.groups)
            self.stats['active_groups'] = len(self.active_groups)
            self.stats['admin_groups'] = len(self.admin_groups)
            self.stats['last_update'] = datetime.now()
            
            self.logger.debug(f"GroupService güncelleme tamamlandı. Toplam {self.stats['total_groups']} grup, "
                             f"{self.stats['active_groups']} aktif, {self.stats['admin_groups']} admin.")
        except Exception as e:
            self.logger.error(f"GroupService güncelleme hatası: {str(e)}", exc_info=True)
    
    async def initialize(self):
        """
        Servisi başlatır ve gerekli kaynakları yükler.
        """
        return await self._start()
    
    async def start(self) -> bool:
        """
        Servisi başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        if not self.initialized:
            await self.initialize()
            
        self.running = True
        self.start_time = datetime.now()
        logger.info(f"{self.service_name} servisi başlatıldı.")
        return True
    
    async def stop(self) -> bool:
        """
        Servisi güvenli bir şekilde durdurur.
        
        Returns:
            bool: Başarılı ise True
        """
        # Önce durum değişkenini güncelle
        self.running = False
        
        # Durdurma sinyalini ayarla (varsa)
        if hasattr(self, 'stop_event') and self.stop_event:
            self.stop_event.set()
            
        # Diğer durdurma sinyallerini de kontrol et
        if hasattr(self, 'shutdown_event'):
            self.shutdown_event.set()
        
        # Çalışan görevleri iptal et
        try:
            service_tasks = [task for task in asyncio.all_tasks() 
                        if (task.get_name().startswith(f"{self.service_name}_task_")) and 
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
        return True
        
    async def load_groups(self):
        """
        Grupları veritabanından yükler.
        """
        try:
            session = next(get_session())
            
            # SQL sorgusu ile aktif grupları çek - UPPER ile büyük/küçük harf duyarsızlığı
            query = text("""
                SELECT group_id, name, is_active, is_admin, created_at, updated_at
                FROM groups
                WHERE UPPER(is_active::text) = 'TRUE'
                ORDER BY updated_at DESC
            """)
            
            result = session.execute(query).all()
            
            # Grupları kaydet
            self.groups = {}
            self.active_groups = set()
            
            for row in result:
                group_id = row[0]
                name = row[1]
                is_active = row[2]
                is_admin = row[3]
                
                # Grup bilgisini kaydet
                self.groups[group_id] = {
                    'name': name,
                    'is_active': is_active,
                    'is_admin': is_admin
                }
                
                # Aktif grupları kaydet
                if is_active:
                    self.active_groups.add(group_id)
                
            self.logger.info(f"Toplam {len(self.groups)} grup yüklendi, {len(self.active_groups)} tanesi aktif")
            
        except Exception as e:
            self.logger.error(f"Gruplar yüklenirken hata: {str(e)}", exc_info=True)
            raise
            
    async def load_admin_groups(self):
        """
        Admin gruplarını veritabanından yükler.
        """
        try:
            session = next(get_session())
            
            # SQL sorgusu ile admin gruplarını çek - UPPER ile büyük/küçük harf duyarsızlığı
            query = text("""
                SELECT group_id, name
                FROM groups
                WHERE UPPER(is_admin::text) = 'TRUE' AND UPPER(is_active::text) = 'TRUE'
                ORDER BY updated_at DESC
            """)
            
            result = session.execute(query).all()
            
            # Admin gruplarını kaydet
            self.admin_groups = set()
            
            for row in result:
                group_id = row[0]
                
                # Admin grubunu kaydet
                self.admin_groups.add(group_id)
                
            self.logger.info(f"Toplam {len(self.admin_groups)} admin grubu yüklendi")
            
        except Exception as e:
            self.logger.error(f"Admin grupları yüklenirken hata: {str(e)}", exc_info=True)
            raise
    
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
            if not self.running:
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