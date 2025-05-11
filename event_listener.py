import asyncio
import logging
from datetime import datetime
import os
import json
import random
from pathlib import Path
from dotenv import load_dotenv

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("event_listener")

# .env dosyasını yükle
load_dotenv()

# Mesaj şablonları
MESSAGES_FILE = Path('data/messages.json')
DM_TEMPLATES_FILE = Path('data/dm_templates.json')

# YENİ: Mesaj etkileşim takibi modelleri
from app.models.messaging import MessageEffectivenessCreate, DMConversionCreate, ConversionType

async def load_templates():
    """Mesaj şablonlarını yükler"""
    templates = {
        "messages": {},
        "dm_templates": {}
    }
    
    try:
        if MESSAGES_FILE.exists():
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                templates["messages"] = json.load(f)
                logger.info(f"Mesaj şablonları yüklendi: {len(templates['messages'])} kategori")
                
        if DM_TEMPLATES_FILE.exists():
            with open(DM_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                templates["dm_templates"] = json.load(f)
                logger.info(f"DM şablonları yüklendi: {len(templates['dm_templates'])} kategori")
    except Exception as e:
        logger.error(f"Şablonları yükleme hatası: {str(e)}")
        
    return templates

async def main():
    logger.info("Telegram olay dinleyicisi başlatılıyor...")
    
    try:
        # Telethon istemci
        from telethon import TelegramClient, events
        from telethon.tl.types import UpdateNewChannelMessage, UpdateNewMessage, User
        
        # API bilgilerini al
        api_id = int(os.getenv("TELEGRAM_API_ID", "20812967"))
        api_hash = os.getenv("TELEGRAM_API_HASH", "5dc3dd519e252c8553ae9e0b4ac0ced8")
        
        # İstemciyi oluştur
        client = TelegramClient("telegram_session", api_id, api_hash)
        await client.start()
        
        me = await client.get_me()
        logger.info(f"Telegram oturumu başlatıldı: {me.first_name} (@{me.username})")
        
        # Veritabanı bağlantısı
        from sqlalchemy import text
        from app.db.session import get_session
        
        session = next(get_session())
        
        # Şablonları yükle
        templates = await load_templates()
        
        # YENİ: Mesaj analitik servisini başlat
        from app.services.analytics.message_analytics_service import MessageAnalyticsService
        
        # Analitik servisini oluştur
        message_analytics = MessageAnalyticsService()
        await message_analytics._start()
        
        # Zamanlanmış yanıt verme için zamanlayıcı
        last_auto_message = datetime.now()
        # 3-7 dakika arası rastgele süre (saniye cinsinden)
        auto_message_interval_min = 3 * 60  # 3 dakika
        auto_message_interval_max = 7 * 60  # 7 dakika
        auto_message_interval = random.randint(auto_message_interval_min, auto_message_interval_max)
        
        # Aktif grupları al
        groups_query = text("""
            SELECT group_id, name, is_active
            FROM groups
            WHERE is_active = TRUE
        """)
        groups = session.execute(groups_query).fetchall()
        group_ids = [str(g[0]) for g in groups]
        
        logger.info(f"Dinlenen gruplar: {len(group_ids)}")
        logger.info(f"Otomatik mesaj aralığı: {auto_message_interval//60} dakika {auto_message_interval%60} saniye")
        
        ######### YENİ EKLENDİ: Otomatik yanıtlar için sayaçlar #########
        # Yanıt istatistikleri
        reply_stats = {
            "total_replies": 0,
            "group_replies": 0,
            "mention_replies": 0,
            "dm_invitations": 0
        }
        
        # Son yanıt verilen kullanıcılar ve gruplar
        last_replied_users = {}
        last_replied_groups = {}
        
        # Kullanıcı başına limitleme (spam önleme)
        user_reply_limit = 3  # Bir kullanıcıya günde max yanıt sayısı
        group_message_limit = 20  # Bir gruba günde max mesaj sayısı (artırıldı)
        
        # Son aktivite zamanları
        last_activity = datetime.now()
        
        # YENİ: Son mesaj ID'leri (DM dönüşümlerini takip etmek için)
        last_sent_messages = {}  # {group_id: {message_id: message_db_id}}
        
        @client.on(events.NewMessage)
        async def handle_messages(event):
            """Yeni mesajları yakalar ve işler"""
            nonlocal last_auto_message, last_activity, auto_message_interval
            
            try:
                # Mesaj kaynağını al
                if event.is_group or event.is_channel:
                    # Grup mesajı
                    chat = await event.get_chat()
                    chat_id = str(chat.id)
                    chat_title = chat.title
                    
                    # Verinin SQL'de güvenli şekilde tutulması için unicode'u temizle
                    if hasattr(chat, 'title'):
                        chat_title = chat.title.encode('utf-8', errors='ignore').decode('utf-8')
                    else:
                        chat_title = "İsimsiz Grup"
                    
                    # Grup kontrolü, bilinen bir grup mu?
                    if chat_id not in group_ids:
                        logger.info(f"Yeni grup tespit edildi: {chat_title} ({chat_id})")
                        
                        # Yeni grubu veritabanına ekle
                        insert_group_query = text("""
                            INSERT INTO groups (group_id, name, is_active, member_count, created_at)
                            VALUES (:group_id, :name, :is_active, :member_count, NOW())
                            ON CONFLICT (group_id) DO UPDATE 
                            SET name = :name, is_active = TRUE, updated_at = NOW()
                        """)
                        
                        session.execute(
                            insert_group_query, 
                            {
                                "group_id": int(chat_id), 
                                "name": chat_title, 
                                "is_active": True,
                                "member_count": getattr(chat, 'participants_count', 0)
                            }
                        )
                        session.commit()
                        
                        # Grup listesini güncelle
                        group_ids.append(chat_id)
                    
                    # Mesaj sahibini al
                    sender = await event.get_sender()
                    
                    # Kullanıcı kontrolü
                    if sender:
                        try:
                            # Yeni bir session oluştur ve kullan
                            user_session = next(get_session())
                            
                            user_query = text("""
                                SELECT * FROM users WHERE user_id = :user_id
                            """)
                            
                            user = None
                            try:
                                result = user_session.execute(user_query, {"user_id": sender.id})
                                user = result.first()
                            except Exception as e:
                                logger.error(f"Kullanıcı sorgulama hatası: {str(e)}")
                                # Hatalı işlemi geri al
                                user_session.rollback()
                                
                            if not user:
                                # Önce sütunların varlığını kontrol et
                                columns_query = text("""
                                    SELECT column_name 
                                    FROM information_schema.columns 
                                    WHERE table_name = 'users'
                                """)
                                
                                columns = None
                                try:
                                    columns_result = user_session.execute(columns_query)
                                    columns = [row[0] for row in columns_result.fetchall()]
                                except Exception as e:
                                    logger.error(f"Sütun sorgulama hatası: {str(e)}")
                                    # Hatalı işlemi geri al
                                    user_session.rollback()
                                    
                                if columns:
                                    # Kullanıcıyı ekle
                                    insert_query = """
                                        INSERT INTO users (
                                            user_id, first_name, last_name, username, 
                                            last_active, is_active
                                    """
                                    
                                    # is_bot sütunu varsa ekle
                                    if 'is_bot' in columns:
                                        insert_query += ", is_bot"
                                    
                                    insert_query += """
                                        ) VALUES (
                                            :user_id, :first_name, :last_name, :username, 
                                            NOW(), :is_active
                                    """
                                    
                                    # is_bot değerini ekle
                                    if 'is_bot' in columns:
                                        insert_query += ", :is_bot"
                                    
                                    insert_query += """
                                        ) ON CONFLICT (user_id) DO UPDATE 
                                        SET last_active = NOW(), updated_at = NOW()
                                    """
                                    
                                    params = {
                                        "user_id": sender.id,
                                        "first_name": getattr(sender, 'first_name', ''),
                                        "last_name": getattr(sender, 'last_name', ''),
                                        "username": getattr(sender, 'username', ''),
                                        "is_active": True
                                    }
                                    
                                    # is_bot parametresi
                                    if 'is_bot' in columns:
                                        params["is_bot"] = getattr(sender, 'bot', False)
                                    
                                    try:
                                        user_session.execute(text(insert_query), params)
                                        user_session.commit()
                                    except Exception as e:
                                        logger.error(f"Kullanıcı ekleme hatası: {str(e)}")
                                        # Hatalı işlemi geri al ve session'ı kapat
                                        user_session.rollback()
                        
                            # Session'ı kapat
                            user_session.close()
                            
                        except Exception as e:
                            logger.error(f"Kullanıcı işleme hatası: {str(e)}")
                            try:
                                # Ana session'ı temizle
                                session.rollback()
                            except:
                                pass
                    
                    # Kullanıcı aktivitesini güncelle
                    last_activity = datetime.now()
                    
                    # Mesaj içeriğini kontrol et
                    message_text = event.message.text if event.message.text else ""
                    
                    # YENİ: Gönderdiğimiz mesajlara verilen tepkileri izle
                    if event.message.reply_to_msg_id:
                        group_messages = last_sent_messages.get(chat_id, {})
                        if event.message.reply_to_msg_id in group_messages:
                            # Mesajımıza yanıt verildi, metrikleri güncelle
                            tracked_message_id = group_messages[event.message.reply_to_msg_id]
                            await message_analytics.update_message_metrics(
                                tracked_message_id, 
                                {"replies": 1}  # Yanıt sayısını artır
                            )
                            logger.debug(f"Mesaj yanıtı takip edildi: Mesaj ID={tracked_message_id}")
                    
                    # Mentions işle - bize mention edildiğinde yanıt ver
                    if me.username and f"@{me.username}" in message_text:
                        logger.info(f"Mention tespit edildi: {chat_title} - {message_text[:50]}...")
                        
                        # Mention yanıtı oluştur
                        await handle_mention(event, sender, chat)
                    
                    # Otomatik mesaj gönderme (aralık kontrolü ile)
                    time_diff = (datetime.now() - last_auto_message).total_seconds()
                    
                    if time_diff > auto_message_interval:
                        # 3-7 dakika arasında bir proaktif engaging mesajı gönder
                        await broadcast_engaging_messages(client, templates)
                        last_auto_message = datetime.now()
                        # Sonraki mesaj için yeni rastgele aralık belirle
                        auto_message_interval = random.randint(auto_message_interval_min, auto_message_interval_max)
                        logger.info(f"Sonraki otomatik mesaj aralığı: {auto_message_interval//60} dakika {auto_message_interval%60} saniye")
                        
                elif event.is_private:
                    # DM mesajı
                    sender = await event.get_sender()
                    
                    if sender and not sender.bot:
                        logger.info(f"DM alındı: {sender.first_name} (@{sender.username}) - {event.message.text[:50]}...")
                        
                        # Kullanıcıyı veritabanına ekle
                        user_query = text("""
                            SELECT * FROM users WHERE user_id = :user_id
                        """)
                        
                        user = session.execute(user_query, {"user_id": sender.id}).first()
                        
                        if not user:
                            # Kullanıcıyı ekle
                            insert_query = text("""
                                INSERT INTO users (user_id, first_name, last_name, username, 
                                                last_active, is_active, is_bot)
                                VALUES (:user_id, :first_name, :last_name, :username, 
                                        NOW(), :is_active, :is_bot)
                                ON CONFLICT (user_id) DO UPDATE 
                                SET last_active = NOW(), updated_at = NOW()
                            """)
                            
                            session.execute(
                                insert_query, 
                                {
                                    "user_id": sender.id,
                                    "first_name": getattr(sender, 'first_name', ''),
                                    "last_name": getattr(sender, 'last_name', ''),
                                    "username": getattr(sender, 'username', ''),
                                    "is_active": True,
                                    "is_bot": getattr(sender, 'bot', False)
                                }
                            )
                            session.commit()
                        
                        # DM'e yanıt ver (grup ve kanal davetleri)
                        await handle_direct_message(event, sender)
            
            except Exception as e:
                logger.error(f"Mesaj işleme hatası: {str(e)}", exc_info=True)
        
        async def handle_mention(event, sender, chat):
            """Mention'a yanıt verir"""
            try:
                # Mention sayacını artır
                reply_stats["mention_replies"] += 1
                
                # Kullanıcı spam kontrolü
                user_id = str(sender.id)
                if user_id in last_replied_users:
                    if last_replied_users[user_id] >= user_reply_limit:
                        logger.info(f"Kullanıcı için günlük mention yanıt limiti aşıldı: {user_id}")
                        return
                    last_replied_users[user_id] += 1
                else:
                    last_replied_users[user_id] = 1
                
                # Rastgele bir mention yanıtı seç
                if "question" in templates["messages"]:
                    reply_text = random.choice(templates["messages"]["question"])
                    sent_message = await event.reply(reply_text)
                    
                    # YENİ: Gönderilen mesajı takip et
                    message_data = MessageEffectivenessCreate(
                        message_id=sent_message.id,
                        group_id=chat.id,
                        content=reply_text,
                        category="question"
                    )
                    tracked_message = await message_analytics.track_message(message_data)
                    
                    if tracked_message:
                        # Mesaj takibini bellekte sakla
                        if str(chat.id) not in last_sent_messages:
                            last_sent_messages[str(chat.id)] = {}
                        last_sent_messages[str(chat.id)][sent_message.id] = tracked_message.id
                    
                    # Yanıt sonrası kullanıcıyı DM'e davet et (50% şans)
                    if random.random() < 0.5:
                        try:
                            dm_message = random.choice(templates["dm_templates"]["response_invite"])
                            dm_sent = await client.send_message(sender.id, dm_message)
                            reply_stats["dm_invitations"] += 1
                            logger.info(f"DM daveti gönderildi: {sender.id}")
                            
                            # YENİ: DM dönüşümünü takip et
                            if tracked_message:
                                conversion_data = DMConversionCreate(
                                    user_id=sender.id,
                                    source_message_id=tracked_message.id,
                                    group_id=chat.id,
                                    conversion_type=ConversionType.INVITE_CLICK
                                )
                                await message_analytics.track_dm_conversion(conversion_data)
                        except Exception as e:
                            logger.error(f"DM daveti gönderme hatası: {str(e)}")
            except Exception as e:
                logger.error(f"Mention yanıtlama hatası: {str(e)}")
        
        async def handle_direct_message(event, sender):
            """DM yanıtlarını işler"""
            try:
                user_id = sender.id
                message_text = event.message.text
                
                # DM ilk mesaj mı? (karşılama)
                user_query = text("""
                    SELECT COUNT(*) as msg_count
                    FROM user_messages
                    WHERE user_id = :user_id
                """)
                
                result = session.execute(user_query, {"user_id": user_id}).fetchone()
                msg_count = result[0] if result else 0
                
                # YENİ: DM dönüşüm metriklerini güncelle
                # Kullanıcının hangi gruptan geldiğini bul
                user_from_group_query = text("""
                    SELECT group_id
                    FROM dm_conversions
                    WHERE user_id = :user_id
                    ORDER BY converted_at DESC
                    LIMIT 1
                """)
                
                group_result = session.execute(user_from_group_query, {"user_id": user_id}).fetchone()
                
                if group_result:
                    # Kullanıcının dönüşüm kaydı var, dönüşüm metriklerini güncelle
                    conversion_update_query = text("""
                        UPDATE dm_conversions
                        SET message_count = message_count + 1,
                            updated_at = NOW(),
                            is_successful = TRUE
                        WHERE user_id = :user_id
                        ORDER BY converted_at DESC
                        LIMIT 1
                        RETURNING id
                    """)
                    
                    update_result = session.execute(conversion_update_query, {"user_id": user_id}).fetchone()
                    
                    if update_result:
                        conversion_id = update_result[0]
                        logger.debug(f"DM dönüşüm metrikleri güncellendi: ID={conversion_id}, Kullanıcı={user_id}")
                
                # Mesajı kaydet
                insert_msg_query = text("""
                    INSERT INTO user_messages (user_id, message, direction, created_at)
                    VALUES (:user_id, :message, 'INCOMING', NOW())
                """)
                
                session.execute(
                    insert_msg_query,
                    {"user_id": user_id, "message": message_text[:500]}  # İlk 500 karakter
                )
                session.commit()
                
                if msg_count == 0:
                    # İlk mesaj - karşılama
                    if "welcome" in templates["dm_templates"]:
                        welcome_msg = random.choice(templates["dm_templates"]["welcome"])
                        await event.reply(welcome_msg)
                    
                    # Takip eden promosyon mesajı
                    if "promotion" in templates["dm_templates"]:
                        promo_msg = random.choice(templates["dm_templates"]["promotion"])
                        await client.send_message(user_id, promo_msg)
                else:
                    # Devam eden sohbet - gruplara davet
                    if "response_invite" in templates["dm_templates"]:
                        response = random.choice(templates["dm_templates"]["response_invite"])
                        await event.reply(response)
                    
                    # İkinci mesaj - premium davet
                    if msg_count == 1 and "premium_invite" in templates["dm_templates"]:
                        premium_msg = random.choice(templates["dm_templates"]["premium_invite"])
                        await client.send_message(user_id, premium_msg)
                
                # Yanıtı kaydet
                insert_reply_query = text("""
                    INSERT INTO user_messages (user_id, message, direction, created_at)
                    VALUES (:user_id, :message, 'OUTGOING', NOW())
                """)
                
                session.execute(
                    insert_reply_query,
                    {"user_id": user_id, "message": "Yanıt verildi (ayrıntılar logda)"}
                )
                session.commit()
                
            except Exception as e:
                logger.error(f"DM yanıtlama hatası: {str(e)}")
        
        async def send_engaging_message(client, chat_id, chat_title, templates):
            """Grup sohbetine otomatik engaging mesajı gönderir"""
            try:
                # Rate limiting - çok fazla mesaj göndermemek için
                await asyncio.sleep(random.uniform(1.0, 3.0))  # Her mesaj gönderimi arasında biraz bekle
                
                # Gönderilecek mesaj içeriğini belirle
                messages = templates.get("messages", {})
                message_types = list(messages.keys())
                
                if not message_types:
                    logger.warning("Gönderilecek mesaj şablonu bulunamadı")
                    return None, None
                
                # Rastgele bir mesaj kategorisi seç
                message_type = random.choice(message_types)
                message_list = messages.get(message_type, [])
                
                if not message_list:
                    logger.warning(f"'{message_type}' kategorisinde mesaj bulunamadı")
                    return None, None
                
                # Rastgele bir mesaj seç
                message_text = random.choice(message_list)
                
                try:
                    # Gruba mesaj gönder
                    message = await client.send_message(int(chat_id), message_text)
                    if message:
                        logger.info(f"Otomatik mesaj gönderildi: {chat_title} - Kategori: {message_type}")
                        return message, message_type
                    return None, None
                except Exception as e:
                    # Hataları daha ayrıntılı logla
                    error_msg = str(e)
                    logger.error(f"Engaging mesajı gönderme hatası: {error_msg}")
                    
                    # Grup bazlı hatalar için işaretleme yap
                    if "banned" in error_msg or "can't write" in error_msg or "permission" in error_msg:
                        # Bu grubu devre dışı bırakmak için veritabanına işaretleyelim
                        try:
                            update_query = text("""
                                UPDATE groups SET 
                                is_active = FALSE, 
                                deactivation_reason = :reason,
                                updated_at = NOW()
                                WHERE group_id = :group_id
                            """)
                            
                            session.execute(
                                update_query, 
                                {"group_id": int(chat_id), "reason": f"Mesaj gönderme hatası: {error_msg[:100]}"}
                            )
                            session.commit()
                            logger.info(f"Grup devre dışı bırakıldı: {chat_id} (Sebep: {error_msg[:100]})")
                        except Exception as db_error:
                            logger.error(f"Grup devre dışı bırakma hatası: {str(db_error)}")
                    
                    return None, None
            except Exception as e:
                logger.error(f"Engaging mesaj oluşturma hatası: {str(e)}")
                return None, None
        
        async def broadcast_engaging_messages(client, templates):
            """Gruplara otomatik mesaj yayını yapar"""
            try:
                # Rastgele grupları seç
                groups_query = text("""
                    SELECT group_id, name, member_count, category,
                           (SELECT COUNT(*) FROM message_effectiveness 
                            WHERE group_id = groups.group_id AND created_at > NOW() - INTERVAL '1 day') 
                           as recent_message_count
                    FROM groups 
                    WHERE is_active = TRUE 
                    ORDER BY recent_message_count ASC, RANDOM() 
                    LIMIT 10
                """)
                
                groups = list(session.execute(groups_query).fetchall())
                
                if not groups:
                    logger.warning("Yayın yapılacak aktif grup bulunamadı")
                    return
                
                # Otomatik mesaj gönderme
                logger.info(f"Engaging mesajı için {len(groups)} gruba yayın yapılacak")
                sent_count = 0
                
                # Rate limiting değişkenleri - daha agresif sınırlama
                MAX_MESSAGE_RATE = 2  # saniyede
                MIN_WAIT_TIME = 2.0  # saniye - minimum bekleme süresini arttır
                BATCH_SIZE = 3  # bir grup içinde gönderilebilecek maksimum mesaj sayısı
                PAUSE_AFTER_BATCH = 10  # saniye - daha uzun bir mola ver
                ADAPTIVE_WAIT = True  # Hata durumunda bekleme süresini artır
                
                # Adaptive rate limiting için değişkenler
                consecutive_errors = 0
                wait_multiplier = 1.0
                
                # Grupları yoğunluğa göre sırala (mesaj sayısı az olanlara öncelik ver)
                groups.sort(key=lambda g: g[4] if len(g) > 4 and g[4] is not None else 9999)
                
                # Grup etiketlerini kontrol et ve büyük gruplara daha az mesaj gönder
                for i, group in enumerate(groups):
                    group_id = str(group[0])
                    group_name = group[1]
                    member_count = group[2] if len(group) > 2 and group[2] is not None else 0
                    recent_messages = group[4] if len(group) > 4 and group[4] is not None else 0
                    
                    # Büyük ve yoğun gruplara daha uzun bekleme süresiyle mesaj gönder
                    group_wait_factor = 1.0
                    if member_count > 1000:
                        group_wait_factor = 1.5
                    if member_count > 5000:
                        group_wait_factor = 2.0
                    if recent_messages > 10:
                        group_wait_factor += 1.0
                    
                    # Flood wait hatalarına karşı rate limiting - grup faktörlerini de dikkate al
                    wait_time = max(MIN_WAIT_TIME, (1.0 / MAX_MESSAGE_RATE) * wait_multiplier * group_wait_factor)
                    logger.debug(f"Grup {group_id} için bekleme süresi: {wait_time:.2f} saniye (çarpan: {group_wait_factor:.1f})")
                    await asyncio.sleep(wait_time)
                    
                    # Periyodik olarak daha uzun duraklamalar yap (Telegram API sınırlamalarından kaçınmak için)
                    if i > 0 and i % BATCH_SIZE == 0:
                        pause_time = PAUSE_AFTER_BATCH + (consecutive_errors * 2)
                        logger.debug(f"Batch duraklaması: {pause_time} saniye")
                        await asyncio.sleep(pause_time)
                    
                    try:
                        # Gruba engaging mesaj gönder
                        message, message_type = await send_engaging_message(client, group_id, group_name, templates)
                        
                        if message:
                            sent_count += 1
                            
                            # YENİ: Gönderilen mesajı takip et
                            message_data = MessageEffectivenessCreate(
                                message_id=message.id,
                                group_id=int(group_id),
                                content=message.text,
                                category=message_type
                            )
                            tracked_message = await message_analytics.track_message(message_data)
                            
                            if tracked_message:
                                # Mesaj takibini bellekte sakla
                                if group_id not in last_sent_messages:
                                    last_sent_messages[group_id] = {}
                                last_sent_messages[group_id][message.id] = tracked_message.id
                            
                            # Başarılı gönderim - hata sayacını sıfırla
                            consecutive_errors = 0
                            wait_multiplier = 1.0
                        else:
                            consecutive_errors += 1
                            # Hata sayısına göre bekleme süresini artır
                            if ADAPTIVE_WAIT:
                                wait_multiplier = min(5.0, 1.0 + (consecutive_errors * 0.5))
                                # Hatalardan sonra daha uzun bekle
                                await asyncio.sleep(consecutive_errors * 1.5)
                    except Exception as e:
                        logger.error(f"Grup {group_id} için mesaj gönderme hatası: {str(e)}")
                        consecutive_errors += 1
                        # Hata durumunda bekleme süresini artır
                        if ADAPTIVE_WAIT:
                            wait_multiplier = min(5.0, 1.0 + (consecutive_errors * 0.5))
                            # Hatalardan sonra daha uzun bekle
                            await asyncio.sleep(consecutive_errors * 1.5)
                
                logger.info(f"Engaging mesaj yayını tamamlandı: {sent_count}/{len(groups)} başarılı")
                
                # Bir sonraki otomatik mesaj için interval belirle - grup yoğunluğuna bağlı
                # Daha fazla mesaj gönderildiyse daha uzun bekle, daha az gönderildiyse daha kısa bekle
                message_ratio = sent_count / max(1, len(groups))  # 0-1 arası oran
                base_interval = 5 * 60  # 5 dakika baz süre
                
                if message_ratio > 0.7:  # Çok sayıda mesaj gönderilebiliyorsa, daha uzun bekle
                    interval_min = 6 * 60  # 6 dakika min
                    interval_max = 7 * 60  # 7 dakika max
                elif message_ratio < 0.3:  # Az mesaj gönderilebiliyorsa, daha kısa bekle
                    interval_min = 3 * 60  # 3 dakika min
                    interval_max = 5 * 60  # 5 dakika max
                else:  # Normal durum
                    interval_min = 4 * 60  # 4 dakika min
                    interval_max = 6 * 60  # 6 dakika max
                
                # Son mesaj yayınındaki hata sayısını da dikkate al
                if consecutive_errors > 5:
                    # Çok fazla hata varsa, daha uzun bekle
                    interval_min += consecutive_errors * 10
                    interval_max += consecutive_errors * 15
                
                auto_message_interval = random.randint(interval_min, interval_max)
                logger.info(f"Sonraki otomatik mesaj aralığı: {auto_message_interval//60} dakika {auto_message_interval%60} saniye (gönderim oranı: {message_ratio:.2f}, hatalar: {consecutive_errors})")
                
                return auto_message_interval
                
            except Exception as e:
                logger.error(f"Otomatik mesaj yayını hatası: {str(e)}")
                return 5 * 60  # Hata durumunda 5 dakika bekle
        
        # Günlük istatistikleri sıfırlama
        async def reset_daily_stats():
            """Günlük limitleri ve istatistikleri sıfırlar"""
            while True:
                # Her gün gece yarısı (00:00) sıfırla
                now = datetime.now()
                next_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                next_day = next_day.replace(day=now.day + 1)  # Bir sonraki gün
                
                # Bir sonraki gün yarısına kadar bekle
                seconds_to_wait = (next_day - now).total_seconds()
                await asyncio.sleep(seconds_to_wait)
                
                # Limitleri sıfırla
                last_replied_users.clear()
                last_replied_groups.clear()
                
                # İstatistikleri logla ve sıfırla
                logger.info(f"Günlük istatistikler sıfırlandı: {reply_stats}")
                
                for key in reply_stats:
                    reply_stats[key] = 0
                
                logger.info("Günlük limitler ve istatistikler sıfırlandı")
        
        # Zaman aşımı koruyucu - eğer uzun süre aktivite yoksa yeniden bağlan
        async def watchdog():
            """Uzun süre aktivite olmaması durumunda yeniden bağlanır"""
            while True:
                await asyncio.sleep(30 * 60)  # 30 dakika bekle
                
                # Son aktiviteden beri 1 saat geçti mi?
                if (datetime.now() - last_activity).total_seconds() > 60 * 60:
                    logger.warning("Uzun süre aktivite yok, bağlantı yenileniyor...")
                    
                    try:
                        await client.disconnect()
                        await asyncio.sleep(5)
                        await client.connect()
                        me = await client.get_me()
                        logger.info(f"Bağlantı yenilendi: {me.first_name} (@{me.username})")
                        last_activity = datetime.now()
                    except Exception as e:
                        logger.error(f"Bağlantı yenileme hatası: {str(e)}")
        
        # Periyodik otomatik mesaj yayını için task
        async def scheduled_message_broadcast():
            """Periyodik olarak gruplara otomatik mesaj gönderir"""
            while True:
                try:
                    # İlk çalıştırmada bekletme süresini 30 saniye olarak ayarla
                    await asyncio.sleep(30)
                    
                    # İlk mesaj yayınını yap
                    logger.info("Periyodik otomatik mesaj yayını başlatılıyor...")
                    await broadcast_engaging_messages(client, templates)
                    
                    # Sonraki mesaj için rastgele aralık belirle (3-7 dakika)
                    wait_time = random.randint(auto_message_interval_min, auto_message_interval_max)
                    logger.info(f"Sonraki otomatik mesaj yayını için bekleniyor: {wait_time//60} dakika {wait_time%60} saniye")
                    
                    # Belirlenen süre kadar bekle
                    await asyncio.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"Zamanlanmış mesaj yayını hatası: {str(e)}")
                    # Hata durumunda 1 dakika bekle ve tekrar dene
                    await asyncio.sleep(60)
        
        # YENİ: Mesaj etkinlik güncellemesi için task
        async def message_effectiveness_update():
            """Mesaj etkinliği metriklerini günceller"""
            try:
                last_updated = datetime.now()
                update_interval = 120  # Saniyede bir güncelle
                MAX_UPDATES_PER_RUN = 30  # Bir seferde maksimum güncellenen mesaj sayısı
                ERROR_THRESHOLD = 5  # Bir grup için maksimum hata sayısı
                
                # Grup başına hata sayaçları
                group_error_counts = {}
                
                while True:
                    await asyncio.sleep(update_interval)
                    
                    try:
                        now = datetime.now()
                        recently_updated = 0
                        update_start_time = datetime.now()
                        
                        # Her grup için takip edilen mesajları güncelle
                        for group_id, messages in list(last_sent_messages.items()):
                            if not messages:
                                continue
                            
                            # Eğer grup çok fazla hata veriyorsa atla
                            if group_id in group_error_counts and group_error_counts[group_id] >= ERROR_THRESHOLD:
                                logger.warning(f"Grup {group_id} çok fazla hata verdiği için atlanıyor (hata sayısı: {group_error_counts[group_id]})")
                                continue
                            
                            # Rate limiting - mevcut işlediğimiz mesaj sayısına göre bekleme süresi ekle
                            if recently_updated >= MAX_UPDATES_PER_RUN:
                                logger.info(f"Maksimum güncelleme sayısına ulaşıldı: {recently_updated}. Sonraki çalıştırmada devam edilecek.")
                                break
                            
                            try:
                                for message_id, tracked_id in list(messages.items()):
                                    try:
                                        # Flood wait hatalarını önlemek için her mesaj arasında biraz bekle
                                        await asyncio.sleep(0.5)
                                        
                                        # Mesaj detaylarını al
                                        try:
                                            message = await client.get_messages(int(group_id), ids=message_id)
                                            if message:
                                                try:
                                                    # Mesaj etkileşim sayılarını al
                                                    reaction_count = 0
                                                    
                                                    # Reactions özelliği None olabiliyor veya len() metodu olmayan bir tipte olabiliyor
                                                    # Bu durumu güvenli şekilde handle edelim
                                                    if hasattr(message, 'reactions') and message.reactions:
                                                        try:
                                                            # Bazı sürümlerde reactions bir liste, bazılarında ise özel bir sınıf
                                                            if hasattr(message.reactions, '__len__'):
                                                                reaction_count = len(message.reactions)
                                                            elif hasattr(message.reactions, 'reactions'):
                                                                # MessageReactions sınıfı olabilir
                                                                reaction_count = len(message.reactions.reactions)
                                                            elif hasattr(message.reactions, 'count'):
                                                                # Doğrudan sayı tutan bir özellik olabilir
                                                                reaction_count = message.reactions.count
                                                            else:
                                                                # Tip bilinmiyor, güvenli bir varsayılan değer kullan
                                                                reaction_count = 0
                                                                logger.warning(f"Bilinmeyen reactions tipi: {type(message.reactions)}")
                                                        except Exception as reaction_error:
                                                            logger.warning(f"Reactions sayısını alırken hata: {reaction_error}")
                                                            reaction_count = 0
                                                
                                                    # Etkileşim sayılarını güncelle
                                                    forward_count = message.forwards or 0
                                                    reply_count = 0  # API'den alınamıyor, takip etmek için özel bir mekanizma gerekli
                                                    
                                                    # View sayısını güvenli şekilde al
                                                    view_count = 0
                                                    if hasattr(message, 'views') and message.views is not None:
                                                        view_count = message.views
                                                    
                                                    await message_analytics.update_message_metrics(tracked_id, {
                                                        "views": view_count,
                                                        "forwards": forward_count,
                                                        "reactions": reaction_count
                                                    })
                                                    recently_updated += 1
                                                    
                                                    # Çok eski mesajları temizle (24 saatten eski)
                                                    if message.date and (now - message.date.replace(tzinfo=None)).total_seconds() > 24 * 60 * 60:
                                                        del messages[message_id]
                                                except Exception as metrics_error:
                                                    logger.warning(f"Mesaj metrikleri alınırken hata: {str(metrics_error)}")
                                                    # Sorunlu mesajı takipten çıkar
                                                    del messages[message_id]
                                            else:
                                                # Mesaj bulunamadı, takipten çıkar
                                                del messages[message_id]
                                        except Exception as msg_error:
                                            logger.error(f"Mesaj detayları alınırken hata: {str(msg_error)}")
                                            # Grup hata sayacını artır
                                            group_error_counts[group_id] = group_error_counts.get(group_id, 0) + 1
                                            # Sorunlu mesajı takipten çıkar
                                            del messages[message_id]
                                    except Exception as e:
                                        logger.error(f"Mesaj işlenirken hata: {str(e)}")
                                        # Sorunlu mesajla işlemeye devam etmemek için atla
                                        continue
                            except Exception as group_error:
                                logger.error(f"Grup mesajları işlenirken hata: {str(group_error)}")
                                # Grup hata sayacını artır
                                group_error_counts[group_id] = group_error_counts.get(group_id, 0) + 1
                        
                        # Günlük olarak hata sayaçlarını sıfırla
                        elapsed_time = (datetime.now() - update_start_time).total_seconds()
                        if (now - last_updated).total_seconds() > 86400:  # 24 saat
                            group_error_counts.clear()
                            last_updated = now
                        
                        logger.debug(f"Mesaj etkinliği güncelleme tamamlandı: {recently_updated} mesaj, {elapsed_time:.2f} saniye")
                    except Exception as update_error:
                        logger.error(f"Mesaj etkinliği güncellenirken genel hata: {str(update_error)}")
            except Exception as e:
                logger.error(f"Mesaj etkinliği güncelleme görevi başlatılırken hata: {str(e)}")
        
        # Görevleri başlat
        tasks = [
            client.run_until_disconnected(),
            reset_daily_stats(),
            watchdog(),
            scheduled_message_broadcast(),
            message_effectiveness_update()  # Yeni eklenen görev
        ]
        
        # Tüm görevleri başlat ve bekle
        await asyncio.gather(*tasks)
        
    except Exception as e:
        logger.error(f"Event Listener hatası: {str(e)}", exc_info=True)
    finally:
        # Temizlik
        try:
            session.close()
            await client.disconnect()
        except:
            pass
        
        logger.info("Event Listener durduruldu")

if __name__ == "__main__":
    asyncio.run(main()) 