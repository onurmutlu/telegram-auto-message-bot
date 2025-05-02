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
from datetime import datetime, timedelta
import random
import traceback

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
        self.running = False  # Servis durumu için running özelliği
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
            
        self.running = True  # running özelliğini güncelle
        self.is_running = True
        self.start_time = datetime.now()
        logger.info(f"{self.service_name} servisi başlatıldı.")
        return True
    
    async def run(self) -> None:
        """
        Servisin ana çalışma döngüsü. Bu metot otomatik olarak gruplara mesaj gönderme işlemini yönetir.
        
        Returns:
            None
        """
        logger.info("MessageService çalışma döngüsü başlatıldı")
        try:
            # İlk çalıştırmada şablonları yeniden yükle
            await self.load_message_templates()
            
            # Veritabanı bağlantısını kontrol et
            if not hasattr(self.db, 'connected') or not self.db.connected:
                logger.error("Veritabanı bağlantısı yok, bağlanmayı deniyorum...")
                try:
                    await self.db.connect()
                except Exception as e:
                    logger.error(f"Veritabanı bağlantısı kurulamadı: {str(e)}")
            
            # GroupHandler'ı initialize et ve başlat
            if not hasattr(self.group_handler, 'initialized') or not self.group_handler.initialized:
                await self.group_handler.initialize()
            
            # İlk çalıştırmada mesaj planını güncelle
            self.next_run_time = datetime.now() + timedelta(seconds=20)  # 20 saniye sonra ilk mesajları gönder
            logger.info(f"İlk mesaj gönderimi planlandı: {self.next_run_time.strftime('%H:%M:%S')}")
            
            # Ana döngü
            while self.running and not self.stop_event.is_set():  # is_running yerine running kullan
                try:
                    # Şu anki zamanı kontrol et
                    now = datetime.now()
                    if now >= self.next_run_time:
                        logger.info("Otomatik mesaj gönderme döngüsü başlatılıyor...")
                        
                        # Mesaj şablonlarını kontrol et
                        if not self.message_templates:
                            logger.warning("Mesaj şablonları eksik, yeniden yükleniyor...")
                            self._load_message_templates()
                            
                            # Şablonlar hala yüklenemezse
                            if not self.message_templates:
                                # Varsayılan şablonları ekle
                                logger.warning("Mesaj şablonları yüklenemedi, varsayılan şablonlar ekleniyor...")
                                self.message_templates = {
                                    'default_1': {
                                        'content': 'Merhaba! Bu otomatik bir mesajdır.',
                                        'category': 'general',
                                        'language': 'tr'
                                    },
                                    'default_2': {
                                        'content': 'Nasılsınız? Grup aktivitesi devam ediyor mu?',
                                        'category': 'general',
                                        'language': 'tr'
                                    }
                                }
                        
                        # Aktif grupları al
                        groups = await self._get_active_groups()
                        if groups:
                            logger.info(f"{len(groups)} aktif grup bulundu, mesaj gönderimi başlıyor...")
                            
                            # Batch olarak grupları işle
                            batches = [groups[i:i + self.batch_size] for i in range(0, len(groups), self.batch_size)]
                            for batch_index, batch in enumerate(batches):
                                logger.info(f"Batch {batch_index+1}/{len(batches)} işleniyor ({len(batch)} grup)")
                                
                                for group in batch:
                                    group_id = group.get('group_id')
                                    if not group_id:
                                        logger.warning(f"Geçersiz grup verisi: {group}")
                                        continue
                                        
                                    try:
                                        # Grup için uygun bir şablon seç
                                        message_template = await self._select_message_template(group)
                                        if message_template:
                                            # Mesajı gönder
                                            logger.info(f"Gruba mesaj gönderiliyor: {group_id}")
                                            await self.send_message(group_id, message_template)
                                            
                                            # Veritabanında işaretle
                                            await self._mark_message_sent(group_id)
                                            
                                            # İstatistik güncelle
                                            if not hasattr(self, 'stats'):
                                                self.stats = {'total_sent': 0, 'last_sent': None}
                                            self.stats['total_sent'] += 1
                                            self.stats['last_sent'] = datetime.now()
                                        else:
                                            logger.warning(f"Grup {group_id} için uygun şablon bulunamadı")
                                    except Exception as e:
                                        logger.error(f"Grup {group_id} için mesaj gönderimi başarısız: {str(e)}")
                                        logger.debug(traceback.format_exc())
                                
                                # Her batch arasında bekleme
                                if not self.stop_event.is_set() and self.is_running and batch_index < len(batches) - 1:
                                    logger.info(f"Batch {batch_index+1} tamamlandı, {self.batch_interval} saniye bekleniyor...")
                                    await asyncio.sleep(self.batch_interval)
                            
                            # İstatistikleri güncelle
                            self.last_run = now
                            
                            # Bir sonraki çalışma zamanını planla
                            self.next_run_time = now + timedelta(seconds=self.current_interval)
                            logger.info(f"Mesaj gönderimi tamamlandı. Bir sonraki mesaj gönderimi: {self.next_run_time.strftime('%H:%M:%S')}")
                        else:
                            logger.warning("Aktif grup bulunamadı! Veritabanı sorgusu kontrol edilmeli.")
                            # Aktif grup kontrolünü 10 dakika sonra tekrar et
                            self.next_run_time = now + timedelta(minutes=10)
                            logger.info(f"Gruplar 10 dakika sonra tekrar kontrol edilecek: {self.next_run_time.strftime('%H:%M:%S')}")
                    
                    # Her 1 saniyede bir kontrol et
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Mesaj gönderme döngüsünde hata: {str(e)}")
                    logger.debug(traceback.format_exc())
                    # Hata durumunda bekle ve tekrar dene
                    await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.info("MessageService çalışma döngüsü iptal edildi")
        except Exception as e:
            logger.error(f"MessageService çalışma döngüsünde kritik hata: {str(e)}")
            logger.debug(traceback.format_exc())
        finally:
            logger.info("MessageService çalışma döngüsü tamamlandı")
    
    async def _get_active_groups(self) -> List[Dict]:
        """
        Aktif grupları veritabanından alır.
        
        Returns:
            List[Dict]: Aktif grupların listesi
        """
        try:
            groups = []
            
            # Veritabanı bağlantısını kontrol et
            if not hasattr(self.db, 'connected') or not self.db.connected:
                try:
                    await self.db.connect()
                except Exception as e:
                    logger.error(f"Veritabanı bağlantısı kurulamadı: {str(e)}")
                    return []
            
            # Aktif grupları ve son mesaj zamanlarını al
            query = """
                SELECT g.group_id, g.name, g.member_count, 
                       COALESCE(MAX(m.sent_at), '1970-01-01'::timestamp) as last_message_time
                FROM groups g
                LEFT JOIN messages m ON g.group_id = m.group_id
                WHERE g.is_active = TRUE 
                AND (g.error_count < 5 OR g.permanent_error = FALSE)
                GROUP BY g.group_id, g.name, g.member_count
                ORDER BY last_message_time ASC, g.member_count DESC
                LIMIT 30
            """
            
            rows = await self.db.fetchall(query)
            
            if not rows:
                logger.warning("Veritabanında aktif grup bulunamadı")
                return []
            
            current_time = datetime.now()
            min_interval = timedelta(minutes=self.interval_multiplier * 60)  # Minimum aralık (saniye)
            
            # Grup listesini oluştur ve zaman filtresi uygula
            for row in rows:
                if len(row) < 4:  # En azından 4 sütun olmalı (group_id, name, member_count, last_message_time)
                    logger.warning(f"Grup verisi eksik sütunlar içeriyor: {row}")
                    continue
                
                group_id = row[0]
                group_name = row[1]
                member_count = row[2] or 0
                last_message_time = row[3]
                
                # Son mesaj zamanından itibaren geçen süreyi kontrol et
                if isinstance(last_message_time, str):
                    try:
                        last_message_time = datetime.fromisoformat(last_message_time.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        last_message_time = datetime(1970, 1, 1)  # Unix epoch başlangıcı
                
                time_diff = current_time - last_message_time
                
                # Minimum aralık geçtiyse grubu listeye ekle
                if time_diff >= min_interval:
                    groups.append({
                        'group_id': group_id,
                        'name': group_name,
                        'member_count': member_count,
                        'last_message': last_message_time,
                        'time_diff_hours': time_diff.total_seconds() / 3600  # Saat cinsinden
                    })
                    logger.debug(f"Aktif grup eklendi: {group_name}, son mesaj: {last_message_time}, süre farkı: {time_diff.total_seconds() / 3600:.2f} saat")
                else:
                    logger.debug(f"Grup minimum aralığı geçmedi: {group_name}, son mesaj: {last_message_time}, süre farkı: {time_diff.total_seconds() / 60:.2f} dakika")
            
            # Önce hiç mesaj gönderilmemiş gruplara öncelik ver, sonra son mesaj zamanına göre sırala
            # Yoksa, üye sayısına göre en çok üyesi olandan en aza doğru sırala
            groups = sorted(groups, key=lambda g: (g['last_message'] == datetime(1970, 1, 1), g['last_message'], -g['member_count']))
            logger.info(f"Toplam {len(groups)} aktif grup bulundu ve aralık kontrolünden geçti")
            
            return groups
            
        except Exception as e:
            logger.error(f"Aktif grupları alma hatası: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
    async def _select_message_template(self, group: Dict) -> str:
        """
        Belirtilen grup için mesaj şablonu seçer.
        
        Args:
            group: Grup bilgileri
            
        Returns:
            str: Mesaj şablonu
        """
        try:
            # Önce grup kategorisine göre şablon seçmeyi dene
            group_category = group.get('category', 'general')
            templates = []
            
            # Kategoriye göre şablonları filtrele
            for template_id, template in self.message_templates.items():
                if template.get('category') == group_category:
                    templates.append(template.get('content'))
            
            # Hiç şablon bulunamadıysa genel şablonları kullan
            if not templates:
                for template_id, template in self.message_templates.items():
                    if template.get('category') == 'general':
                        templates.append(template.get('content'))
            
            # Rastgele bir şablon seç
            if templates:
                return random.choice(templates)
            else:
                # Son çare olarak varsayılan bir mesaj
                return "Merhaba! Bu otomatik bir mesajdır."
        except Exception as e:
            logger.error(f"Mesaj şablonu seçilirken hata: {str(e)}", exc_info=True)
            return "Merhaba! Bu otomatik bir mesajdır."
    
    async def _mark_message_sent(self, group_id: int) -> None:
        """
        Mesaj gönderimini veritabanında kaydeder.
        
        Args:
            group_id: Grup ID
        """
        try:
            # Veritabanında mesaj kaydı
            query = """
                INSERT INTO messages (group_id, content, sent_at, status)
                VALUES (%s, %s, %s, %s)
            """
            await self.db.execute(
                query, 
                (group_id, "Otomatik mesaj", datetime.now(), "sent")
            )
            
            # İstatistik güncelle
            if group_id in self.message_stats:
                self.message_stats[group_id]['message_count'] += 1
                self.message_stats[group_id]['last_message'] = datetime.now()
            else:
                self.message_stats[group_id] = {
                    'message_count': 1,
                    'last_message': datetime.now()
                }
        except Exception as e:
            logger.error(f"Mesaj kaydedilirken hata: {str(e)}", exc_info=True)
    
    async def _run_async_db_method(self, method, *args, **kwargs):
        """
        Veritabanı metodunu async olarak çalıştırır.
        
        Args:
            method: Veritabanı metodu
            *args: Argümanlar
            **kwargs: Anahtar kelime argümanları
            
        Returns:
            Any: Metodun dönüş değeri
        """
        if asyncio.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: method(*args, **kwargs))
        
    async def stop(self) -> None:
        """
        Servisi durdurur.
        
        Returns:
            None
        """
        logger.info(f"{self.service_name} servisi durduruluyor...")
        
        # Çalışma durumunu güncelle
        self.running = False  # running özelliğini güncelle
        self.is_running = False
        
        # GroupHandler'ı durdur
        if self.group_handler:
            await self.group_handler.stop()
        
        # Aktif görevleri iptal et
        tasks = [task for task in asyncio.all_tasks() 
                if task.get_name().startswith(f"{self.service_name}_task_") and 
                not task.done()]
                
        for task in tasks:
            try:
                task.cancel()
            except Exception as e:
                logger.error(f"Görev iptal edilirken hata: {str(e)}")
                
        # İstatistiği güncelle
        self.last_run = datetime.now()
        logger.info(f"{self.service_name} servisi durduruldu")
    
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