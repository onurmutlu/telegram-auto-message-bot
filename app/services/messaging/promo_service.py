"""
# ============================================================================ #
# Dosya: promo_service.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/messaging/promo_service.py
# İşlev: Tanıtım kampanyalarını yöneten servis sınıfı
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

import logging
import random
import json
import os
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, UserIsBlockedError, ChatAdminRequiredError

from app.services.base_service import BaseService
from app.db.session import get_session
from app.core.config import settings
from app.models.user import User
from app.services.analytics.user_service import UserService

logger = logging.getLogger(__name__)

class PromoService(BaseService):
    """
    Tanıtım kampanyaları ve promosyonları yöneten servis.
    - Grup mesajları
    - DM kampanyaları
    - Planlı tanıtımlar
    """
    
    service_name = "promo_service"
    default_interval = 3600 * 6  # 6 saat
    
    def __init__(self, client: TelegramClient, db: AsyncSession = None):
        """
        PromoService sınıfını başlatır.
        
        Args:
            client: TelegramClient
            db: AsyncSession
        """
        super().__init__(name="promo_service")
        self.client = client
        self.db = db
        self.user_service = None
        self.initialized = False
        self.running = False
        
        # Şablonlar ve kampanyalar
        self.promo_templates = {}
        self.active_campaigns = []
        
        # Mesaj limitleri
        self.dm_daily_limit = 100
        self.group_daily_limit = 25
        self.dm_sent_count = 0
        self.group_sent_count = 0
        self.last_reset = datetime.now()
        
        # İnterval ayarları
        self.dm_interval = 180  # saniye (3 dakika)
        self.group_interval = 1800  # saniye (30 dakika)
        self.last_dm_time = datetime.now() - timedelta(hours=1)
        self.last_group_time = datetime.now() - timedelta(hours=1)
        
        # Hedef gruplar
        self.target_groups = []
        
        # Kayıt durumu
        logger.info(f"{self.service_name} servisi başlatıldı")
        
    async def initialize(self):
        """Servisi başlat ve şablonları yükle."""
        self.db = self.db or next(get_session())
        self.user_service = UserService(db=self.db)
        await self._load_templates()
        await self._load_campaigns()
        await self._load_target_groups()
        
        logger.info(f"PromoService initialized with {len(self.active_campaigns)} active campaigns")
        self.initialized = True
        return True
    
    async def _load_templates(self):
        """Tanıtım mesaj şablonlarını yükle."""
        try:
            # Önceki işlemlerden kalan hatayı temizle
            try:
                self.db.rollback()
            except:
                pass
                
            # Önce veritabanı şemasını kontrol et
            schema_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """
            schema_result = self.db.execute(text(schema_query))
            tables = [row[0] for row in schema_result.fetchall()]
            
            if 'message_templates' not in tables:
                logger.warning("Message templates table not found, using default templates")
                # Varsayılan şablonlar ekle
                self.promo_templates = {
                    "promo_general": [(1, "promo_general", "Merhaba! Telegram botumuzdan haberdar mısınız?", True)],
                    "promo_service": [(2, "promo_service", "Yeni hizmetlerimizi denediniz mi?", True)]
                }
            else:
                # DM Tanıtım şablonları
                query = """
                    SELECT id, type, content, is_active FROM message_templates 
                    WHERE is_active = true AND type LIKE 'promo_%'
                """
                result = self.db.execute(text(query))
                templates = result.fetchall()
                
                # Şablonları kategorilere ayır
                self.promo_templates = {}
                for template in templates:
                    template_type = template[1] if isinstance(template, tuple) else template.type
                    
                    if template_type not in self.promo_templates:
                        self.promo_templates[template_type] = []
                        
                    self.promo_templates[template_type].append(template)
            
            logger.info(f"Loaded {sum(len(v) for v in self.promo_templates.values())} promo templates")
        except Exception as e:
            logger.error(f"Error loading promo templates: {str(e)}")
            # Hata olduğunda işlemi geri al
            try:
                self.db.rollback()
            except:
                pass
            # Varsayılan şablonlar ekle
            self.promo_templates = {
                "promo_general": [(1, "promo_general", "Merhaba! Telegram botumuzdan haberdar mısınız?", True)],
                "promo_service": [(2, "promo_service", "Yeni hizmetlerimizi denediniz mi?", True)]
            }
    
    async def _load_campaigns(self):
        """Aktif kampanyaları yükle."""
        try:
            # Önceki işlemlerden kalan hatayı temizle
            try:
                self.db.rollback()
            except:
                pass
                
            # Önce veritabanı şemasını kontrol et
            schema_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """
            schema_result = self.db.execute(text(schema_query))
            tables = [row[0] for row in schema_result.fetchall()]
            
            if 'campaigns' not in tables:
                logger.warning("Campaigns table not found, no active campaigns will be loaded")
                self.active_campaigns = []
            else:
                query = """
                    SELECT id, name, type, target_type, template_type, start_at, end_at, status, rules
                    FROM campaigns
                    WHERE status = 'active' AND end_at > NOW()
                    ORDER BY id DESC
                """
                result = self.db.execute(text(query))
                self.active_campaigns = result.fetchall()
                logger.info(f"Loaded {len(self.active_campaigns)} active campaigns")
        except Exception as e:
            logger.error(f"Error loading campaigns: {str(e)}")
            # Hata olduğunda işlemi geri al
            try:
                self.db.rollback()
            except:
                pass
            self.active_campaigns = []
    
    async def _load_target_groups(self):
        """Tanıtım hedefi olarak kullanılacak grupları yükle."""
        try:
            # Önceki işlemlerden kalan hatayı temizle
            try:
                self.db.rollback()
            except:
                pass
                
            # Önce veritabanı şemasını kontrol et
            schema_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """
            schema_result = self.db.execute(text(schema_query))
            tables = [row[0] for row in schema_result.fetchall()]
            
            if 'groups' not in tables:
                logger.warning("Groups table not found, no target groups will be loaded")
                self.target_groups = []
                return
            
            # 'groups' tablosunun sütunlarını kontrol et
            column_query = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'groups'
            """
            column_result = self.db.execute(text(column_query))
            columns = [row[0] for row in column_result.fetchall()]
            
            # chat_id sütununu kontrol et ve alternatifi kullan
            chat_id_column = None
            for possible_column in ["chat_id", "group_id", "telegram_id", "tg_id"]:
                if possible_column in columns:
                    chat_id_column = possible_column
                    break
                    
            if not chat_id_column:
                logger.warning("No chat ID column found in groups table")
                self.target_groups = []
                return
            
            # Kategori ve keywords sütunlarını kontrol et
            category_column = "category" if "category" in columns else "type"
            if category_column not in columns:
                category_column = "NULL as category"
                
            keywords_column = "keywords" if "keywords" in columns else "tags"
            if keywords_column not in columns:
                keywords_column = "NULL as keywords"
            
            # is_active kontrolü
            is_active_check = "is_active = true" if "is_active" in columns else "1=1"
            
            # Tabloyu sorgula
            query = f"""
                SELECT id, {chat_id_column} as chat_id, 
                       CASE WHEN 'is_admin' = ANY(ARRAY[{', '.join([f"'{col}'" for col in columns])}]) THEN is_admin ELSE true END as is_admin,
                       CASE WHEN 'member_count' = ANY(ARRAY[{', '.join([f"'{col}'" for col in columns])}]) THEN member_count ELSE 0 END as member_count,
                       {category_column}, {keywords_column}
                FROM groups
                WHERE {is_active_check}
                ORDER BY id DESC
            """
            
            result = self.db.execute(text(query))
            self.target_groups = result.fetchall()
            
            logger.info(f"Loaded {len(self.target_groups)} target groups for promotions")
        except Exception as e:
            logger.error(f"Error loading target groups: {str(e)}")
            # Hata olduğunda işlemi geri al
            try:
                self.db.rollback()
            except:
                pass
            self.target_groups = []
    
    async def run_campaign(self, campaign_id: int = None):
        """
        Belirli bir kampanyayı veya tüm aktif kampanyaları çalıştır.
        
        Args:
            campaign_id: Çalıştırılacak kampanya ID'si (None ise tüm aktifler)
        """
        try:
            # Günlük limit kontrolü
            now = datetime.now()
            if (now - self.last_reset).days >= 1:
                self.dm_sent_count = 0
                self.group_sent_count = 0
                self.last_reset = now
                logger.info("Daily promo counters reset")
            
            # Kampanyaları yükle veya filtrele
            campaigns = []
            if campaign_id:
                query = """
                    SELECT id, name, type, target_type, template_type, start_at, end_at, status, rules
                    FROM campaigns
                    WHERE id = :campaign_id AND status = 'active' AND end_at > NOW()
                """
                result = self.db.execute(text(query), {"campaign_id": campaign_id})
                campaigns = result.fetchall()
            else:
                campaigns = self.active_campaigns
            
            if not campaigns:
                logger.warning(f"No active campaigns found{' for ID ' + str(campaign_id) if campaign_id else ''}")
                return
            
            # Her kampanyayı çalıştır
            for campaign in campaigns:
                campaign_id = campaign[0] if isinstance(campaign, tuple) else campaign.id
                campaign_name = campaign[1] if isinstance(campaign, tuple) else campaign.name
                campaign_type = campaign[2] if isinstance(campaign, tuple) else campaign.type
                target_type = campaign[3] if isinstance(campaign, tuple) else campaign.target_type
                template_type = campaign[4] if isinstance(campaign, tuple) else campaign.template_type
                
                logger.info(f"Running campaign: {campaign_name} (ID: {campaign_id}, Type: {campaign_type})")
                
                # Kampanya tipine göre işlem yap
                if campaign_type == "dm" and target_type == "user":
                    await self._run_dm_campaign(campaign)
                elif campaign_type == "group" and target_type == "group":
                    await self._run_group_campaign(campaign)
                else:
                    logger.warning(f"Unsupported campaign type: {campaign_type}/{target_type}")
        
        except Exception as e:
            logger.error(f"Error running campaign: {str(e)}", exc_info=True)
    
    async def _run_dm_campaign(self, campaign):
        """
        DM kampanyasını çalıştır.
        
        Args:
            campaign: Kampanya verisi
        """
        try:
            # Limit kontrolü
            if self.dm_sent_count >= self.dm_daily_limit:
                logger.info(f"Daily DM limit reached ({self.dm_daily_limit}), skipping campaign")
                return
            
            # Zaman aralığı kontrolü
            if (datetime.now() - self.last_dm_time).total_seconds() < self.dm_interval:
                logger.info("DM interval not elapsed, skipping")
                return
            
            # Kampanya bilgilerini çıkar
            campaign_id = campaign[0] if isinstance(campaign, tuple) else campaign.id
            template_type = campaign[4] if isinstance(campaign, tuple) else campaign.template_type
            rules_str = campaign[8] if isinstance(campaign, tuple) else campaign.rules
            
            # Kuralları parse et
            rules = json.loads(rules_str) if rules_str else {}
            limit = rules.get("daily_limit", 20)
            
            # Şablon kontrolü
            if template_type not in self.promo_templates or not self.promo_templates[template_type]:
                logger.warning(f"No templates found for campaign {campaign_id} (type: {template_type})")
                return
            
            # Hedef kullanıcıları çek
            target_users = await self._get_campaign_targets(campaign)
            if not target_users:
                logger.info(f"No target users found for campaign {campaign_id}")
                return
            
            # Limit uygula
            target_users = target_users[:min(limit, len(target_users))]
            logger.info(f"Found {len(target_users)} target users for campaign {campaign_id}")
            
            # Her kullanıcıya mesaj gönder
            sent_count = 0
            for user_id in target_users:
                if self.dm_sent_count >= self.dm_daily_limit:
                    break
                
                # Mesaj gönder
                success = await self._send_promo_dm(user_id, template_type, campaign_id)
                if success:
                    sent_count += 1
                    self.dm_sent_count += 1
                
                # Flood koruması için bekle
                await asyncio.sleep(random.randint(30, 60))
            
            # Kampanya durumunu güncelle
            await self._update_campaign_status(campaign_id, sent_count)
            self.last_dm_time = datetime.now()
            
            logger.info(f"DM campaign {campaign_id} completed: {sent_count} messages sent")
        
        except Exception as e:
            logger.error(f"Error running DM campaign: {str(e)}", exc_info=True)
    
    async def _run_group_campaign(self, campaign):
        """
        Grup kampanyasını çalıştır.
        
        Args:
            campaign: Kampanya verisi
        """
        try:
            # Limit kontrolü
            if self.group_sent_count >= self.group_daily_limit:
                logger.info(f"Daily group post limit reached ({self.group_daily_limit}), skipping campaign")
                return
            
            # Zaman aralığı kontrolü
            if (datetime.now() - self.last_group_time).total_seconds() < self.group_interval:
                logger.info("Group post interval not elapsed, skipping")
                return
            
            # Kampanya bilgilerini çıkar
            campaign_id = campaign[0] if isinstance(campaign, tuple) else campaign.id
            template_type = campaign[4] if isinstance(campaign, tuple) else campaign.template_type
            rules_str = campaign[8] if isinstance(campaign, tuple) else campaign.rules
            
            # Kuralları parse et
            rules = json.loads(rules_str) if rules_str else {}
            limit = rules.get("daily_limit", 5)
            
            # Şablon kontrolü
            if template_type not in self.promo_templates or not self.promo_templates[template_type]:
                logger.warning(f"No templates found for campaign {campaign_id} (type: {template_type})")
                return
            
            # Hedef grupları çek
            target_groups = await self._get_group_targets(campaign)
            if not target_groups:
                logger.info(f"No target groups found for campaign {campaign_id}")
                return
            
            # Limit uygula
            target_groups = target_groups[:min(limit, len(target_groups))]
            logger.info(f"Found {len(target_groups)} target groups for campaign {campaign_id}")
            
            # Her gruba mesaj gönder
            sent_count = 0
            for group_entity in target_groups:
                if self.group_sent_count >= self.group_daily_limit:
                    break
                
                # Mesaj gönder
                group_id = group_entity[2] if isinstance(group_entity, tuple) else group_entity.chat_id
                success = await self._send_promo_group_message(group_id, template_type, campaign_id)
                if success:
                    sent_count += 1
                    self.group_sent_count += 1
                
                # Flood koruması için bekle
                await asyncio.sleep(random.randint(300, 600))  # 5-10 dakika arası
            
            # Kampanya durumunu güncelle
            await self._update_campaign_status(campaign_id, sent_count)
            self.last_group_time = datetime.now()
            
            logger.info(f"Group campaign {campaign_id} completed: {sent_count} messages sent")
        
        except Exception as e:
            logger.error(f"Error running group campaign: {str(e)}", exc_info=True)
    
    async def _get_campaign_targets(self, campaign):
        """
        Kampanya için hedef kullanıcıları getir.
        
        Args:
            campaign: Kampanya verisi
            
        Returns:
            List[int]: Kullanıcı ID'leri listesi
        """
        try:
            campaign_id = campaign[0] if isinstance(campaign, tuple) else campaign.id
            rules_str = campaign[8] if isinstance(campaign, tuple) else campaign.rules
            
            # Kuralları parse et
            rules = json.loads(rules_str) if rules_str else {}
            
            # Temel sorgu
            query = """
                SELECT user_id FROM users 
                WHERE is_active = true 
                  AND is_blocked = false 
                  AND (last_promo_at IS NULL OR last_promo_at < NOW() - INTERVAL '3 days')
            """
            
            # Filtreler ekle
            params = {}
            
            # Üye sayısı filtresi
            if "min_activity" in rules:
                query += " AND message_count >= :min_activity"
                params["min_activity"] = rules["min_activity"]
            
            # Son aktivite filtresi
            if "max_inactive_days" in rules:
                query += " AND last_activity_at > NOW() - INTERVAL ':max_inactive_days days'"
                params["max_inactive_days"] = rules["max_inactive_days"]
            
            # Sıralama ve limit
            query += " ORDER BY last_activity_at DESC LIMIT 100"
            
            # Sorguyu çalıştır
            result = self.db.execute(text(query), params)
            user_ids = [row[0] for row in result.fetchall()]
            
            return user_ids
            
        except Exception as e:
            logger.error(f"Error getting campaign targets: {str(e)}", exc_info=True)
            return []
    
    async def _get_group_targets(self, campaign):
        """
        Kampanya için hedef grupları getir.
        
        Args:
            campaign: Kampanya verisi
            
        Returns:
            List[Any]: Grup verileri listesi
        """
        try:
            campaign_id = campaign[0] if isinstance(campaign, tuple) else campaign.id
            rules_str = campaign[8] if isinstance(campaign, tuple) else campaign.rules
            
            # Kuralları parse et
            rules = json.loads(rules_str) if rules_str else {}
            
            # Filtreleme kriterleri
            min_members = rules.get("min_members", 100)
            keywords = rules.get("keywords", [])
            categories = rules.get("categories", [])
            
            # Hedef grupları filtrele
            filtered_groups = []
            for group in self.target_groups:
                member_count = group[4] if isinstance(group, tuple) else group.member_count
                group_category = group[5] if isinstance(group, tuple) else group.category
                group_keywords = group[6] if isinstance(group, tuple) else group.keywords
                
                # Üye sayısı kontrolü
                if member_count < min_members:
                    continue
                
                # Kategori kontrolü (eğer belirtilmişse)
                if categories and group_category not in categories:
                    continue
                
                # Anahtar kelime kontrolü (eğer belirtilmişse)
                if keywords and group_keywords:
                    group_kw_list = group_keywords.split(',') if isinstance(group_keywords, str) else group_keywords
                    if not any(kw in group_kw_list for kw in keywords):
                        continue
                
                filtered_groups.append(group)
            
            # Grupları son gönderim zamanına göre filtrele
            query = """
                SELECT group_id FROM group_activity 
                WHERE action_type = 'promo_sent' 
                GROUP BY group_id 
                HAVING MAX(created_at) > NOW() - INTERVAL '7 days'
            """
            result = self.db.execute(text(query))
            recent_groups = set(row[0] for row in result.fetchall())
            
            # Son 7 günde gönderim yapılanları hariç tut
            final_groups = [
                g for g in filtered_groups 
                if g[2] not in recent_groups  # chat_id kontrol ediliyor
            ]
            
            return final_groups
            
        except Exception as e:
            logger.error(f"Error getting group targets: {str(e)}", exc_info=True)
            return []
    
    async def _send_promo_dm(self, user_id: int, template_type: str, campaign_id: int) -> bool:
        """
        Belirli bir kullanıcıya tanıtım mesajı gönder.
        
        Args:
            user_id: Hedef kullanıcı ID'si
            template_type: Şablon tipi
            campaign_id: Kampanya ID'si
            
        Returns:
            bool: Başarılı olup olmadığı
        """
        try:
            # Önceki işlemlerden kalan hatayı temizle
            try:
                self.db.rollback()
            except:
                pass
                
            # Şablon kontrolü
            if template_type not in self.promo_templates or not self.promo_templates[template_type]:
                logger.warning(f"No templates found for type: {template_type}")
                return False
            
            # Şablon seç
            template = random.choice(self.promo_templates[template_type])
            message_text = template[2] if isinstance(template, tuple) else template.content
            
            # Kullanıcı bilgilerini getir
            user = await self.user_service.get_user(user_id)
            if not user:
                logger.warning(f"User {user_id} not found")
                return False
            
            # Mesajı kişiselleştir
            first_name = user.get("first_name", "")
            username = user.get("username", "")
            message_text = message_text.replace("{first_name}", first_name).replace("{username}", username)
            
            # Mesajı gönder
            await self.client.send_message(user_id, message_text, parse_mode='md')
            
            # Aktivite ve kullanıcı tablosunun varlığını kontrol et
            try:
                # Önce veritabanı şemasını kontrol et
                schema_query = """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name IN ('user_activity', 'users')
                """
                schema_result = self.db.execute(text(schema_query))
                tables = [row[0] for row in schema_result.fetchall()]
                
                if 'user_activity' in tables:
                    # Aktivite kaydı oluştur
                    self.db.execute(
                        text("""
                            INSERT INTO user_activity (user_id, action_type, action_detail, created_at)
                            VALUES (:user_id, 'promo_received', :detail, NOW())
                        """),
                        {"user_id": user_id, "detail": f"campaign_id:{campaign_id}"}
                    )
                
                if 'users' in tables:
                    # Kullanıcı son tanıtım tarihini güncelle
                    # Önce sütun varlığını kontrol et
                    column_query = """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'users' AND column_name = 'last_promo_at'
                    """
                    column_result = self.db.execute(text(column_query))
                    has_last_promo = column_result.fetchone() is not None
                    
                    if has_last_promo:
                        self.db.execute(
                            text("UPDATE users SET last_promo_at = NOW() WHERE user_id = :user_id"),
                            {"user_id": user_id}
                        )
                
                self.db.commit()
            except Exception as e:
                logger.warning(f"Could not update user activity or status: {str(e)}")
                try:
                    self.db.rollback()
                except:
                    pass
            
            logger.info(f"Promo DM sent to user {user_id} for campaign {campaign_id}")
            return True
            
        except UserIsBlockedError:
            logger.info(f"User {user_id} has blocked the bot")
            # Kullanıcı durumunu güncelle
            try:
                self.db.execute(
                    text("UPDATE users SET is_blocked = true WHERE user_id = :user_id"),
                    {"user_id": user_id}
                )
                self.db.commit()
            except:
                try:
                    self.db.rollback() 
                except:
                    pass
            return False
            
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError: Need to wait {wait_time} seconds")
            return False
            
        except Exception as e:
            logger.error(f"Error sending promo DM to {user_id}: {str(e)}", exc_info=True)
            return False
    
    async def _send_promo_group_message(self, group_id: int, template_type: str, campaign_id: int) -> bool:
        """
        Belirli bir gruba tanıtım mesajı gönder.
        
        Args:
            group_id: Hedef grup ID'si
            template_type: Şablon tipi
            campaign_id: Kampanya ID'si
            
        Returns:
            bool: Başarılı olup olmadığı
        """
        try:
            # Önceki işlemlerden kalan hatayı temizle
            try:
                self.db.rollback()
            except:
                pass
                
            # Şablon kontrolü
            if template_type not in self.promo_templates or not self.promo_templates[template_type]:
                logger.warning(f"No templates found for type: {template_type}")
                return False
            
            # Şablon seç
            template = random.choice(self.promo_templates[template_type])
            message_text = template[2] if isinstance(template, tuple) else template.content
            
            # Mesajı gönder
            await self.client.send_message(group_id, message_text, parse_mode='md')
            
            # Aktivite tablosunun varlığını kontrol et
            try:
                # Önce veritabanı şemasını kontrol et
                schema_query = """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'group_activity'
                """
                schema_result = self.db.execute(text(schema_query))
                table_exists = schema_result.fetchone() is not None
                
                if table_exists:
                    # Aktivite kaydı oluştur
                    self.db.execute(
                        text("""
                            INSERT INTO group_activity (group_id, action_type, action_detail, created_at)
                            VALUES (:group_id, 'promo_sent', :detail, NOW())
                        """),
                        {"group_id": group_id, "detail": f"campaign_id:{campaign_id}"}
                    )
                    self.db.commit()
            except Exception as e:
                logger.warning(f"Could not log group activity: {str(e)}")
                try:
                    self.db.rollback()
                except:
                    pass
            
            logger.info(f"Promo message sent to group {group_id} for campaign {campaign_id}")
            return True
            
        except ChatAdminRequiredError:
            logger.warning(f"Admin permission required to post in group {group_id}")
            # Grup soğutma işlemi uygula
            await self._cool_down_group(group_id, 1440)  # 24 saat soğut
            return False
            
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError: Need to wait {wait_time} seconds")
            return False
            
        except Exception as e:
            logger.error(f"Error sending promo message to group {group_id}: {str(e)}", exc_info=True)
            return False
    
    async def _update_campaign_status(self, campaign_id: int, sent_count: int):
        """
        Kampanya istatistiklerini güncelle.
        
        Args:
            campaign_id: Kampanya ID'si
            sent_count: Gönderilen mesaj sayısı
        """
        try:
            # Önceki işlemlerden kalan hatayı temizle
            try:
                self.db.rollback()
            except:
                pass
                
            # Önce veritabanı şemasını kontrol et
            schema_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'campaign_stats'
            """
            schema_result = self.db.execute(text(schema_query))
            table_exists = schema_result.fetchone() is not None
            
            if not table_exists:
                logger.warning("Campaign stats table doesn't exist, skipping update")
                return
                
            # Kampanya istatistiklerini güncelle
            update_query = text("""
                UPDATE campaign_stats 
                SET sent_count = sent_count + :sent_count, 
                    last_run_at = NOW()
                WHERE campaign_id = :campaign_id
            """)
            
            result = self.db.execute(update_query, {"campaign_id": campaign_id, "sent_count": sent_count})
            
            # Kayıt yoksa oluştur
            if result.rowcount == 0:
                self.db.execute(
                    text("""
                        INSERT INTO campaign_stats (campaign_id, sent_count, last_run_at)
                        VALUES (:campaign_id, :sent_count, NOW())
                    """),
                    {"campaign_id": campaign_id, "sent_count": sent_count}
                )
            
            self.db.commit()
            logger.info(f"Updated campaign status for ID {campaign_id}: sent {sent_count} messages")
            
        except Exception as e:
            logger.error(f"Error updating campaign status: {str(e)}", exc_info=True)
            try:
                self.db.rollback()
            except:
                pass
    
    async def _cool_down_group(self, group_id: int, minutes: int = 180) -> None:
        """Grubu belirtilen süre kadar soğut."""
        try:
            # cooling_groups dictionary'si mevcut değilse oluştur
            if not hasattr(self, 'cooling_groups'):
                self.cooling_groups = {}
                
            cool_until = datetime.now() + timedelta(minutes=minutes)
            self.cooling_groups[group_id] = cool_until
            
            # Veritabanı tablosunun varlığını kontrol et
            schema_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'group_cooldowns'
            """
            schema_result = self.db.execute(text(schema_query))
            table_exists = schema_result.fetchone() is not None
            
            if table_exists:
                # Veritabanına kaydedelim
                query = """
                    INSERT INTO group_cooldowns (group_id, until, reason, created_at)
                    VALUES (:group_id, :until, 'Promo error threshold exceeded', NOW())
                    ON CONFLICT (group_id) DO UPDATE
                    SET until = :until, updated_at = NOW()
                """
                self.db.execute(text(query), {"group_id": group_id, "until": cool_until})
                self.db.commit()
            
            logger.info(f"Cooling down group {group_id} for promo until {cool_until}")
        except Exception as e:
            logger.error(f"Error cooling down group {group_id}: {str(e)}")
            # Hata olsa bile en azından memory'de soğutmayı ayarla
            if hasattr(self, 'cooling_groups'):
                self.cooling_groups[group_id] = datetime.now() + timedelta(minutes=minutes)
    
    async def start_promo_loop(self):
        """Kampanya yönetim döngüsü."""
        logger.info("Starting promotional campaign loop")
        self.running = True
        
        while self.running:
            try:
                # Kampanyaları yeniden yükle
                await self._load_campaigns()
                
                # Tüm aktif kampanyaları çalıştır
                if self.active_campaigns:
                    logger.info(f"Running {len(self.active_campaigns)} active campaigns")
                    await self.run_campaign()
                else:
                    logger.info("No active campaigns found")
                
                # Sonraki çalıştırma öncesi bekle
                await asyncio.sleep(3600)  # 1 saat
                
            except Exception as e:
                logger.error(f"Error in campaign loop: {str(e)}", exc_info=True)
                await asyncio.sleep(1800)  # Hata durumunda 30 dakika bekle
    
    async def cleanup(self):
        """Servis kapatılırken temizlik."""
        logger.info("PromoService cleanup completed")
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servis durumunu döndürür.
        
        Returns:
            Dict[str, Any]: Durum bilgileri
        """
        return {
            "name": self.service_name,
            "initialized": self.initialized,
            "running": self.running,
            "templates": {k: len(v) for k, v in self.promo_templates.items()},
            "campaigns": len(self.active_campaigns),
            "target_groups": len(self.target_groups),
            "stats": {
                "dm_sent_today": self.dm_sent_count,
                "group_sent_today": self.group_sent_count,
                "dm_limit": self.dm_daily_limit,
                "group_limit": self.group_daily_limit,
                "last_reset": self.last_reset.isoformat()
            }
        }

    async def _start(self) -> bool:
        """BaseService için başlatma metodu"""
        return await self.initialize()
        
    async def _stop(self) -> bool:
        """BaseService için durdurma metodu"""
        try:
            self.running = False
            await self.cleanup()
            return True
        except Exception as e:
            logger.error(f"Error stopping service: {str(e)}", exc_info=True)
            return False

    async def _update(self) -> bool:
        """Periyodik güncelleme metodu"""
        # Şablonları ve kampanyaları yeniden yükle
        await self._load_templates()
        await self._load_campaigns()
        await self._load_target_groups()
        return True
