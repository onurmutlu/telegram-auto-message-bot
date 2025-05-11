"""
# ============================================================================ #
# Dosya: error_handler.py
# Yol: /Users/siyahkare/code/telegram-bot/app/utils/error_handler.py
# Açıklama: Telegram botu için hata yakalama, işleme ve yönetimi.
#
# Bu modül, Telegram botunun karşılaştığı hataları yakalar, işler ve yönetir.
# Temel Özellikler:
# - Hata istatistiklerini tutma ve raporlama.
# - Tekrarlanan hataları filtreleme.
# - FloodWait hatalarını akıllıca yönetme.
# - Hata mesajlarını açıklama ve çözüm önerileri sunma.
# - Özel log işleyicileri ile Telethon loglarını özelleştirme.
#
# Geliştirme: 2025-04-01
# Versiyon: v3.4.0
# Lisans: MIT
#
# Telif Hakkı (c) 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır.
# ============================================================================ #
"""
import logging
import asyncio
import time
from typing import Dict, Any, List, Tuple
from colorama import Fore, Style
from tabulate import tabulate

logger = logging.getLogger(__name__)

class ErrorHandler:
    """
    Hata ve log yönetimi sınıfı.

    Bu sınıf, Telegram botunda meydana gelen hataları yakalar, işler, istatistiklerini tutar ve yönetir.
    Ayrıca, Telethon kütüphanesinden gelen logları özelleştirerek daha anlamlı hale getirir.
    """
    
    def __init__(self, db, config): # Removed bot dependency, pass db and config directly
        """
        ErrorHandler sınıfının yapılandırıcısı.

        Args:
            db: UserDatabase nesnesi.
            config: Config nesnesi.
        """
        # self.bot = bot # Removed bot reference
        self.db = db
        self.config = config
        self.error_stats = {}
        self.telethon_log_cache = {}  # Telethon logları için önbellek
        self.last_log_time = {}  # Son log zamanı
        
        # Flood wait ve rate limiting için gerekli değişkenler
        self.flood_wait_times = {}
        self.rate_limit_cooldowns = {}
        self.error_counter = {}  # Hata sayacı
        
        # Orijinal logger'ları koru
        self._setup_custom_loggers()
    
    def _setup_custom_loggers(self):
        """
        Özel log işleyicilerini ayarlar.

        Bu metot, Telethon logger'ına özel bir işleyici ekleyerek log mesajlarını özelleştirir.
        Tekrarlanan mesajları filtreler ve FloodWait hatalarını yönetir.
        """
        import logging
        import time
        
        # Telethon logger'ının orijinal işleyicisini kaydet
        telethon_logger = logging.getLogger('telethon')
        self.original_telethon_handler = telethon_logger.handlers.copy() if telethon_logger.handlers else []
        
        # Telethon logger'ını özelleştir
        # Eski handlers'ları kaldır
        for handler in telethon_logger.handlers[:]:
            telethon_logger.removeHandler(handler)
            
        # Özel handler ekle
        custom_handler = logging.StreamHandler()
        # 'levellevel' hatası düzeltildi - doğru formatter kullan
        custom_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        custom_handler.emit = self._custom_emit  # Özel emit metodu
        telethon_logger.addHandler(custom_handler)
    
    def _custom_emit(self, record):
        """
        Özel log emisyonu - tekrarlanan mesajları filtreler.

        Bu metot, log kayıtlarını işler ve tekrarlanan mesajları filtreleyerek konsola yazdırır.
        FloodWait mesajlarını özel olarak yönetir ve özet mesajlar gösterir.

        Args:
            record (logging.LogRecord): Log kaydı nesnesi.
        """
        try:
            import time
            
            if record.name.startswith('telethon') and hasattr(record, 'msg') and 'Sleeping for' in str(record.msg):
                # FloodWait mesajlarını yönet
                import re
                match = re.search(r'Sleeping for (\d+)s .* on (\w+)', str(record.msg))
                if match:
                    wait_time = match.group(1)
                    request_type = match.group(2)
                    cache_key = f"{request_type}_flood"
                    
                    # Eğer bu tür bir mesaj daha önce loglanmamışsa veya 10+ saniye geçtiyse logla
                    current_time = time.time()
                    if cache_key not in self.telethon_log_cache:
                        # İlk kez bu mesaj görülüyor
                        self.telethon_log_cache[cache_key] = {
                            'count': 1,
                            'last_time': current_time,
                            'wait_time': wait_time
                        }
                        # Normal log göster
                        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {record.name} - {record.levelname} - {record.getMessage()}")
                    else:
                        # Bu mesaj daha önce görüldü
                        self.telethon_log_cache[cache_key]['count'] += 1
                        time_diff = current_time - self.telethon_log_cache[cache_key]['last_time']
                        
                        # 10 saniyeden fazla geçtiyse veya bekleyen süre değiştiyse
                        if time_diff > 10 or wait_time != self.telethon_log_cache[cache_key]['wait_time']:
                            # Özet mesaj göster
                            count = self.telethon_log_cache[cache_key]['count']
                            print(f"\r⏳ {request_type} için {wait_time}s bekleniyor ({count} istek)")
                            # Önbelleği sıfırla
                            self.telethon_log_cache[cache_key] = {
                                'count': 0,
                                'last_time': current_time,
                                'wait_time': wait_time
                            }
                else:
                    # Normal Telethon mesajı
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {record.name} - {record.levelname} - {record.getMessage()}")
            else:
                # Diğer tüm mesajlar
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {record.name} - {record.levelname} - {record.getMessage()}")
        except Exception as e:
            # Hata durumunda orijinal mesajı al
            print(f"LOG HATASI: {e} - Orijinal mesaj: {getattr(record, 'msg', 'bilinmeyen mesaj')}")

    def _original_emit(self, record):
        """
        Orijinal log emitter - düzeltilmiş versiyon.

        Bu metot, orijinal log mesajlarını güvenli bir şekilde formatlar ve yazdırır.
        Hata durumunda, hatayı yakalar ve güvenli bir şekilde loglar.

        Args:
            record (logging.LogRecord): Log kaydı nesnesi.
        """
        try:
            # Direkt formatter kullanmak yerine manuel olarak formatla
            # Sorunlu alan: formatter = logging.Formatter('%(asctime)s - %(name)s - %(levellevel)s - %(message)s')
            # Buradaki hatayı düzelt (levellevel -> levelname)
            
            # Güvenli formatla
            import time
            message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {record.name} - {record.levelname} - {record.getMessage()}"
            print(message)
        except Exception as e:
            # Hatayı bastır ve güvenli bir şekilde logla
            print(f"LOG HATASI: {e} - Orijinal mesaj: {getattr(record, 'msg', 'bilinmeyen mesaj')}")

    async def manage_error_groups(self):
        """
        Grup hata kayıtlarını yönetir - iyileştirilmiş tablo formatı.

        Bu metot, veritabanından hata gruplarını alır ve konsola tablo formatında yazdırır.
        Hata temizleme işlemi artık main.py'deki argümanla yönetilir.
        """
        if not hasattr(self.db, 'get_error_groups'):
             logger.error("Veritabanı nesnesinde 'get_error_groups' metodu bulunamadı.")
             return

        error_groups = self.db.get_error_groups()
        if not error_groups:
            logger.info("Hata veren grup kaydı bulunmadı.")
            return
        
        # Konsola hata gruplarını göster - İYİLEŞTİRİLMİŞ TABLO FORMATI
        print(f"\n{Fore.YELLOW}⚠️ {len(error_groups)} adet hata veren grup kaydı bulundu:{Style.RESET_ALL}")
        
        # Tablo verilerini hazırla
        headers = ["Grup ID", "Grup Adı", "Hata", "Yeniden Deneme"]
        error_table = []
        
        for group_id, group_title, error_reason, error_time, retry_after in error_groups:
            # Grup adını kısalt (çok uzunsa)
            if len(group_title) > 30:
                group_title = group_title[:27] + "..."
                
            # Hata nedenini kısalt (çok uzunsa)
            if len(error_reason) > 60:
                error_reason = error_reason[:57] + "..."
                
            error_table.append([
                group_id,  
                group_title,
                error_reason,
                retry_after.strftime('%Y-%m-%d %H:%M:%S') if retry_after else "Belirsiz"
            ])
        
        # Tablo göster - İYİLEŞTİRİLMİŞ FORMATLAMA
        table_output = tabulate(
            error_table, 
            headers=headers, 
            tablefmt="grid",
            colalign=("right", "left", "left", "center")  # Hizalama ekledik
        )
        
        print(table_output)

        # Removed user interaction for clearing errors. This is handled by --reset-errors arg in main.py
        # The main function should call db.reset_error_groups() if the arg is present.
        logger.info("Hata veren gruplar listelendi. Temizlemek için --reset-errors argümanını kullanın.")

    def log_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """
        Hataları loglar ve tekrarları filtreler.

        Bu metot, hataları loglar, tekrarlarını filtreler ve istatistiklerini tutar.
        FloodWait hatalarını özel olarak işler.

        Args:
            error_type (str): Hata türü.
            error_message (str): Hata mesajı.
            context (Dict[str, Any], optional): Hata bağlamı. Varsayılan olarak None.

        Returns:
            bool: Hata loglandıysa True, aksi halde False.
        """
        # Context yoksa boş dict oluştur
        context = context or {}
        
        # FloodWait hatalarını özel olarak işle
        if "wait" in error_message.lower() and any(x in error_message for x in ["seconds", "saniye"]):
            return self.handle_flood_wait(error_type, error_message, context)
            
        error_key = f"{error_type}_{str(error_message)[:30]}"
        
        if error_key not in self.error_counter:
            self.error_counter[error_key] = 0
        
        self.error_counter[error_key] += 1
        count = self.error_counter[error_key]
        
        # İstatistikleri güncelle
        if error_type not in self.error_stats:
            self.error_stats[error_type] = {'count': 0, 'first_seen': None, 'examples': []}
        
        self.error_stats[error_type]['count'] += 1
        if not self.error_stats[error_type]['first_seen']:
            self.error_stats[error_type]['first_seen'] = time.time()
        
        # Örnek hatalar listesi (en fazla 5 farklı örnek)
        if (
            error_message not in self.error_stats[error_type]['examples'] and 
            len(self.error_stats[error_type]['examples']) < 5
        ):
            self.error_stats[error_type]['examples'].append(error_message)
        
        # İlk hata veya her N hatada bir günlüğe kaydet
        log_threshold = self._calculate_log_threshold(count)
        if count <= 3 or count % log_threshold == 0:
            if count > 3:
                message = f"{error_message} (tekrar sayısı: {count})"
            else:
                message = error_message
                
            logger.error(f"{error_type}: {message}")
            return True
            
        return False
        
    def handle_flood_wait(self, error_type: str, error_message: str, context: Dict[str, Any]) -> bool:
        """
        FloodWait hatalarını akıllıca işler.

        Bu metot, FloodWait hatalarını analiz eder, bekleme süresini çıkartır ve loglar.
        Ayrıca, rate limit için önerilen bekleme süresini günceller.

        Args:
            error_type (str): Hata türü.
            error_message (str): Hata mesajı.
            context (Dict[str, Any]): Hata bağlamı.

        Returns:
            bool: Hata loglandıysa True, aksi halde False.
        """
        import re
        wait_time_match = re.search(r'(\d+) second', error_message)
        wait_time = int(wait_time_match.group(1)) if wait_time_match else 60
        
        # İstek türünü belirle (GetUsersRequest, GetDialogsRequest vb.)
        request_type = "unknown"
        if "caused by" in error_message:
            request_match = re.search(r'caused by (\w+)', error_message)
            request_type = request_match.group(1) if request_match else "unknown"
        
        # Bu tür için şu ana kadar kaydedilmiş hataları kontrol et
        key = f"floodwait_{request_type}"
        
        if key not in self.flood_wait_times:
            # İlk defa görülen hata - log yaz
            self.flood_wait_times[key] = {
                'timestamp': time.time(),
                'wait_time': wait_time,
                'count': 1
            }
            logger.warning(f"⚠️ {request_type} için {wait_time} saniye bekleme gerekli")
            return True
            
        # Mevcut hata kaydını güncelle
        current_time = time.time()
        last_log = self.flood_wait_times[key]
        
        # Bu tür için log sıklığını sınırla (en az 60 saniye ara ile)
        if current_time - last_log['timestamp'] < 60:
            # Son 60 saniye içinde benzer hata loglanmış, sayacı artır
            self.flood_wait_times[key]['count'] += 1
            return False
            
        # 60 saniye geçmiş, yeni log yazabiliriz
        count = last_log['count'] + 1
        logger.warning(f"⚠️ {request_type} için {wait_time} saniye bekleme gerekli (son 1 dk içinde {count} kez)")
        
        # Rate limit için önerilen bekleme süresini güncelle
        self.rate_limit_cooldowns[request_type] = max(wait_time + 5, self.rate_limit_cooldowns.get(request_type, 0))
        
        # İstatistikleri sıfırla
        self.flood_wait_times[key] = {
            'timestamp': current_time,
            'wait_time': wait_time,
            'count': 1
        }
        
        return True
    
    def should_throttle(self, request_type: str) -> Tuple[bool, int]:
        """
        Belirli bir istek türü için throttling kararı verir.

        Args:
            request_type (str): İstek türü.

        Returns:
            Tuple[bool, int]: (Beklemeli mi?, Ne kadar beklemeli?)
        """
        if request_type not in self.rate_limit_cooldowns:
            return False, 0
            
        cooldown = self.rate_limit_cooldowns[request_type]
        current_time = time.time()
        
        # Son hata mesajından ne kadar zaman geçti?
        key = f"floodwait_{request_type}"
        if key in self.flood_wait_times:
            last_error_time = self.flood_wait_times[key]['timestamp']
            elapsed = current_time - last_error_time
            
            if elapsed < cooldown:
                # Hala bekleme süresindeyiz
                remaining = int(cooldown - elapsed)
                return True, remaining
                
        # Bekleme süresi bitti veya hiç hata olmadı
        return False, 0
        
    def _calculate_log_threshold(self, count: int) -> int:
        """
        Logaritmik loglama eşik değerini hesaplar:
        < 10: Her 5 hatada bir
        < 100: Her 10 hatada bir
        < 1000: Her 50 hatada bir
        >= 1000: Her 100 hatada bir
        """
        if count < 10:
            return 5
        elif count < 100:
            return 10
        elif count < 1000:
            return 50
        else:
            return 100
            
    def get_stats(self):
        """
        Hata istatistiklerini rapor olarak döndürür.

        Returns:
            str: Hata istatistikleri tablosu.
        """
        if not self.error_stats:
            return "Henüz kaydedilmiş hata yok"
            
        stats_table = []
        for error_type, stats in self.error_stats.items():
            examples = ", ".join(stats['examples'][:2])  # Sadece 2 örnek göster
            if len(stats['examples']) > 2:
                examples += f" (+{len(stats['examples']) - 2} daha)"
                
            stats_table.append([
                error_type,
                stats['count'],
                examples
            ])
            
        return tabulate(stats_table, headers=["Hata Tipi", "Sayı", "Örnekler"], tablefmt="grid")
        
    def explain_error(self, error_message: str) -> str:
        """
        Yaygın hataları açıklar ve çözüm önerileri sunar.

        Args:
            error_message (str): Hata mesajı.

        Returns:
            str: Hata açıklaması ve çözüm önerileri.
        """
        explanations = {
            "FloodWaitError": "Telegram API hız sınırı aşıldı; belirtilen süre kadar beklemeniz gerekiyor.",
            "A wait of": "Telegram API hız sınırı aşıldı; belirtilen süre kadar beklenecek.",
            "Could not find the input entity": "Bu kullanıcı veya grup bilgisine erişilemiyor. Kullanıcı hesabını silmiş olabilir.",
            "Got difference for channel": "Telegram, kanalın durumundaki değişiklikleri bildiriyor (güncelleme).",
            "PeerIdInvalidError": "Geçersiz kullanıcı/grup kimliği (ID). Bu kullanıcı artık mevcut olmayabilir.",
            "UserIsBlockedError": "Kullanıcı sizi engellemiş veya mesaj gönderemiyorsunuz.",
            "database is locked": "SQLite veritabanı başka bir işlem tarafından kullanılıyor."
        }
        
        for key, explanation in explanations.items():
            if key in error_message:
                return explanation
                
        return "Bilinmeyen hata. Lütfen logları kontrol edin."
