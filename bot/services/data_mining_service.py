"""
# ============================================================================ #
# Dosya: data_mining_service.py
# İşlev: Telegram gruplarından detaylı kullanıcı verilerini toplama ve analiz.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
import pandas as pd
import random
import traceback
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
import functools

from telethon import errors, functions, types
from bot.services.base_service import BaseService

logger = logging.getLogger(__name__)

class DataMiningService(BaseService):
    """
    Telegram gruplarından detaylı kullanıcı verilerini toplama ve analiz servisi.
    
    Bu servis şunları yapar:
    1. Tüm erişilebilir gruplardan kullanıcı bilgilerini toplar
    2. Kullanıcıların demografik verilerini analiz eder
    3. Hedefli kampanyalar için kullanıcı segmentleri oluşturur
    """
    
    def __init__(self, client, config, db, stop_event=None):
        """Servis başlatıcı."""
        super().__init__("datamining", client, config, db, stop_event)
        
        # Ana değişkenler
        self.groups = {}             # Grup ID -> Grup bilgileri
        self.total_users_mined = 0   # Toplanan toplam kullanıcı sayısı
        self.total_groups_mined = 0  # Taranan toplam grup sayısı
        self.last_mining_time = None # Son veri toplama zamanı
        self.mining_stats = {}       # İstatistikler
        
        # Kullanıcı segmentleri
        self.segments = {
            "active": set(),      # Son 7 günde aktif kullanıcılar
            "influencer": set(),  # Çok takipçisi olan kullanıcılar
            "casual": set(),      # Ara sıra aktif olan kullanıcılar
            "new": set(),         # Son 30 günde katılan yeni kullanıcılar
            "premium": set(),     # Premium/VIP kullanıcılar
            "dormant": set()      # 30 günden fazla süredir aktif olmayan kullanıcılar
        }
        
        # Veri toplama parametreleri
        self.settings = {
            "mining_interval_hours": 24,    # Her 24 saatte bir tam veri toplama
            "incremental_interval_min": 60, # Her 60 dakikada bir artırımlı toplama
            "max_users_per_group": 500,     # Her gruptan maksimum kullanıcı sayısı
            "max_groups_per_run": 20,       # Her çalıştırmada maksimum grup sayısı
            "store_profile_pictures": True, # Profil resimlerini sakla
            "analyze_bio_text": True,       # Bio metinlerini analiz et
            "gather_language_data": True,   # Dil verilerini topla
            "deep_user_analysis": False     # Derinlemesine kullanıcı analizi (yavaş)
        }
        
        # Diğer servislerle entegrasyon
        self.services = {}
        
    def set_services(self, services):
        """Diğer servislere referansları ayarlar."""
        self.services = services
        logger.debug(f"{self.name} servisi diğer servislere bağlandı")

    async def initialize(self) -> bool:
        """Servisi başlatmadan önce hazırlar."""
        await super().initialize()
        
        # Veritabanını kontrol et ve gerekirse tabloları oluştur
        await self._ensure_database_tables()
        
        # Önceki veri toplamadan istatistikleri yükle
        if hasattr(self.db, 'get_mining_stats'):
            try:
                stats = await self._run_async_db_method(self.db.get_mining_stats)
                if stats:
                    self.mining_stats = stats
                    logger.info(f"Önceki veri toplama istatistikleri yüklendi: {len(stats)} kayıt")
            except Exception as e:
                logger.error(f"İstatistik yükleme hatası: {str(e)}")
        
        return True
        
    async def _ensure_database_tables(self):
        """Gerekli veritabanı tablolarının varlığını kontrol eder ve oluşturur."""
        if not hasattr(self.db, 'execute'):
            logger.error("Veritabanı nesnesi 'execute' metoduna sahip değil")
            return
            
        tables = {
            "user_demographics": """
                CREATE TABLE IF NOT EXISTS user_demographics (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT,
                    country TEXT,
                    city TEXT,
                    age_group TEXT,
                    gender TEXT,
                    interests TEXT,
                    bio_keywords TEXT,
                    premium_status INTEGER DEFAULT 0,
                    profile_picture_url TEXT,
                    last_updated TIMESTAMP
                )
            """,
            "user_activity": """
                CREATE TABLE IF NOT EXISTS user_activity (
                    user_id INTEGER,
                    group_id INTEGER, 
                    last_message_time TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    avg_message_length INTEGER DEFAULT 0,
                    active_hours TEXT,
                    topics TEXT,
                    PRIMARY KEY (user_id, group_id)
                )
            """,
            "user_relationships": """
                CREATE TABLE IF NOT EXISTS user_relationships (
                    user_id INTEGER,
                    related_user_id INTEGER,
                    relationship_strength FLOAT,
                    common_groups INTEGER DEFAULT 0,
                    last_interaction TIMESTAMP,
                    PRIMARY KEY (user_id, related_user_id)
                )
            """,
            "mining_logs": """
                CREATE TABLE IF NOT EXISTS mining_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP,
                    groups_processed INTEGER,
                    users_processed INTEGER,
                    new_users INTEGER,
                    updated_users INTEGER,
                    duration_seconds INTEGER
                )
            """
        }
        
        for table_name, create_query in tables.items():
            try:
                await self._run_async_db_method(self.db.execute, create_query)
                logger.debug(f"{table_name} tablosu kontrol edildi/oluşturuldu")
            except Exception as e:
                logger.error(f"{table_name} tablosu oluşturma hatası: {str(e)}")
                
    async def run(self):
        """Ana çalışma döngüsü."""
        logger.info("Veri madenciliği servisi başlatıldı")
        
        # İlk çalıştırmada tam bir veri toplama yap
        await self._full_data_mining()
        
        mining_interval = self.settings["mining_interval_hours"] * 3600
        incremental_interval = self.settings["incremental_interval_min"] * 60
        
        last_full_mining = datetime.now()
        last_incremental_mining = datetime.now()
        
        while self.running and not self.stop_event.is_set():
            try:
                now = datetime.now()
                
                # Tam veri toplama zamanı geldi mi?
                if (now - last_full_mining).total_seconds() >= mining_interval:
                    logger.info("Zamanlı tam veri toplama başlatılıyor...")
                    await self._full_data_mining()
                    last_full_mining = now
                    last_incremental_mining = now
                    
                # Artırımlı veri toplama zamanı geldi mi?
                elif (now - last_incremental_mining).total_seconds() >= incremental_interval:
                    logger.info("Artırımlı veri toplama başlatılıyor...")
                    await self._incremental_data_mining()
                    last_incremental_mining = now
                
                # Kullanıcı segmentlerini güncelle
                await self._update_user_segments()
                
                # Kısa bir süre bekle ve kontrol et
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Veri madenciliği döngü hatası: {str(e)}")
                logger.debug(traceback.format_exc())
                await asyncio.sleep(300)  # Hata durumunda 5 dakika bekle
        
        logger.info("Veri madenciliği servisi durduruldu")
            
    async def _full_data_mining(self):
        """
        Tam kapsamlı veri toplama işlemi.
        
        Bu metot tüm erişilebilir grupları tarar ve kullanıcı bilgilerini toplar.
        """
        start_time = datetime.now()
        total_users = 0
        total_groups = 0
        new_users = 0
        updated_users = 0
        
        try:
            # 1. Tüm grupları getir
            all_groups = await self._get_all_groups()
            logger.info(f"Veri toplamak için {len(all_groups)} grup bulundu")
            
            # Grup sayısını sınırla
            max_groups = min(len(all_groups), self.settings["max_groups_per_run"])
            selected_groups = all_groups[:max_groups]
            
            # 2. Her gruptan kullanıcı bilgilerini topla
            for group in selected_groups:
                group_id = group.get('id') or group.get('chat_id')
                group_title = group.get('title', 'Bilinmeyen Grup')
                
                if not group_id:
                    continue
                    
                logger.info(f"'{group_title}' grubundan kullanıcı verileri toplanıyor...")
                
                try:
                    # Grup üyelerini getir
                    members = await self._get_detailed_group_members(group_id)
                    
                    # Her üye için bilgi topla ve kaydet
                    for member in members:
                        # Ayrıntılı kullanıcı bilgilerini topla ve veritabanına kaydet
                        user_id = member.get('id')
                        
                        if not user_id:
                            continue
                            
                        # Kullanıcıyı veritabanına ekle/güncelle
                        result = await self._store_user_data(user_id, member, group_id)
                        
                        # İstatistikleri güncelle
                        total_users += 1
                        if result == "new":
                            new_users += 1
                        elif result == "updated":
                            updated_users += 1
                            
                    logger.info(f"'{group_title}' grubundan {len(members)} kullanıcı toplandı")
                    total_groups += 1
                    
                except Exception as e:
                    logger.error(f"'{group_title}' grubundan veri toplama hatası: {str(e)}")
                    
                # Gruplar arası kısa bir bekleme ekle
                await asyncio.sleep(random.uniform(2, 5))
                
            # İstatistikleri güncelle
            duration = (datetime.now() - start_time).total_seconds()
            
            self.total_users_mined += total_users
            self.total_groups_mined += total_groups
            self.last_mining_time = datetime.now()
            
            log_entry = {
                "timestamp": self.last_mining_time,
                "groups_processed": total_groups,
                "users_processed": total_users,
                "new_users": new_users,
                "updated_users": updated_users,
                "duration_seconds": int(duration)
            }
            
            # Veritabanına kaydet
            if hasattr(self.db, 'log_mining_activity'):
                await self._run_async_db_method(self.db.log_mining_activity, log_entry)
                
            logger.info(f"Tam veri toplama tamamlandı: {total_groups} grup, {total_users} kullanıcı, süre: {int(duration)}sn")
            
        except Exception as e:
            logger.error(f"Tam veri toplama hatası: {str(e)}")
            logger.debug(traceback.format_exc())
            
    async def _incremental_data_mining(self):
        """
        Artırımlı veri toplama işlemi.
        
        Sadece aktif gruplardan ve son giriş yapan kullanıcılardan veri toplar.
        """
        start_time = datetime.now()
        total_users = 0
        total_groups = 0
        
        try:
            # 1. Aktif grupları getir (son 24 saat içinde mesaj olan)
            active_groups = await self._get_active_groups()
            
            if not active_groups:
                logger.info("Artırımlı veri toplama için aktif grup bulunamadı")
                return
                
            logger.info(f"Artırımlı veri toplama için {len(active_groups)} aktif grup bulundu")
            
            # 2. Her aktif gruptaki yeni kullanıcıları topla
            for group in active_groups:
                group_id = group.get('id') or group.get('chat_id')
                group_title = group.get('title', 'Bilinmeyen Grup')
                
                if not group_id:
                    continue
                
                try:
                    # Son kullanıcıları getir
                    recent_members = await self._get_recent_group_members(group_id)
                    
                    if not recent_members:
                        continue
                        
                    # Her üye için bilgi topla ve kaydet
                    for member in recent_members:
                        user_id = member.get('id')
                        if not user_id:
                            continue
                            
                        # Kullanıcıyı veritabanına ekle/güncelle
                        await self._store_user_data(user_id, member, group_id)
                        total_users += 1
                        
                    logger.info(f"'{group_title}' grubundan {len(recent_members)} yeni kullanıcı toplandı")
                    total_groups += 1
                    
                except Exception as e:
                    logger.error(f"'{group_title}' grubundan artırımlı veri toplama hatası: {str(e)}")
                
                # Gruplar arası kısa bir bekleme ekle
                await asyncio.sleep(random.uniform(1, 3))
                
            # İstatistikleri güncelle
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Artırımlı veri toplama tamamlandı: {total_groups} grup, {total_users} kullanıcı, süre: {int(duration)}sn")
            
        except Exception as e:
            logger.error(f"Artırımlı veri toplama hatası: {str(e)}")
            
    async def _get_all_groups(self) -> List[Dict]:
        """
        Botun erişebildiği tüm grupları getirir.
        
        Returns:
            List[Dict]: Grup bilgilerinin listesi
        """
        groups = []
        
        try:
            # Önce diğer servislerden grup bilgilerini kontrol et
            if 'group' in self.services:
                if hasattr(self.services['group'], 'get_groups'):
                    service_groups = await self.services['group'].get_groups()
                    if service_groups:
                        groups.extend(service_groups)
                        
            # Veritabanında kayıtlı grupları kontrol et
            if not groups and hasattr(self.db, 'get_all_groups'):
                db_groups = await self._run_async_db_method(self.db.get_all_groups)
                if db_groups:
                    groups.extend(db_groups)
            
            # Eğer hala grup yoksa doğrudan Telegram API'den getir
            if not groups:
                try:
                    # Dialogs çağrısı
                    dialogs = await self.client.get_dialogs()
                    
                    for dialog in dialogs:
                        entity = dialog.entity
                        if hasattr(entity, 'megagroup') and entity.megagroup:
                            # Süper grup
                            group_info = {
                                'id': entity.id,
                                'title': entity.title,
                                'username': getattr(entity, 'username', None),
                                'members_count': getattr(entity, 'participants_count', 0),
                                'source': 'dialog'
                            }
                            groups.append(group_info)
                            
                except Exception as e:
                    logger.error(f"Dialog yöntemiyle grup getirme hatası: {str(e)}")
            
            # Benzersiz grupları döndür (ID'ye göre)
            unique_groups = []
            seen_ids = set()
            
            for group in groups:
                group_id = group.get('id') or group.get('chat_id')
                if group_id and group_id not in seen_ids:
                    seen_ids.add(group_id)
                    unique_groups.append(group)
                    
            return unique_groups
            
        except Exception as e:
            logger.error(f"Grupları getirme hatası: {str(e)}")
            return []
            
    async def _get_active_groups(self) -> List[Dict]:
        """
        Son 24 saat içinde aktif olan grupları getirir.
        
        Returns:
            List[Dict]: Aktif grup bilgilerinin listesi
        """
        active_groups = []
        
        try:
            # Group servisinden aktif grupları almaya çalış
            if 'group' in self.services and hasattr(self.services['group'], 'get_active_groups'):
                groups = await self.services['group'].get_active_groups()
                if groups:
                    return groups
                    
            # Tüm grupları getir ve son mesajları kontrol et
            all_groups = await self._get_all_groups()
            
            for group in all_groups:
                group_id = group.get('id') or group.get('chat_id')
                
                if not group_id:
                    continue
                
                try:
                    # Grubun son mesajlarını kontrol et
                    messages = await self.client.get_messages(group_id, limit=1)
                    
                    if messages and len(messages) > 0:
                        last_msg_time = messages[0].date
                        # Son 24 saat içinde mesaj varsa aktif kabul et
                        if (datetime.now() - last_msg_time.replace(tzinfo=None)).total_seconds() < 86400:
                            active_groups.append(group)
                except:
                    # Hata durumunda grubu atla
                    pass
                    
            return active_groups
            
        except Exception as e:
            logger.error(f"Aktif grupları getirme hatası: {str(e)}")
            return []
            
    async def _get_detailed_group_members(self, group_id) -> List[Dict]:
        """
        Bir gruptaki üyelerin detaylı bilgilerini getirir.
        
        Args:
            group_id: Grup ID
            
        Returns:
            List[Dict]: Üye bilgilerinin listesi
        """
        members = []
        
        try:
            # GetParticipants çağrısını yap
            participants = await self.client(functions.channels.GetParticipantsRequest(
                channel=group_id,
                filter=types.ChannelParticipantsRecent(),
                offset=0,
                limit=self.settings["max_users_per_group"],
                hash=0
            ))
            
            # Kullanıcı bilgilerini topla
            for user in participants.users:
                if user.bot:
                    continue  # Botları atla
                    
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone': user.phone,
                    'photo': bool(user.photo),
                    'status': str(user.status).split('(')[0] if user.status else 'Unknown',
                    'bot': user.bot,
                    'verified': user.verified,
                    'restricted': user.restricted,
                    'lang_code': getattr(user, 'lang_code', None),
                    'access_hash': user.access_hash,
                }
                
                # Bio bilgisini almaya çalış
                if self.settings["analyze_bio_text"]:
                    try:
                        full_user = await self.client(functions.users.GetFullUserRequest(
                            id=user.id
                        ))
                        user_data['bio'] = full_user.about
                    except:
                        user_data['bio'] = None
                
                members.append(user_data)
                
            return members
            
        except Exception as e:
            logger.error(f"Grup üyelerini getirme hatası ({group_id}): {str(e)}")
            return []
            
    async def _get_recent_group_members(self, group_id) -> List[Dict]:
        """
        Bir gruptaki son giriş yapan üyeleri getirir.
        
        Args:
            group_id: Grup ID
            
        Returns:
            List[Dict]: Üye bilgilerinin listesi
        """
        try:
            # Son giriş yapan üyeleri getir
            recent_participants = await self.client(functions.channels.GetParticipantsRequest(
                channel=group_id,
                filter=types.ChannelParticipantsRecent(),
                offset=0,
                limit=30,  # Son 30 aktif üye
                hash=0
            ))
            
            members = []
            for user in recent_participants.users:
                if user.bot:
                    continue
                    
                member_data = {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'status': str(user.status).split('(')[0] if user.status else 'Unknown',
                }
                
                members.append(member_data)
                
            return members
            
        except Exception as e:
            logger.error(f"Son grup üyelerini getirme hatası ({group_id}): {str(e)}")
            return []
            
    async def _store_user_data(self, user_id, user_data, group_id=None) -> str:
        """
        Kullanıcı bilgilerini veritabanına kaydeder.
        
        Args:
            user_id: Kullanıcı ID
            user_data: Kullanıcı bilgileri
            group_id: Grup ID (opsiyonel)
            
        Returns:
            str: "new", "updated" veya "unchanged"
        """
        try:
            # 1. Önce kullanıcı temel bilgilerini kaydet
            result = "unchanged"
            
            # Kullanıcı daha önce kaydedilmiş mi kontrol et
            existing_user = None
            
            if hasattr(self.db, 'get_user_by_id'):
                existing_user = await self._run_async_db_method(self.db.get_user_by_id, user_id)
                
            if not existing_user:
                # Yeni kullanıcı ekle
                if hasattr(self.db, 'add_user'):
                    await self._run_async_db_method(
                        self.db.add_user,
                        user_id,
                        user_data.get('username'),
                        user_data.get('first_name'),
                        user_data.get('last_name'),
                        user_data.get('bot', False),
                        True  # is_active
                    )
                result = "new"
            else:
                # Kullanıcıyı güncelle
                if hasattr(self.db, 'update_user'):
                    await self._run_async_db_method(
                        self.db.update_user,
                        user_id,
                        user_data.get('username'),
                        user_data.get('first_name'),
                        user_data.get('last_name'),
                        user_data.get('bot', False),
                        True  # is_active
                    )
                result = "updated"
            
            # 2. Demografik bilgileri kaydet
            if hasattr(self.db, 'update_user_demographics'):
                demos = {
                    'user_id': user_id,
                    'language': user_data.get('lang_code'),
                    'bio_keywords': self._extract_bio_keywords(user_data.get('bio', '')),
                    'profile_picture_url': None,
                    'last_updated': datetime.now()
                }
                
                await self._run_async_db_method(self.db.update_user_demographics, demos)
            
            # 3. Grup aktivitesini kaydet (eğer grup ID verilmişse)
            if group_id and hasattr(self.db, 'update_user_group_activity'):
                activity = {
                    'user_id': user_id,
                    'group_id': group_id,
                    'last_seen': datetime.now()
                }
                
                await self._run_async_db_method(self.db.update_user_group_activity, activity)
            
            return result
            
        except Exception as e:
            logger.error(f"Kullanıcı verisi kaydetme hatası ({user_id}): {str(e)}")
            return "error"
            
    def _extract_bio_keywords(self, bio_text: str) -> Optional[str]:
        """
        Bio metninden anahtar kelimeleri çıkarır.
        
        Args:
            bio_text: Bio metni
            
        Returns:
            Optional[str]: Anahtar kelimeler (JSON formatında) veya None
        """
        if not bio_text:
            return None
            
        # Basit bir kelime listesi çıkarma
        words = bio_text.lower().split()
        # Stop kelimeleri çıkar
        stop_words = {"ve", "ile", "bu", "bir", "için", "ben", "sen", "o", "biz", "siz", "onlar"}
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        
        # En fazla 10 anahtar kelime döndür
        return json.dumps(keywords[:10]) if keywords else None
            
    async def _update_user_segments(self):
        """
        Kullanıcı segmentlerini günceller.
        """
        try:
            # 1. Aktif kullanıcılar
            active_users = set()
            if hasattr(self.db, 'get_active_users'):
                active_list = await self._run_async_db_method(self.db.get_active_users, 7)  # Son 7 gün
                active_users = set(u.get('id') for u in active_list if u.get('id'))
            
            # 2. Yeni kullanıcılar
            new_users = set()
            if hasattr(self.db, 'get_new_users'):
                new_list = await self._run_async_db_method(self.db.get_new_users, 30)  # Son 30 gün
                new_users = set(u.get('id') for u in new_list if u.get('id'))
                
            # 3. Pasif kullanıcılar
            dormant_users = set()
            if hasattr(self.db, 'get_dormant_users'):
                dormant_list = await self._run_async_db_method(self.db.get_dormant_users, 30)  # 30 günden fazla
                dormant_users = set(u.get('id') for u in dormant_list if u.get('id'))
                
            # Segmentleri güncelle
            self.segments["active"] = active_users
            self.segments["new"] = new_users
            self.segments["dormant"] = dormant_users
            
            # Değişiklikleri veritabanına kaydet
            if hasattr(self.db, 'save_user_segments'):
                await self._run_async_db_method(
                    self.db.save_user_segments,
                    {
                        "active": list(active_users),
                        "new": list(new_users),
                        "dormant": list(dormant_users)
                    }
                )
                
        except Exception as e:
            logger.error(f"Segment güncelleme hatası: {str(e)}")
            
    async def _run_async_db_method(self, method, *args, **kwargs):
        """Veritabanı metodunu thread-safe biçimde çalıştırır."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, 
            functools.partial(method, *args, **kwargs)
        )
            
    async def get_user_segment(self, segment_name: str) -> List[int]:
        """
        Belirli bir kullanıcı segmentini döndürür.
        
        Args:
            segment_name: Segment adı
            
        Returns:
            List[int]: Segmentteki kullanıcı ID'leri
        """
        if segment_name in self.segments:
            return list(self.segments[segment_name])
        return []
        
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgileri
        """
        status = await super().get_status()
        
        # Servis durumunu güncelle
        extra_status = {
            'total_users_mined': self.total_users_mined,
            'total_groups_mined': self.total_groups_mined,
            'last_mining_time': self.last_mining_time.isoformat() if self.last_mining_time else None,
            'active_users_count': len(self.segments["active"]),
            'new_users_count': len(self.segments["new"]),
            'dormant_users_count': len(self.segments["dormant"])
        }
        
        status.update(extra_status)
        return status
        
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servisin istatistiklerini döndürür.
        
        Returns:
            Dict: Servis istatistikleri
        """
        # Segment büyüklükleri
        segment_stats = {name: len(users) for name, users in self.segments.items()}
        
        # Veri toplama istatistikleri
        mining_stats = {}
        if hasattr(self.db, 'get_mining_stats_summary'):
            mining_stats = await self._run_async_db_method(self.db.get_mining_stats_summary)
        
        return {
            'segments': segment_stats,
            'mining': mining_stats,
            'total_users': self.total_users_mined,
            'total_groups': self.total_groups_mined,
            'last_update': self.last_mining_time.isoformat() if self.last_mining_time else None
        }

    async def generate_demographic_report(self, format='json') -> str:
        """
        Demografik analiz raporu oluşturur.
        
        Args:
            format: Çıktı formatı ('json' veya 'text')
            
        Returns:
            str: Analiz raporu
        """
        try:
            # 1. Dil dağılımı
            language_dist = {}
            if hasattr(self.db, 'get_language_distribution'):
                language_dist = await self._run_async_db_method(self.db.get_language_distribution)
            
            # 2. Aktiflik dağılımı
            activity_dist = {
                "active": len(self.segments["active"]),
                "new": len(self.segments["new"]),
                "dormant": len(self.segments["dormant"])
            }
            
            # 3. Grup dağılımı
            group_dist = {}
            if hasattr(self.db, 'get_group_distribution'):
                group_dist = await self._run_async_db_method(self.db.get_group_distribution)
            
            # Rapor oluştur
            report = {
                "generated_at": datetime.now().isoformat(),
                "total_users": self.total_users_mined,
                "language_distribution": language_dist,
                "activity_distribution": activity_dist,
                "group_distribution": group_dist
            }
            
            if format == 'json':
                return json.dumps(report, indent=2)
            else:
                # Text formatında rapor
                text_report = f"DEMOGRAFIK ANALİZ RAPORU - {datetime.now()}\n\n"
                text_report += f"Toplam Kullanıcı: {self.total_users_mined}\n\n"
                
                text_report += "DİL DAĞILIMI:\n"
                for lang, count in language_dist.items():
                    text_report += f"- {lang}: {count}\n"
                
                text_report += "\nAKTİFLİK DAĞILIMI:\n"
                for status, count in activity_dist.items():
                    text_report += f"- {status}: {count}\n"
                    
                text_report += "\nGRUP DAĞILIMI:\n"
                for group, count in list(group_dist.items())[:10]:  # İlk 10 grup
                    text_report += f"- {group}: {count}\n"
                
                return text_report
                
        except Exception as e:
            logger.error(f"Demografik rapor oluşturma hatası: {str(e)}")
            return f"Rapor oluşturma hatası: {str(e)}"