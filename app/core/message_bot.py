import os
import json
from dotenv import load_dotenv
from telethon import TelegramClient, events
from app.handlers.group_handler import GroupHandler
from app.utils.db_setup import Database

# .env dosyasını yükle
load_dotenv()

class MessageBot:
    def __init__(self):
        # API bilgilerini al
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.bot_token = os.getenv('BOT_TOKEN')
        
        # Hedef grupları ve süper kullanıcıları al
        self.target_groups = json.loads(os.getenv('TARGET_GROUPS', '[]'))
        self.super_users = json.loads(os.getenv('SUPER_USERS', '[]'))
        
        # Veritabanı bağlantısı
        self.db = Database()
        
        # Telegram istemcisi
        self.client = TelegramClient('bot_session', self.api_id, self.api_hash)
        
        # Grup işleyici
        self.group_handler = GroupHandler(self.client, self, self.db)
        
    async def start(self):
        """Bot'u başlatır"""
        try:
            # Veritabanını başlat
            await self.db.init_db()
            
            # Telegram istemcisini başlat
            await self.client.start(bot_token=self.bot_token)
            
            # Grup işleyiciyi başlat
            await self.group_handler.initialize()
            
            # Event handler'ları ekle
            self.client.add_event_handler(
                self.group_handler.handle_group_message,
                events.NewMessage(chats=self.target_groups)
            )
            
            self.client.add_event_handler(
                self.group_handler.handle_private_message,
                events.NewMessage(func=lambda e: e.is_private)
            )
            
            # Grup mesaj gönderim döngüsünü başlat
            await self.group_handler.process_group_messages()
            
        except Exception as e:
            print(f"Bot başlatma hatası: {str(e)}")
            raise
            
    async def stop(self):
        """Bot'u durdurur"""
        try:
            await self.group_handler.shutdown()
            await self.client.disconnect()
            self.db.close()
        except Exception as e:
            print(f"Bot durdurma hatası: {str(e)}")
            raise 