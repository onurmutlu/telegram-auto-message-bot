"""
# DataMining servisi - veri madenciliği ve analiz için kullanılır
"""
from app.services.base_service import BaseService
import logging
import json
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set, Optional, Union
from telethon import errors
from telethon.errors import (
    RPCError, FloodWaitError, ChannelPrivateError, 
    ChannelInvalidError, ChannelsTooMuchError
)
from telethon.tl.types import User, Message, Channel, Chat, ChatFull, PeerChannel
from telethon.tl.functions.channels import GetParticipantsRequest, GetFullChannelRequest, GetChannelsRequest
from telethon.tl.functions.messages import GetChatsRequest, GetFullChatRequest
from telethon.tl.types import ChannelParticipantsRecent, InputChannel, InputPeerChannel, InputPeerChat

logger = logging.getLogger(__name__)

class DataMiningService(BaseService):
    def __init__(self, client, config, db, stop_event=None):
        super().__init__("datamining", client, config, db, stop_event)
        self.mining_data = {}
        self.mining_stats = {}
        self.last_update = datetime.now()
        self.data = {}
        self.stats = {
            'total_processed': 0,
            'last_processed': None
        }
    
    async def _start(self) -> bool:
        """
        Servisi başlatır. BaseService.initialize() tarafından çağrılır.
        
        Returns:
            bool: Başarılı olursa True, başarısız olursa False
        """
        try:
            # Her adımı ayrı olarak ele alıp, bir hata olursa diğer adımlara devam edelim
            try:
                # Veri madenciliği verilerini yükle
                await self._load_mining_data()
            except Exception as e:
                logger.error(f"Veri madenciliği verileri yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir dict ile devam et
                self.mining_data = {}
            
            try:
                await self._load_mining_stats()
            except Exception as e:
                logger.error(f"Veri madenciliği istatistikleri yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir dict ile devam et
                self.mining_stats = {}
            
            # Veri toplama görevini başlat
            if hasattr(self, "start_data_collection_task"):
                asyncio.create_task(self.start_data_collection_task())
            
            logger.info(f"{self.service_name} servisi başlatıldı.")
            return True
            
        except Exception as e:
            logger.error(f"{self.service_name} servisi başlatılırken genel hata: {str(e)}", exc_info=True)
            return False
    
    async def _stop(self) -> bool:
        """
        Servisi durdurur. BaseService.stop() tarafından çağrılır.
        
        Returns:
            bool: Başarılı olursa True, başarısız olursa False
        """
        try:
            # Servis verilerini kaydet
            logger.info(f"{self.service_name} servisi durduruluyor...")
            # İhtiyaç duyulan temizleme işlemleri burada yapılabilir
            logger.info(f"{self.service_name} servisi durduruldu.")
            return True
        except Exception as e:
            logger.error(f"{self.service_name} servisi durdurulurken hata: {str(e)}", exc_info=True)
            return False
    
    async def _update(self) -> None:
        """
        Periyodik güncelleme. BaseService.run() tarafından periyodik olarak çağrılır.
        """
        try:
            logger.debug(f"{self.service_name} servisi güncelleniyor...")
            
            # İstatistikleri güncelle
            await self._load_mining_stats()
            
            # Zamanı gelmiş madencilik işlerini çalıştır
            active_jobs = [job for job in self.mining_data.values() if job.get('is_active', True)]
            for job in active_jobs:
                try:
                    group_id = job.get('group_id')
                    if group_id:
                        # Grup verilerini güncelle
                        await self.update_group_data()
                except Exception as e:
                    logger.error(f"Madencilik işi çalıştırılırken hata: {str(e)}", exc_info=True)
            
            self.last_update = datetime.now()
            self.stats['total_processed'] += len(active_jobs)
            self.stats['last_processed'] = self.last_update
            
            logger.debug(f"{self.service_name} servisi güncelleme tamamlandı.")
        except Exception as e:
            logger.error(f"{self.service_name} servisi güncellenirken hata: {str(e)}", exc_info=True)
    
    async def initialize(self) -> bool:
        """
        Servisi başlatır.
        """
        await super().initialize()
        
        try:
            # Her adımı ayrı olarak ele alıp, bir hata olursa diğer adımlara devam edelim
            try:
                # Veri madenciliği verilerini yükle
                await self._load_mining_data()
            except Exception as e:
                logger.error(f"Veri madenciliği verileri yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir dict ile devam et
                self.mining_data = {}
            
            try:
                await self._load_mining_stats()
            except Exception as e:
                logger.error(f"Veri madenciliği istatistikleri yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir dict ile devam et
                self.mining_stats = {}
            
            # Başarıyla tamamlandı
            self.initialized = True
            logger.info(f"{self.service_name} servisi başlatıldı.")
            
            # Veri toplama görevini başlat
            if hasattr(self, "start_data_collection_task"):
                asyncio.create_task(self.start_data_collection_task())
            
            return True
            
        except Exception as e:
            logger.error(f"{self.service_name} servisi başlatılırken genel hata: {str(e)}", exc_info=True)
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
            
        self.running = True
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
        
    async def _load_mining_data(self):
        """Veri madenciliği verilerini yükler"""
        try:
            # Veritabanı bağlantısını kontrol et
            if not self.db.connected or not self.db.cursor:
                await self.db.connect()
                if not self.db.cursor:
                    logger.error("Veritabanı bağlantısı kurulamadı, DB cursor null")
                    return
            
            data = await self.db.fetchall("SELECT * FROM mining_data")
            
            if not data:
                logger.warning("Veri madenciliği verisi bulunamadı.")
                return
            
            for item in data:
                if isinstance(item, dict):
                    # Eğer dict olarak dönüyorsa
                    item_id = item.get('id')
                    if item_id:
                        self.mining_data[item_id] = item
                elif isinstance(item, (list, tuple)) and len(item) > 0:
                    # Eğer tuple/list olarak dönüyorsa
                    item_id = item[0]  # id değerini al
                    self.mining_data[item_id] = {
                        'id': item_id,
                        'group_id': item[1] if len(item) > 1 else None,
                        'keywords': item[2] if len(item) > 2 else None,
                        'is_active': item[3] if len(item) > 3 else True
                    }
                
            logger.info(f"{len(self.mining_data)} veri madenciliği kaydı yüklendi")
            
        except Exception as e:
            logger.error(f"Veri madenciliği verileri yüklenirken hata: {str(e)}")
            # Hatada boş değerle devam et
            self.mining_data = {}
            
    async def _load_mining_stats(self):
        """Veri madenciliği istatistiklerini yükler"""
        try:
            # Veritabanı bağlantısını kontrol et
            if not self.db.connected or not self.db.cursor:
                await self.db.connect()
                if not self.db.cursor:
                    logger.error("Veritabanı bağlantısı kurulamadı, DB cursor null")
                    return
            
            # Kolon kontrolü olmadan, daha güvenli sorgu
            stats = await self.db.fetchall("""
                SELECT mining_id, COUNT(*) as total_records,
                       COUNT(*) as unique_users,
                       MAX(created_at) as last_record
                FROM mining_logs
                GROUP BY mining_id
            """)
            
            if not stats:
                logger.warning("Veri madenciliği istatistiği bulunamadı.")
                return
            
            for stat in stats:
                if isinstance(stat, dict):
                    # Eğer dict olarak dönüyorsa
                    mining_id = stat.get('mining_id')
                    if mining_id:
                        self.mining_stats[mining_id] = {
                            'total_records': stat.get('total_records', 0),
                            'unique_users': stat.get('unique_users', 0),
                            'last_record': stat.get('last_record')
                        }
                elif isinstance(stat, (list, tuple)) and len(stat) >= 4:
                    # Eğer tuple/list olarak dönüyorsa
                    mining_id = stat[0]
                    self.mining_stats[mining_id] = {
                        'total_records': stat[1],
                        'unique_users': stat[2],
                        'last_record': stat[3]
                    }
                
            logger.info(f"{len(self.mining_stats)} veri madenciliği istatistiği yüklendi")
            
        except Exception as e:
            logger.error(f"Veri madenciliği istatistikleri yüklenirken hata: {str(e)}")
            # Hatada boş değerle devam et
            self.mining_stats = {}
            
    async def create_mining_job(self, job_data):
        """Yeni veri madenciliği işi oluşturur"""
        try:
            params = (
                job_data['group_id'],
                job_data['keywords'],
                job_data.get('is_active', True)
            )
            job_id = await self.db.execute(
                "INSERT INTO mining_data (group_id, keywords, is_active) VALUES ($1, $2, $3) RETURNING id",
                params
            )
            
            await self._load_mining_data()
            
            logger.debug(f"Yeni veri madenciliği işi oluşturuldu: {job_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Veri madenciliği işi oluşturulurken hata: {str(e)}")
            return None
            
    async def update_mining_job(self, job_id, job_data):
        """Veri madenciliği işini günceller"""
        try:
            params = (
                job_data['group_id'],
                job_data['keywords'],
                job_data.get('is_active', True),
                job_id
            )
            await self.db.execute(
                "UPDATE mining_data SET group_id = $1, keywords = $2, is_active = $3 WHERE id = $4",
                params
            )
            
            await self._load_mining_data()
            
            logger.debug(f"Veri madenciliği işi güncellendi: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Veri madenciliği işi güncellenirken hata: {str(e)}")
            return False
            
    async def delete_mining_job(self, job_id):
        """Veri madenciliği işini siler"""
        try:
            await self.db.execute("DELETE FROM mining_logs WHERE mining_id = $1", (job_id,))
            await self.db.execute("DELETE FROM mining_data WHERE id = $1", (job_id,))
            
            await self._load_mining_data()
            await self._load_mining_stats()
            
            logger.debug(f"Veri madenciliği işi silindi: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Veri madenciliği işi silinirken hata: {str(e)}")
            return False
            
    async def log_mining_result(self, job_id, user_id, data):
        """Veri madenciliği sonucunu kaydeder"""
        try:
            params = (job_id, user_id, data)
            await self.db.execute(
                "INSERT INTO mining_logs (mining_id, user_id, data) VALUES ($1, $2, $3)",
                params
            )
            
            await self._load_mining_stats()
            
            logger.debug(f"Veri madenciliği sonucu kaydedildi: {job_id}, {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Veri madenciliği sonucu kaydedilirken hata: {str(e)}")
            return False
            
    async def get_mining_stats(self, job_id):
        """Veri madenciliği istatistiklerini getirir"""
        return self.mining_stats.get(job_id, {
            'total_records': 0,
            'unique_users': 0,
            'last_record': None
        }) 

    async def start_data_collection_task(self):
        """
        Verileri kalıcı olarak toplamak için arkaplan görevi başlatır
        """
        logger.info("Veri toplama görevi başlatılıyor...")
        
        # Her 5 dakikada bir grup ve kullanıcı verilerini topla (önceden 30 dakikaydı)
        while self.running and not self.stop_event.is_set():
            try:
                # Grupları güncelle
                await self.update_group_data()
                
                # Her 1 saatte bir grup kullanıcılarını güncelle
                current_hour = datetime.now().hour
                if current_hour % 1 == 0:  # 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00
                    await self.update_group_members()
                
                # 15 dakika bekle (önceden 30 dakikaydı)
                await asyncio.sleep(15 * 60)
                
            except asyncio.CancelledError:
                logger.info("Veri toplama görevi iptal edildi")
                break
            except Exception as e:
                logger.error(f"Veri toplama sırasında hata: {str(e)}", exc_info=True)
                await asyncio.sleep(2 * 60)  # 2 dakika bekle ve tekrar dene (önceden 5 dakikaydı)

    async def update_group_data(self):
        """
        Tüm grupların verilerini günceller ve PostgreSQL'e kaydeder
        """
        try:
            logger.info("Grup verilerini güncelleme görevi başladı")
            
            # Grup servisine erişim kontrolü
            if not hasattr(self, 'group_service') or not self.group_service:
                logger.warning("Grup servisi bulunamadı, grup verileri güncellenemiyor")
                
                # Alternatif olarak, eğer servisler içinde grup servisi varsa kullan
                if hasattr(self, 'services') and 'group' in self.services:
                    self.group_service = self.services['group']
                    logger.info("Grup servisi servisler listesinden bulundu")
                else:
                    return False
            
            # Grup servisinden grupları al
            try:
                # get_target_groups metodu var mı kontrol et
                if hasattr(self.group_service, 'get_target_groups'):
                    groups = await self.group_service.get_target_groups()
                    if not groups:
                        logger.warning("Grup servisi grupları getirmedi")
                        return False
                else:
                    logger.warning("Grup servisinde get_target_groups metodu bulunamadı")
                    return False
            except Exception as e:
                logger.error(f"Grup verilerini alma hatası: {str(e)}")
                return False
                
            # Veritabanı bağlantısını kontrol et
            if not self.db.connected:
                await self.db.connect()
                
            updated_count = 0
            new_count = 0
            
            # Her grup için:
            for group in groups:
                try:
                    group_id = group.get('group_id')
                    if not group_id:
                        continue
                    
                    # Grup entity'sini al
                    entity = None
                    try:
                        # ID'nin türünü kontrol et ve debug bilgisi ekle
                        real_id = int(group_id)
                        logger.debug(f"Entity almaya çalışılıyor: ID={real_id}, tip={type(real_id)}")
                        entity = await self.client.get_entity(real_id)
                    except ValueError:
                        # Sayısal değilse doğrudan kullan (username olabilir)
                        logger.debug(f"Entity almaya çalışılıyor: ID={group_id}, (sayısal olmayan)")
                        entity = await self.client.get_entity(group_id)
                    except RPCError as e:
                        logger.warning(f"Grup entity alma hatası: {group_id} -> {str(e)}")
                        continue
                        
                    # Entity alınamadıysa
                    if not entity:
                        logger.warning(f"Grup entity alınamadı: {group_id}")
                        continue
                    
                    # Entity'den grup verilerini çıkar
                    group_data = {
                        'id': group_id,
                        'name': getattr(entity, 'title', None) or group.get('name', f"Grup {group_id}"),
                        'username': getattr(entity, 'username', None),
                        'description': getattr(entity, 'about', None),
                        'member_count': getattr(entity, 'participants_count', 0),
                        'is_public': getattr(entity, 'username', None) is not None,
                        'source': 'discover'
                    }
                    
                    # Mevcut grup mu kontrol et
                    query = "SELECT group_id FROM groups WHERE group_id = %s"
                    existing_group = await self.db.fetchone(query, (group_id,))
                    
                    if existing_group:
                        # Grubu güncelle
                        update_query = """
                        UPDATE groups SET
                            name = %s, 
                            username = %s, 
                            description = %s, 
                            is_public = %s
                        WHERE group_id = %s
                        """
                        
                        params = (
                            group_data['name'], 
                            group_data['username'], 
                            group_data['description'], 
                            group_data['is_public'],
                            group_id
                        )
                        await self.db.execute(update_query, params)
                        updated_count += 1
                    else:
                        # Yeni grup ekle
                        insert_query = """
                        INSERT INTO groups (
                            group_id, name, username, description, is_public, source
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        
                        params = (
                            group_id, 
                            group_data['name'], 
                            group_data['username'], 
                            group_data['description'], 
                            group_data['is_public'],
                            group_data['source']
                        )
                        await self.db.execute(insert_query, params)
                        new_count += 1
                        
                    # Mining verisini kaydet
                    await self.store_group_mining_data(group_id, group_data)
                    
                except Exception as e:
                    logger.error(f"Grup verisi güncellenirken hata: {str(e)}")
                    logger.debug(traceback.format_exc())
            
            logger.info(f"Grup verileri güncellendi: {updated_count} güncellendi, {new_count} yeni eklendi")
            return True
                
        except Exception as e:
            logger.error(f"Grup verilerini güncelleme işlemi başarısız: {str(e)}")
            logger.debug(traceback.format_exc())
            return False

    async def update_group_members(self):
        """
        Tüm gruplardaki üyeleri günceller ve PostgreSQL'e kaydeder
        """
        try:
            logger.info("Grup üyelerini güncelleme görevi başladı")
            
            # Veritabanı bağlantısını kontrol et
            if not self.db.connected:
                await self.db.connect()
                
            # Aktif grupları al (limit artırıldı)
            query = "SELECT group_id, name FROM groups WHERE is_active = TRUE LIMIT 100"
            groups = await self.db.fetchall(query)
            
            if not groups:
                logger.warning("Aktif grup bulunamadı")
                return
            
            total_users = 0
            processed_groups = 0
            error_groups = 0
            
            # Rate limit önlemi - işlem adımı başına gecikme ekle
            delay_between_groups = 5  # saniye
            
            # Her grup için
            for group in groups:
                # Durdurma sinyali kontrol et
                if self.stop_event.is_set() or not self.running:
                    logger.info("Durdurma sinyali alındı, grup üyesi güncelleme işlemi yarıda kesiliyor")
                    break
                
                # Gruba başlamadan önce bekle - rate limit önlemi
                await asyncio.sleep(delay_between_groups)
                
                group_id = group[0] if isinstance(group, tuple) else group.get('group_id')
                group_name = group[1] if isinstance(group, tuple) else group.get('name')
                
                try:
                    logger.info(f"Grubun üyeleri alınıyor: {group_name} ({group_id})")
                    
                    try:
                        # ID'nin türünü kontrol et ve debug bilgisi ekle
                        real_id = int(group_id)
                        logger.debug(f"Entity almaya çalışılıyor: ID={real_id}, tip={type(real_id)}")
                        entity = await self.client.get_entity(real_id)
                    except ValueError:
                        # Sayısal değilse doğrudan kullan (username olabilir)
                        logger.debug(f"Entity almaya çalışılıyor: ID={group_id}, (sayısal olmayan)")
                        entity = await self.client.get_entity(group_id)
                    except RPCError as e:
                        logger.warning(f"Grup entity alma hatası: {group_id} -> {str(e)}")
                        continue
                        
                    # Entity alınamadıysa
                    if not entity:
                        logger.error(f"Grup {group_id} için entity alınamadı, grup atlanıyor")
                        continue
                    
                    # Üyeleri al (maksimum 200 -> 300)
                    participants = []
                    try:
                        if hasattr(entity, 'megagroup') or hasattr(entity, 'channel') or hasattr(entity, 'username'):
                            # Bu bir channel (süper grup / megagroup) veya username'i olan bir varlık
                            from telethon.tl.functions.channels import GetParticipantsRequest
                            from telethon.tl.types import ChannelParticipantsRecent, ChannelParticipantsAdmins
                            
                            try:
                                # Önce adminleri almayı dene
                                admin_participants = await self.client(GetParticipantsRequest(
                                    channel=entity, 
                                    filter=ChannelParticipantsAdmins(), 
                                    offset=0, 
                                    limit=100, 
                                    hash=0
                                ))
                                
                                # Sonra normal üyeleri almayı dene
                                user_participants = await self.client(GetParticipantsRequest(
                                    channel=entity, 
                                    filter=ChannelParticipantsRecent(), 
                                    offset=0, 
                                    limit=200, 
                                    hash=0
                                ))
                                
                                # Eğer adminler alınabildiyse kullanıcıları ekle
                                if hasattr(admin_participants, 'users') and admin_participants.users:
                                    participants = admin_participants
                                    logger.debug(f"Grup {group_id} için {len(admin_participants.users)} admin bulundu")
                                
                                # Eğer kullanıcılar alınabildiyse, katılımcılara ekle
                                if hasattr(user_participants, 'users') and user_participants.users:
                                    if not participants:
                                        participants = user_participants
                                    else:
                                        # Admin ve kullanıcıları birleştir
                                        # Basit birleştirme
                                        admin_ids = set()
                                        if hasattr(participants, 'users'):
                                            admin_ids = {u.id for u in participants.users}
                                        
                                        # Adminler arasında olmayan kullanıcıları ekle
                                        for user in user_participants.users:
                                            if user.id not in admin_ids:
                                                participants.users.append(user)
                                                
                                    logger.debug(f"Grup {group_id} için {len(user_participants.users)} kullanıcı bulundu")
                                    
                            except Exception as part_error:
                                logger.error(f"Grup üyeleri alınamadı (channel): {group_id}, hata: {str(part_error)}")
                                raise # Üst seviye exception handler'a gönder
                        elif hasattr(entity, 'chat_id') or str(entity.__class__).find('Chat') != -1:
                            # Bu bir normal chat
                            from telethon.tl.functions.messages import GetFullChatRequest
                            
                            try:
                                # Chat ID'yi al
                                chat_id = getattr(entity, 'chat_id', getattr(entity, 'id', None))
                                
                                if chat_id:
                                    # Chat bilgilerini al
                                    full_chat = await self.client(GetFullChatRequest(chat_id=chat_id))
                                    
                                    if hasattr(full_chat, 'users'):
                                        # Telethon'un beklediği formatı oluştur
                                        class SimpleParticipants:
                                            def __init__(self, users):
                                                self.users = users
                                                
                                        participants = SimpleParticipants(full_chat.users)
                                        logger.debug(f"Grup {group_id} için {len(full_chat.users)} kullanıcı bulundu (normal chat)")
                            except Exception as chat_error:
                                logger.error(f"Grup üyeleri alınamadı (chat): {group_id}, hata: {str(chat_error)}")
                                raise # Üst seviye exception handler'a gönder
                        else:
                            # Bilinmeyen bir entity tipi
                            logger.warning(f"Grup {group_id} için bilinmeyen entity tipi: {type(entity)}, öznitelikler: {dir(entity)}")
                            continue
                            
                    except Exception as part_error:
                        logger.error(f"Grup üyeleri alınamadı: {group_id}, hata: {str(part_error)}")
                        continue
                    
                    if not participants or not hasattr(participants, 'users') or not participants.users:
                        logger.warning(f"Grup {group_id} için üye bulunamadı")
                        continue
                    
                    logger.info(f"Grup {group_id} için {len(participants.users)} üye bulundu")
                    
                    # Her kullanıcı için
                    user_count = 0
                    for user in participants.users:
                        if not hasattr(user, 'id'):
                            continue
                        
                        user_id = user.id
                        
                        # Kullanıcı verilerini hazırla
                        user_data = {
                            'user_id': user_id,
                            'username': getattr(user, 'username', None),
                            'first_name': getattr(user, 'first_name', None),
                            'last_name': getattr(user, 'last_name', None),
                            'is_bot': getattr(user, 'bot', False),
                            'is_premium': getattr(user, 'premium', False),
                            'language_code': getattr(user, 'lang_code', None),
                            'phone': getattr(user, 'phone', None)
                        }
                        
                        # Kullanıcıyı veritabanına kaydet
                        try:
                            # Kullanıcı var mı kontrol et
                            user_query = "SELECT user_id FROM telegram_users WHERE user_id = %s"
                            user_result = await self.db.fetchone(user_query, (user_id,))
                            
                            if user_result:
                                # Mevcut kullanıcıyı güncelle
                                update_query = """
                                UPDATE telegram_users SET 
                                    username = %s, 
                                    first_name = %s, 
                                    last_name = %s, 
                                    is_bot = %s,
                                    is_premium = %s,
                                    language_code = %s,
                                    phone = %s,
                                    last_seen = NOW(),
                                    updated_at = NOW()
                                WHERE user_id = %s
                                """
                                await self.db.execute(update_query, (
                                    user_data['username'],
                                    user_data['first_name'],
                                    user_data['last_name'],
                                    user_data['is_bot'],
                                    user_data['is_premium'],
                                    user_data['language_code'],
                                    user_data['phone'],
                                    user_id
                                ))
                            else:
                                # Yeni kullanıcı ekle
                                insert_query = """
                                INSERT INTO telegram_users (
                                    user_id, username, first_name, last_name, 
                                    is_bot, is_premium, language_code, phone,
                                    first_seen, last_seen, created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW(), NOW())
                                """
                                await self.db.execute(insert_query, (
                                    user_id,
                                    user_data['username'],
                                    user_data['first_name'],
                                    user_data['last_name'],
                                    user_data['is_bot'],
                                    user_data['is_premium'],
                                    user_data['language_code'],
                                    user_data['phone']
                                ))
                            
                            # Grup-Kullanıcı ilişkisini güncelle
                            relation_query = """
                            INSERT INTO group_members (user_id, group_id, joined_at, last_seen, is_active, created_at, updated_at)
                            VALUES (%s, %s, NOW(), NOW(), TRUE, NOW(), NOW())
                            ON CONFLICT (user_id, group_id) DO UPDATE SET
                            last_seen = NOW(), is_active = TRUE, updated_at = NOW()
                            """
                            await self.db.execute(relation_query, (user_id, group_id))
                            
                            # Data mining tablosuna da kaydet
                            await self.store_user_mining_data(user_id, user_data, group_id)
                            
                            user_count += 1
                            
                        except Exception as user_error:
                            logger.error(f"Kullanıcı {user_id} kaydedilirken hata: {str(user_error)}")
                    
                    logger.info(f"Grup {group_name} için {user_count} kullanıcı işlendi")
                    total_users += user_count
                    processed_groups += 1
                    
                    # Her grup işlemi arasında biraz bekle (kısaltıldı)
                    await asyncio.sleep(2)
                    
                except Exception as group_error:
                    logger.error(f"Grup {group_id} üyeleri işlenirken hata: {str(group_error)}")
            
            logger.info(f"Grup üyelerini güncelleme tamamlandı: {processed_groups} grup, {total_users} kullanıcı")
            
        except Exception as e:
            logger.error(f"Grup üyelerini güncelleme hatası: {str(e)}", exc_info=True)

    async def store_group_mining_data(self, group_id, group_data):
        """
        Grup verilerini data_mining tablosuna kaydeder
        """
        try:
            if not self.db.connected:
                await self.db.connect()
                
            import json
            data_json = json.dumps(group_data)
            
            query = """
            INSERT INTO data_mining (
                telegram_id, user_id, group_id, type, source, data, 
                is_processed, created_at
            ) VALUES (%s, NULL, %s, 'group', 'discover', %s, TRUE, NOW())
            """
            
            # Parametre olarak tuple kullan, yıldız operatörü kullanma
            await self.db.execute(query, (group_id, group_id, data_json))
            
            logger.debug(f"Grup verisi kaydedildi: {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"Grup verisi kaydedilirken hata: {str(e)}")
            return False
            
    async def store_user_mining_data(self, user_id, user_data, group_id=None):
        """
        Kullanıcı verilerini data_mining tablosuna kaydeder
        """
        try:
            if not self.db.connected:
                await self.db.connect()
                
            import json
            data_json = json.dumps(user_data)
            
            query = """
            INSERT INTO data_mining (
                telegram_id, user_id, group_id, type, source, data, 
                is_processed, created_at
            ) VALUES (%s, %s, %s, 'user', 'discover', %s, TRUE, NOW())
            """
            
            # Parametre olarak tuple kullan, yıldız operatörü kullanma
            await self.db.execute(query, (user_id, user_id, group_id, data_json))
            
            logger.debug(f"Kullanıcı verisi kaydedildi: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Kullanıcı verisi kaydedilirken hata: {str(e)}")
            return False

    async def get_group_analytics(self, group_id=None, limit=10):
        """
        Gruplar için analitik verileri döndürür
        """
        try:
            if not self.db.connected:
                await self.db.connect()
                
            if group_id:
                # Belirli bir grup için analitik verileri al
                query = """
                SELECT g.group_id, g.name, g.username, 
                       COUNT(DISTINCT gm.user_id) as member_count,
                       COUNT(DISTINCT mt.id) as message_count,
                       (SELECT COUNT(*) FROM group_members WHERE group_id = g.group_id AND is_admin = TRUE) as admin_count
                FROM groups g
                LEFT JOIN group_members gm ON g.group_id = gm.group_id
                LEFT JOIN message_tracking mt ON g.group_id = mt.group_id
                WHERE g.group_id = %s
                GROUP BY g.group_id, g.name, g.username
                """
                return await self.db.fetchone(query, (group_id,))
            else:
                # En aktif grupların listesini al
                query = """
                SELECT g.group_id, g.name, g.username, 
                       COUNT(DISTINCT gm.user_id) as member_count,
                       COUNT(DISTINCT mt.id) as message_count,
                       g.last_message
                FROM groups g
                LEFT JOIN group_members gm ON g.group_id = gm.group_id
                LEFT JOIN message_tracking mt ON g.group_id = mt.group_id
                WHERE g.is_active = TRUE
                GROUP BY g.group_id, g.name, g.username, g.last_message
                ORDER BY message_count DESC, member_count DESC
                LIMIT %s
                """
                return await self.db.fetchall(query, (limit,))
                
        except Exception as e:
            logger.error(f"Grup analitik verileri alınırken hata: {str(e)}")
            return [] if group_id is None else None

    async def set_services(self, services):
        """
        Diğer servislere referansları ayarlar
        """
        self.services = services
        
        # Group Service referansını özel olarak ayarla
        if 'group' in services:
            self.group_service = services['group']
            logger.info("DataMiningService, GroupService'e başarıyla bağlandı")
        else:
            logger.warning("Grup servisi bulunamadı, grup verileri güncellenemiyor")
            
        logger.info("DataMiningService diğer servislere bağlandı") 