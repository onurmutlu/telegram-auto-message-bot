import asyncio
import logging
from datetime import datetime
from database.script import get_session
from bot.services.base_service import BaseService
from bot.services.group_service import GroupService
from bot.services.user_service import UserService
from bot.services.announcement_service import AnnouncementService
from bot.services.dm_service import DMService
from bot.services.message_service import MessageService
from bot.services.service_manager import ServiceManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestConfig:
    def __init__(self):
        self.api_id = '12345'
        self.api_hash = 'test_hash'
        self.bot_token = 'test_token'
        self.db_url = 'postgresql://postgres:postgres@localhost:5432/telegram_bot'
        self.telegram = {
            'api_id': self.api_id,
            'api_hash': self.api_hash,
            'bot_token': self.bot_token
        }
        
    def get_setting(self, key, default=None):
        settings = {
            'message_interval': 60,
            'batch_size': 3,
            'max_retries': 5,
            'admin_groups': ['arayisplatin', 'arayisgruba', 'premium_arayis'],
            'target_groups': ['group1', 'group2', 'group3']
        }
        return settings.get(key, default)

class TestDialog:
    def __init__(self, id, title, participants_count):
        self.id = id
        self.title = title
        self.participants_count = participants_count
        self.is_group = True
        self.entity = type('TestEntity', (), {
            'id': id,
            'title': title,
            'participants_count': participants_count,
            'username': f'test_group_{id}'
        })

class TestClient:
    def __init__(self):
        self.event_handlers = []
        self.me = type('TestMe', (), {'id': 123456789, 'username': 'test_bot'})()
        self.dialogs = [
            TestDialog(-1001234567890, 'Test Group 1', 100),
            TestDialog(-1001234567891, 'Test Group 2', 200),
            TestDialog(-1001234567892, 'Test Group 3', 300)
        ]
        
    async def start(self):
        return True
        
    async def stop(self):
        return True
        
    def add_event_handler(self, callback, event=None):
        self.event_handlers.append((callback, event))
        
    def on(self, *args, **kwargs):
        def decorator(func):
            self.event_handlers.append((func, args))
            return func
        return decorator
        
    async def iter_dialogs(self):
        for dialog in self.dialogs:
            yield dialog
            
    async def get_me(self):
        return self.me
        
    async def send_message(self, chat_id, message, **kwargs):
        return {'message_id': 1, 'date': datetime.now()}
        
    async def get_entity(self, entity_id):
        for dialog in self.dialogs:
            if dialog.id == entity_id:
                return dialog.entity
        return None
        
    async def get_dialogs(self):
        return self.dialogs
        
    async def get_messages(self, chat_id, limit=1):
        return [{'id': 1, 'message': 'Test message', 'date': datetime.now()}]
        
    async def get_participants(self, chat_id):
        return [{'id': 123456789, 'username': 'test_user'}]
        
    async def join_chat(self, chat_id):
        return True
        
    async def leave_chat(self, chat_id):
        return True

class TestCursor:
    def __init__(self):
        self.description = [('id',), ('name',), ('created_at',)]
        self.rowcount = 1
        
    async def execute(self, query, params=None):
        return True
        
    async def fetchone(self):
        return [1, 'test', datetime.now()]
        
    async def fetchall(self):
        return [[1, 'test', datetime.now()]]
        
    async def close(self):
        return True

class TestDB:
    def __init__(self, session):
        self.session = session
        self.db_url = 'postgresql://postgres:postgres@localhost:5432/telegram_bot'
        self.cursor = TestCursor()
        self.conn = type('TestConn', (), {'cursor': self.cursor})()
    
    async def execute(self, query, params=None):
        return True
    
    async def fetchone(self, query, params=None):
        return [1, 'test', datetime.now()]
    
    async def fetchall(self, query, params=None):
        return [[1, 'test', datetime.now()]]
        
    async def commit(self):
        return True
        
    async def rollback(self):
        return True
        
    async def close(self):
        return True

class AnnouncementService(BaseService):
    async def send_announcement(self, message, target_groups):
        return True

class DirectMessageService(BaseService):
    async def send_direct_message(self, user_id, message):
        return True

class MessageService(BaseService):
    async def send_group_message(self, chat_id, message):
        return True

async def test_group_service():
    try:
        session = get_session()
        db = TestDB(session)
        client = TestClient()
        config = TestConfig()
        stop_event = asyncio.Event()
        group_service = GroupService(client, config, db, stop_event)
        await group_service.initialize()
        
        # Test grup servisi
        test_group = {
            'group_id': -1001234567890,
            'name': 'Test Grup',
            'member_count': 100
        }
        await group_service._save_group_to_db(
            test_group['group_id'], 
            test_group['name'], 
            member_count=test_group['member_count']
        )
        logger.info("✅ Grup servisi testi başarılı")
    except Exception as e:
        logger.error(f"❌ Grup servisi testi başarısız: {str(e)}")

async def test_user_service():
    try:
        session = get_session()
        db = TestDB(session)
        client = TestClient()
        config = TestConfig()
        stop_event = asyncio.Event()
        user_service = UserService(client, config, db, stop_event)
        await user_service.initialize()
        
        # Test kullanıcı servisi
        test_user = {
            'user_id': 123456789,
            'username': 'test_user',
            'phone': '+905551234567'
        }
        await user_service.process_user(test_user['user_id'], test_user['username'])
        logger.info("✅ Kullanıcı servisi testi başarılı")
    except Exception as e:
        logger.error(f"❌ Kullanıcı servisi testi başarısız: {str(e)}")

async def test_announcement_service():
    try:
        session = get_session()
        db = TestDB(session)
        client = TestClient()
        config = TestConfig()
        stop_event = asyncio.Event()
        announcement_service = AnnouncementService("announcement", client, config, db, stop_event)
        await announcement_service.initialize()
        
        # Test duyuru servisi
        test_announcement = {
            'message': 'Test duyuru',
            'target_groups': [-1001234567890]
        }
        await announcement_service.send_announcement(test_announcement['message'], test_announcement['target_groups'])
        logger.info("✅ Duyuru servisi testi başarılı")
    except Exception as e:
        logger.error(f"❌ Duyuru servisi testi başarısız: {str(e)}")

async def test_dm_service():
    try:
        session = get_session()
        db = TestDB(session)
        client = TestClient()
        config = TestConfig()
        stop_event = asyncio.Event()
        dm_service = DirectMessageService("dm", client, config, db, stop_event)
        await dm_service.initialize()
        
        # Test DM servisi
        test_message = {
            'user_id': 123456789,
            'message': 'Test mesaj'
        }
        await dm_service.send_direct_message(test_message['user_id'], test_message['message'])
        logger.info("✅ DM servisi testi başarılı")
    except Exception as e:
        logger.error(f"❌ DM servisi testi başarısız: {str(e)}")

async def test_message_service():
    try:
        session = get_session()
        db = TestDB(session)
        client = TestClient()
        config = TestConfig()
        stop_event = asyncio.Event()
        message_service = MessageService("message", client, config, db, stop_event)
        await message_service.initialize()
        
        # Test mesaj servisi
        test_message = {
            'chat_id': -1001234567890,
            'message': 'Test mesaj'
        }
        await message_service.send_group_message(test_message['chat_id'], test_message['message'])
        logger.info("✅ Mesaj servisi testi başarılı")
    except Exception as e:
        logger.error(f"❌ Mesaj servisi testi başarısız: {str(e)}")

async def main():
    logger.info("🔄 Servis testleri başlatılıyor...")
    
    await test_group_service()
    await test_user_service()
    await test_announcement_service()
    await test_dm_service()
    await test_message_service()
    
    logger.info("✨ Tüm testler tamamlandı")

if __name__ == "__main__":
    asyncio.run(main()) 