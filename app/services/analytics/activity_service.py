"""
# ============================================================================ #
# Dosya: activity_service.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/analytics/activity_service.py
# İşlev: Kullanıcı aktivite ve etkileşimlerini izleme servisi.
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import get_session
from app.services.base import BaseService
from app.models.user import User
from app.models.message import Message
from app.models.group import Group
# Activity model henüz oluşturulmamış olabilir
# from app.models.activity import Activity

logger = logging.getLogger(__name__)

class ActivityService(BaseService):
    """
    Kullanıcı aktivitelerini izleyen ve raporlayan servis.
    - Grup ve kullanıcı aktivitesini analiz eder
    - Veritabanına aktivite kayıtları ekler
    - Periyodik aktivite raporları oluşturur
    """
    
    service_name = "activity_service"
    default_interval = 3600  # 1 saat
    
    def __init__(self, db: AsyncSession = None):
        """ActivityService başlatıcısı."""
        super().__init__(name="activity_service")
        self.db = db
        self.running = False
        self.initialized = False
        self.last_analysis_time = None
        self.activity_stats = {
            "users": {},
            "groups": {},
            "messages": {}
        }
        self.db_retry_count = 0
        self.max_db_retries = 3
    
    async def initialize(self) -> bool:
        """Servisi başlat."""
        try:
            self.db = self.db or next(get_session())
            self.initialized = True
            self.last_analysis_time = datetime.now()
            logger.info("Activity monitoring service initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing ActivityService: {str(e)}", exc_info=True)
            return False
    
    async def start(self):
        """Aktivite izleme servisini başlat."""
        logger.info("Starting activity monitoring loop")
        self.running = True
        
        while self.running:
            try:
                # Aktivite istatistiklerini analiz et
                await self._analyze_activity()
                
                # İstatistikleri raporla
                await self._log_activity_stats()
                
                # Belirlenen aralıkta bekle
                interval = int(settings.SCHEDULER_INTERVAL)
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in activity monitoring loop: {str(e)}", exc_info=True)
                await asyncio.sleep(60)  # Hata durumunda 1 dakika bekle
    
    async def _analyze_activity(self):
        """Aktivite verilerini analiz et."""
        logger.debug("Analyzing activity data")
        self.last_analysis_time = datetime.now()
        
        # Veritabanı bağlantısını kontrol et
        if not await self._ensure_db_connection():
            logger.error("Database connection failed, skipping activity analysis")
            return
        
        try:
            # Yeni bir transaction başlat
            self.db.rollback()
            
            # Son 24 saatteki aktiviteyi analiz et
            since = datetime.now() - timedelta(hours=24)
            
            # Kullanıcı istatistikleri
            try:
                await self._analyze_user_activity(since)
            except Exception as e:
                logger.error(f"User activity analysis failed: {str(e)}")
                self.db.rollback()  # Hata durumunda transaction'ı rollback yap
            
            # Grup istatistikleri
            try:
                await self._analyze_group_activity(since)
            except Exception as e:
                logger.error(f"Group activity analysis failed: {str(e)}")
                self.db.rollback()  # Hata durumunda transaction'ı rollback yap
            
            # Mesaj istatistikleri
            try:
                await self._analyze_message_activity(since)
            except Exception as e:
                logger.error(f"Message activity analysis failed: {str(e)}")
                self.db.rollback()  # Hata durumunda transaction'ı rollback yap
            
            # Aktivite kaydı oluştur
            try:
                await self._create_activity_record()
            except Exception as e:
                logger.error(f"Activity record creation failed: {str(e)}")
                self.db.rollback()  # Hata durumunda transaction'ı rollback yap
            
        except Exception as e:
            logger.error(f"Error analyzing activity: {str(e)}", exc_info=True)
            # Genel hata durumunda rollback
            try:
                self.db.rollback()
            except:
                pass
    
    async def _ensure_db_connection(self) -> bool:
        """Veritabanı bağlantısını kontrol et, gerekirse yeniden bağlan."""
        try:
            if not self.db:
                self.db = next(get_session())
            
            # Muhtemel bir bekleyen transaction'ı rollback yapalım
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.warning(f"Rollback error: {str(rollback_error)}")
                # Hatada oturumu yenile
                try:
                    self.db.close()
                except:
                    pass
                self.db = next(get_session())
                
            # Bağlantıyı test et
            query_result = self.db.execute(text("SELECT 1 as result"))
            row = query_result.fetchone()
            if row and row.result == 1:
                # Bağlantı başarılı
                self.db_retry_count = 0
                return True
            
            # Bağlantı başarısız
            logger.warning("Database connection test failed")
            
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
        
        # Yeniden bağlanma denemesi
        if self.db_retry_count < self.max_db_retries:
            self.db_retry_count += 1
            logger.info(f"Attempting to reconnect to database (attempt {self.db_retry_count})")
            
            try:
                # Mevcut bağlantıyı kapat
                if self.db:
                    try:
                        self.db.close()
                    except:
                        pass
                
                # Yeni bağlantı oluştur
                self.db = next(get_session())
                
                # Test et
                query_result = self.db.execute(text("SELECT 1 as result"))
                row = query_result.fetchone()
                if row and row.result == 1:
                    logger.info("Database reconnection successful")
                    self.db_retry_count = 0
                    return True
            except Exception as reconnect_error:
                logger.error(f"Database reconnection failed: {str(reconnect_error)}")
        
        return False
    
    async def _analyze_user_activity(self, since: datetime):
        """Kullanıcı aktivitelerini analiz et."""
        try:
            # Transaction'ı sıfırlayalım
            self.db.rollback()
            
            # Son N saatte aktif olan kullanıcılar - users tablosunu kullan
            active_users_query = text("""
                SELECT COUNT(DISTINCT id) as count
                FROM users 
                WHERE last_activity_at > :since
            """)
            
            result = self.db.execute(active_users_query, {"since": since})
            row = result.fetchone()
            active_users_count = row.count if row else 0
            
            # Toplam kullanıcı sayısı
            total_users_query = text("SELECT COUNT(*) as count FROM users")
            result = self.db.execute(total_users_query)
            row = result.fetchone()
            total_users = row.count if row else 0
            
            # Son kayıt olan kullanıcılar
            new_users_query = text("""
                SELECT COUNT(*) as count
                FROM users 
                WHERE created_at > :since
            """)
            
            result = self.db.execute(new_users_query, {"since": since})
            row = result.fetchone()
            new_users_count = row.count if row else 0
            
            # Sonuçları kaydet
            self.activity_stats["users"] = {
                "total": total_users,
                "active": active_users_count,
                "new": new_users_count,
                "active_percentage": round((active_users_count / total_users) * 100, 2) if total_users > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing user activity: {str(e)}", exc_info=True)
            self.activity_stats["users"] = {
                "error": str(e)
            }
            # Hata durumunda rollback yaparak transaction'ı temizle
            try:
                self.db.rollback()
            except:
                pass
    
    async def _analyze_group_activity(self, since: datetime):
        """Grup aktivitelerini analiz et."""
        try:
            # Her fonksiyon çağrısı başında transaction sıfırlama
            self.db.rollback()
            
            # Aktif gruplar
            active_groups_query = text("""
                SELECT COUNT(DISTINCT group_id) as count
                FROM messages 
                WHERE created_at > :since
            """)
            
            result = self.db.execute(active_groups_query, {"since": since})
            row = result.fetchone()
            active_groups_count = row.count if row else 0
            
            # Toplam grup sayısı
            total_groups_query = text("SELECT COUNT(*) as count FROM groups")
            result = self.db.execute(total_groups_query)
            row = result.fetchone()
            total_groups = row.count if row else 0
            
            # En aktif gruplar (en çok mesaj olan)
            top_groups_query = text("""
                SELECT g.name as title, COUNT(m.id) as message_count 
                FROM messages m
                JOIN groups g ON m.group_id = g.group_id
                WHERE m.created_at > :since
                GROUP BY g.id, g.name
                ORDER BY message_count DESC
                LIMIT 5
            """)
            
            result = self.db.execute(top_groups_query, {"since": since})
            top_groups = [{"title": row.title, "message_count": row.message_count} for row in result.fetchall()]
            
            # Sonuçları kaydet
            self.activity_stats["groups"] = {
                "total": total_groups,
                "active": active_groups_count,
                "active_percentage": round((active_groups_count / total_groups) * 100, 2) if total_groups > 0 else 0,
                "top_active": top_groups
            }
            
        except Exception as e:
            logger.error(f"Error analyzing group activity: {str(e)}", exc_info=True)
            self.activity_stats["groups"] = {
                "error": str(e)
            }
            # Hata durumunda rollback yaparak transaction'ı temizle
            try:
                self.db.rollback()
            except:
                pass
    
    async def _analyze_message_activity(self, since: datetime):
        """Mesaj aktivitelerini analiz et."""
        try:
            # Her fonksiyon çağrısı başında transaction sıfırlama
            self.db.rollback()
            
            # Toplam mesaj sayısı
            total_messages_query = text("SELECT COUNT(*) as count FROM messages")
            result = self.db.execute(total_messages_query)
            row = result.fetchone()
            total_messages = row.count if row else 0
            
            # Son N saatte gönderilen mesajlar
            recent_messages_query = text("""
                SELECT COUNT(*) as count
                FROM messages 
                WHERE created_at > :since
            """)
            
            result = self.db.execute(recent_messages_query, {"since": since})
            row = result.fetchone()
            recent_messages_count = row.count if row else 0
            
            # Mesaj türü dağılımı
            message_types_query = text("""
                SELECT message_type, COUNT(*) as count
                FROM messages
                WHERE created_at > :since
                GROUP BY message_type
                ORDER BY count DESC
            """)
            
            result = self.db.execute(message_types_query, {"since": since})
            message_types = [{"type": row.message_type, "count": row.count} for row in result.fetchall()]
            
            # Sonuçları kaydet
            self.activity_stats["messages"] = {
                "total": total_messages,
                "recent": recent_messages_count,
                "hourly_average": round(recent_messages_count / 24, 2),
                "types": message_types
            }
            
        except Exception as e:
            logger.error(f"Error analyzing message activity: {str(e)}", exc_info=True)
            self.activity_stats["messages"] = {
                "error": str(e)
            }
            # Hata durumunda rollback yaparak transaction'ı temizle
            try:
                self.db.rollback()
            except:
                pass
    
    async def _create_activity_record(self):
        """Aktivite istatistiklerini veritabanına kaydet."""
        try:
            # Önceki hatalı transaction'ları temizle
            self.db.rollback()
            
            # Hata durumunda yeni bir session oluştur
            if "error" in self.activity_stats.get("users", {}) or "error" in self.activity_stats.get("groups", {}) or "error" in self.activity_stats.get("messages", {}):
                # Mevcut oturumu kapat
                try:
                    self.db.close()
                except:
                    pass
                # Yeni oturum oluştur
                self.db = next(get_session())
            
            # activities tablosunun var olup olmadığını kontrol et
            check_table_query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'activities'
                ) as table_exists;
            """)
            
            result = self.db.execute(check_table_query)
            row = result.fetchone()
            table_exists = row.table_exists if row else False
            
            # Tablo yoksa oluştur
            if not table_exists:
                create_table_query = text("""
                    CREATE TABLE IF NOT EXISTS activities (
                        id SERIAL PRIMARY KEY,
                        activity_type VARCHAR(50) NOT NULL,
                        activity_data JSONB,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                self.db.execute(create_table_query)
                self.db.commit()
                logger.info("Activities tablosu oluşturuldu")
            
            # JSON olarak aktivite verilerini hazırla
            import json
            activity_data = json.dumps(self.activity_stats)
            
            # Yeni aktivite kaydı oluştur
            new_activity_query = text("""
                INSERT INTO activities (activity_type, activity_data, created_at)
                VALUES ('daily_stats', :activity_data, NOW())
            """)
            
            self.db.execute(new_activity_query, {"activity_data": activity_data})
            self.db.commit()
            
            logger.debug("Activity record created successfully")
            
        except Exception as e:
            logger.error(f"Error creating activity record: {str(e)}", exc_info=True)
            # Rollback işlemi
            try:
                self.db.rollback()
            except:
                pass
    
    async def _log_activity_stats(self):
        """Aktivite istatistiklerini log olarak raporla."""
        try:
            users = self.activity_stats.get("users", {})
            groups = self.activity_stats.get("groups", {})
            messages = self.activity_stats.get("messages", {})
            
            if "error" not in users and "error" not in groups and "error" not in messages:
                logger.info(f"Activity Stats: {users.get('active', 0)}/{users.get('total', 0)} users active, "
                          f"{groups.get('active', 0)}/{groups.get('total', 0)} groups active, "
                          f"{messages.get('recent', 0)} recent messages")
            else:
                logger.warning("Activity stats contains errors, see detailed logs")
        except Exception as e:
            logger.error(f"Error logging activity stats: {str(e)}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Servis durumunu al."""
        return {
            "name": self.service_name,
            "running": self.running,
            "initialized": self.initialized,
            "last_analysis": self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            "db_connection": await self._ensure_db_connection(),
            "stats_summary": {
                "users": self.activity_stats.get("users", {}).get("active", 0),
                "groups": self.activity_stats.get("groups", {}).get("active", 0),
                "messages": self.activity_stats.get("messages", {}).get("recent", 0)
            }
        }
    
    async def get_detailed_stats(self) -> Dict[str, Any]:
        """Detaylı aktivite istatistiklerini al."""
        return {
            "timestamp": datetime.now().isoformat(),
            "stats": self.activity_stats,
            "last_update": self.last_analysis_time.isoformat() if self.last_analysis_time else None
        }
    
    async def cleanup(self):
        """Servis kapatılırken temizlik işleri."""
        self.running = False
        if self.db:
            try:
                await self.db.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {str(e)}")
        logger.info("Activity monitoring service stopped")
    
    async def _start(self) -> bool:
        """BaseService için başlatma metodu"""
        return await self.initialize()
    
    async def _stop(self) -> bool:
        """BaseService için durdurma metodu"""
        try:
            self.initialized = False
            self.running = False
            await self.cleanup()
            return True
        except Exception as e:
            logger.error(f"ActivityService durdurma hatası: {e}")
            return False
    
    async def _update(self) -> bool:
        """Periyodik güncelleme metodu"""
        await self._analyze_activity()
        return True 