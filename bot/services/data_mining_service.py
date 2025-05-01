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
            "mining_interval_hours": 12,    # Her 12 saatte bir tam veri toplama (eskiden 24)
            "incremental_interval_min": 30, # Her 30 dakikada bir artırımlı toplama (eskiden 60)
            "max_users_per_group": 1000,    # Her gruptan maksimum kullanıcı sayısı (eskiden 500)
            "max_groups_per_run": 50,       # Her çalıştırmada maksimum grup sayısı (eskiden 20)
            "store_profile_pictures": True, # Profil resimlerini sakla
            "analyze_bio_text": True,       # Bio metinlerini analiz et
            "gather_language_data": True,   # Dil verilerini topla
            "deep_user_analysis": True,     # Derinlemesine kullanıcı analizi (eskiden False)
            "aggressive_discovery": True,    # Agresif grup keşfi modu (yeni eklendi)
            "fetch_user_bios": True,         # Kullanıcı biosunu al
            "include_bots": True,            # Botları da dahil et
            "force_refresh": False           # Her zaman yeni bilgi topla
        }
        
        # Diğer servislerle entegrasyon
        self.services = {}
        
        # Agresif keşif özellikleri
        self.discovery_depth = 3       # Keşif derinliği seviyesi (yeni eklendi)
        self.analyzed_groups = set()   # Analiz edilen grupların kümesi (yeni eklendi)
        self.analyzed_users = set()    # Analiz edilen kullanıcıların kümesi (yeni eklendi)
        
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
        """
        Analiz için gerekli veritabanı tablolarını oluşturur veya günceller
        """
        try:
            # PostgreSQL için tablo oluşturma sorguları
            create_user_demographics = """
            CREATE TABLE IF NOT EXISTS user_demographics (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE REFERENCES users(user_id),
                language TEXT,
                bio_keywords TEXT,
                country TEXT,
                interests TEXT[],
                profile_picture_url TEXT,
                last_updated TIMESTAMP,
                verified BOOLEAN DEFAULT FALSE,
                premium BOOLEAN DEFAULT FALSE,
                mutual_contact BOOLEAN DEFAULT FALSE,
                common_chats_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sentiments JSONB
            )
            """
            
            create_group_analytics = """
            CREATE TABLE IF NOT EXISTS group_analytics (
                id SERIAL PRIMARY KEY,
                group_id BIGINT UNIQUE REFERENCES groups(group_id),
                analysis_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            
            create_user_group_activity = """
            CREATE TABLE IF NOT EXISTS user_group_activity (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                group_id BIGINT REFERENCES groups(group_id),
                last_seen TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                is_admin BOOLEAN DEFAULT FALSE,
                message_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id)
            )
            """
            
            # Kullanıcı biyografilerindeki linkleri takip etmek için tablo
            create_user_bio_links = """
            CREATE TABLE IF NOT EXISTS user_bio_links (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                link_type TEXT,  -- 'group', 'channel', 'user', etc.
                link_url TEXT NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                group_id BIGINT REFERENCES groups(group_id) NULL,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                UNIQUE(user_id, link_url)
            )
            """
            
            # Biyografi tarama logları
            create_user_bio_scan_logs = """
            CREATE TABLE IF NOT EXISTS user_bio_scan_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                scan_results JSONB,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            
            # Showcu kategorilerine özel gruplar tablosu
            create_category_groups = """
            CREATE TABLE IF NOT EXISTS category_groups (
                id SERIAL PRIMARY KEY,
                group_id BIGINT REFERENCES groups(group_id),
                category TEXT NOT NULL,
                source TEXT,  -- discovery source
                confidence INTEGER DEFAULT 1,  -- 1-10 for how confident we are in the category
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, category)
            )
            """
            
            # İndeksleri oluştur
            create_indices = [
                "CREATE INDEX IF NOT EXISTS idx_user_demographics_language ON user_demographics(language)",
                "CREATE INDEX IF NOT EXISTS idx_user_demographics_verified ON user_demographics(verified)",
                "CREATE INDEX IF NOT EXISTS idx_user_demographics_premium ON user_demographics(premium)",
                "CREATE INDEX IF NOT EXISTS idx_user_group_activity_user ON user_group_activity(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_user_group_activity_group ON user_group_activity(group_id)",
                "CREATE INDEX IF NOT EXISTS idx_user_group_activity_active ON user_group_activity(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_user_bio_links_user ON user_bio_links(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_user_bio_links_type ON user_bio_links(link_type)",
                "CREATE INDEX IF NOT EXISTS idx_user_bio_links_active ON user_bio_links(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_category_groups_category ON category_groups(category)"
            ]
            
            # Tabloları oluştur
            if hasattr(self.db, 'execute'):
                # Ana tablolar
                await self._run_async_db_method(self.db.execute, create_user_demographics)
                await self._run_async_db_method(self.db.execute, create_group_analytics)
                await self._run_async_db_method(self.db.execute, create_user_group_activity)
                await self._run_async_db_method(self.db.execute, create_user_bio_links)
                await self._run_async_db_method(self.db.execute, create_user_bio_scan_logs)
                await self._run_async_db_method(self.db.execute, create_category_groups)
                
                # İndeksler
                for index_query in create_indices:
                    await self._run_async_db_method(self.db.execute, index_query)
                
                # Grup tablosuna analiz sütunu ekleyelim (eğer yoksa)
                try:
                    check_query = """
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'groups' AND column_name = 'analytics_summary'
                    );
                    """
                    result = await self._run_async_db_method(self.db.fetchone, check_query)
                    
                    if not result or not result[0]:
                        alter_query = """
                        ALTER TABLE groups ADD COLUMN analytics_summary JSONB;
                        """
                        await self._run_async_db_method(self.db.execute, alter_query)
                        logger.info("Grup tablosuna analytics_summary kolonu eklendi")
                        
                    # Grup tablosuna invite_link kolonu ekle
                    check_query = """
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'groups' AND column_name = 'invite_link'
                    );
                    """
                    result = await self._run_async_db_method(self.db.fetchone, check_query)
                    
                    if not result or not result[0]:
                        alter_query = """
                        ALTER TABLE groups ADD COLUMN invite_link TEXT;
                        """
                        await self._run_async_db_method(self.db.execute, alter_query)
                        logger.info("Grup tablosuna invite_link kolonu eklendi")
                except Exception as e:
                    logger.error(f"Grup tablosu kolonu ekleme hatası: {str(e)}")
            else:
                logger.warning("Veritabanı bağlantısı uygun değil, tablolar oluşturulamadı")
                
            return True
        except Exception as e:
            logger.error(f"Analiz tablolarını oluşturma hatası: {str(e)}")
            return False
            
    async def run(self):
        """Ana çalışma döngüsü."""
        logger.info("Veri madenciliği servisi başlatıldı")
        
        # İlk çalıştırmada tam bir veri toplama yap
        await self._full_data_mining()
        
        # Otomatik grup keşfi ve katılımını başlat
        try:
            logger.info("Otomatik showcu profil analizi ve grup katılımı başlatılıyor")
            asyncio.create_task(self.auto_discover_and_join_groups("showcu", 15, 24))  # Her 24 saatte bir 15 gruba kadar
            
            # Showcu kızların linklerini keşfet ve katıl
            logger.info("'Showcu kızlar' gruplarına otomatik katılma başlatılıyor")
            asyncio.create_task(self.discover_groups_from_showcu_girls(limit=15, auto_join=True))
        except Exception as e:
            logger.error(f"Otomatik grup keşfi başlatma hatası: {str(e)}")
        
        mining_interval = self.settings["mining_interval_hours"] * 3600
        incremental_interval = self.settings["incremental_interval_min"] * 60
        
        last_full_mining = datetime.now()
        last_incremental_mining = datetime.now()
        last_report_generation = datetime.now()
        last_showcu_analysis = datetime.now()
        last_showcu_girls_discovery = datetime.now()
        
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
                
                # Periyodik rapor oluştur (her 6 saatte bir)
                if (now - last_report_generation).total_seconds() >= 21600:
                    logger.info("Periyodik analiz raporu oluşturuluyor...")
                    await self._generate_periodic_reports()
                    last_report_generation = now
                
                # Showcu analizi günde bir kez çalıştır
                if (now - last_showcu_analysis).total_seconds() >= 86400:  # 24 saat
                    logger.info("Showcu profil analizi başlatılıyor...")
                    asyncio.create_task(self.analyze_profiles_for_showcu())
                    last_showcu_analysis = now
                
                # Showcu kızlardan grup keşfi günde iki kez
                if (now - last_showcu_girls_discovery).total_seconds() >= 43200:  # 12 saat
                    logger.info("'Showcu kızlar' gruplarının keşfi başlatılıyor...")
                    asyncio.create_task(self.discover_groups_from_showcu_girls(limit=10, auto_join=True))
                    last_showcu_girls_discovery = now
                
                # Kısa bir süre bekle ve kontrol et
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Veri madenciliği döngü hatası: {str(e)}")
                logger.debug(traceback.format_exc())
                await asyncio.sleep(300)  # Hata durumunda 5 dakika bekle
        
        logger.info("Veri madenciliği servisi durduruldu")
            
    async def _full_data_mining(self):
        """
        Tam kapsamlı veri toplama işlemi.
        Bu, tüm gruplardaki tüm kullanıcıları kapsar.
        """
        try:
            if not self.client.is_connected():
                await self.client.connect()
                
            logger.info("Tam kapsamlı veri toplama işlemi başlatılıyor...")
            
            # 1. Aktif grupları getir
            all_groups = await self._get_all_groups()
            if not all_groups:
                logger.warning("Hiç grup bulunamadı, veri toplama işlemi iptal ediliyor")
                return
                
            # Maksimum grup sayısını sınırla
            max_groups = min(len(all_groups), self.settings.get("max_groups_per_run", 50))
            selected_groups = random.sample(all_groups, max_groups)
            
            logger.info(f"Veri toplama için {max_groups} grup seçildi (toplam {len(all_groups)} grup)")
            
            # 2. Her gruptan kullanıcıları çek
            # İlerleme çubuğunu hazırla
            total_users = 0
            total_groups = 0
            
            # İlerleme bilgisini logla
            logger.info(f"Toplam {len(selected_groups)} gruptan kullanıcı verileri toplanıyor")
            
            for idx, group in enumerate(selected_groups, 1):
                try:
                    group_id = group.get("group_id") or group.get("chat_id")
                    group_title = group.get("title", "")
                    
                    # Her bir grubun içeriğini al
                    logger.info(f"[{idx}/{len(selected_groups)}] {group_title} grubundan kullanıcı verileri toplanıyor")
                    users = await self._get_detailed_group_members(group_id)
                    
                    # Verileri veritabanına kaydet
                    for user in users:
                        await self._store_user_data(user.get("id"), user, group_id)
                        total_users += 1
                    
                    # Grup analizini işaretle
                    self.analyzed_groups.add(group_id)
                    total_groups += 1
                    
                    logger.info(f"[{idx}/{len(selected_groups)}] {group_title} grubundan {len(users)} kullanıcı toplandı")
                    
                except Exception as group_error:
                    logger.error(f"Grup verileri toplanırken hata: {str(group_error)}")
                    continue
            
            # Kullanıcı segmentlerini güncelle
            await self._update_user_segments()
            
            # İstatistikleri güncelle
            self.total_users_mined += total_users
            self.total_groups_mined += total_groups
            self.last_mining_time = datetime.now()
            
            # Mining istatistiklerini güncelle
            self.mining_stats = {
                "last_full_mining": datetime.now().isoformat(),
                "total_users_mined": self.total_users_mined,
                "total_groups_mined": self.total_groups_mined
            }
            
            # Son olarak grupları detaylı analiz et
            logger.info("Grupların detaylı analizi başlatılıyor...")
            await self._perform_detailed_group_analysis(selected_groups)
            
            logger.info(f"Tam kapsamlı veri toplama tamamlandı: {total_users} kullanıcı, {total_groups} grup")
            
        except Exception as e:
            logger.error(f"Tam kapsamlı veri toplama hatası: {str(e)}")
            
    async def _perform_detailed_group_analysis(self, groups):
        """
        Seçilen grupların detaylı analizini yapar.
        
        Args:
            groups: Analiz edilecek grupların listesi
        """
        try:
            logger.info(f"Detaylı grup analizi başlatılıyor: {len(groups)} grup")
            
            # Analysis klasörünü oluştur
            os.makedirs('data/analysis', exist_ok=True)
            
            for group in groups:
                try:
                    group_id = group.get("group_id") or group.get("chat_id")
                    group_title = group.get("title", "Bilinmeyen Grup")
                    
                    if not group_id:
                        continue
                    
                    logger.debug(f"Grup analiz ediliyor: {group_title} (ID: {group_id})")
                    
                    # 1. Temel grup bilgilerini topla
                    analysis_data = {
                        "group_id": group_id,
                        "title": group_title,
                        "username": group.get("username"),
                        "member_count": group.get("member_count", 0),
                        "active_count": 0,
                        "new_count": 0,
                        "language_distribution": {},
                        "collection_time": datetime.now().isoformat()
                    }
                    
                    # 2. Grup üyelerinin dillerini analiz et
                    language_query = """
                    SELECT 
                        COALESCE(ud.language, 'unknown') as lang, 
                        COUNT(*) as count
                    FROM user_group_activity uga
                    LEFT JOIN user_demographics ud ON uga.user_id = ud.user_id
                    WHERE uga.group_id = %s
                    GROUP BY lang
                    ORDER BY count DESC
                    """
                    
                    if hasattr(self.db, 'fetchall'):
                        language_results = await self._run_async_db_method(
                            self.db.fetchall, 
                            language_query, 
                            (group_id,)
                        )
                        
                        if language_results:
                            for lang, count in language_results:
                                if lang and lang != 'unknown':
                                    analysis_data["language_distribution"][lang] = count
                    
                    # 3. Aktif üye sayısını analiz et
                    activity_query = """
                    SELECT 
                        COUNT(DISTINCT CASE WHEN uga.is_active = TRUE THEN uga.user_id END) as active_users,
                        COUNT(DISTINCT uga.user_id) as total_users
                    FROM user_group_activity uga
                    WHERE uga.group_id = %s
                    """
                    
                    if hasattr(self.db, 'fetchone'):
                        activity_results = await self._run_async_db_method(
                            self.db.fetchone, 
                            activity_query, 
                            (group_id,)
                        )
                        
                        if activity_results:
                            analysis_data["active_count"] = activity_results[0]
                    
                    # 4. Son 30 günde katılan yeni üyeleri analiz et
                    new_users_query = """
                    SELECT COUNT(*) 
                    FROM user_group_activity 
                    WHERE group_id = %s AND created_at > NOW() - INTERVAL '30 days'
                    """
                    
                    if hasattr(self.db, 'fetchone'):
                        new_users_results = await self._run_async_db_method(
                            self.db.fetchone, 
                            new_users_query, 
                            (group_id,)
                        )
                        
                        if new_users_results:
                            analysis_data["new_count"] = new_users_results[0]
                    
                    # 5. Analizi JSON dosyasına kaydet
                    try:
                        with open(f'data/analysis/group_{group_id}.json', 'w', encoding='utf-8') as f:
                            json.dump(analysis_data, f, ensure_ascii=False)
                        logger.debug(f"Grup analizi kaydedildi: data/analysis/group_{group_id}.json")
                    except Exception as save_error:
                        logger.error(f"Grup analizi kaydedilemedi: {str(save_error)}")
                    
                    # 6. Veritabanına kaydet
                    await self._store_group_analysis(group_id, analysis_data)
                    
                except Exception as group_analysis_error:
                    logger.error(f"Grup analizi hatası (ID: {group.get('group_id')}): {str(group_analysis_error)}")
                    continue
            
            logger.info(f"Detaylı grup analizi tamamlandı: {len(groups)} grup")
            
        except Exception as e:
            logger.error(f"Detaylı grup analizi hatası: {str(e)}")
            traceback.print_exc()
            
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
        Grubun üye listesini detaylı olarak getirir. Üyeleri veritabanında saklar ve
        sadece güncellenmiş veya yeni üyeleri çeker.
        
        Args:
            group_id: Grup ID
            
        Returns:
            List[Dict]: Üyelerin listesi (detaylı bilgilerle)
        """
        try:
            # 1. Önce mevcut veritabanı kayıtlarını kontrol et - bu gruptan zaten kayıtlı kullanıcılar var mı?
            cached_members = await self._get_cached_group_members(group_id)
            
            # 2. Yüksek düzeyde aktivite veya çok az üye varsa, yeniden bilgi topla
            if len(cached_members) < 10 or self.settings.get("force_refresh", False):
                logger.info(f"Grup {group_id} için detaylı üye bilgileri toplanıyor (DB'de {len(cached_members)} üye bulundu)")
                
                # Tüm katılımcıları getir
                participants = []
                
                # Farklı filtrelerle üye getirmeyi dene
                all_filters = [
                    types.ChannelParticipantsRecent(),  # Son etkinlik gösteren üyeler
                    types.ChannelParticipantsAdmins(),  # Yöneticiler
                    types.ChannelParticipantsBots()     # Botlar (analiz için)
                ]
                
                # Ekstra filtreler (başarısız olursa kullan)
                backup_filters = [
                    types.ChannelParticipantsSearch(q="a"),  # "a" ile başlayan kullanıcılar için arama
                    types.ChannelParticipantsContacts()   # Kişiler
                ]
                
                # Her filtre için ayrı ayrı getir ve birleştir
                seen_user_ids = set()
                for filter_type in all_filters:
                    try:
                        batch = await self.client(functions.channels.GetParticipantsRequest(
                            channel=group_id,
                            filter=filter_type,
                            offset=0,
                            limit=self.settings["max_users_per_group"],
                            hash=0
                        ))
                        
                        # Benzersiz kullanıcıları ekle
                        for user in batch.users:
                            if user.id not in seen_user_ids:
                                seen_user_ids.add(user.id)
                                participants.append(user)
                    except Exception as filter_error:
                        logger.warning(f"Filtre {filter_type.__class__.__name__} ile üye getirme hatası: {str(filter_error)}")
                        continue
                
                # Eğer tüm filtreler başarısızsa, ekstra filtreleri deneyin
                if not participants:
                    for filter_type in backup_filters:
                        try:
                            batch = await self.client(functions.channels.GetParticipantsRequest(
                                channel=group_id,
                                filter=filter_type,
                                offset=0,
                                limit=self.settings["max_users_per_group"],
                                hash=0
                            ))
                            
                            # Benzersiz kullanıcıları ekle
                            for user in batch.users:
                                if user.id not in seen_user_ids:
                                    seen_user_ids.add(user.id)
                                    participants.append(user)
                        except Exception as backup_error:
                            logger.warning(f"Ekstra filtre {filter_type.__class__.__name__} ile üye getirme hatası: {str(backup_error)}")
                            continue
                
                # Telethon User nesnelerini dict'e dönüştür
                members = []
                for user in participants:
                    # Bot'ları es geç (seçeneğe bağlı)
                    if user.bot and not self.settings.get("include_bots", False):
                        continue
                        
                    # Kullanıcı bilgilerini hazırla
                    member_data = {
                        'id': user.id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'phone': user.phone if hasattr(user, 'phone') else None,
                        'bot': user.bot if hasattr(user, 'bot') else False,
                        'status': str(user.status).split('(')[0] if hasattr(user, 'status') and user.status else 'Unknown',
                        'lang_code': user.lang_code if hasattr(user, 'lang_code') else None,
                        'premium': user.premium if hasattr(user, 'premium') else False,
                        'verified': user.verified if hasattr(user, 'verified') else False,
                        'restricted': user.restricted if hasattr(user, 'restricted') else False,
                        'mutual_contact': user.mutual_contact if hasattr(user, 'mutual_contact') else False,
                        'has_profile_photo': (user.photo is not None) if hasattr(user, 'photo') else False,
                        'last_updated': datetime.now().isoformat(),
                    }
                    
                    # Bioyu getir (varsa ve ayarlarda etkinse)
                    if self.settings.get("fetch_user_bios", False):
                        try:
                            full_user = await self.client(functions.users.GetFullUserRequest(id=user.id))
                            member_data['bio'] = full_user.about
                        except Exception as bio_error:
                            member_data['bio'] = None
                    
                    members.append(member_data)
                    
                    # Kullanıcıyı veritabanına kalıcı olarak kaydet
                    try:
                        result = await self._store_user_data(user.id, member_data, group_id)
                        if result == "new":
                            logger.debug(f"Yeni kullanıcı eklendi: {user.id} ({user.first_name or ''} {user.last_name or ''})")
                    except Exception as db_error:
                        logger.error(f"Kullanıcı veritabanına kaydedilirken hata: {str(db_error)}")
                
                # Grup üye sayısını güncelle
                if hasattr(self.db, 'update_group') and len(members) > 0:
                    await self._run_async_db_method(
                        self.db.update_group,
                        group_id,
                        {'member_count': len(members)}
                    )
                    
                # Grup analizini güncelle
                analysis_data = {
                    'total_members': len(members),
                    'active_members': sum(1 for m in members if m.get('status') in ['UserStatusRecently', 'UserStatusOnline']),
                    'bots': sum(1 for m in members if m.get('bot', False)),
                    'premium_users': sum(1 for m in members if m.get('premium', False)),
                    'verified_users': sum(1 for m in members if m.get('verified', False)),
                    'has_profile_photos': sum(1 for m in members if m.get('has_profile_photo', False)),
                    'analyzed_at': datetime.now().isoformat()
                }
                
                await self._store_group_analysis(group_id, analysis_data)
                
                # Yukarıda DB'ye kaydettiğimiz için işleme sonuçlarını döndür
                logger.info(f"Grup {group_id} için {len(members)} üye çekildi ve veritabanına kaydedildi")
                return members
            else:
                # 3. Veritabanından önbelleği kullan
                logger.info(f"Grup {group_id} için önbellekten {len(cached_members)} üye kullanılıyor")
                return cached_members
            
        except Exception as e:
            logger.error(f"Grup üyelerini getirme hatası ({group_id}): {str(e)}")
            return []
    
    async def _get_cached_group_members(self, group_id) -> List[Dict]:
        """
        Veritabanından grup üyelerini getirir.
        
        Args:
            group_id: Grup ID
            
        Returns:
            List[Dict]: Üye listesi
        """
        try:
            # Veritabanından grup üyelerini getir
            if hasattr(self.db, 'get_group_members'):
                members = await self._run_async_db_method(self.db.get_group_members, group_id)
                return members
            
            # Alternatif SQL sorgusu
            query = """
            SELECT u.user_id, u.first_name, u.last_name, u.username, 
                   u.is_premium as premium, u.is_verified as verified, u.is_bot as bot,
                   u.last_active_at as last_active
            FROM users u
            JOIN user_group_activity uga ON u.user_id = uga.user_id
            WHERE uga.group_id = %s
            ORDER BY uga.last_seen DESC
            """
            
            result = await self._run_async_db_method(self.db.fetchall, query, (group_id,))
            
            if result:
                members = []
                for row in result:
                    # Row'u dict'e dönüştür - asıl veritabanı yapınıza göre ayarlayın
                    if isinstance(row, dict):
                        members.append(row)
                    elif isinstance(row, tuple):
                        member = {
                            'id': row[0],
                            'first_name': row[1],
                            'last_name': row[2],
                            'username': row[3],
                            'premium': row[4],
                            'verified': row[5],
                            'bot': row[6],
                            'last_active': row[7].isoformat() if row[7] else None
                        }
                        members.append(member)
                return members
            else:
                return []
            
        except Exception as e:
            logger.error(f"Önbellekten grup üyeleri alınırken hata: {str(e)}")
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
                        True,  # is_active
                        user_data.get('premium', False)
                    )
                result = "updated"
            
            # 2. Demografik bilgileri kaydet
            if hasattr(self.db, 'update_user_demographics'):
                now = datetime.now()
                has_profile_photo = user_data.get('has_profile_photo', False) or bool(user_data.get('photo', False))
                
                # Tam biyografiyi alma (varsa)
                bio_text = user_data.get('bio', '')
                if not bio_text and self.settings.get("fetch_user_bios", False):
                    try:
                        full_user = await self.client(functions.users.GetFullUserRequest(id=user_id))
                        bio_text = full_user.about or ""
                    except Exception as e:
                        logger.debug(f"Tam biyografi alınamadı ({user_id}): {str(e)}")
                
                # Biyografiden anahtar kelimeleri çıkar
                bio_keywords = self._extract_bio_keywords(bio_text)
                
                # Kullanıcı kategorilerini belirle
                interests = {}
                if bio_text:
                    interests = await self.analyze_bio_text_for_interests(bio_text)
                
                # Biyografideki grup linklerini tara
                telegram_links = []
                if bio_text:
                    telegram_links = self._extract_telegram_links(bio_text)
                
                # Demografik bilgileri hazırla
                demos = {
                    'user_id': user_id,
                    'language': user_data.get('lang_code'),
                    'bio_keywords': bio_keywords,
                    'profile_picture_url': "has_photo" if has_profile_photo else None,
                    'last_updated': now,
                    'verified': user_data.get('verified', False),
                    'premium': user_data.get('premium', False),
                    'mutual_contact': user_data.get('mutual_contact', False),
                    'common_chats_count': user_data.get('common_chats_count', 0)
                }
                
                # Ek bilgileri ekle
                if interests:
                    demos['interests'] = list(interests.keys())
                
                # Bulunan grup linkleri varsa
                if telegram_links:
                    # Bulunan linkleri kaydet (ayrı bir tabloya)
                    try:
                        if hasattr(self.db, 'execute'):
                            for link in telegram_links:
                                insert_query = """
                                INSERT INTO user_bio_links (
                                    user_id, link_type, link_url, discovered_at
                                ) VALUES (%s, %s, %s, %s)
                                ON CONFLICT (user_id, link_url) DO NOTHING
                                """
                                
                                link_type = 'group' if '/joinchat/' in link or '/join/' in link else 'channel'
                                await self._run_async_db_method(
                                    self.db.execute,
                                    insert_query,
                                    (user_id, link_type, link, now)
                                )
                    except Exception as link_error:
                        logger.warning(f"Kullanıcı {user_id} linkleri kaydedilemedi: {str(link_error)}")
                
                # Kullanıcı demografik bilgilerini güncelle  
                await self._run_async_db_method(self.db.update_user_demographics, demos)
                
                # "showcu" kategorisindeyse ve oto-keşif etkinse, linklerini tara 
                if "showcu" in interests and self.settings.get("aggressive_discovery", True):
                    if telegram_links:
                        asyncio.create_task(self._check_user_bio_links(user_id, telegram_links))
            
            # 3. Grup aktivitesini kaydet (eğer grup ID verilmişse)
            if group_id and hasattr(self.db, 'update_user_group_activity'):
                now = datetime.now()
                status_active = user_data.get('status') in ['UserStatusRecently', 'UserStatusOnline']
                
                activity = {
                    'user_id': user_id,
                    'group_id': group_id,
                    'last_seen': now,
                    'is_active': status_active,
                    'is_admin': False,  # Varsayılan değer
                    'message_count': 0  # Varsayılan değer
                }
                
                # Aktif statüye göre son aktif zamanı güncelle
                if hasattr(self.db, 'update_user_last_active') and status_active:
                    await self._run_async_db_method(self.db.update_user_last_active, user_id, now)
                
                await self._run_async_db_method(self.db.update_user_group_activity, activity)
            
            # 4. Kullanıcı aktivite logunu kaydet
            if hasattr(self.db, 'log_user_activity'):
                log_data = {
                    'user_id': user_id,
                    'action': 'discovery',
                    'details': json.dumps({
                        'source': 'data_mining',
                        'group_id': group_id,
                        'status': user_data.get('status'),
                        'found_at': datetime.now().isoformat()
                    }),
                    'timestamp': datetime.now()
                }
                
                await self._run_async_db_method(self.db.log_user_activity, log_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Kullanıcı verisi kaydetme hatası ({user_id}): {str(e)}")
            return "error"
            
    async def _check_user_bio_links(self, user_id, links, auto_join=False):
        """
        Kullanıcı biyografisindeki linkleri otomatik olarak kontrol eder.
        
        Args:
            user_id: Kullanıcı ID
            links: Kontrol edilecek linkler listesi
            auto_join: Otomatik katılma seçeneği
        """
        try:
            logger.info(f"Kullanıcı {user_id} biyografisindeki {len(links)} link kontrol ediliyor")
            
            joined_groups = 0
            discovered_groups = []
            
            for link in links:
                # Zaten keşfedilmiş grup mu kontrol et
                if hasattr(self.db, 'execute'):
                    check_query = """
                    SELECT COUNT(*) FROM groups 
                    WHERE invite_link = %s
                    """
                    result = await self._run_async_db_method(self.db.fetchone, check_query, (link,))
                    
                    if result and result[0] > 0:
                        logger.debug(f"Link zaten keşfedilmiş: {link}")
                        continue
                
                # Gruba katılmayı dene
                group_info = await self._join_group_via_link(link, auto_join)
                
                if group_info:
                    discovered_groups.append(group_info)
                    
                    if group_info.get('joined'):
                        joined_groups += 1
                        
                # Her link arasında kısa bir bekleme
                await asyncio.sleep(random.uniform(2, 5))
                    
            logger.info(f"Kullanıcı {user_id} biyografi link taraması tamamlandı: {len(discovered_groups)} grup keşfedildi, {joined_groups} gruba katılındı")
            
            # Sonuçları kaydet
            results = {
                "user_id": user_id,
                "discovered_groups": discovered_groups,
                "joined_groups": joined_groups,
                "scanned_links": len(links),
                "timestamp": datetime.now().isoformat()
            }
            
            # Veritabanına kaydet
            if hasattr(self.db, 'execute'):
                try:
                    insert_log = """
                    INSERT INTO user_bio_scan_logs (
                        user_id, scan_results, scanned_at
                    ) VALUES (%s, %s, %s)
                    """
                    
                    await self._run_async_db_method(
                        self.db.execute,
                        insert_log,
                        (user_id, json.dumps(results), datetime.now())
                    )
                except Exception as log_error:
                    logger.warning(f"Biyografi tarama logu kaydedilemedi: {str(log_error)}")
                
        except Exception as e:
            logger.error(f"Kullanıcı biyografi linklerini kontrol ederken hata ({user_id}): {str(e)}")

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
        """
        Veritabanı metodunu thread-safe biçimde çalıştırır.
        Senkron ve asenkron metodları otomatik algılar ve uygun şekilde çalıştırır.
        """
        try:
            # Metod zaten bir coroutine ise (asenkron)
            if asyncio.iscoroutinefunction(method):
                return await method(*args, **kwargs)
            # Senkron bir fonksiyon ise executor kullan
            else:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, 
                    functools.partial(method, *args, **kwargs)
                )
        except Exception as e:
            logger.error(f"Veritabanı metodu çalıştırılırken hata: {str(e)}, metod: {method.__name__}")
            # Uygun bir varsayılan değer döndür
            if method.__name__ == 'fetchall':
                return []
            elif method.__name__ == 'fetchone':
                return None
            else:
                raise  # Diğer durumlarda hatayı yeniden fırlat
            
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
        Kullanıcı demografik verilerinden kapsamlı bir rapor oluşturur.
        
        Args:
            format: Raporun formatı ('json', 'text', 'html')
            
        Returns:
            str: Oluşturulan rapor
        """
        try:
            # Veritabanından demographic bilgileri al
            demo_data = {}
            
            # 1. Dil dağılımı
            if hasattr(self.db, 'execute'):
                query = """
                SELECT language, COUNT(*) as count 
                FROM user_demographics 
                WHERE language IS NOT NULL 
                GROUP BY language 
                ORDER BY count DESC
                """
                language_data = await self._run_async_db_method(self.db.fetchall, query)
                
                demo_data['languages'] = {
                    row[0]: row[1] 
                    for row in language_data 
                    if row and len(row) >= 2
                }
                
            # 2. Aktif/pasif kullanıcı oranı
            if hasattr(self.db, 'execute'):
                query = """
                SELECT 
                    CASE 
                        WHEN last_active_at > NOW() - INTERVAL '30 days' THEN 'active'
                        WHEN last_active_at > NOW() - INTERVAL '90 days' THEN 'semi_active'
                        ELSE 'inactive' 
                    END as status,
                    COUNT(*) as count
                FROM users
                GROUP BY status
                ORDER BY count DESC
                """
                activity_data = await self._run_async_db_method(self.db.fetchall, query)
                
                demo_data['activity_status'] = {
                    row[0]: row[1] 
                    for row in activity_data 
                    if row and len(row) >= 2
                }
                
            # 3. Premium/Doğrulanmış/Bot kullanıcı oranları
            if hasattr(self.db, 'execute'):
                query = """
                SELECT 
                    SUM(CASE WHEN is_premium = TRUE THEN 1 ELSE 0 END) as premium_count,
                    SUM(CASE WHEN is_verified = TRUE THEN 1 ELSE 0 END) as verified_count,
                    SUM(CASE WHEN is_bot = TRUE THEN 1 ELSE 0 END) as bot_count,
                    COUNT(*) as total
                FROM users
                """
                user_types = await self._run_async_db_method(self.db.fetchone, query)
                
                if user_types and len(user_types) >= 4:
                    demo_data['user_types'] = {
                        'premium': user_types[0],
                        'verified': user_types[1],
                        'bot': user_types[2],
                        'total': user_types[3]
                    }
                    
            # 4. Kullanıcı profil fotoğrafı analizi
            if hasattr(self.db, 'execute'):
                query = """
                SELECT 
                    SUM(CASE WHEN profile_picture_url IS NOT NULL THEN 1 ELSE 0 END) as with_photo,
                    COUNT(*) as total
                FROM user_demographics
                """
                profile_data = await self._run_async_db_method(self.db.fetchone, query)
                
                if profile_data and len(profile_data) >= 2:
                    with_photo = profile_data[0] or 0
                    total = profile_data[1] or 1  # 0'a bölmeyi önle
                    
                    demo_data['profile_photos'] = {
                        'with_photo': with_photo,
                        'without_photo': total - with_photo,
                        'percentage': round((with_photo / total) * 100, 2)
                    }
                    
            # 5. Bio kelime analizi
            if hasattr(self.db, 'execute'):
                query = """
                SELECT bio_keywords, COUNT(*) 
                FROM user_demographics 
                WHERE bio_keywords IS NOT NULL 
                GROUP BY bio_keywords 
                ORDER BY COUNT(*) DESC 
                LIMIT 20
                """
                bio_data = await self._run_async_db_method(self.db.fetchall, query)
                
                # Anahtar kelime sıklığını analiz et
                keyword_freq = {}
                for row in bio_data:
                    if row and len(row) >= 1 and row[0]:
                        try:
                            keywords = json.loads(row[0])
                            for kw in keywords:
                                keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
                        except:
                            pass
                
                # En yaygın 10 anahtar kelimeyi al
                top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]
                demo_data['bio_keywords'] = {k: v for k, v in top_keywords}
                
            # 6. Gruplar arası ortak kullanıcı sayısı
            demo_data['group_overlap'] = await self._analyze_group_overlap()
                
            # 7. Kullanıcı büyüme analizi
            if hasattr(self.db, 'execute'):
                query = """
                SELECT 
                    DATE_TRUNC('month', created_at) as month,
                    COUNT(*) as new_users
                FROM users
                WHERE created_at > NOW() - INTERVAL '1 year'
                GROUP BY month
                ORDER BY month
                """
                growth_data = await self._run_async_db_method(self.db.fetchall, query)
                
                demo_data['user_growth'] = {
                    row[0].strftime('%Y-%m'): row[1]
                    for row in growth_data
                    if row and len(row) >= 2 and hasattr(row[0], 'strftime')
                }
                
            # İstenilen formatta çıktı üret
            if format == 'json':
                return json.dumps(demo_data, indent=2, default=str)
            elif format == 'text':
                # Basit metin formatı
                text_report = "KULLANICI DEMOGRAFİK RAPORU\n"
                text_report += "========================\n\n"
                
                # Her bir veri bölümünü ekle
                for section, data in demo_data.items():
                    text_report += f"{section.upper()}:\n"
                    if isinstance(data, dict):
                        for key, value in data.items():
                            text_report += f"  {key}: {value}\n"
                    text_report += "\n"
                    
                return text_report
            else:
                return json.dumps(demo_data, default=str)
                
        except Exception as e:
            logger.error(f"Demografik rapor oluşturma hatası: {str(e)}")
            return json.dumps({"error": str(e)})

    async def _analyze_group_overlap(self):
        """
        Gruplar arasındaki ortak kullanıcı sayısını analiz eder.
        
        Returns:
            dict: Grup çiftleri arasındaki ortak kullanıcı sayısı ve detaylı analiz
        """
        try:
            # En popüler 10 grubu seç
            if hasattr(self.db, 'execute'):
                query = """
                SELECT group_id, title, COUNT(*) as user_count
                FROM user_group_activity uga
                JOIN groups g ON uga.group_id = g.group_id
                GROUP BY uga.group_id, g.title
                ORDER BY user_count DESC
                LIMIT 15
                """
                top_groups = await self._run_async_db_method(self.db.fetchall, query)
                
                results = {
                    "overlap_stats": {},
                    "language_stats": {},
                    "active_users": {},
                    "premium_ratio": {},
                    "user_types": {}
                }
                
                # Her grup çifti için ortak kullanıcı sayısını hesapla
                for i, group1 in enumerate(top_groups):
                    group1_id = group1[0]
                    group1_name = group1[1]
                    
                    # Grubun genel kullanıcı dil istatistiklerini getir
                    lang_query = """
                    SELECT 
                        ud.language, 
                        COUNT(*) as lang_count
                    FROM user_demographics ud
                    JOIN user_group_activity uga ON ud.user_id = uga.user_id
                    WHERE uga.group_id = %s AND ud.language IS NOT NULL
                    GROUP BY ud.language
                    ORDER BY lang_count DESC
                    LIMIT 5
                    """
                    language_stats = await self._run_async_db_method(
                        self.db.fetchall, 
                        lang_query, 
                        (group1_id,)
                    )
                    
                    # Kullanıcı tipi analizi
                    user_type_query = """
                    SELECT 
                        COUNT(DISTINCT CASE WHEN ud.premium = TRUE THEN ud.user_id END) as premium_count,
                        COUNT(DISTINCT CASE WHEN ud.verified = TRUE THEN ud.user_id END) as verified_count,
                        COUNT(DISTINCT CASE WHEN ud.mutual_contact = TRUE THEN ud.user_id END) as mutual_count,
                        COUNT(DISTINCT ud.user_id) as total_users
                    FROM user_demographics ud
                    JOIN user_group_activity uga ON ud.user_id = uga.user_id
                    WHERE uga.group_id = %s
                    """
                    user_types = await self._run_async_db_method(
                        self.db.fetchone, 
                        user_type_query, 
                        (group1_id,)
                    )
                    
                    # Kullanıcı aktivite analizi
                    activity_query = """
                    SELECT 
                        COUNT(DISTINCT CASE WHEN uga.is_active = TRUE THEN uga.user_id END) as active_users,
                        COUNT(DISTINCT CASE WHEN uga.is_admin = TRUE THEN uga.user_id END) as admin_users,
                        COUNT(DISTINCT uga.user_id) as total_users,
                        COALESCE(AVG(CASE WHEN uga.is_active = TRUE THEN uga.message_count END), 0) as avg_messages
                    FROM user_group_activity uga
                    WHERE uga.group_id = %s
                    """
                    activity_stats = await self._run_async_db_method(
                        self.db.fetchone, 
                        activity_query, 
                        (group1_id,)
                    )
                    
                    # Dil istatistiklerini kaydet
                    if language_stats:
                        results["language_stats"][group1_name] = {
                            lang[0]: lang[1] for lang in language_stats if lang[0]
                        }
                    
                    # Kullanıcı tipi istatistiklerini kaydet
                    if user_types and user_types[3] > 0:
                        total_users = max(user_types[3], 1)
                        results["user_types"][group1_name] = {
                            "premium_ratio": round(user_types[0] / total_users, 3),
                            "verified_ratio": round(user_types[1] / total_users, 3),
                            "mutual_ratio": round(user_types[2] / total_users, 3),
                            "total_users": total_users
                        }
                    
                    # Aktivite istatistiklerini kaydet
                    if activity_stats and activity_stats[2] > 0:
                        total_users = max(activity_stats[2], 1)
                        results["active_users"][group1_name] = {
                            "active_ratio": round(activity_stats[0] / total_users, 3),
                            "admin_ratio": round(activity_stats[1] / total_users, 3),
                            "avg_messages": round(activity_stats[3], 1),
                            "total_users": total_users
                        }
                    
                    for j, group2 in enumerate(top_groups[i+1:], i+1):
                        group2_id = group2[0]
                        group2_name = group2[1]
                        
                        # Bu iki grup arasındaki ortak kullanıcı sayısını bul
                        overlap_query = """
                        SELECT COUNT(DISTINCT uga1.user_id) as overlap_count
                        FROM user_group_activity uga1
                        JOIN user_group_activity uga2 ON uga1.user_id = uga2.user_id
                        WHERE uga1.group_id = %s AND uga2.group_id = %s
                        """
                        overlap_count = await self._run_async_db_method(
                            self.db.fetchone, 
                            overlap_query, 
                            (group1_id, group2_id)
                        )
                        
                        if overlap_count and overlap_count[0]:
                            key = f"{group1_name} - {group2_name}"
                            results["overlap_stats"][key] = overlap_count[0]
                            
                            # Ayrıca premium kullanıcı örtüşmesi
                            premium_overlap_query = """
                            SELECT COUNT(DISTINCT uga1.user_id) as overlap_count
                            FROM user_group_activity uga1
                            JOIN user_group_activity uga2 ON uga1.user_id = uga2.user_id
                            JOIN user_demographics ud ON uga1.user_id = ud.user_id
                            WHERE uga1.group_id = %s AND uga2.group_id = %s
                            AND ud.premium = TRUE
                            """
                            premium_overlap = await self._run_async_db_method(
                                self.db.fetchone, 
                                premium_overlap_query, 
                                (group1_id, group2_id)
                            )
                            
                            if premium_overlap and premium_overlap[0]:
                                results["premium_ratio"][key] = premium_overlap[0]
                
                # Analiz sonuçlarını diske kaydet
                try:
                    os.makedirs('data/analysis', exist_ok=True)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    with open(f'data/analysis/group_overlap_{timestamp}.json', 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                    logger.info(f"Grup örtüşme analizi kaydedildi: data/analysis/group_overlap_{timestamp}.json")
                except Exception as save_error:
                    logger.error(f"Grup analiz sonuçları kaydedilemedi: {str(save_error)}")
                
                return results
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Grup örtüşme analizi hatası: {str(e)}")
            traceback.print_exc()
            return {}

    async def _store_group_analysis(self, group_id, analysis_data):
        """
        Grup analiz verilerini saklar.
        
        Args:
            group_id: Grup ID'si
            analysis_data: Analiz verileri sözlüğü
        """
        try:
            # JSON alanını hazırla
            analysis_json = json.dumps(analysis_data)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Önce kayıt var mı kontrol et
            if hasattr(self.db, 'execute'):
                check_query = """
                SELECT COUNT(*) FROM group_analytics 
                WHERE group_id = %s
                """
                result = await self._run_async_db_method(self.db.fetchone, check_query, (group_id,))
                
                if result and result[0] > 0:
                    # Güncelle
                    update_query = """
                    UPDATE group_analytics SET 
                        analysis_data = %s,
                        updated_at = %s
                    WHERE group_id = %s
                    """
                    await self._run_async_db_method(
                        self.db.execute, 
                        update_query, 
                        (analysis_json, now, group_id)
                    )
                else:
                    # Yeni ekle
                    insert_query = """
                    INSERT INTO group_analytics (
                        group_id, analysis_data, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (group_id) DO UPDATE SET
                        analysis_data = EXCLUDED.analysis_data,
                        updated_at = EXCLUDED.updated_at
                    """
                    await self._run_async_db_method(
                        self.db.execute, 
                        insert_query, 
                        (group_id, analysis_json, now, now)
                    )
            
            # Grup tablosunu da güncelle
            if hasattr(self.db, 'execute'):
                # Grup tablosuna analytics_summary alanı ekleme
                try:
                    # Analiz özetini hazırla
                    summary = {
                        "activity_level": "high" if analysis_data.get("active_members", 0) > 10 else "medium",
                        "members": analysis_data.get("total_members", 0),
                        "active_members": analysis_data.get("active_members", 0),
                        "premium_ratio": round(analysis_data.get("premium_users", 0) / max(analysis_data.get("total_members", 1), 1), 2),
                        "analyzed_at": analysis_data.get("analyzed_at")
                    }
                    
                    # Grup tablosuna analiz özetini ekle
                    update_query = """
                    UPDATE groups SET 
                        analytics_summary = %s,
                        member_count = %s,
                        updated_at = %s
                    WHERE group_id = %s
                    """
                    await self._run_async_db_method(
                        self.db.execute,
                        update_query,
                        (json.dumps(summary), analysis_data.get("total_members", 0), now, group_id)
                    )
                except Exception as group_update_error:
                    logger.warning(f"Grup tablosu analiz güncelleme hatası: {str(group_update_error)}")
            
            logger.debug(f"Grup analiz verileri saklandı: {group_id}")
        except Exception as e:
            logger.error(f"Grup analiz verilerini saklama hatası: {str(e)}")

    async def _generate_periodic_reports(self):
        """
        Periyodik analiz raporları oluşturur ve kaydeder.
        """
        try:
            # 1. Demografik rapor
            demo_report = await self.generate_demographic_report()
            
            # 2. Kullanıcı segmentleri raporu
            segment_stats = {name: len(users) for name, users in self.segments.items()}
            
            # 3. Grup aktivite raporu
            group_activity = {}
            if hasattr(self.db, 'get_group_activity_stats'):
                group_activity = await self._run_async_db_method(self.db.get_group_activity_stats)
            
            # Raporu oluştur
            full_report = {
                "timestamp": datetime.now().isoformat(),
                "demographics": json.loads(demo_report) if isinstance(demo_report, str) else demo_report,
                "segments": segment_stats,
                "group_activity": group_activity,
                "mining_stats": {
                    "total_users": self.total_users_mined,
                    "total_groups": self.total_groups_mined,
                    "analyzed_users": len(self.analyzed_users),
                    "analyzed_groups": len(self.analyzed_groups)
                }
            }
            
            # Raporu kaydet
            report_json = json.dumps(full_report, indent=2)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            os.makedirs('data/reports', exist_ok=True)
            with open(f'data/reports/analysis_{timestamp}.json', 'w') as f:
                f.write(report_json)
                
            logger.info(f"Periyodik analiz raporu oluşturuldu: data/reports/analysis_{timestamp}.json")
            
        except Exception as e:
            logger.error(f"Periyodik rapor oluşturma hatası: {str(e)}")

    async def _generate_geographic_analysis(self):
        """
        Kullanıcı coğrafi dağılımını analiz eder (ülkeler bazında)
        
        Returns:
            dict: Ülkere göre kullanıcı dağılımı
        """
        try:
            # Saat dilimi ve dil koduna göre ülke tahmini yap
            if hasattr(self.db, 'execute'):
                query = """
                SELECT 
                    language,
                    COUNT(*) as user_count
                FROM user_demographics
                WHERE language IS NOT NULL
                GROUP BY language
                ORDER BY user_count DESC
                """
                language_data = await self._run_async_db_method(self.db.fetchall, query)
                
                # Dil kodlarını ülke adlarına dönüştür (basit eşleştirme)
                language_to_country = {
                    'tr': 'Turkey',
                    'en': 'United States',
                    'ru': 'Russia',
                    'ar': 'Saudi Arabia',
                    'fr': 'France',
                    'de': 'Germany',
                    'es': 'Spain',
                    'it': 'Italy',
                    'zh': 'China',
                    'ja': 'Japan',
                    'ko': 'South Korea'
                }
                
                country_distribution = {}
                for row in language_data:
                    if row and len(row) >= 2:
                        lang_code = row[0].lower()[:2] if row[0] else 'unknown'
                        count = row[1]
                        
                        country = language_to_country.get(lang_code, 'Unknown')
                        country_distribution[country] = country_distribution.get(country, 0) + count
                
                return country_distribution
                
            return {}
            
        except Exception as e:
            logger.error(f"Coğrafi analiz hatası: {str(e)}")
            return {}

    async def discover_groups_from_bios(self, profile_type=None, auto_join=False, limit=20):
        """
        Kullanıcı biyografilerindeki Telegram grup linklerini tespit eder ve 
        bu gruplara otomatik katılır.
        
        Args:
            profile_type: Belirli bir profil tipine sahip kullanıcıları filtrelemek için (örn: "showcu")
            auto_join: Bulunan gruplara otomatik katılma seçeneği
            limit: Keşfedilecek maksimum grup sayısı
            
        Returns:
            dict: Keşfedilen gruplar ve sonuçlar
        """
        try:
            discovered_groups = []
            total_scanned = 0
            total_joined = 0
            
            # Biyografileri içeren kullanıcıları getir
            query = """
            SELECT user_id, bio_keywords, language
            FROM user_demographics
            WHERE bio_keywords IS NOT NULL
            """
            
            # Profil tipine göre filtreleme
            if profile_type:
                profile_keywords = profile_type.lower().split()
                
                conditions = []
                for keyword in profile_keywords:
                    conditions.append(f"LOWER(bio_keywords) LIKE '%{keyword}%'")
                
                if conditions:
                    query += " AND (" + " OR ".join(conditions) + ")"
            
            # Sorguyu çalıştır
            users_with_bios = await self._run_async_db_method(self.db.fetchall, query)
            logger.info(f"İncelenecek {len(users_with_bios)} kullanıcı profili bulundu")
            
            # Biyografileri analiz et
            for user_data in users_with_bios:
                try:
                    if not user_data or len(user_data) < 2 or not user_data[1]:
                        continue
                    
                    user_id = user_data[0]
                    bio_data = user_data[1]
                    
                    # Biyografiyi JSON'dan çöz
                    try:
                        bio_keywords = json.loads(bio_data)
                    except:
                        bio_keywords = []
                    
                    # Eğer JSON parse edilemediyse
                    if isinstance(bio_data, str) and bio_data.startswith('{'):
                        # Tam biyografiyi almaya çalış
                        try:
                            full_user = await self.client(functions.users.GetFullUserRequest(id=user_id))
                            bio_text = full_user.about or ""
                        except Exception as e:
                            logger.debug(f"Kullanıcı biyografisi alınamadı ({user_id}): {str(e)}")
                            bio_text = bio_data
                    else:
                        # Tam biyografiyi al
                        try:
                            full_user = await self.client(functions.users.GetFullUserRequest(id=user_id))
                            bio_text = full_user.about or ""
                        except Exception as e:
                            logger.debug(f"Kullanıcı biyografisi alınamadı ({user_id}): {str(e)}")
                            continue
                    
                    # Grup linklerini kontrol et (t.me/, telegram.me/, joinchat/)
                    found_links = self._extract_telegram_links(bio_text)
                    total_scanned += 1
                    
                    if found_links:
                        for link in found_links:
                            # Link zaten keşfedildi mi kontrol et
                            if link in [g.get('invite_link') for g in discovered_groups]:
                                continue
                                
                            # Gruba katılmayı dene
                            group_info = await self._join_group_via_link(link, auto_join)
                            
                            if group_info:
                                discovered_groups.append(group_info)
                                logger.info(f"Kullanıcı {user_id} biyografisinden yeni grup keşfedildi: {group_info.get('title')}")
                                
                                if group_info.get('joined') and auto_join:
                                    total_joined += 1
                                    
                                # Limit kontrolü
                                if len(discovered_groups) >= limit:
                                    logger.info(f"Grup keşif limiti ({limit}) aşıldı, işlem durduruluyor")
                                    break
                    
                    # Dış döngüyü durdurmak için kontrol
                    if len(discovered_groups) >= limit:
                        break
                        
                except Exception as user_error:
                    logger.warning(f"Kullanıcı {user_data[0] if user_data and len(user_data) > 0 else 'bilinmeyen'} analizi hatası: {str(user_error)}")
                    continue
            
            # Sonuçları raporla
            results = {
                "discovered_groups": discovered_groups,
                "total_scanned": total_scanned,
                "total_joined": total_joined,
                "profile_type": profile_type,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Biyografi analizi tamamlandı: {len(discovered_groups)} grup keşfedildi, {total_joined} gruba katılındı")
            return results
            
        except Exception as e:
            logger.error(f"Biyografilerden grup keşfetme hatası: {str(e)}")
            return {"error": str(e)}
    
    def _extract_telegram_links(self, text):
        """
        Metinden Telegram grup linklerini çıkarır
        
        Args:
            text: Analiz edilecek metin
            
        Returns:
            list: Bulunan Telegram linkleri
        """
        if not text:
            return []
            
        links = []
        import re
        
        # Telegram grup/kanal link formatları
        patterns = [
            r"(?:https?://)?(?:www\.)?t\.me/(?:joinchat|join)?/?([a-zA-Z0-9_\-]+)",
            r"(?:https?://)?(?:www\.)?telegram\.me/(?:joinchat|join)?/?([a-zA-Z0-9_\-]+)",
            r"(?:https?://)?(?:www\.)?telegram\.dog/(?:joinchat|join)?/?([a-zA-Z0-9_\-]+)"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            
            for match in matches:
                # Tam linki oluştur
                if "joinchat" in pattern or "join" in pattern:
                    link = f"https://t.me/joinchat/{match}"
                else:
                    link = f"https://t.me/{match}"
                    
                if link not in links:
                    links.append(link)
                    
        return links
        
    async def _join_group_via_link(self, link, auto_join=False):
        """
        Verilen link üzerinden gruba katılır
        
        Args:
            link: Katılmak için grup linki
            auto_join: Otomatik katılma seçeneği
            
        Returns:
            dict: Grup bilgileri veya None
        """
        try:
            # Link tipini belirle: Genel kanal/grup veya özel davet
            is_public = '/joinchat/' not in link and '/join/' not in link
            
            group_info = {
                'invite_link': link,
                'source': 'bio_discovery',
                'discovered_at': datetime.now().isoformat(),
                'type': 'public' if is_public else 'private',
                'joined': False
            }
            
            if is_public:
                # Genel kanal/grup
                username = link.split('/')[-1]
                
                try:
                    # Grup bilgilerini getir
                    entity = await self.client.get_entity(username)
                    group_info['title'] = entity.title
                    group_info['username'] = username
                    group_info['id'] = entity.id
                    group_info['members_count'] = getattr(entity, 'participants_count', 0)
                    
                    # Otomatik katılma seçeneği etkinse
                    if auto_join:
                        await self.client(JoinChannelRequest(entity))
                        group_info['joined'] = True
                        logger.info(f"Başarıyla katıldı: {entity.title}")
                        
                        # Grubu veritabanına kaydet
                        if hasattr(self.db, 'add_group'):
                            await self._run_async_db_method(
                                self.db.add_group, 
                                entity.id, 
                                entity.title, 
                                username, 
                                None, 
                                getattr(entity, 'participants_count', 0), 
                                True  # is_active
                            )
                except Exception as public_error:
                    logger.warning(f"Genel gruba katılma hatası ({username}): {str(public_error)}")
                    group_info['error'] = str(public_error)
            else:
                # Özel davetli grup
                hash_part = link.split('/')[-1]
                
                try:
                    # Gruba katıl
                    if '/joinchat/' in link:
                        updates = await self.client(ImportChatInviteRequest(hash_part))
                    else:
                        updates = await self.client(ImportChatInviteRequest(hash_part))
                    
                    # Grup bilgilerini güncelle
                    if hasattr(updates, 'chats') and updates.chats:
                        chat = updates.chats[0]
                        group_info['title'] = chat.title
                        group_info['id'] = chat.id
                        group_info['members_count'] = getattr(chat, 'participants_count', 0)
                        group_info['joined'] = True
                        
                        # Grubu veritabanına kaydet
                        if hasattr(self.db, 'add_group'):
                            await self._run_async_db_method(
                                self.db.add_group, 
                                chat.id, 
                                chat.title, 
                                getattr(chat, 'username', None), 
                                None, 
                                getattr(chat, 'participants_count', 0), 
                                True  # is_active
                            )
                        
                        logger.info(f"Başarıyla özel gruba katıldı: {chat.title}")
                except Exception as private_error:
                    logger.warning(f"Özel gruba katılma hatası ({hash_part}): {str(private_error)}")
                    group_info['error'] = str(private_error)
                
            return group_info
        except Exception as e:
            logger.error(f"Gruba katılma hatası ({link}): {str(e)}")
            return None
            
    async def analyze_profiles_for_showcu(self):
        """
        'Showcu' profillerine sahip kullanıcıları belirler ve onların
        biyografilerindeki grup linklerini keşfeder.
        
        Returns:
            dict: Analiz sonuçları
        """
        try:
            # Showcu olabilecek profilleri bulmak için anahtar kelimeler
            search_keywords = ["show", "dans", "sahne", "performans", "dansçı", "model"]
            
            # İlk önce bio_keywords alanında bu terimleri içeren kullanıcıları bul
            query = """
            SELECT user_id, bio_keywords
            FROM user_demographics
            WHERE bio_keywords IS NOT NULL AND (
            """
            
            conditions = []
            for keyword in search_keywords:
                conditions.append(f"LOWER(bio_keywords) LIKE '%{keyword.lower()}%'")
            
            query += " OR ".join(conditions) + ")"
            
            showcu_profiles = await self._run_async_db_method(self.db.fetchall, query)
            logger.info(f"Potansiyel 'showcu' profili olan {len(showcu_profiles)} kullanıcı bulundu")
            
            # Bu kullanıcıların biyografilerindeki grup linklerini keşfet
            discovered_groups = await self.discover_groups_from_bios(profile_type="showcu", auto_join=True, limit=30)
            
            # Sonuçları raporla
            results = {
                "showcu_profiles_count": len(showcu_profiles),
                "discovered_groups": discovered_groups.get("discovered_groups", []),
                "total_joined": discovered_groups.get("total_joined", 0),
                "timestamp": datetime.now().isoformat()
            }
            
            # Raporu kaydet
            report_path = os.path.join('data', 'reports', f'showcu_groups_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
                
            logger.info(f"'Showcu' profil analizi tamamlandı ve {report_path} dosyasına kaydedildi")
            return results
            
        except Exception as e:
            logger.error(f"'Showcu' profil analizi hatası: {str(e)}")
            return {"error": str(e)}
            
    async def auto_discover_and_join_groups(self, category="showcu", limit=20, schedule_hours=12):
        """
        Belirli kategorideki kullanıcı biyografilerindeki grup linklerini periyodik olarak 
        keşfeder ve otomatik olarak gruplara katılır.
        
        Args:
            category: Aranacak profil kategorisi (örn: "showcu", "müzik", "sanat")
            limit: Her çalıştırmada katılınacak maksimum grup sayısı
            schedule_hours: Otomatik çalışma aralığı (saat)
            
        Returns:
            dict: İşlem sonuçları
        """
        results = await self.discover_groups_from_bios(profile_type=category, auto_join=True, limit=limit)
        
        # Takvime ekle
        if schedule_hours > 0:
            logger.info(f"Grup keşif işlemi {schedule_hours} saat sonra tekrar çalışacak şekilde ayarlandı")
            
            # Periyodik çalışmayı ayarla
            asyncio.create_task(self._schedule_discovery(category, limit, schedule_hours))
            
        return results
        
    async def _schedule_discovery(self, category, limit, hours):
        """
        Grup keşfini periyodik olarak çalıştırır
        """
        await asyncio.sleep(hours * 3600)  # Saati saniyeye çevir
        
        try:
            logger.info(f"Zamanlanmış grup keşfi başlatılıyor (kategori: {category})")
            await self.auto_discover_and_join_groups(category, limit, hours)
        except Exception as e:
            logger.error(f"Zamanlanmış grup keşfi hatası: {str(e)}")
            
            # Hata olsa bile tekrar çalıştırmayı dene
            asyncio.create_task(self._schedule_discovery(category, limit, hours))

    async def analyze_bio_text_for_interests(self, bio_text, categories=None):
        """
        Biyografi metnini analiz ederek ilgi alanlarını belirlemeye çalışır.
        
        Args:
            bio_text: Analiz edilecek biyografi metni
            categories: Kontrol edilecek kategori listesi, yoksa varsayılan kategoriler kullanılır
            
        Returns:
            dict: Tespit edilen kategoriler ve puanları
        """
        if not bio_text:
            return {}
            
        # Varsayılan kategoriler ve anahtar kelimeleri
        default_categories = {
            "showcu": ["dans", "sahne", "model", "dansçı", "show", "performans", "gösteri", "sahne"],
            "müzik": ["şarkı", "müzik", "dj", "konser", "rap", "şarkıcı", "artist", "müzisyen", "hip hop"],
            "spor": ["fitness", "gym", "crossfit", "antrenör", "futbol", "basketbol", "spor", "sporcu"],
            "sanat": ["resim", "fotoğraf", "fotoğrafçı", "sanat", "artist", "çizim", "tasarım"],
            "moda": ["moda", "stil", "fashion", "model", "influencer", "makyaj", "güzellik", "kozmetik"],
            "eğlence": ["parti", "club", "gece", "event", "etkinlik", "eğlence", "organizasyon"]
        }
        
        # Belirtilen kategorileri kullan veya varsayılanları kullan
        categories = categories or default_categories
        
        # Her kategori için puan hesapla
        results = {}
        bio_lower = bio_text.lower()
        
        for category, keywords in categories.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in bio_lower:
                    score += 1
                    
            if score > 0:
                results[category] = score
                
        # Tespit edilen kategorileri döndür
        return results

    async def discover_groups_from_showcu_girls(self, limit=10, auto_join=False):
        """
        Showcu olarak bilinen kızların profillerindeki grup bağlantılarını keşfeder ve 
        isteğe bağlı olarak bu gruplara otomatik katılır.
        
        Args:
            limit (int): Keşfedilecek/katılacak maksimum grup sayısı
            auto_join (bool): Keşfedilen gruplara otomatik katılıp katılmayacağı
        
        Returns:
            list: Keşfedilen grup bağlantılarının listesi
        """
        try:
            logger.info(f"Showcu kızlardan grup keşfi başlatılıyor. Limit: {limit}, Otomatik katılım: {auto_join}")
            
            # Veritabanından 'showcu' olarak işaretlenmiş kullanıcıları al
            showcu_query = """
            SELECT u.user_id, u.username, d.bio_keywords 
            FROM users u 
            LEFT JOIN user_demographics d ON u.user_id = d.user_id
            WHERE u.tags @> ARRAY['showcu'] 
            AND u.is_female = true
            ORDER BY u.last_activity_date DESC 
            LIMIT 100
            """
            
            showcu_users = await self._run_async_db_method(self.db.fetchall, showcu_query)
            
            if not showcu_users:
                logger.info("İşaretlenmiş showcu kız bulunamadı")
                return []
            
            logger.info(f"{len(showcu_users)} showcu kız kullanıcısı bulundu, grup bağlantıları analiz ediliyor")
            
            discovered_links = []
            joined_count = 0
            
            for user_data in showcu_users:
                user_id, username, bio = user_data
                
                try:
                    # Kullanıcı bilgilerini al
                    if username:
                        user_entity = await self.client.get_entity(username)
                    else:
                        user_entity = await self.client.get_entity(user_id)
                    
                    # Profil açıklamasındaki bağlantıları incele
                    if user_entity.about:
                        # t.me/ linklerini ara
                        links = self._extract_telegram_links(user_entity.about)
                        
                        for link in links:
                            if link not in discovered_links:
                                discovered_links.append(link)
                                
                                # Otomatik katılım etkinse
                                if auto_join and joined_count < limit:
                                    try:
                                        # Grup bilgilerini al
                                        group_entity = await self.client.get_entity(link)
                                        
                                        # Sadece gerçek bir grup ise katıl
                                        if hasattr(group_entity, 'megagroup') and group_entity.megagroup:
                                            # Grup zaten veritabanında var mı kontrol et
                                            exists = await self._check_group_exists(group_entity.id)
                                            
                                            if not exists:
                                                await self.client(functions.channels.JoinChannelRequest(group_entity))
                                                joined_count += 1
                                                
                                                # Grubu veritabanına ekle
                                                await self._add_group_to_database(group_entity)
                                                
                                                logger.info(f"Showcu kız profilinden grup keşfedildi ve katıldı: {link}")
                                                
                                                # Gruba katıldıktan sonra biraz bekle
                                                await asyncio.sleep(random.uniform(10, 20))
                                    except Exception as e:
                                        logger.error(f"Gruba katılma hatası ({link}): {str(e)}")
                    
                    # Her kullanıcı arasında biraz bekle
                    await asyncio.sleep(random.uniform(2, 5))
                    
                except Exception as e:
                    logger.error(f"Kullanıcı analizi hatası (ID: {user_id}): {str(e)}")
            
            logger.info(f"Showcu kız profillerinden toplam {len(discovered_links)} grup bağlantısı keşfedildi, {joined_count} gruba katılındı")
            return discovered_links
            
        except Exception as e:
            logger.error(f"Showcu kızlardan grup keşfi hatası: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
    def _extract_telegram_links(self, text):
        """
        Metinden Telegram bağlantılarını çıkarır.
        
        Args:
            text (str): İncelenecek metin
            
        Returns:
            list: Telegram bağlantılarının listesi
        """
        import re
        
        # t.me/ ile başlayan bağlantıları bul
        pattern = r'(t\.me/[a-zA-Z0-9_]+)'
        links = re.findall(pattern, text)
        
        # @ ile başlayan kullanıcı/grup adlarını bul
        username_pattern = r'@([a-zA-Z0-9_]+)'
        usernames = re.findall(username_pattern, text)
        
        # Kullanıcı adlarını t.me formatına dönüştür
        username_links = [f"t.me/{username}" for username in usernames]
        
        # Tüm bağlantıları birleştir ve tekte döndür
        return list(set(links + username_links))
    
    async def _check_group_exists(self, group_id):
        """
        Bir grubun veritabanında kayıtlı olup olmadığını kontrol eder.
        
        Args:
            group_id: Kontrol edilecek grup ID'si
            
        Returns:
            bool: Grup varsa True, yoksa False
        """
        try:
            query = "SELECT group_id FROM groups WHERE group_id = %s"
            result = await self._run_async_db_method(self.db.fetchone, query, (group_id,))
            return bool(result)
        except Exception as e:
            logger.error(f"Grup varlık kontrolü hatası: {str(e)}")
            return False
            
    async def _add_group_to_database(self, group_entity):
        """
        Keşfedilen bir grubu veritabanına ekler.
        
        Args:
            group_entity: Telegram'dan alınan grup varlığı
        """
        try:
            # Grup temel bilgilerini hazırla
            group_id = group_entity.id
            title = group_entity.title
            username = group_entity.username if hasattr(group_entity, 'username') else None
            description = group_entity.about if hasattr(group_entity, 'about') else None
            
            # Grubun üye sayısını al
            try:
                full_chat = await self.client(functions.channels.GetFullChannelRequest(group_entity))
                member_count = full_chat.full_chat.participants_count
            except:
                member_count = 0
                
            # Veritabanına ekle
            current_time = datetime.now()
            
            # Önce grubun mevcut durumunu kontrol et
            check_query = "SELECT is_active FROM groups WHERE group_id = %s"
            existing = await self._run_async_db_method(self.db.fetchone, check_query, (group_id,))
            
            insert_query = """
            INSERT INTO groups (group_id, title, username, description, member_count, 
                               created_at, updated_at, discovery_source, is_active) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (group_id) DO UPDATE 
            SET title = EXCLUDED.title,
                username = EXCLUDED.username,
                description = EXCLUDED.description,
                member_count = EXCLUDED.member_count,
                updated_at = EXCLUDED.updated_at
            """
            
            is_active = True
            # Eğer grup zaten varsa ve pasif ise, durumunu koru
            if existing and not existing[0]:
                logger.debug(f"Grup {group_id} daha önce pasif olarak işaretlenmiş, bu durum korunacak")
                is_active = False
            
            values = (
                group_id, title, username, description, member_count,
                current_time, current_time, 'showcu_profile', is_active
            )
            
            await self._run_async_db_method(self.db.execute, insert_query, values)
            
            # Grup aktif değilse ve yeniden aktiflenmesi isteniyorsa ayrı sorgu ile güncelle
            if not is_active and self.settings.get("reactivate_groups", False):
                update_query = "UPDATE groups SET is_active = TRUE WHERE group_id = %s"
                await self._run_async_db_method(self.db.execute, update_query, (group_id,))
                logger.info(f"Pasif grup yeniden aktifleştirildi: {title} (ID: {group_id})")
            
            logger.debug(f"Grup veritabanına eklendi: {title} (ID: {group_id})")
            
        except Exception as e:
            logger.error(f"Grup veritabanına ekleme hatası: {str(e)}")
            logger.debug(traceback.format_exc())