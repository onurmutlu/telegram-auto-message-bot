#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analytics Service - Grup aktivite ve etkileşim analizlerini yöneten servis
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import func, select, and_, or_, desc, asc, text, update, insert
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from functools import lru_cache
import os
import json

from bot.services.base_service import BaseService
from bot.services.event_service import Event, on_event
from database.models import Group, GroupAnalytics, GroupMember, TelegramUser, MessageTracking
from database.db_connection import get_db_pool, transactional

# Log ayarları
logger = logging.getLogger(__name__)

class AnalyticsService(BaseService):
    """
    Grup analitik servisi - Grupların etkileşimini ve aktivitesini izler ve raporlar
    """
    
    def __init__(self, client=None, config=None, db=None, stop_event=None):
        """
        AnalyticsService constructor
        
        Args:
            client: Telegram istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            stop_event: Durdurma eventi
        """
        super().__init__("analytics", client, config, db, stop_event)
        self.db_pool = get_db_pool()
        self.update_interval = 3600  # Varsayılan olarak saatte bir güncelle (saniye)
        self.refresh_task = None
        self.is_refreshing = False
        
    async def initialize(self) -> bool:
        """
        Servisi başlat ve gerekli kaynakları yükle
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("AnalyticsService başlatılıyor...")
            
            # Konfigürasyondan güncelleme aralığını yükle (varsa)
            if hasattr(self.config, 'get_setting'):
                self.update_interval = self.config.get_setting('analytics.update_interval', 3600)
                self.max_retained_reports = self.config.get_setting('analytics.max_retained_reports', 30)
            elif isinstance(self.config, dict) and 'analytics' in self.config:
                self.update_interval = self.config['analytics'].get('update_interval', 3600)
                self.max_retained_reports = self.config['analytics'].get('max_retained_reports', 30)
            
            self.initialized = True
            logger.info("AnalyticsService başlatıldı")
            return True
        except Exception as e:
            logger.error(f"AnalyticsService başlatılırken hata: {e}")
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
            # Başlangıçta bir refresh işlemi başlat
            logger.info("İlk analitik veriler toplanıyor...")
            await self.refresh_analytics()
            
            # Periyodik yenileme görevini başlat
            self.refresh_task = asyncio.create_task(self._periodic_refresh())
            
            self.is_running = True
            logger.info("AnalyticsService çalışıyor")
            return True
            
        except Exception as e:
            logger.error(f"AnalyticsService başlatılırken hata: {str(e)}", exc_info=True)
            return False
    
    async def stop(self) -> None:
        """
        Servisi durdur
        
        Returns:
            None
        """
        # Periyodik görev çalışıyorsa durdur
        if self.refresh_task and not self.refresh_task.done():
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass
            
        self.is_running = False
        logger.info("AnalyticsService durduruldu")
        
    async def _periodic_refresh(self):
        """
        Periyodik olarak analitiği güncelleme görevi
        """
        try:
            while not self.stop_event.is_set() and self.is_running:
                # İlk çalıştırmada bekletmeden başlattık, şimdi interval kadar bekle
                await asyncio.sleep(self.update_interval)
                
                if self.is_refreshing:
                    logger.info("Önceki refresh işlemi hala devam ediyor, bu yenileme atlanıyor")
                    continue
                    
                # Analitikleri yenile
                try:
                    self.is_refreshing = True
                    await self.refresh_analytics()
                except Exception as e:
                    logger.error(f"Periyodik analitik güncellemesi sırasında hata: {str(e)}", exc_info=True)
                finally:
                    self.is_refreshing = False
                    
        except asyncio.CancelledError:
            logger.info("Periyodik analitik güncelleme görevi iptal edildi")
            raise
        except Exception as e:
            logger.error(f"Periyodik analitik güncelleme görevinde beklenmeyen hata: {str(e)}", exc_info=True)
            
    async def refresh_analytics(self):
        """
        Tüm grup analitiklerini yeniler
        """
        logger.info("Tüm gruplar için analitik veriler yenileniyor...")
        
        try:
            async with self.db_pool.get_async_session() as session:
                # Aktif grupları al
                query = select(Group.group_id).where(Group.is_active == True)
                result = await session.execute(query)
                group_ids = [row[0] for row in result]
                
                logger.info(f"{len(group_ids)} aktif grup için analitik hesaplanacak")
                
                # Her grup için analitik hesapla
                for group_id in group_ids:
                    try:
                        await self.calculate_group_analytics(group_id, session)
                    except Exception as e:
                        logger.error(f"Grup {group_id} için analitik hesaplanırken hata: {str(e)}", exc_info=True)
                
                logger.info("Grup analitikleri başarıyla güncellendi")
                
        except Exception as e:
            logger.error(f"Analitik yenileme sırasında hata: {str(e)}", exc_info=True)
            raise
    
    @transactional
    async def calculate_group_analytics(self, group_id: int, session: AsyncSession) -> Optional[GroupAnalytics]:
        """
        Belirli bir grup için analitikleri hesaplar ve kaydeder
        
        Args:
            group_id: Hesaplama yapılacak grup ID
            session: Veritabanı oturumu
            
        Returns:
            Oluşturulan veya güncellenen GroupAnalytics nesnesi veya None
        """
        logger.debug(f"Grup {group_id} için analitik hesaplanıyor...")
        
        try:
            # Bugünün tarihi
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 1. Bugün için mevcut analitik kaydı var mı?
            query = select(GroupAnalytics).where(
                and_(
                    GroupAnalytics.group_id == group_id,
                    GroupAnalytics.date == today
                )
            )
            result = await session.execute(query)
            analytics = result.scalars().first()
            
            # Yoksa yeni oluştur
            if not analytics:
                analytics = GroupAnalytics(
                    group_id=group_id,
                    date=today,
                    member_count=0,
                    message_count=0,
                    active_users=0,
                    engagement_rate=0,
                    growth_rate=0
                )
                session.add(analytics)
            
            # 2. Toplam üye sayısını hesapla
            query = select(func.count()).where(
                and_(
                    GroupMember.group_id == group_id,
                    GroupMember.is_active == True
                )
            ).select_from(GroupMember)
            result = await session.execute(query)
            member_count = result.scalar() or 0
            
            # 3. Bugünkü mesaj sayısını hesapla
            query = select(func.count()).where(
                and_(
                    MessageTracking.group_id == group_id,
                    MessageTracking.sent_at >= today,
                    MessageTracking.sent_at < today + timedelta(days=1)
                )
            ).select_from(MessageTracking)
            result = await session.execute(query)
            message_count = result.scalar() or 0
            
            # 4. Bugün aktif olan üye sayısını hesapla
            query = select(func.count(func.distinct(MessageTracking.user_id))).where(
                and_(
                    MessageTracking.group_id == group_id,
                    MessageTracking.sent_at >= today,
                    MessageTracking.sent_at < today + timedelta(days=1)
                )
            ).select_from(MessageTracking)
            result = await session.execute(query)
            active_users = result.scalar() or 0
            
            # 5. Etkileşim oranını hesapla (mesaj / üye)
            engagement_rate = 0
            if member_count > 0:
                engagement_rate = round((message_count / member_count) * 100)
            
            # 6. Büyüme oranını hesapla
            # Bir önceki günün üye sayısını bul
            yesterday = today - timedelta(days=1)
            query = select(GroupAnalytics.member_count).where(
                and_(
                    GroupAnalytics.group_id == group_id,
                    GroupAnalytics.date == yesterday
                )
            )
            result = await session.execute(query)
            yesterday_members = result.scalar()
            
            growth_rate = 0
            if yesterday_members and yesterday_members > 0:
                growth_diff = member_count - yesterday_members
                growth_rate = round((growth_diff / yesterday_members) * 100)
            
            # 7. Analitik nesnesini güncelle
            analytics.member_count = member_count
            analytics.message_count = message_count
            analytics.active_users = active_users
            analytics.engagement_rate = engagement_rate
            analytics.growth_rate = growth_rate
            analytics.updated_at = datetime.now()
            
            # 8. Grup nesnesini de güncelle
            query = update(Group).where(Group.group_id == group_id).values(
                member_count=member_count,
                updated_at=datetime.now()
            )
            await session.execute(query)
            
            await session.commit()
            logger.debug(f"Grup {group_id} analitik güncellendi: Üye={member_count}, Mesaj={message_count}, Aktif={active_users}")
            
            return analytics
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Grup {group_id} analitik hesaplama hatası: {str(e)}", exc_info=True)
            raise
    
    async def get_group_analytics(self, group_id: int, days: int = 7) -> List[Dict]:
        """
        Bir grup için belirli gün sayısı kadar analitikleri getirir
        
        Args:
            group_id: Grup ID
            days: Kaç günlük analitik getirileceği
            
        Returns:
            Analitik kayıtları listesi
        """
        try:
            end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = end_date - timedelta(days=days)
            
            async with self.db_pool.get_async_session() as session:
                query = select(GroupAnalytics).where(
                    and_(
                        GroupAnalytics.group_id == group_id,
                        GroupAnalytics.date >= start_date,
                        GroupAnalytics.date <= end_date
                    )
                ).order_by(GroupAnalytics.date.asc())
                
                result = await session.execute(query)
                analytics_records = result.scalars().all()
                
                # Dict listesine dönüştür
                analytics_list = []
                for record in analytics_records:
                    analytics_list.append({
                        'date': record.date.strftime('%Y-%m-%d'),
                        'member_count': record.member_count,
                        'message_count': record.message_count,
                        'active_users': record.active_users,
                        'engagement_rate': record.engagement_rate,
                        'growth_rate': record.growth_rate
                    })
                
                return analytics_list
                
        except Exception as e:
            logger.error(f"Grup {group_id} analitik verilerini getirirken hata: {str(e)}", exc_info=True)
            return []
    
    async def get_top_active_groups(self, limit: int = 10) -> List[Dict]:
        """
        En aktif grupları getirir (mesaj sayısına göre)
        
        Args:
            limit: Kaç grup getirileceği
            
        Returns:
            En aktif gruplar listesi
        """
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            async with self.db_pool.get_async_session() as session:
                query = select(
                    Group.group_id,
                    Group.name,
                    Group.username,
                    GroupAnalytics.message_count,
                    GroupAnalytics.member_count,
                    GroupAnalytics.active_users,
                    GroupAnalytics.engagement_rate
                ).join(
                    GroupAnalytics, Group.group_id == GroupAnalytics.group_id
                ).where(
                    and_(
                        GroupAnalytics.date == today,
                        Group.is_active == True
                    )
                ).order_by(
                    GroupAnalytics.message_count.desc()
                ).limit(limit)
                
                result = await session.execute(query)
                top_groups = result.all()
                
                # Dict listesine dönüştür
                top_groups_list = []
                for group in top_groups:
                    top_groups_list.append({
                        'group_id': group.group_id,
                        'name': group.name,
                        'username': group.username,
                        'message_count': group.message_count,
                        'member_count': group.member_count,
                        'active_users': group.active_users,
                        'engagement_rate': group.engagement_rate
                    })
                
                return top_groups_list
                
        except Exception as e:
            logger.error(f"En aktif grupları getirirken hata: {str(e)}", exc_info=True)
            return []
    
    async def get_top_growing_groups(self, limit: int = 10) -> List[Dict]:
        """
        En hızlı büyüyen grupları getirir (büyüme oranına göre)
        
        Args:
            limit: Kaç grup getirileceği
            
        Returns:
            En hızlı büyüyen gruplar listesi
        """
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            async with self.db_pool.get_async_session() as session:
                query = select(
                    Group.group_id,
                    Group.name,
                    Group.username,
                    GroupAnalytics.member_count,
                    GroupAnalytics.growth_rate
                ).join(
                    GroupAnalytics, Group.group_id == GroupAnalytics.group_id
                ).where(
                    and_(
                        GroupAnalytics.date == today,
                        Group.is_active == True,
                        GroupAnalytics.growth_rate > 0
                    )
                ).order_by(
                    GroupAnalytics.growth_rate.desc()
                ).limit(limit)
                
                result = await session.execute(query)
                growing_groups = result.all()
                
                # Dict listesine dönüştür
                growing_groups_list = []
                for group in growing_groups:
                    growing_groups_list.append({
                        'group_id': group.group_id,
                        'name': group.name,
                        'username': group.username,
                        'member_count': group.member_count,
                        'growth_rate': group.growth_rate
                    })
                
                return growing_groups_list
                
        except Exception as e:
            logger.error(f"En hızlı büyüyen grupları getirirken hata: {str(e)}", exc_info=True)
            return []
    
    async def get_most_engaged_groups(self, limit: int = 10) -> List[Dict]:
        """
        En yüksek etkileşimli grupları getirir (mesaj/üye oranına göre)
        
        Args:
            limit: Kaç grup getirileceği
            
        Returns:
            En yüksek etkileşimli gruplar listesi
        """
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            async with self.db_pool.get_async_session() as session:
                query = select(
                    Group.group_id,
                    Group.name,
                    Group.username,
                    GroupAnalytics.member_count,
                    GroupAnalytics.message_count,
                    GroupAnalytics.active_users,
                    GroupAnalytics.engagement_rate
                ).join(
                    GroupAnalytics, Group.group_id == GroupAnalytics.group_id
                ).where(
                    and_(
                        GroupAnalytics.date == today,
                        Group.is_active == True,
                        GroupAnalytics.member_count > 10  # En az 10 üyesi olan gruplar
                    )
                ).order_by(
                    GroupAnalytics.engagement_rate.desc()
                ).limit(limit)
                
                result = await session.execute(query)
                engaged_groups = result.all()
                
                # Dict listesine dönüştür
                engaged_groups_list = []
                for group in engaged_groups:
                    engaged_groups_list.append({
                        'group_id': group.group_id,
                        'name': group.name,
                        'username': group.username,
                        'member_count': group.member_count,
                        'message_count': group.message_count,
                        'active_users': group.active_users,
                        'engagement_rate': group.engagement_rate
                    })
                
                return engaged_groups_list
                
        except Exception as e:
            logger.error(f"En yüksek etkileşimli grupları getirirken hata: {str(e)}", exc_info=True)
            return []
    
    async def get_inactive_groups(self, days: int = 7, limit: int = 20) -> List[Dict]:
        """
        Belirli gün sayısı kadar inaktif olan grupları getirir
        
        Args:
            days: Kaç gündür inaktif olduğu
            limit: Kaç grup getirileceği
            
        Returns:
            İnaktif gruplar listesi
        """
        try:
            inactive_date = datetime.now() - timedelta(days=days)
            
            async with self.db_pool.get_async_session() as session:
                query = select(
                    Group.group_id,
                    Group.name,
                    Group.username,
                    Group.last_message,
                    Group.member_count
                ).where(
                    and_(
                        Group.is_active == True,
                        or_(
                            Group.last_message < inactive_date,
                            Group.last_message == None
                        )
                    )
                ).order_by(
                    Group.last_message.asc().nulls_first()
                ).limit(limit)
                
                result = await session.execute(query)
                inactive_groups = result.all()
                
                # Dict listesine dönüştür
                inactive_groups_list = []
                for group in inactive_groups:
                    last_message_str = group.last_message.strftime('%Y-%m-%d %H:%M:%S') if group.last_message else "Hiç"
                    inactive_groups_list.append({
                        'group_id': group.group_id,
                        'name': group.name,
                        'username': group.username,
                        'last_message': last_message_str,
                        'member_count': group.member_count,
                        'inactive_days': days
                    })
                
                return inactive_groups_list
                
        except Exception as e:
            logger.error(f"İnaktif grupları getirirken hata: {str(e)}", exc_info=True)
            return []
            
    @on_event("message_received", service_name="analytics")
    async def handle_message_received(self, event: Event):
        """
        Alınan mesaj olaylarını işler ve grup analitiklerini günceller
        
        Args:
            event: Mesaj olayı
        """
        try:
            data = event.data
            if not data or 'group_id' not in data:
                return
                
            group_id = data.get('group_id')
            
            # Grup son mesaj zamanını güncelle
            async with self.db_pool.get_async_session() as session:
                now = datetime.now()
                query = update(Group).where(Group.group_id == group_id).values(
                    last_message=now,
                    last_active=now,
                    updated_at=now
                )
                await session.execute(query)
                await session.commit()
                
            # Eğer analitik değerleri hesaplamak için çok fazla mesaj işlemeyi istemiyorsak
            # burada bir sınır koyabiliriz (örn. her 10 mesajda bir analitik hesapla gibi)
                
        except Exception as e:
            logger.error(f"Mesaj olayı işlenirken hata: {str(e)}", exc_info=True)
            
    @on_event("user_joined_group", service_name="analytics")
    async def handle_user_joined_group(self, event: Event):
        """
        Kullanıcı gruba katılma olaylarını işler ve grup analitiklerini günceller
        
        Args:
            event: Kullanıcı katılma olayı
        """
        try:
            data = event.data
            if not data or 'group_id' not in data:
                return
                
            group_id = data.get('group_id')
            
            # Grup üye sayısını artır
            async with self.db_pool.get_async_session() as session:
                # Mevcut üye sayısını al
                query = select(Group.member_count).where(Group.group_id == group_id)
                result = await session.execute(query)
                current_count = result.scalar() or 0
                
                # Üye sayısını güncelle
                query = update(Group).where(Group.group_id == group_id).values(
                    member_count=current_count + 1,
                    last_active=datetime.now(),
                    updated_at=datetime.now()
                )
                await session.execute(query)
                await session.commit()
                
        except Exception as e:
            logger.error(f"Kullanıcı katılma olayı işlenirken hata: {str(e)}", exc_info=True)
            
    @on_event("user_left_group", service_name="analytics")
    async def handle_user_left_group(self, event: Event):
        """
        Kullanıcı gruptan ayrılma olaylarını işler ve grup analitiklerini günceller
        
        Args:
            event: Kullanıcı ayrılma olayı
        """
        try:
            data = event.data
            if not data or 'group_id' not in data:
                return
                
            group_id = data.get('group_id')
            
            # Grup üye sayısını azalt
            async with self.db_pool.get_async_session() as session:
                # Mevcut üye sayısını al
                query = select(Group.member_count).where(Group.group_id == group_id)
                result = await session.execute(query)
                current_count = result.scalar() or 0
                
                # Üye sayısını güncelle (negatif olmasını önle)
                new_count = max(0, current_count - 1)
                query = update(Group).where(Group.group_id == group_id).values(
                    member_count=new_count,
                    last_active=datetime.now(),
                    updated_at=datetime.now()
                )
                await session.execute(query)
                await session.commit()
                
        except Exception as e:
            logger.error(f"Kullanıcı ayrılma olayı işlenirken hata: {str(e)}", exc_info=True)
            
    async def generate_analytics_report(self, days: int = 7) -> Dict:
        """
        Tüm grup analitikleri için kapsamlı bir rapor oluşturur
        
        Args:
            days: Rapor için geçmiş gün sayısı
            
        Returns:
            Analitik raporu
        """
        try:
            # Rapor verilerini topla
            top_active = await self.get_top_active_groups(10)
            top_growing = await self.get_top_growing_groups(10)
            top_engaged = await self.get_most_engaged_groups(10)
            inactive_groups = await self.get_inactive_groups(days, 20)
            
            # Toplam grup sayısı
            async with self.db_pool.get_async_session() as session:
                query = select(func.count()).where(Group.is_active == True).select_from(Group)
                result = await session.execute(query)
                total_groups = result.scalar() or 0
                
                # Toplam üye sayısı
                query = select(func.sum(Group.member_count)).where(Group.is_active == True).select_from(Group)
                result = await session.execute(query)
                total_members = result.scalar() or 0
                
                # Bugünkü toplam mesaj sayısı
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                query = select(func.count()).where(
                    and_(
                        MessageTracking.sent_at >= today,
                        MessageTracking.sent_at < today + timedelta(days=1)
                    )
                ).select_from(MessageTracking)
                result = await session.execute(query)
                total_messages_today = result.scalar() or 0
                
                # Son hafta içindeki toplam mesaj sayısı
                week_ago = datetime.now() - timedelta(days=7)
                query = select(func.count()).where(
                    MessageTracking.sent_at >= week_ago
                ).select_from(MessageTracking)
                result = await session.execute(query)
                total_messages_week = result.scalar() or 0
            
            # Raporu oluştur
            report = {
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'period_days': days,
                'total_groups': total_groups,
                'total_members': total_members,
                'total_messages_today': total_messages_today,
                'total_messages_week': total_messages_week,
                'top_active_groups': top_active,
                'top_growing_groups': top_growing,
                'top_engaged_groups': top_engaged,
                'inactive_groups': inactive_groups
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Analitik raporu oluşturulurken hata: {str(e)}", exc_info=True)
            return {
                'error': f"Rapor oluşturma hatası: {str(e)}",
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

    async def get_most_interactive_users(self, group_id: int = None, limit: int = 10, days: int = 7) -> List[Dict]:
        """
        En çok etkileşimde bulunan kullanıcıları döndürür
        
        Args:
            group_id: Belirli bir grup için sorgu (None ise tüm gruplar)
            limit: Döndürülecek maksimum kullanıcı sayısı
            days: Son kaç gündeki aktiviteye bakılacak
            
        Returns:
            List[Dict]: En aktif kullanıcıların bilgileri
        """
        try:
            logger.debug(f"En aktif kullanıcılar hesaplanıyor{'(Grup: '+str(group_id)+')' if group_id else ''}")
            start_date = datetime.now() - timedelta(days=days)
            
            async with self.db_pool.get_async_session() as session:
                # SQL sorgusu oluştur
                query = """
                SELECT 
                    tu.user_id, 
                    tu.username, 
                    tu.first_name, 
                    tu.last_name,
                    COUNT(mt.id) as message_count,
                    COUNT(DISTINCT mt.group_id) as active_group_count,
                    MAX(mt.sent_at) as last_activity
                FROM 
                    telegram_users tu
                JOIN 
                    message_tracking mt ON tu.user_id = mt.user_id
                WHERE 
                    mt.sent_at >= :start_date
                """
                
                params = {"start_date": start_date}
                
                # Belirli bir grup için filtreleme
                if group_id:
                    query += " AND mt.group_id = :group_id"
                    params["group_id"] = group_id
                    
                query += """
                GROUP BY 
                    tu.user_id, tu.username, tu.first_name, tu.last_name
                ORDER BY 
                    message_count DESC
                LIMIT :limit
                """
                
                params["limit"] = limit
                
                # Sorguyu çalıştır
                result = await session.execute(text(query), params)
                rows = result.fetchall()
                
                # Sonuçları biçimlendir
                users = []
                for row in rows:
                    # Dict olarak erişim için dict() fonksiyonunu kullan
                    row_dict = dict(row._mapping)
                    
                    users.append({
                        'user_id': row_dict['user_id'],
                        'username': row_dict['username'],
                        'first_name': row_dict['first_name'],
                        'last_name': row_dict['last_name'],
                        'message_count': row_dict['message_count'],
                        'active_group_count': row_dict['active_group_count'],
                        'last_activity': row_dict['last_activity'].isoformat() if row_dict['last_activity'] else None
                    })
                
                return users
                
        except Exception as e:
            logger.error(f"En aktif kullanıcılar hesaplanırken hata: {str(e)}", exc_info=True)
            return []

    async def get_group_activity_trends(self, group_id: int, days: int = 30) -> Dict:
        """
        Grup aktivite trendlerini döndürür
        
        Args:
            group_id: Grup ID
            days: Analiz edilecek gün sayısı
            
        Returns:
            Dict: Trend verisi
        """
        try:
            logger.debug(f"Grup {group_id} için aktivite trendleri hesaplanıyor")
            
            # Bugün ve başlangıç günü
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = today - timedelta(days=days)
            
            async with self.db_pool.get_async_session() as session:
                # Günlük analitik verileri al
                query = select(GroupAnalytics).where(
                    and_(
                        GroupAnalytics.group_id == group_id,
                        GroupAnalytics.date >= start_date,
                        GroupAnalytics.date <= today
                    )
                ).order_by(asc(GroupAnalytics.date))
                
                result = await session.execute(query)
                analytics_records = result.scalars().all()
                
                # Tarihler ve ölçümler için veri yapıları oluştur
                dates = []
                message_counts = []
                member_counts = []
                active_users = []
                engagement_rates = []
                
                # Eksik günler için boşluk bırakmamak adına tüm günleri oluştur
                date_map = {}
                current_date = start_date
                while current_date <= today:
                    date_str = current_date.strftime('%Y-%m-%d')
                    date_map[date_str] = {
                        'message_count': 0,
                        'member_count': 0,
                        'active_users': 0,
                        'engagement_rate': 0
                    }
                    current_date += timedelta(days=1)
                
                # Veritabanından gelen kayıtları doldur
                for record in analytics_records:
                    date_str = record.date.strftime('%Y-%m-%d')
                    if date_str in date_map:
                        date_map[date_str] = {
                            'message_count': record.message_count,
                            'member_count': record.member_count,
                            'active_users': record.active_users,
                            'engagement_rate': record.engagement_rate
                        }
                
                # Sıralı veriyi oluştur
                for date_str, values in sorted(date_map.items()):
                    dates.append(date_str)
                    message_counts.append(values['message_count'])
                    member_counts.append(values['member_count'])
                    active_users.append(values['active_users'])
                    engagement_rates.append(values['engagement_rate'])
                
                # Son 7, 14 ve 30 günlük ortalama aktiviteyi hesapla
                avg_7d = {
                    'message_count': sum(message_counts[-7:]) / min(7, len(message_counts[-7:])),
                    'active_users': sum(active_users[-7:]) / min(7, len(active_users[-7:])),
                    'engagement_rate': sum(engagement_rates[-7:]) / min(7, len(engagement_rates[-7:]))
                }
                
                avg_14d = {
                    'message_count': sum(message_counts[-14:]) / min(14, len(message_counts[-14:])),
                    'active_users': sum(active_users[-14:]) / min(14, len(active_users[-14:])),
                    'engagement_rate': sum(engagement_rates[-14:]) / min(14, len(engagement_rates[-14:]))
                }
                
                avg_30d = {
                    'message_count': sum(message_counts) / len(message_counts) if message_counts else 0,
                    'active_users': sum(active_users) / len(active_users) if active_users else 0,
                    'engagement_rate': sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0
                }
                
                # Büyüme oranını hesapla (başlangıç ve son üye sayıları karşılaştırılarak)
                first_members = member_counts[0] if member_counts else 0
                last_members = member_counts[-1] if member_counts else 0
                growth_rate = ((last_members - first_members) / first_members * 100) if first_members > 0 else 0
                
                # Son ay, hafta ve gün için aktivite değişimini hesapla
                activity_change = {
                    'daily': {
                        'message_change': message_counts[-1] - message_counts[-2] if len(message_counts) >= 2 else 0,
                        'user_change': active_users[-1] - active_users[-2] if len(active_users) >= 2 else 0
                    },
                    'weekly': {
                        'message_change': sum(message_counts[-7:]) - sum(message_counts[-14:-7]) if len(message_counts) >= 14 else 0,
                        'user_change': sum(active_users[-7:]) - sum(active_users[-14:-7]) if len(active_users) >= 14 else 0
                    },
                    'monthly': {
                        'message_change': sum(message_counts[-30:]) - sum(message_counts[-60:-30]) if len(message_counts) >= 60 else 0,
                        'user_change': sum(active_users[-30:]) - sum(active_users[-60:-30]) if len(active_users) >= 60 else 0
                    }
                }
                
                return {
                    'group_id': group_id,
                    'timespan_days': days,
                    'dates': dates,
                    'metrics': {
                        'message_counts': message_counts,
                        'member_counts': member_counts,
                        'active_users': active_users,
                        'engagement_rates': engagement_rates
                    },
                    'averages': {
                        '7d': avg_7d,
                        '14d': avg_14d,
                        '30d': avg_30d
                    },
                    'growth_rate': growth_rate,
                    'activity_change': activity_change,
                    'current': {
                        'message_count': message_counts[-1] if message_counts else 0,
                        'member_count': member_counts[-1] if member_counts else 0,
                        'active_users': active_users[-1] if active_users else 0,
                        'engagement_rate': engagement_rates[-1] if engagement_rates else 0
                    }
                }
                
        except Exception as e:
            logger.error(f"Grup aktivite trendleri hesaplanırken hata: {str(e)}", exc_info=True)
            return {
                'group_id': group_id,
                'error': str(e),
                'timespan_days': days
            } 

    async def generate_weekly_report(self, group_id: int = None) -> Dict:
        """
        Haftalık grup raporunu oluşturur
        
        Args:
            group_id: Belirli bir grup için rapor oluştur (None ise tüm gruplar için özet rapor)
            
        Returns:
            Dict: Rapor verisi
        """
        try:
            logger.info(f"Haftalık rapor oluşturuluyor{' (Grup: '+str(group_id)+')' if group_id else ''}")
            
            # Rapor zaman aralığı
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            # Rapor sonuçları
            report = {
                'generated_at': end_date.isoformat(),
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': 7
                }
            }
            
            async with self.db_pool.get_async_session() as session:
                if group_id:
                    # Tek grup için detaylı rapor
                    # 1. Grup bilgilerini al
                    query = select(Group).where(Group.group_id == group_id)
                    result = await session.execute(query)
                    group = result.scalars().first()
                    
                    if not group:
                        logger.warning(f"Grup bulunamadı: {group_id}")
                        return {'error': 'Grup bulunamadı', 'group_id': group_id}
                    
                    # 2. Grup meta verileri
                    group_info = {
                        'group_id': group.group_id,
                        'name': group.name,
                        'username': group.username,
                        'member_count': group.member_count,
                        'is_public': group.is_public,
                        'created_at': group.created_at.isoformat() if group.created_at else None,
                        'last_active': group.last_active.isoformat() if group.last_active else None
                    }
                    
                    # 3. Aktivite trendlerini al
                    activity_trends = await self.get_group_activity_trends(group_id, days=30)
                    
                    # 4. En aktif üyeleri al
                    active_users = await self.get_most_interactive_users(group_id=group_id, limit=10)
                    
                    # 5. Mesaj tipleri dağılımını hesapla
                    query = """
                    SELECT 
                        content_type, 
                        COUNT(*) as count 
                    FROM 
                        message_tracking 
                    WHERE 
                        group_id = :group_id AND
                        sent_at BETWEEN :start_date AND :end_date
                    GROUP BY 
                        content_type
                    ORDER BY 
                        count DESC
                    """
                    result = await session.execute(
                        text(query), 
                        {'group_id': group_id, 'start_date': start_date, 'end_date': end_date}
                    )
                    message_types = [dict(row._mapping) for row in result.fetchall()]
                    
                    # 6. Saatlik aktivite dağılımı
                    query = """
                    SELECT 
                        EXTRACT(HOUR FROM sent_at) as hour, 
                        COUNT(*) as count 
                    FROM 
                        message_tracking 
                    WHERE 
                        group_id = :group_id AND 
                        sent_at BETWEEN :start_date AND :end_date
                    GROUP BY 
                        hour
                    ORDER BY 
                        hour
                    """
                    result = await session.execute(
                        text(query), 
                        {'group_id': group_id, 'start_date': start_date, 'end_date': end_date}
                    )
                    hourly_activity = [dict(row._mapping) for row in result.fetchall()]
                    
                    # 7. Haftalık üye değişimi
                    query = """
                    SELECT 
                        date_trunc('day', joined_at) as day,
                        COUNT(*) as joined
                    FROM 
                        group_members
                    WHERE 
                        group_id = :group_id AND 
                        joined_at BETWEEN :start_date AND :end_date
                    GROUP BY 
                        day
                    ORDER BY 
                        day
                    """
                    result = await session.execute(
                        text(query), 
                        {'group_id': group_id, 'start_date': start_date, 'end_date': end_date}
                    )
                    member_joins = [dict(row._mapping) for row in result.fetchall()]
                    
                    # Tek grup raporu sonuçları
                    report.update({
                        'group': group_info,
                        'activity_trends': activity_trends,
                        'active_users': active_users,
                        'message_types': message_types,
                        'hourly_activity': hourly_activity,
                        'member_changes': {
                            'joins': member_joins
                        }
                    })
                    
                else:
                    # Tüm gruplar için özet rapor
                    # 1. En aktif grupları al
                    top_active_groups = await self.get_top_active_groups(limit=10)
                    
                    # 2. En hızlı büyüyen grupları al
                    top_growing_groups = await self.get_top_growing_groups(limit=10)
                    
                    # 3. En etkileşimli grupları al
                    most_engaged_groups = await self.get_most_engaged_groups(limit=10)
                    
                    # 4. İnaktif grupları al
                    inactive_groups = await self.get_inactive_groups(days=7, limit=10)
                    
                    # 5. En aktif kullanıcıları al (tüm gruplarda)
                    most_active_users = await self.get_most_interactive_users(limit=20)
                    
                    # 6. Global mesaj tipleri dağılımı
                    query = """
                    SELECT 
                        content_type, 
                        COUNT(*) as count 
                    FROM 
                        message_tracking 
                    WHERE 
                        sent_at BETWEEN :start_date AND :end_date
                    GROUP BY 
                        content_type
                    ORDER BY 
                        count DESC
                    """
                    result = await session.execute(
                        text(query), 
                        {'start_date': start_date, 'end_date': end_date}
                    )
                    message_types = [dict(row._mapping) for row in result.fetchall()]
                    
                    # 7. Haftanın en aktif günleri
                    query = """
                    SELECT 
                        EXTRACT(DOW FROM sent_at) as day_of_week, 
                        COUNT(*) as count 
                    FROM 
                        message_tracking 
                    WHERE 
                        sent_at BETWEEN :start_date AND :end_date
                    GROUP BY 
                        day_of_week
                    ORDER BY 
                        day_of_week
                    """
                    result = await session.execute(
                        text(query), 
                        {'start_date': start_date, 'end_date': end_date}
                    )
                    day_of_week_activity = [dict(row._mapping) for row in result.fetchall()]
                    
                    # 8. Toplam ve ortalama istatistikler
                    query = """
                    SELECT 
                        COUNT(DISTINCT group_id) as active_group_count,
                        COUNT(DISTINCT user_id) as active_user_count,
                        COUNT(*) as total_messages
                    FROM 
                        message_tracking 
                    WHERE 
                        sent_at BETWEEN :start_date AND :end_date
                    """
                    result = await session.execute(
                        text(query), 
                        {'start_date': start_date, 'end_date': end_date}
                    )
                    stats = dict(result.fetchone()._mapping)
                    
                    # Özet rapor sonuçları
                    report.update({
                        'overview': {
                            'active_group_count': stats['active_group_count'],
                            'active_user_count': stats['active_user_count'],
                            'total_messages': stats['total_messages'],
                            'avg_messages_per_day': stats['total_messages'] / 7,
                            'avg_messages_per_group': stats['total_messages'] / stats['active_group_count'] if stats['active_group_count'] > 0 else 0
                        },
                        'top_active_groups': top_active_groups,
                        'top_growing_groups': top_growing_groups,
                        'most_engaged_groups': most_engaged_groups,
                        'inactive_groups': inactive_groups,
                        'most_active_users': most_active_users,
                        'message_types': message_types,
                        'day_of_week_activity': day_of_week_activity
                    })
            
            return report
            
        except Exception as e:
            logger.error(f"Haftalık rapor oluşturulurken hata: {str(e)}", exc_info=True)
            return {
                'error': str(e),
                'group_id': group_id,
                'generated_at': datetime.now().isoformat()
            } 

    async def export_analytics(self, group_id: int, format: str = "json", days: int = 30) -> str:
        """
        Grup analitik verilerini dışa aktarır
        
        Args:
            group_id: Grup ID
            format: Dışa aktarma formatı ("json" veya "csv")
            days: Kaç günlük veri dışa aktarılacak
            
        Returns:
            str: Dışa aktarılan veri dosyasının yolu
        """
        try:
            logger.info(f"Grup {group_id} için analitik verileri dışa aktarılıyor (format: {format})")
            
            # Analitik verilerini al
            analytics_data = await self.get_group_analytics(group_id, days)
            trends_data = await self.get_group_activity_trends(group_id, days)
            
            if not analytics_data:
                logger.warning(f"Grup {group_id} için analitik verisi bulunamadı")
                return None
            
            # Grup bilgilerini al
            async with self.db_pool.get_async_session() as session:
                query = select(Group).where(Group.group_id == group_id)
                result = await session.execute(query)
                group = result.scalars().first()
                
                if not group:
                    logger.warning(f"Grup bulunamadı: {group_id}")
                    return None
                
                group_name = group.name or str(group_id)
                safe_name = "".join([c if c.isalnum() else "_" for c in group_name])[:20]
            
            # Timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Dosya adı ve çıktı dizini
            output_dir = "data/analytics_export"
            os.makedirs(output_dir, exist_ok=True)
            
            if format.lower() == "json":
                # JSON formatında dışa aktar
                export_data = {
                    "group_id": group_id,
                    "group_name": group_name,
                    "export_date": datetime.now().isoformat(),
                    "timespan_days": days,
                    "analytics": analytics_data,
                    "trends": trends_data
                }
                
                filename = f"{output_dir}/{safe_name}_{group_id}_analytics_{timestamp}.json"
                
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Analitik veriler JSON olarak dışa aktarıldı: {filename}")
                return filename
            
            elif format.lower() == "csv":
                # CSV formatında dışa aktar
                filename = f"{output_dir}/{safe_name}_{group_id}_analytics_{timestamp}.csv"
                
                import csv
                
                with open(filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    
                    # Başlık satırı
                    writer.writerow([
                        "Tarih", "Mesaj Sayısı", "Üye Sayısı", "Aktif Kullanıcı Sayısı", 
                        "Etkileşim Oranı (%)", "Büyüme Oranı (%)"
                    ])
                    
                    # Veri satırları
                    for item in analytics_data:
                        writer.writerow([
                            item["date"],
                            item["message_count"],
                            item["member_count"],
                            item["active_users"],
                            item["engagement_rate"],
                            item["growth_rate"]
                        ])
                
                logger.info(f"Analitik veriler CSV olarak dışa aktarıldı: {filename}")
                return filename
            
            else:
                logger.error(f"Desteklenmeyen dışa aktarma formatı: {format}")
                return None
            
        except Exception as e:
            logger.error(f"Analitik verileri dışa aktarılırken hata: {str(e)}", exc_info=True)
            return None 