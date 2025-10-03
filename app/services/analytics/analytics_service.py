"""
Telegram Bot Analitik Servisi

Kullanıcı ve grup istatistiklerini toplama ve analiz etme.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set, Optional, Tuple, Union

from app.services.base_service import BaseService
from app.core.logger import get_logger

logger = get_logger(__name__)

class AnalyticsService(BaseService):
    """
    Kullanıcı ve grup istatistiklerini toplama ve analiz servisi.
    
    Bu servis:
    1. Kullanıcı aktivitelerini takip eder
    2. Grup istatistiklerini toplar
    3. Mesaj analizleri yapar
    4. Kullanım trendlerini hesaplar
    5. Periyodik raporlar oluşturur
    
    Attributes:
        user_stats: Kullanıcı istatistikleri
        group_stats: Grup istatistikleri
        message_stats: Mesaj istatistikleri
    """
    
    service_name = "analytics_service"
    default_interval = 1800  # 30 dakika
    
    def __init__(self, name='analytics_service', db=None, config=None, client=None, stop_event=None, *args, **kwargs):
        """
        AnalyticsService sınıfının başlatıcısı.
        
        Args:
            name: Servis adı
            db: Veritabanı bağlantısı
            config: Konfigürasyon nesnesi
            client: Telegram client
            stop_event: Durdurma eventi
            **kwargs: Temel servis parametreleri
        """
        super().__init__(name=name)
        
        # Servis bağımlılıkları
        self.db = db
        self.config = config
        self.client = client
        self.stop_event = stop_event
        
        # İstatistikler
        self.user_stats = {}
        self.group_stats = {}
        self.message_stats = {}
        
        # Zaman dilimleri
        self.stats_periods = {
            'daily': {},
            'weekly': {},
            'monthly': {}
        }
        
        # Son güncelleme zamanları
        self.last_update = {
            'user_stats': datetime.now(),
            'group_stats': datetime.now(),
            'message_stats': datetime.now()
        }
        
        # Genel istatistikler
        self.total_stats = {
            'total_users': 0,
            'active_users': 0,
            'total_groups': 0,
            'active_groups': 0,
            'total_messages': 0,
            'total_commands': 0
        }
        
        # Diğer servisler
        self.services = kwargs.get('services', {})
    
    async def _start(self) -> bool:
        """
        Servisi başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("Analitik servisi başlatılıyor")
            
            # İstatistikleri yükle
            await self._load_statistics()
            
            logger.info("Analitik servisi başlatıldı")
            return True
            
        except Exception as e:
            logger.exception(f"Analitik servisi başlatma hatası: {str(e)}")
            return False
    
    async def _stop(self) -> bool:
        """
        Servisi durdurur.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("Analitik servisi durduruluyor")
            
            # İstatistikleri kaydet
            await self._save_statistics()
            
            logger.info("Analitik servisi durduruldu")
            return True
            
        except Exception as e:
            logger.exception(f"Analitik servisi durdurma hatası: {str(e)}")
            return False
    
    async def _update(self) -> None:
        """Periyodik istatistik güncelleme."""
        try:
            # Kullanıcı istatistiklerini güncelle
            await self._update_user_stats()
            
            # Grup istatistiklerini güncelle
            await self._update_group_stats()
            
            # Mesaj istatistiklerini güncelle
            await self._update_message_stats()
            
            # İstatistikleri kaydet
            await self._save_statistics()
            
        except Exception as e:
            logger.exception(f"Analitik güncelleme hatası: {str(e)}")
    
    async def _load_statistics(self):
        """İstatistikleri veritabanından yükler."""
        try:
            # Veritabanından istatistikleri yükle
            if hasattr(self.db, 'get_analytics'):
                stats = await self._run_async_db_method(self.db.get_analytics)
                
                if stats:
                    self.user_stats = stats.get('user_stats', {})
                    self.group_stats = stats.get('group_stats', {})
                    self.message_stats = stats.get('message_stats', {})
                    self.stats_periods = stats.get('stats_periods', self.stats_periods)
                    self.total_stats = stats.get('total_stats', self.total_stats)
                    
                    logger.info("İstatistikler yüklendi")
                else:
                    logger.info("Veritabanında istatistik bulunamadı, yeni oluşturuluyor")
                    
        except Exception as e:
            logger.error(f"İstatistikler yüklenirken hata: {str(e)}")
    
    async def _save_statistics(self):
        """İstatistikleri veritabanına kaydeder."""
        try:
            # Veritabanına istatistikleri kaydet
            if hasattr(self.db, 'save_analytics'):
                stats = {
                    'user_stats': self.user_stats,
                    'group_stats': self.group_stats,
                    'message_stats': self.message_stats,
                    'stats_periods': self.stats_periods,
                    'total_stats': self.total_stats,
                    'last_update': datetime.now().isoformat()
                }
                
                await self._run_async_db_method(self.db.save_analytics, stats)
                logger.info("İstatistikler kaydedildi")
                
        except Exception as e:
            logger.error(f"İstatistikler kaydedilirken hata: {str(e)}")
    
    async def _update_user_stats(self):
        """Kullanıcı istatistiklerini günceller."""
        try:
            # Kullanıcı servisi mevcutsa
            if 'user_service' in self.services:
                # Tüm aktif kullanıcıları al
                active_users = await self.services['user_service'].get_all_active_users()
                
                # Aktif kullanıcı sayısını güncelle
                self.total_stats['active_users'] = len(active_users)
                
                # Toplam kullanıcı sayısını güncelle
                total_users = await self.services['user_service'].get_total_user_count()
                self.total_stats['total_users'] = total_users
                
                # Son güncelleme zamanını güncelle
                self.last_update['user_stats'] = datetime.now()
                
                logger.debug(f"Kullanıcı istatistikleri güncellendi: {self.total_stats['active_users']} aktif, {self.total_stats['total_users']} toplam")
                
        except Exception as e:
            logger.error(f"Kullanıcı istatistikleri güncellenirken hata: {str(e)}")
    
    async def _update_group_stats(self):
        """Grup istatistiklerini günceller."""
        try:
            # Grup servisi mevcutsa
            if 'group_service' in self.services:
                # Tüm grupları al
                all_groups = await self.services['group_service'].get_all_groups()
                
                # Toplam grup sayısını güncelle
                self.total_stats['total_groups'] = len(all_groups)
                
                # Aktif grupları say
                active_groups = [g for g in all_groups if g.get('is_active', False)]
                self.total_stats['active_groups'] = len(active_groups)
                
                # Son güncelleme zamanını güncelle
                self.last_update['group_stats'] = datetime.now()
                
                logger.debug(f"Grup istatistikleri güncellendi: {self.total_stats['active_groups']} aktif, {self.total_stats['total_groups']} toplam")
                
        except Exception as e:
            logger.error(f"Grup istatistikleri güncellenirken hata: {str(e)}")
    
    async def _update_message_stats(self):
        """Mesaj istatistiklerini günceller."""
        try:
            # Mesaj servisi mevcutsa
            if 'message_service' in self.services:
                # Toplam mesaj sayısını al
                total_messages = await self.services['message_service'].get_total_message_count()
                self.total_stats['total_messages'] = total_messages
                
                # Komut sayısını al
                total_commands = await self.services['message_service'].get_total_command_count()
                self.total_stats['total_commands'] = total_commands
                
                # Son güncelleme zamanını güncelle
                self.last_update['message_stats'] = datetime.now()
                
                logger.debug(f"Mesaj istatistikleri güncellendi: {self.total_stats['total_messages']} mesaj, {self.total_stats['total_commands']} komut")
                
        except Exception as e:
            logger.error(f"Mesaj istatistikleri güncellenirken hata: {str(e)}")
    
    async def track_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Bir olayı takip eder.
        
        Args:
            event_type: Olay tipi
            event_data: Olay verisi
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Olayları kategorilerine göre işle
            if event_type == 'user_activity':
                return await self._track_user_activity(event_data)
            elif event_type == 'group_activity':
                return await self._track_group_activity(event_data)
            elif event_type == 'message':
                return await self._track_message(event_data)
            elif event_type == 'command':
                return await self._track_command(event_data)
            else:
                logger.warning(f"Bilinmeyen olay tipi: {event_type}")
                return False
                
        except Exception as e:
            logger.exception(f"Olay takibi hatası: {str(e)}")
            return False
    
    async def _track_user_activity(self, event_data: Dict[str, Any]) -> bool:
        """Kullanıcı aktivitesini takip eder."""
        try:
            user_id = event_data.get('user_id')
            if not user_id:
                return False
                
            activity_type = event_data.get('activity_type', 'unknown')
            
            # Kullanıcı istatistiklerini güncelle
            if str(user_id) not in self.user_stats:
                self.user_stats[str(user_id)] = {
                    'activities': {},
                    'first_seen': datetime.now().isoformat(),
                    'last_seen': datetime.now().isoformat()
                }
                
            # Aktivite sayısını artır
            if activity_type not in self.user_stats[str(user_id)]['activities']:
                self.user_stats[str(user_id)]['activities'][activity_type] = 0
                
            self.user_stats[str(user_id)]['activities'][activity_type] += 1
            self.user_stats[str(user_id)]['last_seen'] = datetime.now().isoformat()
            
            return True
            
        except Exception as e:
            logger.exception(f"Kullanıcı aktivitesi takibi hatası: {str(e)}")
            return False
    
    async def _track_group_activity(self, event_data: Dict[str, Any]) -> bool:
        """Grup aktivitesini takip eder."""
        try:
            group_id = event_data.get('group_id')
            if not group_id:
                return False
                
            activity_type = event_data.get('activity_type', 'unknown')
            
            # Grup istatistiklerini güncelle
            if str(group_id) not in self.group_stats:
                self.group_stats[str(group_id)] = {
                    'activities': {},
                    'first_seen': datetime.now().isoformat(),
                    'last_seen': datetime.now().isoformat(),
                    'message_count': 0,
                    'user_count': 0
                }
                
            # Aktivite sayısını artır
            if activity_type not in self.group_stats[str(group_id)]['activities']:
                self.group_stats[str(group_id)]['activities'][activity_type] = 0
                
            self.group_stats[str(group_id)]['activities'][activity_type] += 1
            self.group_stats[str(group_id)]['last_seen'] = datetime.now().isoformat()
            
            # Mesaj sayısını artır
            if activity_type == 'message':
                self.group_stats[str(group_id)]['message_count'] += 1
                
            # Kullanıcı sayısını güncelle
            if activity_type == 'user_join':
                self.group_stats[str(group_id)]['user_count'] += 1
                
            if activity_type == 'user_leave':
                self.group_stats[str(group_id)]['user_count'] = max(0, self.group_stats[str(group_id)]['user_count'] - 1)
                
            return True
            
        except Exception as e:
            logger.exception(f"Grup aktivitesi takibi hatası: {str(e)}")
            return False
    
    async def _track_message(self, event_data: Dict[str, Any]) -> bool:
        """Mesaj istatistiklerini takip eder."""
        try:
            message_type = event_data.get('message_type', 'text')
            
            # Mesaj istatistiklerini güncelle
            if message_type not in self.message_stats:
                self.message_stats[message_type] = 0
                
            self.message_stats[message_type] += 1
            self.total_stats['total_messages'] += 1
            
            return True
            
        except Exception as e:
            logger.exception(f"Mesaj takibi hatası: {str(e)}")
            return False
    
    async def _track_command(self, event_data: Dict[str, Any]) -> bool:
        """Komut istatistiklerini takip eder."""
        try:
            command = event_data.get('command', 'unknown')
            
            # Komut istatistiklerini güncelle
            if 'commands' not in self.message_stats:
                self.message_stats['commands'] = {}
                
            if command not in self.message_stats['commands']:
                self.message_stats['commands'][command] = 0
                
            self.message_stats['commands'][command] += 1
            self.total_stats['total_commands'] += 1
            
            return True
            
        except Exception as e:
            logger.exception(f"Komut takibi hatası: {str(e)}")
            return False
    
    async def get_user_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Kullanıcı istatistiklerini getirir.
        
        Args:
            user_id: Kullanıcı ID (None ise tüm kullanıcılar)
            
        Returns:
            Dict[str, Any]: Kullanıcı istatistikleri
        """
        if user_id:
            return self.user_stats.get(str(user_id), {})
        return self.user_stats
    
    async def get_group_stats(self, group_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Grup istatistiklerini getirir.
        
        Args:
            group_id: Grup ID (None ise tüm gruplar)
            
        Returns:
            Dict[str, Any]: Grup istatistikleri
        """
        if group_id:
            return self.group_stats.get(str(group_id), {})
        return self.group_stats
    
    async def get_message_stats(self) -> Dict[str, Any]:
        """
        Mesaj istatistiklerini getirir.
        
        Returns:
            Dict[str, Any]: Mesaj istatistikleri
        """
        return self.message_stats
    
    async def get_summary_stats(self) -> Dict[str, Any]:
        """
        Özet istatistikleri getirir.
        
        Returns:
            Dict[str, Any]: Özet istatistikler
        """
        return self.total_stats
    
    async def generate_report(self, report_type: str = 'daily') -> Dict[str, Any]:
        """
        İstatistik raporu oluşturur.
        
        Args:
            report_type: Rapor tipi (daily, weekly, monthly)
            
        Returns:
            Dict[str, Any]: Rapor
        """
        try:
            now = datetime.now()
            
            # Rapor tarihi
            report_date = now.strftime('%Y-%m-%d')
            
            # Tüm istatistikleri topla
            report = {
                'generated_at': now.isoformat(),
                'report_type': report_type,
                'report_date': report_date,
                'user_stats': {
                    'total': self.total_stats['total_users'],
                    'active': self.total_stats['active_users']
                },
                'group_stats': {
                    'total': self.total_stats['total_groups'],
                    'active': self.total_stats['active_groups']
                },
                'message_stats': {
                    'total': self.total_stats['total_messages'],
                    'commands': self.total_stats['total_commands'],
                    'by_type': self.message_stats
                }
            }
            
            # Raporu kaydet
            self.stats_periods[report_type][report_date] = report
            
            return report
            
        except Exception as e:
            logger.exception(f"Rapor oluşturma hatası: {str(e)}")
            return {}
    
    async def get_report(self, report_type: str = 'daily', report_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Belirli bir raporu getirir.
        
        Args:
            report_type: Rapor tipi (daily, weekly, monthly)
            report_date: Rapor tarihi (None ise en son rapor)
            
        Returns:
            Optional[Dict[str, Any]]: Rapor
        """
        try:
            if report_type not in self.stats_periods:
                return None
                
            if report_date:
                return self.stats_periods[report_type].get(report_date)
                
            # En son raporu getir
            if not self.stats_periods[report_type]:
                return None
                
            latest_date = max(self.stats_periods[report_type].keys())
            return self.stats_periods[report_type][latest_date]
            
        except Exception as e:
            logger.exception(f"Rapor getirme hatası: {str(e)}")
            return None
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servis durum bilgilerini döndürür.
        
        Returns:
            Dict[str, Any]: Durum bilgileri
        """
        return {
            'service': 'analytics',
            'total_users': self.total_stats['total_users'],
            'active_users': self.total_stats['active_users'],
            'total_groups': self.total_stats['total_groups'],
            'active_groups': self.total_stats['active_groups'],
            'total_messages': self.total_stats['total_messages'],
            'total_commands': self.total_stats['total_commands'],
            'last_update': {
                'user_stats': self.last_update['user_stats'].isoformat(),
                'group_stats': self.last_update['group_stats'].isoformat(),
                'message_stats': self.last_update['message_stats'].isoformat()
            }
        }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servis istatistiklerini döndürür.
        
        Returns:
            Dict[str, Any]: İstatistik bilgileri
        """
        return self.total_stats
    
    async def _run_async_db_method(self, method, *args, **kwargs):
        """
        Asenkron veritabanı metodunu çalıştırır.
        
        Args:
            method: Çalıştırılacak metod
            *args: Argümanlar
            **kwargs: Anahtar kelime argümanları
            
        Returns:
            Any: Metod sonucu
        """
        try:
            if asyncio.iscoroutinefunction(method):
                return await method(*args, **kwargs)
            else:
                # Senkron metodu threadpool'da çalıştır
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: method(*args, **kwargs)
                )
        except Exception as e:
            logger.error(f"Veritabanı metodu çalıştırma hatası: {str(e)}")
            return None 