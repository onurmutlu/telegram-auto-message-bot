"""
# ============================================================================ #
# Dosya: message_analytics_service.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/analytics/message_analytics_service.py
# İşlev: Mesaj etkinliği ve DM dönüşüm takibi için analitik servis.
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from sqlmodel import Session, select, and_, or_, func, col
from sqlalchemy import text

from app.services.base_service import BaseService
from app.db.session import get_session
from app.models.messaging import (
    MessageEffectiveness, DMConversion,
    MessageEffectivenessCreate, DMConversionCreate
)
from app.core.logger import get_logger

logger = get_logger(__name__)

class MessageAnalyticsService(BaseService):
    """
    Mesaj etkinliği ve DM dönüşüm takibi için analitik servisi.
    
    Bu servis:
    1. Gönderilen mesajların etkinliğini takip eder
    2. Mesajların aldığı tepkileri ve görüntülenmeleri ölçer
    3. DM dönüşümlerini takip eder
    4. Mesaj kategorilerine göre performans raporları oluşturur
    5. En etkili mesaj türlerini analiz eder
    """
    
    service_name = "message_analytics_service"
    default_interval = 600  # 10 dakika
    
    def __init__(self, name='message_analytics_service', db=None, config=None, client=None, stop_event=None, *args, **kwargs):
        """
        MessageAnalyticsService sınıfının başlatıcısı.
        
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
        
        self.running = False
        self.initialized = False
        
        # Mesaj kategorisi etkinlik metrikleri
        self.category_metrics = {}
        
        # DM dönüşüm metrikleri
        self.conversion_metrics = {
            "total": 0,
            "successful": 0,
            "by_type": {},
            "by_source": {}
        }
        
        # Son rapor oluşturma zamanı
        self.last_report_time = datetime.now() - timedelta(days=1)
        
        # Diğer servisler
        self.services = kwargs.get('services', {})
        
        logger.info(f"{self.service_name} oluşturuldu")
    
    async def _start(self) -> bool:
        """
        Servisi başlatır.
        
        Returns:
            bool: Başarılı olursa True
        """
        try:
            logger.info(f"{self.service_name} başlatılıyor...")
            
            # İlk metrikleri yükle
            await self._load_metrics()
            
            self.initialized = True
            self.running = True
            
            logger.info(f"{self.service_name} başlatıldı")
            return True
        except Exception as e:
            logger.error(f"{self.service_name} başlatma hatası: {str(e)}", exc_info=True)
            return False
    
    async def _stop(self) -> bool:
        """
        Servisi durdurur.
        
        Returns:
            bool: Başarılı olursa True
        """
        try:
            logger.info(f"{self.service_name} durduruluyor...")
            self.running = False
            self.initialized = False
            logger.info(f"{self.service_name} durduruldu")
            return True
        except Exception as e:
            logger.error(f"{self.service_name} durdurma hatası: {str(e)}", exc_info=True)
            return False
    
    async def _update(self) -> None:
        """
        Periyodik güncelleme fonksiyonu.
        """
        try:
            if not self.initialized:
                logger.warning(f"{self.service_name} başlatılmadı, güncelleme atlanıyor")
                return
                
            logger.debug(f"{self.service_name} güncelleniyor...")
            
            # Metrikleri güncelle
            await self._update_metrics()
            
            # Günlük rapor oluştur (son rapordan 24 saat geçtiyse)
            now = datetime.now()
            if (now - self.last_report_time).total_seconds() >= 24 * 60 * 60:
                await self._generate_daily_report()
                self.last_report_time = now
                
            logger.debug(f"{self.service_name} güncelleme tamamlandı")
        except Exception as e:
            logger.error(f"{self.service_name} güncelleme hatası: {str(e)}", exc_info=True)
    
    async def _load_metrics(self) -> None:
        """Mevcut metrikleri veritabanından yükler."""
        try:
            session = next(get_session())
            
            # Mesaj kategorisi metriklerini yükle
            query = text("""
                SELECT category, 
                       COUNT(*) as count,
                       AVG(views) as avg_views,
                       AVG(reactions) as avg_reactions,
                       AVG(replies) as avg_replies,
                       AVG(forwards) as avg_forwards
                FROM message_effectiveness
                GROUP BY category
            """)
            
            result = session.execute(query)
            
            for row in result:
                category = row[0]
                self.category_metrics[category] = {
                    "count": row[1],
                    "avg_views": row[2] or 0,
                    "avg_reactions": row[3] or 0,
                    "avg_replies": row[4] or 0,
                    "avg_forwards": row[5] or 0
                }
            
            # DM dönüşüm metriklerini yükle
            conv_query = text("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN is_successful THEN 1 ELSE 0 END) as successful,
                       conversion_type,
                       COUNT(DISTINCT user_id) as unique_users
                FROM dm_conversions
                GROUP BY conversion_type
            """)
            
            conv_result = session.execute(conv_query)
            
            total_conversions = 0
            successful_conversions = 0
            
            for row in conv_result:
                conv_type = row[2]
                conv_count = row[0]
                successful = row[1]
                
                total_conversions += conv_count
                successful_conversions += successful
                
                self.conversion_metrics["by_type"][conv_type] = {
                    "count": conv_count,
                    "successful": successful,
                    "unique_users": row[3]
                }
            
            self.conversion_metrics["total"] = total_conversions
            self.conversion_metrics["successful"] = successful_conversions
            
            # Kaynak mesaj kategorilerine göre dönüşüm metrikleri
            source_query = text("""
                SELECT m.category, 
                       COUNT(d.id) as conv_count,
                       SUM(CASE WHEN d.is_successful THEN 1 ELSE 0 END) as successful
                FROM dm_conversions d
                JOIN message_effectiveness m ON d.source_message_id = m.id
                GROUP BY m.category
            """)
            
            source_result = session.execute(source_query)
            
            for row in source_result:
                category = row[0]
                self.conversion_metrics["by_source"][category] = {
                    "count": row[1],
                    "successful": row[2],
                    "conversion_rate": row[2] / row[1] if row[1] > 0 else 0
                }
                
            logger.info(f"Metrikler yüklendi: {len(self.category_metrics)} kategori, {self.conversion_metrics['total']} dönüşüm")
            
        except Exception as e:
            logger.error(f"Metrik yükleme hatası: {str(e)}", exc_info=True)
    
    async def _update_metrics(self) -> None:
        """Mevcut metrikleri günceller."""
        try:
            # Metrikler güncellenmeden önce yeniden yükle
            await self._load_metrics()
            
        except Exception as e:
            logger.error(f"Metrik güncelleme hatası: {str(e)}", exc_info=True)
    
    async def _generate_daily_report(self) -> Dict[str, Any]:
        """
        Günlük rapor oluşturur.
        
        Returns:
            Dict[str, Any]: Oluşturulan rapor
        """
        try:
            session = next(get_session())
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Günlük mesaj istatistikleri
            daily_msg_query = text("""
                SELECT category, COUNT(*) as count,
                       AVG(views) as avg_views,
                       AVG(reactions) as avg_reactions,
                       AVG(replies) as avg_replies,
                       AVG(forwards) as avg_forwards
                FROM message_effectiveness
                WHERE sent_at BETWEEN :start AND :end
                GROUP BY category
            """)
            
            daily_msg_result = session.execute(
                daily_msg_query, 
                {"start": yesterday_start, "end": yesterday_end}
            )
            
            daily_msg_stats = {}
            for row in daily_msg_result:
                daily_msg_stats[row[0]] = {
                    "count": row[1],
                    "avg_views": row[2] or 0,
                    "avg_reactions": row[3] or 0,
                    "avg_replies": row[4] or 0,
                    "avg_forwards": row[5] or 0
                }
            
            # Günlük dönüşüm istatistikleri
            daily_conv_query = text("""
                SELECT conversion_type, COUNT(*) as count,
                       SUM(CASE WHEN is_successful THEN 1 ELSE 0 END) as successful,
                       AVG(message_count) as avg_messages,
                       AVG(session_duration) as avg_duration
                FROM dm_conversions
                WHERE converted_at BETWEEN :start AND :end
                GROUP BY conversion_type
            """)
            
            daily_conv_result = session.execute(
                daily_conv_query,
                {"start": yesterday_start, "end": yesterday_end}
            )
            
            daily_conv_stats = {}
            for row in daily_conv_result:
                daily_conv_stats[row[0]] = {
                    "count": row[1],
                    "successful": row[2],
                    "avg_messages": row[3] or 0,
                    "avg_duration": row[4] or 0
                }
            
            # Günlük en etkili mesajlar
            top_msgs_query = text("""
                SELECT id, category, content, views, reactions, replies, forwards
                FROM message_effectiveness
                WHERE sent_at BETWEEN :start AND :end
                ORDER BY (views + reactions * 2 + replies * 3 + forwards * 5) DESC
                LIMIT 5
            """)
            
            top_msgs_result = session.execute(
                top_msgs_query,
                {"start": yesterday_start, "end": yesterday_end}
            )
            
            top_messages = []
            for row in top_msgs_result:
                top_messages.append({
                    "id": row[0],
                    "category": row[1],
                    "content": row[2],
                    "views": row[3],
                    "reactions": row[4],
                    "replies": row[5],
                    "forwards": row[6]
                })
            
            # Raporu oluştur
            report = {
                "date": yesterday.strftime("%Y-%m-%d"),
                "generated_at": datetime.now().isoformat(),
                "message_stats": daily_msg_stats,
                "conversion_stats": daily_conv_stats,
                "top_messages": top_messages,
                "summary": {
                    "total_messages": sum(s["count"] for s in daily_msg_stats.values()),
                    "total_conversions": sum(s["count"] for s in daily_conv_stats.values()),
                    "successful_conversions": sum(s["successful"] for s in daily_conv_stats.values()),
                    "conversion_rate": 0.0  # Aşağıda hesaplanacak
                }
            }
            
            # Dönüşüm oranını hesapla
            total_messages = report["summary"]["total_messages"]
            total_conversions = report["summary"]["total_conversions"]
            if total_messages > 0:
                report["summary"]["conversion_rate"] = total_conversions / total_messages
            
            # Raporu kaydet
            report_json = json.dumps(report, ensure_ascii=False)
            
            save_query = text("""
                INSERT INTO analytics_reports (report_date, report_type, content)
                VALUES (:date, 'message_daily', :content)
                ON CONFLICT (report_date, report_type) DO UPDATE
                SET content = :content, updated_at = NOW()
            """)
            
            session.execute(
                save_query, 
                {"date": yesterday.strftime("%Y-%m-%d"), "content": report_json}
            )
            session.commit()
            
            logger.info(f"Günlük mesaj analitik raporu oluşturuldu: {yesterday.strftime('%Y-%m-%d')}")
            return report
            
        except Exception as e:
            logger.error(f"Günlük rapor oluşturma hatası: {str(e)}", exc_info=True)
            return {}
    
    async def track_message(self, message_data: MessageEffectivenessCreate) -> Optional[MessageEffectiveness]:
        """
        Yeni bir mesajı takip etmeye başlar.
        
        Args:
            message_data: Mesaj verisi
            
        Returns:
            Optional[MessageEffectiveness]: Oluşturulan mesaj takip nesnesi
        """
        try:
            session = next(get_session())
            
            # Yeni mesaj oluştur
            message = MessageEffectiveness(
                message_id=message_data.message_id,
                group_id=message_data.group_id,
                content=message_data.content,
                category=message_data.category,
                sent_at=datetime.now()
            )
            
            session.add(message)
            session.commit()
            session.refresh(message)
            
            logger.debug(f"Mesaj takibe alındı: ID={message.id}, Kategori={message.category}")
            return message
        
        except Exception as e:
            logger.error(f"Mesaj takip hatası: {str(e)}", exc_info=True)
            return None
    
    async def update_message_metrics(self, message_id: int, metrics: Dict[str, int]) -> bool:
        """
        Mesaj metriklerini günceller.
        
        Args:
            message_id: Mesaj ID
            metrics: Güncellenecek metrikler
            
        Returns:
            bool: Başarılı olursa True
        """
        try:
            session = next(get_session())
            
            # Mesajı bul
            message = session.get(MessageEffectiveness, message_id)
            if not message:
                logger.warning(f"Güncellenecek mesaj bulunamadı: ID={message_id}")
                return False
                
            # Metrikleri güncelle
            for metric, value in metrics.items():
                if hasattr(message, metric):
                    setattr(message, metric, value)
            
            # Kaydet
            session.add(message)
            session.commit()
            
            logger.debug(f"Mesaj metrikleri güncellendi: ID={message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Mesaj metrikleri güncelleme hatası: {str(e)}", exc_info=True)
            return False
    
    async def track_dm_conversion(self, conversion_data: DMConversionCreate) -> Optional[DMConversion]:
        """
        Yeni bir DM dönüşümünü takip etmeye başlar.
        
        Args:
            conversion_data: Dönüşüm verisi
            
        Returns:
            Optional[DMConversion]: Oluşturulan dönüşüm takip nesnesi
        """
        try:
            session = next(get_session())
            
            # Yeni dönüşüm oluştur
            conversion = DMConversion(
                user_id=conversion_data.user_id,
                source_message_id=conversion_data.source_message_id,
                group_id=conversion_data.group_id,
                conversion_type=conversion_data.conversion_type,
                converted_at=datetime.now()
            )
            
            session.add(conversion)
            session.commit()
            session.refresh(conversion)
            
            logger.debug(f"DM dönüşümü takibe alındı: ID={conversion.id}, Kullanıcı={conversion.user_id}")
            return conversion
            
        except Exception as e:
            logger.error(f"DM dönüşüm takip hatası: {str(e)}", exc_info=True)
            return None
    
    async def update_conversion_metrics(self, conversion_id: int, metrics: Dict[str, Any]) -> bool:
        """
        Dönüşüm metriklerini günceller.
        
        Args:
            conversion_id: Dönüşüm ID
            metrics: Güncellenecek metrikler
            
        Returns:
            bool: Başarılı olursa True
        """
        try:
            session = next(get_session())
            
            # Dönüşümü bul
            conversion = session.get(DMConversion, conversion_id)
            if not conversion:
                logger.warning(f"Güncellenecek dönüşüm bulunamadı: ID={conversion_id}")
                return False
                
            # Metrikleri güncelle
            for metric, value in metrics.items():
                if hasattr(conversion, metric):
                    setattr(conversion, metric, value)
            
            # Kaydet
            session.add(conversion)
            session.commit()
            
            logger.debug(f"Dönüşüm metrikleri güncellendi: ID={conversion_id}")
            return True
            
        except Exception as e:
            logger.error(f"Dönüşüm metrikleri güncelleme hatası: {str(e)}", exc_info=True)
            return False
    
    async def get_top_performing_messages(self, days: int = 7, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        En iyi performans gösteren mesajları getirir.
        
        Args:
            days: Kaç günlük mesajları getireceği
            category: Mesaj kategorisi (None ise tüm kategoriler)
            
        Returns:
            List[Dict[str, Any]]: Mesaj listesi
        """
        try:
            session = next(get_session())
            start_date = datetime.now() - timedelta(days=days)
            
            query_text = """
                SELECT id, message_id, group_id, category, content, sent_at,
                       views, reactions, replies, forwards
                FROM message_effectiveness
                WHERE sent_at >= :start_date
            """
            
            params = {"start_date": start_date}
            
            if category:
                query_text += " AND category = :category"
                params["category"] = category
                
            query_text += """
                ORDER BY (views + reactions * 2 + replies * 3 + forwards * 5) DESC
                LIMIT 20
            """
            
            query = text(query_text)
            result = session.execute(query, params)
            
            messages = []
            for row in result:
                messages.append({
                    "id": row[0],
                    "message_id": row[1],
                    "group_id": row[2],
                    "category": row[3],
                    "content": row[4],
                    "sent_at": row[5].isoformat(),
                    "views": row[6],
                    "reactions": row[7],
                    "replies": row[8],
                    "forwards": row[9],
                    "total_score": row[6] + row[7] * 2 + row[8] * 3 + row[9] * 5
                })
                
            return messages
            
        except Exception as e:
            logger.error(f"En iyi mesajları getirme hatası: {str(e)}", exc_info=True)
            return []
    
    async def get_category_performance(self) -> Dict[str, Any]:
        """
        Kategori bazında performans raporunu getirir.
        
        Returns:
            Dict[str, Any]: Kategori performans raporu
        """
        return self.category_metrics
    
    async def get_conversion_metrics(self) -> Dict[str, Any]:
        """
        DM dönüşüm metriklerini getirir.
        
        Returns:
            Dict[str, Any]: Dönüşüm metrikleri
        """
        return self.conversion_metrics
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servis durumunu getirir.
        
        Returns:
            Dict[str, Any]: Servis durumu
        """
        return {
            "name": self.service_name,
            "running": self.running,
            "initialized": self.initialized,
            "categories": len(self.category_metrics),
            "total_conversions": self.conversion_metrics["total"],
            "successful_conversions": self.conversion_metrics["successful"],
            "last_report": self.last_report_time.isoformat()
        } 