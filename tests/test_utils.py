import logging
from datetime import datetime

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