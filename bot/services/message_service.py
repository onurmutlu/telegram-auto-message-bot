"""
# ============================================================================ #
# Dosya: message_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/message_service.py
# İşlev: Telegram bot için mesaj gönderimi servisi.
#
# Amaç: Bu modül, gruplara otomatik mesaj gönderme işlevselliğini sağlar.
#       GroupHandler sınıfı üzerine inşa edilmiş bir wrapper servistir.
#
# Build: 2025-04-10-20:30:00
# Versiyon: v3.5.0
# ============================================================================ #
"""
import logging
import asyncio
import functools
import os
import json
from typing import Dict, Any, List
from bot.handlers.group_handler import GroupHandler
from bot.services.base_service import BaseService
from datetime import datetime
import random

logger = logging.getLogger(__name__)

class MessageService(BaseService):
    """
    Telegram gruplarına mesaj gönderimi için servis sınıfı.
    Bu sınıf, GroupHandler sınıfını kullanarak mesaj gönderme işlevselliğini sağlar.
    """
    
    def __init__(self, client, config, db, stop_event=None):
        """
        MessageService sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            stop_event: Durdurma eventi (opsiyonel)
        """
        super().__init__("message", client, config, db, stop_event)
        
        # Gerekli modülleri import et
        from bot.handlers.group_handler import GroupHandler
        from bot.services.user_service import UserService
        from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter
        
        # RateLimiter'ı kur
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=5.0,  # Saniyede 5 istek (önceden 1.0 idi)
            period=5,         # 5 saniyelik periyot (önceden 15 idi)
            error_backoff=1.05, # Hata durumunda 1.05x yavaşlama (önceden 1.2 idi)
            max_jitter=0.2     # Maksimum 0.2 saniyelik rastgele gecikme (önceden 1 idi)
        )
        
        # Handler'ları oluştur
        self.group_handler = GroupHandler(client, config, db)
        
        # Çalışma durumu değişkenleri
        self.is_running = False
        self.messages_sent = 0
        self.messages_failed = 0
        self.last_run = datetime.now()
        
        # Mesaj gönderme ayarları
        self.batch_size = self.config.get_setting('message_batch_size', 50)  # Önceden 10 idi
        self.batch_interval = self.config.get_setting('message_batch_interval', 30)  # Önceden 90 idi
        self.interval_multiplier = 0.2  # Önceden 0.5 idi
        self.default_interval = 60  # Önceden 450 idi
        
        # Çalışma zamanı değişkenleri
        self.current_interval = self.default_interval
        self.next_run_time = datetime.now()
        
        # Mesaj şablonları
        self.message_templates = {}
        self.message_queue = []
        self.template_files = {
            'announcements': 'data/announcements.json',
            'campaigns': 'data/campaigns.json',
            'invites': 'data/invites.json',
            'messages': 'data/messages.json',
            'promos': 'data/promos.json',
            'responses': 'data/responses.json'
        }
        
        # Mesaj havuzu
        self._load_message_templates()
        
        self.messages = {}
        self.stats = {
            'total_sent': 0,
            'last_sent': None
        }
        self.active_messages = set()
        self.message_stats = {}
        self.last_update = datetime.now()
        
        logger.info("MessageService başlatıldı")
    
    async def initialize(self):
        """
        Servisi başlatır ve gerekli kaynakları yükler.
        """
        try:
            logger.info("MessageService başlatılıyor...")
            
            # Her adımı ayrı olarak ele alıp, bir hata olursa diğer adımlara devam edelim
            try:
                await self.load_messages()
            except Exception as e:
                logger.error(f"Mesajlar yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir dict ile devam et
                self.messages = {}
                self.active_messages = set()
            
            try:
                await self.load_message_stats()
            except Exception as e:
                logger.error(f"Mesaj istatistikleri yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa boş bir dict ile devam et
                self.message_stats = {}
            
            try:
                await self.load_message_templates()
            except Exception as e:
                logger.error(f"Mesaj şablonları yüklenirken hata: {str(e)}", exc_info=True)
                # Hata olursa JSON dosyalarını kullanmayı dene
                self.message_templates = {}
                self._load_message_templates()
            
            # Başarıyla tamamlandı
            self.initialized = True
            logger.info("MessageService başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"MessageService başlatılırken genel hata: {str(e)}", exc_info=True)
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
    
    async def load_messages(self):
        """
        Mesajları veritabanından yükler.
        """
        try:
            logger.info("Mesajlar yükleniyor...")
            
            # Veritabanı bağlantısını kontrol et
            if not self.db.connected or not self.db.cursor:
                await self.db.connect()
                if not self.db.cursor:
                    logger.error("Veritabanı bağlantısı kurulamadı, DB cursor null")
                    return
            
            query = "SELECT * FROM messages WHERE is_active = TRUE LIMIT 1000"
            rows = await self.db.fetchall(query)
            
            if not rows:
                logger.warning("Aktif mesaj bulunamadı.")
                return
            
            for row in rows:
                if len(row) < 6:  # En azından id, group_id, content, sent_at, status, error olmalı
                    logger.warning(f"Mesaj verisi eksik sütunlar içeriyor: {row}")
                    continue
                
                message_id = row[0]
                self.messages[message_id] = {
                    "group_id": row[1],
                    "content": row[2],
                    "sent_at": row[3],
                    "status": row[4],
                    "error": row[5],
                    "user_id": row[6] if len(row) > 6 else None
                }
                self.active_messages.add(message_id)
            
            logger.info(f"{len(self.messages)} mesaj yüklendi")
        except Exception as e:
            logger.error(f"Mesajlar yüklenirken hata: {str(e)}", exc_info=True)
            # Varsayılan boş verilerle devam et
            self.messages = {}
            self.active_messages = set()
    
    async def load_message_stats(self):
        """
        Mesaj istatistiklerini veritabanından yükler.
        """
        try:
            logger.info("Mesaj istatistikleri yükleniyor...")
            
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
                LIMIT 1000
            """
            rows = await self.db.fetchall(query)
            
            if not rows:
                logger.warning("Mesaj istatistiği bulunamadı.")
                return
            
            for row in rows:
                if len(row) < 3:  # En azından group_id, count, max_sent_at olmalı
                    logger.warning(f"Mesaj istatistik verisi eksik sütunlar içeriyor: {row}")
                    continue
                
                group_id = row[0]
                self.message_stats[group_id] = {
                    "message_count": row[1],
                    "last_message": row[2]
                }
            
            logger.info(f"{len(self.message_stats)} mesaj istatistiği yüklendi")
        except Exception as e:
            logger.error(f"Mesaj istatistikleri yüklenirken hata: {str(e)}", exc_info=True)
            # Varsayılan boş verilerle devam et
            self.message_stats = {}
    
    async def load_message_templates(self):
        """
        Mesaj şablonlarını yükler.
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
                self._load_message_templates()  # Veritabanından yüklenemezse JSON dosyalarını kullan
                return
            
            for row in rows:
                if len(row) < 4:  # En azından id, content, category, language olmalı
                    logger.warning(f"Mesaj şablonu verisi eksik sütunlar içeriyor: {row}")
                    continue
                
                template_id = row[0]
                self.message_templates[template_id] = {
                    "content": row[1],
                    "category": row[2],
                    "language": row[3]
                }
            
            # Eğer hiç şablon yüklenmediyse, JSON dosyalarına başvur
            if not self.message_templates:
                logger.warning("Veritabanından hiç şablon yüklenemedi, JSON dosyalarını kullanıyoruz.")
                self._load_message_templates()
            else:
                logger.info(f"{len(self.message_templates)} mesaj şablonu yüklendi")
                
        except Exception as e:
            logger.error(f"Mesaj şablonları yüklenirken hata: {str(e)}", exc_info=True)
            # JSON dosyalarına başvur
            self.message_templates = {}
            self._load_message_templates()
            logger.info(f"Hata sonrası JSON'dan {len(self.message_templates)} mesaj şablonu yüklendi")
    
    def _load_message_templates(self):
        """
        Mesaj şablonlarını JSON dosyalarından yükler.
        """
        try:
            logger.info("Mesaj şablonları JSON dosyalarından yükleniyor...")
            self.message_templates = {}
            
            for template_type, file_path in self.template_files.items():
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                            # Şablonları ID'ye göre kaydediyoruz
                            if isinstance(data, dict):
                                # Her bir şablon kaydı için 
                                for key, template in data.items():
                                    template_id = str(key)  # ID'yi string'e çeviriyoruz
                                    
                                    # Eğer şablon doğrudan string ise
                                    if isinstance(template, str):
                                        self.message_templates[template_id] = {
                                            "content": template,
                                            "category": template_type,
                                            "language": "tr"
                                        }
                                    # Eğer şablon bir sözlük ise
                                    elif isinstance(template, dict) and "content" in template:
                                        self.message_templates[template_id] = {
                                            "content": template["content"],
                                            "category": template.get("category", template_type),
                                            "language": template.get("language", "tr")
                                        }
                                
                                # Özel format kontrolleri (invites içindeki listeler gibi)
                                for special_key in ["invites", "first_invite", "invites_outro", "redirect_messages"]:
                                    if special_key in data and isinstance(data[special_key], list):
                                        list_items = data[special_key]
                                        for i, item in enumerate(list_items):
                                            special_id = f"{special_key}_{i+1}"
                                            self.message_templates[special_id] = {
                                                "content": item,
                                                "category": special_key,
                                                "language": "tr"
                                            }
                            
                            # Eski liste formatını destekle
                            elif isinstance(data, list):
                                for i, content in enumerate(data, 1):
                                    template_id = f"{template_type}_{i}"
                                    self.message_templates[template_id] = {
                                        "content": content,
                                        "category": template_type,
                                        "language": "tr"
                                    }
                            
                            logger.info(f"{template_type} şablonları başarıyla yüklendi!")
                    except json.JSONDecodeError:
                        logger.error(f"{file_path} dosyası geçerli bir JSON dosyası değil")
                    except Exception as e:
                        logger.error(f"{file_path} dosyası yüklenirken hata: {str(e)}")
                else:
                    logger.warning(f"{file_path} dosyası bulunamadı")
            
            logger.info(f"Toplam {len(self.message_templates)} mesaj şablonu yüklendi")
        except Exception as e:
            logger.error(f"Mesaj şablonları yüklenirken hata: {str(e)}", exc_info=True)
            self.message_templates = {}  # Hata durumunda boş bir sözlük oluştur
    
    async def send_message(self, group_id, message):
        """
        Belirtilen gruba mesaj gönderir.
        
        Args:
            group_id: Hedef grup ID'si
            message: Gönderilecek mesaj
        """
        try:
            await self.rate_limiter.wait()
            await self.group_handler.send_message(group_id, message)
            self.messages_sent += 1
            logger.info(f"Mesaj gönderildi: Grup {group_id}")
        except Exception as e:
            self.messages_failed += 1
            logger.error(f"Mesaj gönderilirken hata: {str(e)}", exc_info=True)
            raise
    
    async def get_message_stats(self, group_id):
        """
        Belirtilen grup için mesaj istatistiklerini döndürür.
        
        Args:
            group_id: Grup ID'si
            
        Returns:
            Dict: Mesaj istatistikleri
        """
        return self.message_stats.get(group_id, {
            "message_count": 0,
            "last_message": None
        })
    
    async def get_template(self, template_type, category=None):
        """
        Belirtilen tür ve kategori için mesaj şablonu döndürür.
        
        Args:
            template_type: Şablon türü
            category: Şablon kategorisi (opsiyonel)
            
        Returns:
            str: Mesaj şablonu
        """
        try:
            templates = self.message_templates.get(template_type, [])
            if category:
                templates = [t for t in templates if t.get("category") == category]
            return random.choice(templates) if templates else None
        except Exception as e:
            logger.error(f"Şablon alınırken hata: {str(e)}", exc_info=True)
            return None