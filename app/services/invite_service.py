"""
Telegram bot için otomatik davet gönderme servisi (yeni konum).
Tüm eski InviteService mantığı buraya taşınacak ve güncellenecek.
"""

import os
import json
import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import functools

from telethon import errors
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class InviteService(BaseService):
    """Davet servisi (app/services altında yeni yapı)."""
    
    def __init__(self, client, config, db, stop_event=None):
        super().__init__("invite", client, config, db, stop_event)
        self.invite_batch_size = getattr(config, 'invite_batch_size', 50)
        self.last_message_times = {}
        self.sent_count = 0
        self.error_count = 0
        self.stats = {'total_sent': 0, 'failed_sends': 0, 'last_send_time': None}
        self.batch_size = 5
        self.interval_minutes = 60
        self.daily_limit = 50
        self.hourly_limit = 15
        self.invite_stats = {'total_sent': 0, 'daily_sent': 0, 'success': 0, 'failed': 0}
        self.invite_cooldown_minutes = 5
        self._setup_rate_limiter()
        self.group_links = self._parse_group_links()
        self.invite_templates = self._load_invite_templates()
        self.running = True
        self.stop_event = stop_event or asyncio.Event()
        self.services = {}

    def _setup_rate_limiter(self):
        from app.utils.adaptive_rate_limiter import AdaptiveRateLimiter
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=15.0,
            period=60,
            error_backoff=1.2,
            max_jitter=0.5
        )
        self.invite_state = {
            'burst_count': 0,
            'hourly_count': 0,
            'hour_start': datetime.now(),
            'last_invite_time': None,
            'consecutive_errors': 0
        }
        self.limits = {
            'hourly_max': 100,
            'daily_max': 500,
            'burst_size': 20,
            'burst_cooldown': 2,
            'error_cooldown': 15
        }

    def _parse_group_links(self) -> List[str]:
        group_links = []
        env_links = os.environ.get("GROUP_LINKS", "")
        if env_links:
            links = [link.strip() for link in env_links.split(",") if link.strip()]
            group_links.extend(links)
        if hasattr(self.config, 'GROUP_LINKS'):
            config_links = self.config.GROUP_LINKS
            if isinstance(config_links, list):
                group_links.extend(config_links)
            elif isinstance(config_links, str):
                links = [link.strip() for link in config_links.split(",") if link.strip()]
                group_links.extend(links)
        if hasattr(self.db, 'get_group_links'):
            try:
                db_links = self.db.get_group_links()
                if db_links:
                    group_links.extend(db_links)
            except Exception as e:
                logger.warning(f"Veritabanından grup bağlantıları alınamadı: {e}")
        return list(dict.fromkeys(group_links))

    def _load_invite_templates(self) -> List[str]:
        try:
            if hasattr(self.config, 'INVITE_TEMPLATES'):
                templates = self.config.INVITE_TEMPLATES
                if templates:
                    logger.info(f"{len(templates)} davet şablonu konfigürasyondan yüklendi")
                    return templates
            template_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "templates.json"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "invites.json"),
                "data/templates.json",
                "data/invites.json"
            ]
            for path in template_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            if "invites" in data:
                                templates = data["invites"]
                                if templates:
                                    logger.info(f"{len(templates)} davet şablonu {path} dosyasından yüklendi")
                                    return templates
                            elif "templates" in data:
                                templates = data["templates"]
                                if templates:
                                    logger.info(f"{len(templates)} davet şablonu {path} dosyasından yüklendi")
                                    return templates
                        elif isinstance(data, list):
                            if data:
                                logger.info(f"{len(data)} davet şablonu {path} dosyasından yüklendi")
                                return data
        except Exception as e:
            logger.error(f"Davet şablonları yüklenemedi: {str(e)}")
        default_templates = [
            "Merhaba! Grubuma katılmak ister misin?",
            "Selam! Telegram gruplarımıza bekliyoruz!",
            "Merhaba, sohbet gruplarımıza göz atmak ister misin?",
            "Selam {name}! Gruplarımıza davetlisin!",
            "Merhaba, yeni sohbet arkadaşları arıyorsan gruplarımıza bekleriz."
        ]
        logger.info(f"{len(default_templates)} varsayılan davet şablonu kullanılıyor")
        return default_templates

    async def _run_async_db_method(self, method, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(method, *args, **kwargs))

    async def _get_users_for_invite(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            if hasattr(self.db, 'get_users_for_invite'):
                try:
                    users = await self._run_async_db_method(self.db.get_users_for_invite, limit)
                    if users and len(users) > 0:
                        return users
                except Exception as e:
                    logger.error(f"Veritabanından davet edilecek kullanıcıları alma hatası: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Davet edilecek kullanıcıları alma hatası: {str(e)}")
            return []

    async def _get_user_entity(self, user_id, username=None):
        try:
            try:
                return await self.client.get_entity(user_id)
            except ValueError:
                pass
            if username:
                try:
                    return await self.client.get_entity(f"@{username}")
                except ValueError:
                    pass
            if hasattr(self.db, 'get_user_by_id'):
                user_info = await self._run_async_db_method(self.db.get_user_by_id, user_id)
                if user_info and user_info.get('username'):
                    try:
                        return await self.client.get_entity(f"@{user_info['username']}")
                    except ValueError:
                        pass
            return None
        except Exception as e:
            logger.error(f"Entity alımı sırasında hata: {str(e)}")
            return None

    async def _get_group_members(self, group_id, limit=50):
        try:
            members = []
            offset = 0
            total_retrieved = 0
            from telethon import functions as tfunc, tl
            while total_retrieved < limit:
                try:
                    participants = await self.client(tfunc.channels.GetParticipantsRequest(
                        channel=group_id,
                        filter=tl.types.ChannelParticipantsRecent(),
                        offset=offset,
                        limit=100,
                        hash=0
                    ))
                    if not participants.users:
                        break
                    for user in participants.users:
                        if not user.bot:
                            members.append({
                                'id': user.id,
                                'username': user.username,
                                'first_name': user.first_name,
                                'last_name': user.last_name
                            })
                            total_retrieved += 1
                            if total_retrieved >= limit:
                                break
                    offset += len(participants.users)
                except Exception as e:
                    logger.error(f"Grup üyelerini alırken hata: {str(e)}")
                    break
            return members
        except Exception as e:
            logger.error(f"Grup üyelerini çekerken hata: {str(e)}")
            return []

    async def _process_user(self, user):
        try:
            user_id = user.get("user_id")
            username = user.get("username")
            first_name = user.get("first_name", "Kullanıcı")
            try:
                user_entity = await self.client.get_entity(user_id)
            except ValueError as e:
                logger.warning(f"Kullanıcı bulunamadı: {user_id} - {str(e)}")
                if hasattr(self.db, 'mark_user_not_found'):
                    await self._run_async_db_method(self.db.mark_user_not_found, user_id)
                return False
            invite_template = random.choice(self.invite_templates)
            personalized_message = invite_template.replace("{name}", first_name or "değerli kullanıcı")
            group_links_text = ""
            if self.group_links:
                group_links_text = "\n\n" + "\n".join([f"• {link}" for link in self.group_links])
            try:
                await self.client.send_message(
                    user_entity, 
                    personalized_message + group_links_text,
                    link_preview=False
                )
            except Exception as e:
                logger.error(f"Hata oluştu: {str(e)}")
            self.rate_limiter.mark_used()
            if hasattr(self.db, 'mark_user_invited'):
                await self._run_async_db_method(self.db.mark_user_invited, user_id)
            return True
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError davet gönderirken: {wait_time} saniye bekleniyor")
            self.rate_limiter.register_error(e)
            await asyncio.sleep(wait_time + 1)
            return False
        except errors.UserPrivacyRestrictedError:
            logger.info(f"Kullanıcı gizlilik ayarları nedeniyle mesaj kabul etmiyor: {user_id}")
            return False
        except Exception as e:
            logger.error(f"Kullanıcı işleme hatası ({user_id}): {str(e)}")
            return False

    async def _send_invites(self, aggressive=False):
        try:
            users = await self._run_async_db_method(
                self.db.get_users_for_invite, 
                self.invite_batch_size
            )
            if not users or len(users) == 0:
                logger.warning("Davet için uygun kullanıcı bulunamadı")
                return 0
            sent_count = 0
            for user in users:
                if await self._process_user(user):
                    sent_count += 1
                await asyncio.sleep(random.randint(10, 30))
            logger.info(f"💌 Davet gönderim döngüsü tamamlandı. Toplam: {sent_count}")
            self.sent_count += sent_count
            return sent_count
        except Exception as e:
            logger.error(f"_send_invites genel hatası: {str(e)}")
            return 0

    async def _aggressive_user_discovery(self):
        discovered = 0
        try:
            if 'group' in self.services and hasattr(self.services['group'], 'get_groups'):
                groups = await self.services['group'].get_groups(True)
                for group in groups:
                    group_id = group.get('chat_id') or group.get('id')
                    logger.info(f"Gruptan üye çekiliyor: {group.get('title', 'Bilinmeyen')} ({group_id})")
                    try:
                        members = await self._get_group_members(group_id, limit=50)
                        for member in members:
                            user_id = member.get('id')
                            if user_id and hasattr(self.db, 'add_user_if_not_exists'):
                                await self._run_async_db_method(
                                    self.db.add_user_if_not_exists,
                                    user_id,
                                    member.get('username'),
                                    member.get('first_name'),
                                    member.get('last_name')
                                )
                                discovered += 1
                    except Exception as e:
                        logger.error(f"Grup üyelerini çekerken hata: {str(e)}")
            if discovered == 0:
                if hasattr(self.db, 'reset_invite_cooldowns'):
                    reset_count = await self._run_async_db_method(self.db.reset_invite_cooldowns)
                    logger.info(f"Davet süresi sıfırlanan kullanıcı sayısı: {reset_count}")
            logger.info(f"Agresif keşifte bulunan toplam kullanıcı: {discovered}")
            return discovered
        except Exception as e:
            logger.error(f"Agresif kullanıcı keşfi hatası: {str(e)}")
            return 0

    async def run(self):
        logger.info("Davet servisi başlatıldı")
        while self.running and not self.stop_event.is_set():
            try:
                await self._aggressive_user_discovery()
                sent_count = await self._send_invites(aggressive=True)
                if sent_count > 0:
                    logger.info(f"✅ {sent_count} kullanıcıya davet gönderildi!")
                    wait_time = 30
                else:
                    wait_time = 60
                logger.info(f"⏳ Sonraki davet gönderimi için {wait_time//60} dakika {wait_time%60} saniye bekleniyor...")
                for _ in range(wait_time):
                    if not self.running or self.stop_event.is_set():
                        break
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Davet servis döngüsü hatası: {str(e)}")
                await asyncio.sleep(10)

    async def stop(self) -> None:
        self.running = False
        logger.info("Davet servisi durdurma sinyali gönderildi")

    async def pause(self) -> None:
        if self.running:
            self.running = False
            logger.info("Davet servisi duraklatıldı")

    async def resume(self) -> None:
        if not self.running:
            self.running = True
            logger.info("Davet servisi devam ettiriliyor")

    def set_services(self, services: Dict[str, Any]) -> None:
        self.services = services
        logger.debug(f"{self.name} servisi diğer servislere bağlandı")

    async def initialize(self) -> bool:
        await super().initialize()
        self._can_use_dialogs = True
        self._can_invite_users = True
        logger.info("✅ Davet servisi kullanıcı hesabı ile çalışıyor, tüm özellikler etkin.")
        return True
