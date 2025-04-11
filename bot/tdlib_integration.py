"""
# ============================================================================ #
# Dosya: tdlib_integration.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/tdlib_integration.py
# İşlev: TDLib (Telegram Database Library) entegrasyonu ve grup keşfi.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""
import json
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

import pytdlib as td
from pytdlib.client import TdClient
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, SpinnerColumn

from database.user_db import UserDatabase

logger = logging.getLogger(__name__)
console = Console()

class TelegramDiscoveryService:
    """
    TDLib kullanarak Telegram grupları keşfetme ve izleme servisi.
    
    Bu servis:
    1. Henüz üye olunmayan grupları keşfeder
    2. Grupları analiz eder ve kategorize eder
    3. Uygun grupları veritabanına kaydeder
    4. İsteğe bağlı olarak bu gruplara otomatik katılır
    """
    
    def __init__(self, db: UserDatabase, config: Any, stop_event: asyncio.Event = None):
        """
        TelegramDiscoveryService başlatıcısı
        
        Args:
            db: Veritabanı bağlantısı
            config: Yapılandırma ayarları
            stop_event: Durdurma sinyali
        """
        self.db = db
        self.config = config
        self.stop_event = stop_event or asyncio.Event()
        self.running = False
        self.tdlib_client = None
        
        # İstatistikler
        self.discovered_groups = 0
        self.joined_groups = 0
        self.blacklisted_groups = 0
        
        # Grup izleme
        self.known_groups: Set[int] = set()
        self.group_capabilities: Dict[int, Dict[str, Any]] = {}
        
        # Yapılandırma
        self._load_settings()
    
    def _load_settings(self) -> None:
        """TDLib ayarlarını yükler."""
        # TDLib yapılandırması
        self.api_id = self.config.telegram.api_id
        self.api_hash = self.config.telegram.api_hash
        self.phone = getattr(self.config.telegram, 'phone', '')
        
        # Grup keşif ayarları
        self.auto_join = getattr(self.config, 'auto_join_groups', False)
        self.min_group_size = getattr(self.config, 'min_group_size', 30)
        self.group_blacklist = getattr(self.config, 'group_blacklist', [])
        self.group_keywords = getattr(self.config, 'group_keywords', 
                                     ['chat', 'sohbet', 'muhabbet', 'arkadaş',
                                      'friend', 'talk', 'omegle', 'aşk', 'ask', 'arayış', 'arayis'])
    
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
        """Ana kaynaklardan (herkese açık gruplar) grupları keşfeder."""
        try:
            # Herkese açık grupları al
            public_chats = await self.tdlib_client.get_chats(limit=1000)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Ana grupları işleniyor...", total=len(public_chats))
                
                for chat_id in public_chats:
                    progress.update(task, advance=1)
                    
                    # Bilinen grupları atla
                    if chat_id in self.known_groups:
                        continue
                    
                    # Grup bilgilerini al
                    chat = await self.tdlib_client.get_chat(chat_id)
                    
                    # Grup kontrolü yap
                    if await self._is_valid_group(chat_id, chat):
                        await self._process_discovered_group(chat_id, chat)
                        self.discovered_groups += 1
                    
                    # Rate limiting - Telegram API sınırlamalarına takılmamak için
                    await asyncio.sleep(0.5)
        
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
        Grubun geçerli bir hedef olup olmadığını kontrol eder.
        
        Args:
            chat_id: Grup ID'si
            chat: Grup bilgileri
            
        Returns:
            bool: Grup geçerli ise True
        """
        try:
            # Temel tip kontrolü
            if chat.get('type', {}).get('@type') not in ['supergroup', 'basicGroup', 'channel']:
                return False
            
            # Karaliste kontrolü
            if chat_id in self.group_blacklist:
                return False
            
            # Minimum üye sayısı kontrolü
            member_count = chat.get('member_count', 0)
            if member_count < self.min_group_size:
                return False
            
            # Başarılı kontrollerden sonra, grubun yeteneklerini analiz et
            await self._analyze_group_capabilities(chat_id, chat)
            
            return True
        
        except Exception as e:
            logger.debug(f"Grup geçerlilik kontrolü hatası: {str(e)}")
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
        Keşfedilen bir grubu işler.
        
        Args:
            chat_id: Grup ID'si
            chat: Grup bilgileri
        """
        try:
            # Grubun yeteneklerine bak
            capabilities = self.group_capabilities.get(chat_id, {})
            
            # Grup verisini hazırla
            group_data = {
                'group_id': chat_id,
                'title': chat.get('title', f'Group {chat_id}'),
                'username': chat.get('username', ''),
                'member_count': chat.get('member_count', 0),
                'description': chat.get('description', ''),
                'is_public': bool(chat.get('username')),
                'can_send_messages': capabilities.get('can_send_messages', False),
                'can_invite_users': capabilities.get('can_invite_users', False),
                'can_join': capabilities.get('can_join', False),
                'is_member': chat.get('is_member', False),
                'discovery_date': datetime.now()
            }
            
            # Veritabanına kaydet
            if hasattr(self.db, 'add_discovered_group'):
                await self.db.add_discovered_group(group_data)
            
            # Gruba otomatik katıl
            if self.auto_join and capabilities.get('can_join', False) and not chat.get('is_member', False):
                await self._join_group(chat_id, chat)
            
            # Bilinen gruplara ekle
            self.known_groups.add(chat_id)
            
        except Exception as e:
            logger.error(f"Grup işleme hatası: {str(e)}")
    
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