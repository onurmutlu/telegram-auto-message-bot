"""
# ============================================================================ #
# Dosya: tdlib_integration.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/tdlib_integration.py
# İşlev: TDLib (Telegram Database Library) entegrasyonu ve grup keşfi.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""
import os
import logging
import asyncio
import platform
import ctypes
import uuid
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Union

# TDLib wrapper'ını doğru şekilde import et
try:
    from tdlib import Client as TdClient
    TDLIB_AVAILABLE = True
except ImportError:
    TDLIB_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("TDLib Python wrapper bulunamadı. Grup keşif özellikleri devre dışı.")

from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, SpinnerColumn

from database.user_db import UserDatabase
from bot.services.base_service import BaseService  # BaseService sınıfını import et

logger = logging.getLogger(__name__)
console = Console()

class TelegramDiscoveryService(BaseService):  # BaseService'den türetildiğini varsayıyorum
    """
    TDLib kullanarak Telegram grupları keşfetme ve izleme servisi.
    
    Bu servis:
    1. Henüz üye olunmayan grupları keşfeder
    2. Grupları analiz eder ve kategorize eder
    3. Uygun grupları veritabanına kaydeder
    4. İsteğe bağlı olarak bu gruplara otomatik katılır
    """
    
    def __init__(self, db, config, stop_event=None):
        super().__init__("discovery", None, config, db, stop_event)
        
        # db None olabileceği için kontrol ekleyin
        self.db = db  # Referansı sakla, hata kontrolü için gerekebilir
        
        # TDLib entegrasyonu mevcut mu kontrol et
        if not TDLIB_AVAILABLE:
            logger.warning("TDLib entegrasyonu bulunamadı, servis sınırlı çalışacak")
            self.have_tdlib = False
        else:
            self.have_tdlib = True
            
        # debug_tdlib_setup() metodu için diğer parametreler olmadan da çalışabilmeli
        # Bu nedenle baseService parametrelerini daha güvenli hale getirin
        
        # Asenkron işlemler için gerekli yapılar
        self.requests = {}  # Request ID -> Future eşlemesi
        self.update_handlers = []  # TDLib güncelleme işleyicileri
        self.is_closed = False
        
        # Yapılandırma
        self._load_settings()
    
    def _load_settings(self) -> None:
        """TDLib ayarlarını yükler."""
        # TDLib yapılandırması - önce config nesnesinden, yoksa çevre değişkenlerinden
        self.api_id = getattr(self.config.telegram, 'api_id', int(os.environ.get('API_ID', 0)))
        self.api_hash = getattr(self.config.telegram, 'api_hash', os.environ.get('API_HASH', ''))
        self.phone = getattr(self.config.telegram, 'phone', os.environ.get('PHONE', ''))
        
        # Grup keşif ayarları
        self.auto_join = getattr(self.config, 'auto_join_groups', False)
        self.min_group_size = getattr(self.config, 'min_group_size', 30)
        self.group_blacklist = getattr(self.config, 'group_blacklist', [])
        self.group_keywords = getattr(self.config, 'group_keywords', 
                                     ['chat', 'sohbet', 'muhabbet', 'arkadaş',
                                      'friend', 'talk', 'omegle', 'aşk', 'ask', 'arayış', 'arayis'])
    
    def _find_tdjson_path(self) -> Optional[str]:
        """
        Sistem platformuna göre TDLib JSON kütüphanesini bul
        
        Returns:
            str: Bulunan kütüphane yolu veya None
        """
        system = platform.system().lower()
        
        # Varsayılan yol listesi
        paths = []
        
        if system == 'darwin':  # macOS
            paths = [
                '/usr/local/lib/libtdjson.dylib',
                '/opt/homebrew/lib/libtdjson.dylib',
                '/usr/lib/libtdjson.dylib',
                'libtdjson.dylib'
            ]
        elif system == 'linux':
            paths = [
                '/usr/local/lib/libtdjson.so',
                '/usr/lib/libtdjson.so',
                'libtdjson.so'
            ]
        elif system == 'windows':
            paths = [
                'C:\\Program Files\\TDLib\\bin\\tdjson.dll',
                'C:\\TDLib\\bin\\tdjson.dll',
                'tdjson.dll'
            ]
            
        # Çevresel değişken kontrol et
        if 'TDJSON_PATH' in os.environ:
            paths.insert(0, os.environ['TDJSON_PATH'])
            
        # Yolları dene
        for path in paths:
            try:
                # Dinamik olarak kütüphaneyi yüklemeyi dene
                ctypes.CDLL(path)
                logger.info(f"TDLib JSON kütüphanesi bulundu: {path}")
                return path
            except OSError:
                # Bu yolda kütüphane bulunamadı, bir sonrakini dene
                continue
                
        return None
    
    def debug_tdlib_setup(self):
        """TDLib kurulumunu test et ve sonuçları logla"""
        print("\n===== TDLIB KURULUM TESTİ =====")
        
        # Sistem bilgileri
        import platform
        print(f"İşletim Sistemi: {platform.system()} {platform.release()}")
        
        # Çevre değişkeni kontrolü
        tdlib_path_env = os.environ.get('TDJSON_PATH', 'Tanımlanmamış')
        print(f"TDJSON_PATH çevre değişkeni: {tdlib_path_env}")
        
        # Olası yolları kontrol et
        paths_to_check = [
            '/usr/local/lib/libtdjson.dylib',
            '/opt/homebrew/lib/libtdjson.dylib',
            '/usr/lib/libtdjson.dylib',
            tdlib_path_env
        ]
        
        print("\nKütüphane yollarını kontrol ediyorum:")
        for path in paths_to_check:
            exists = os.path.exists(path)
            status = "✅ MEVCUT" if exists else "❌ BULUNAMADI"
            print(f"  {path}: {status}")
        
        # Seçilen yolu göster
        selected_path = self._find_tdjson_path()
        print(f"\nSeçilen kütüphane yolu: {selected_path}")
        
        # Kütüphaneyi yüklemeyi dene
        if selected_path:
            try:
                import ctypes
                lib = ctypes.CDLL(selected_path)
                version_func = getattr(lib, 'td_get_version', None)
                if version_func:
                    version = version_func()
                    print(f"TDLib sürümü: {version}")
                print("✅ Kütüphane başarıyla yüklendi!")
                return True
            except Exception as e:
                print(f"❌ Kütüphane yüklenirken hata: {str(e)}")
        else:
            print("❌ Uygun kütüphane yolu bulunamadı!")
        
        print("==================================")
        return False
    
    async def initialize(self) -> bool:
        """
        TDLib istemcisini başlatır.
        
        Returns:
            bool: Başlatma başarılı ise True
        """
        try:
            # TDLib istemcisi oluştur
            self.tdlib_client = TdClient(
                api_id=self.api_id,
                api_hash=self.api_hash,
                phone=self.phone,
                database_directory=Path('tdlib_data'),
                files_directory=Path('tdlib_files')
            )
            
            # İstemciyi başlat
            await self.tdlib_client.start()
            logger.info("TDLib istemcisi başarıyla başlatıldı")
            
            # Mevcut grupları yükle
            await self._load_existing_groups()
            
            return True
        except Exception as e:
            logger.error(f"TDLib istemci başlatma hatası: {str(e)}")
            return False
    
    async def _load_existing_groups(self) -> None:
        """Veritabanından mevcut grupları yükler."""
        try:
            if hasattr(self.db, 'get_all_groups'):
                groups = await self.db.get_all_groups()
                if groups:
                    for group in groups:
                        self.known_groups.add(group['group_id'])
                    
                    logger.info(f"Veritabanından {len(self.known_groups)} grup yüklendi")
        except Exception as e:
            logger.error(f"Mevcut grupları yükleme hatası: {str(e)}")
    
    async def start(self) -> bool:
        """
        Keşif servisini başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        if self.running:
            logger.info("TDLib keşif servisi zaten çalışıyor")
            return False
        
        if not self.tdlib_client:
            if not await self.initialize():
                logger.error("TDLib istemcisi başlatılamadı, keşif başarısız")
                return False
        
        self.running = True
        logger.info("TDLib grup keşif servisi başlatıldı")
        
        # Ana döngü taski oluştur ve başlat
        asyncio.create_task(self._discovery_loop())
        
        return True
    
    async def stop(self) -> None:
        """Keşif servisini durdurur."""
        self.running = False
        logger.info("TDLib grup keşif servisi durduruluyor...")
        
        if self.tdlib_client:
            await self.tdlib_client.stop()
            self.tdlib_client = None
        
        logger.info("TDLib grup keşif servisi durduruldu")
    
    async def _discovery_loop(self) -> None:
        """Ana keşif döngüsü."""
        try:
            while self.running and not self.stop_event.is_set():
                logger.info("Grup keşif döngüsü başlıyor...")
                
                # İlk kaynaklardan grup keşfi
                await self._discover_from_primary_sources()
                
                # İkincil kaynaklardan grup keşfi (kullanıcı grupları)
                await self._discover_from_user_groups()
                
                # Arama bazlı grup keşfi
                await self._discover_via_search()
                
                # Sonraki döngüye kadar bekle (6 saat)
                logger.info(f"Grup keşfi tamamlandı. Toplam: {self.discovered_groups} grup keşfedildi")
                
                # Her 6 saatte bir çalıştır
                await asyncio.sleep(6 * 60 * 60)
                
        except asyncio.CancelledError:
            logger.info("Grup keşif döngüsü iptal edildi")
        except Exception as e:
            logger.error(f"Grup keşfi sırasında hata oluştu: {str(e)}", exc_info=True)
    
    async def _discover_from_primary_sources(self) -> None:
        """Ana kaynaklardan (herkese açık gruplar) grupları keşfeder"""
        try:
            # Herkese açık grupları al
            logger.info("Ana kaynaklardan gruplar keşfediliyor...")
            
            try:
                # Popüler anahtar kelimelerle herkese açık grupları ara
                public_chats = []
                search_keywords = self.group_keywords or ["sohbet", "chat", "group", "arayış"]
                
                for keyword in search_keywords:
                    logger.info(f"'{keyword}' anahtar kelimesi ile grup aranıyor...")
                    
                    try:
                        # TDLib arama metodunu kullan
                        search_result = await self.tdlib_client.search_public_chats(keyword)
                        public_chats.extend(search_result)
                        logger.info(f"'{keyword}' arama sonucu: {len(search_result)} grup bulundu")
                        
                        # Çok fazla istek göndermeyi önlemek için bekleme
                        await asyncio.sleep(2.0)
                    except Exception as keyword_err:
                        logger.error(f"Anahtar kelime araması hatası ({keyword}): {str(keyword_err)}")
                
                # Tekrarlanan grupları temizle
                unique_chats = list(set(public_chats))
                logger.info(f"Toplam {len(unique_chats)} benzersiz grup bulundu")
            except Exception as e:
                logger.error(f"Herkese açık grupları alma hatası: {str(e)}")
                public_chats = []
                    
            # Her grubu işle
            for chat_id in public_chats:
                try:
                    # Grup detaylarını al
                    chat = await self.tdlib_client.get_chat(chat_id)
                    
                    # Grup geçerli mi kontrol et
                    is_valid = await self._is_valid_group(chat_id, chat)
                    
                    if is_valid:
                        # Grup yeteneklerini analiz et
                        await self._analyze_group_capabilities(chat_id, chat)
                        
                        # Keşfedilen grubu işle
                        await self._process_discovered_group(chat_id, chat)
                        
                    # İşlem limitini aşmamak için her 3 grupta bir bekleme
                    await asyncio.sleep(1.0)
                except Exception as chat_err:
                    logger.error(f"Grup işleme hatası (ID: {chat_id}): {str(chat_err)}")
                    
            logger.info(f"Ana kaynaklardan keşif tamamlandı: {self.discovered_groups} grup keşfedildi")
                
            # Bilinen grupları yükle
            await self._load_existing_groups()
        except Exception as e:
            logger.error(f"Ana kaynaklardan keşif sırasında hata: {str(e)}")
    
    async def _discover_from_user_groups(self) -> None:
        """Kullanıcıların üye olduğu gruplardan yeni gruplar keşfeder."""
        try:
            # Veritabanından kullanıcıları çek
            if not hasattr(self.db, 'get_users_sample'):
                logger.warning("Veritabanında get_users_sample metodu yok, kullanıcı grupları keşfedilemedi")
                return
            
            # Rassal kullanıcı örneklemi al (en fazla 1000)
            users = await self.db.get_users_sample(1000)
            if not users:
                logger.info("Keşfedilecek kullanıcı bulunamadı")
                return
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Kullanıcı grupları işleniyor...", total=len(users))
                
                for user in users:
                    progress.update(task, advance=1)
                    
                    # Kullanıcının gruplarını al
                    try:
                        user_id = user['user_id']
                        user_chats = await self.tdlib_client.get_user_chats(user_id, limit=100)
                        
                        for chat_id in user_chats:
                            # Bilinen grupları atla
                            if chat_id in self.known_groups:
                                continue
                            
                            # Grup bilgilerini al
                            chat = await self.tdlib_client.get_chat(chat_id)
                            
                            # Grup kontrolü yap
                            if await self._is_valid_group(chat_id, chat):
                                await self._process_discovered_group(chat_id, chat)
                                self.discovered_groups += 1
                    
                    except Exception as e:
                        logger.debug(f"Kullanıcı grubu işleme hatası ({user.get('user_id')}): {str(e)}")
                    
                    # Rate limiting
                    await asyncio.sleep(1.0)
        
        except Exception as e:
            logger.error(f"Kullanıcı gruplarından keşif sırasında hata: {str(e)}")
    
    async def _discover_via_search(self) -> None:
        """Arama terimleri kullanarak yeni grupları keşfeder."""
        try:
            for keyword in self.group_keywords:
                logger.info(f"'{keyword}' anahtar kelimesi ile grup aranıyor...")
                
                # Arama yap
                search_results = await self.tdlib_client.search_public_chats(keyword)
                
                for chat_id in search_results:
                    # Bilinen grupları atla
                    if chat_id in self.known_groups:
                        continue
                    
                    # Grup bilgilerini al
                    chat = await self.tdlib_client.get_chat(chat_id)
                    
                    # Grup kontrolü yap
                    if await self._is_valid_group(chat_id, chat):
                        await self._process_discovered_group(chat_id, chat)
                        self.discovered_groups += 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.5)
                
                # Anahtar kelimeler arası bekleme
                await asyncio.sleep(5.0)
        
        except Exception as e:
            logger.error(f"Arama bazlı keşif sırasında hata: {str(e)}")
    
    async def _is_valid_group(self, chat_id: int, chat: Dict[str, Any]) -> bool:
        """
        Grubun geçerli bir hedef olup olmadığını kontrol eder
        
        Args:
            chat_id: Grup ID
            chat: Grup bilgileri
            
        Returns:
            bool: Geçerli ise True
        """
        try:
            # Temel kontroller
            if not chat or not isinstance(chat, dict):
                return False
                
            # Kara listede olup olmadığını kontrol et
            if chat_id in self.blacklisted_groups:
                logger.debug(f"Grup kara listede: {chat_id}")
                self.blacklisted_groups += 1
                return False
                
            # Grup türünü kontrol et
            chat_type = chat.get('type', {})
            type_name = chat_type.get('@type', '')
            
            if type_name not in ('basicGroup', 'supergroup'):
                logger.debug(f"Geçersiz grup türü: {type_name}")
                return False
                
            # Grup boyutunu kontrol et
            member_count = chat.get('member_count', 0)
            if member_count < self.min_group_size:
                logger.debug(f"Grup çok küçük: {member_count} üye (min: {self.min_group_size})")
                return False
                
            # Katılma izinlerini kontrol et
            if chat.get('joined', False):
                logger.debug(f"Gruba zaten katılmışız: {chat_id}")
                return True
                
            # Anahtar kelimeleri kontrol et (opsiyonel)
            title = chat.get('title', '').lower()
            description = chat.get('description', '').lower()
            
            has_keyword = False
            for keyword in self.group_keywords:
                if keyword.lower() in title or keyword.lower() in description:
                    has_keyword = True
                    break
                    
            return has_keyword
            
        except Exception as e:
            logger.error(f"Grup geçerlilik kontrolü hatası: {str(e)}")
            return False

    async def _analyze_group_capabilities(self, chat_id: int, chat: Dict[str, Any]) -> None:
        """
        Grubun yeteneklerini analiz eder (mesaj gönderimi, üyelik, vb.).
        
        Args:
            chat_id: Grup ID'si
            chat: Grup bilgileri
        """
        capabilities = {
            'can_send_messages': False,
            'can_invite_users': False,
            'has_username': bool(chat.get('username')),
            'is_public': bool(chat.get('username')),
            'member_count': chat.get('member_count', 0),
            'last_analyzed': datetime.now()
        }
        
        try:
            # Temel izinleri kontrol et
            permissions = chat.get('permissions', {})
            capabilities['can_send_messages'] = permissions.get('can_send_messages', False)
            capabilities['can_invite_users'] = permissions.get('can_invite_users', False)
            
            # Gruba katılabiliyor muyuz?
            capabilities['can_join'] = await self._can_join_group(chat_id, chat)
            
            # Başka analizler...
            
            # Yetenekleri kaydet
            self.group_capabilities[chat_id] = capabilities
            
        except Exception as e:
            logger.debug(f"Grup yetenek analizi hatası: {str(e)}")
    
    async def _can_join_group(self, chat_id: int, chat: Dict[str, Any]) -> bool:
        """
        Gruba katılabilme durumunu kontrol eder.
        
        Args:
            chat_id: Grup ID'si
            chat: Grup bilgileri
            
        Returns:
            bool: Katılabilirse True
        """
        if chat.get('is_member', False):
            return True
            
        # Grup türüne göre kontrol
        chat_type = chat.get('type', {}).get('@type')
        
        if chat_type == 'supergroup' or chat_type == 'channel':
            # Herkese açık grup/kanal
            if chat.get('username'):
                return True
        elif chat_type == 'basicGroup':
            # Temel grup - davetiye gerekebilir
            return False
        
        return False
    
    async def _process_discovered_group(self, chat_id: int, chat: Dict[str, Any]) -> None:
        """
        Keşfedilen grubu işler
        
        Args:
            chat_id: Grup ID
            chat: Grup bilgileri
        """
        try:
            # Önce yetenek analizi yap
            if chat_id not in self.group_capabilities:
                await self._analyze_group_capabilities(chat_id, chat)
            
            capabilities = self.group_capabilities.get(chat_id, {})
            
            # Grup verilerini hazırla
            group_data = {
                'group_id': chat_id,
                'title': chat.get('title', f"Group {chat_id}"),
                'username': chat.get('username', ''),
                'description': chat.get('description', ''),
                'member_count': chat.get('member_count', 0),
                'is_public': 'username' in chat and bool(chat['username']),
                'can_send_messages': capabilities.get('can_send_messages', False),
                'is_member': chat.get('joined', False)
            }
            
            # Veritabanına ekle/güncelle
            if hasattr(self.db, 'add_discovered_group'):
                result = await self._run_async_db_method(
                    self.db.add_discovered_group, 
                    group_data
                )
                
                if result == "added":
                    # İstatistikleri güncelle
                    self.discovered_groups += 1
                    logger.info(f"Yeni grup keşfedildi: {group_data['title']} (ID: {chat_id})")
                    
                    # Gruba katılma (opsiyonel)
                    if self.auto_join and capabilities.get('can_invite_users', False):
                        await self._try_join_group(chat_id, group_data)
                
            # Bilinen grupları güncelle
            self.known_groups.add(chat_id)
                
        except Exception as e:
            logger.error(f"Keşfedilen grubu işleme hatası: {str(e)}")
    
    async def _join_group(self, chat_id: int, chat: Dict[str, Any]) -> bool:
        """
        Gruba katılır.
        
        Args:
            chat_id: Grup ID'si
            chat: Grup bilgileri
            
        Returns:
            bool: Katılım başarılı ise True
        """
        try:
            # Gruba nasıl katılacağımızı belirle
            if chat.get('username'):
                # Kullanıcı adı ile katıl
                await self.tdlib_client.join_chat_by_username(chat.get('username'))
            elif chat.get('invite_link'):
                # Davet bağlantısı ile katıl
                await self.tdlib_client.join_chat_by_invite_link(chat.get('invite_link'))
            else:
                logger.warning(f"Gruba katılmak için yöntem bulunamadı: {chat_id}")
                return False
            
            logger.info(f"Gruba başarıyla katıldı: {chat.get('title')} ({chat_id})")
            self.joined_groups += 1
            
            return True
        
        except Exception as e:
            logger.error(f"Gruba katılma hatası: {str(e)}")
            return False
    
    async def _receive_loop(self):
        """TDLib'den sürekli yanıt alma döngüsü"""
        while not self.is_closed:
            try:
                # TDLib'den güncelleme al
                event = self.client.receive(timeout=1.0)
                
                if event:
                    # Event'i işle
                    await self._process_event(event)
                    
                # Her döngü arasında kısa bekleme
                await asyncio.sleep(0.001)  # Event loop tıkanmasını önler
            except asyncio.CancelledError:
                logger.info("TDLib alma döngüsü iptal edildi")
                break
            except Exception as e:
                logger.error(f"TDLib alma döngüsü hatası: {str(e)}")
                await asyncio.sleep(1.0)  # Hata durumunda biraz bekle

    async def _process_event(self, event):
        """
        TDLib olayını işle
        
        Args:
            event: TDLib olayı
        """
        if '@extra' in event and event['@extra'] in self.requests:
            future = self.requests.pop(event['@extra'])
            if not future.done():
                future.set_result(event)
        elif event.get('@type') == 'updateAuthorizationState':
            await self._process_auth_state(event['authorization_state'])
        else:
            # Diğer güncellemeler
            for handler in self.update_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"TDLib olay işleyici hatası: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Keşif istatistiklerini döndürür.
        
        Returns:
            Dict[str, Any]: İstatistikler
        """
        return {
            'discovered_groups': self.discovered_groups,
            'joined_groups': self.joined_groups,
            'blacklisted_groups': self.blacklisted_groups,
            'known_groups': len(self.known_groups),
            'analyzed_groups': len(self.group_capabilities)
        }