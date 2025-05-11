"""
Telegram Bot Database Servisi Testleri

Bu test modülü, Database servisinin işlevselliğini test eder:
1. Model CRUD işlemleri
2. Veri yedekleme/geri yükleme
3. Veritabanı bağlantı yönetimi
4. Performans sorguları
"""

import os
import asyncio
import pytest
import pytest_asyncio
import tempfile
import json
import datetime
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from pathlib import Path

# Veri modelleri için basit sınıflar
class Message:
    def __init__(self, id=None, content=None, chat_id=None, scheduled_time=None, status=None, account_id=None):
        self.id = id
        self.content = content
        self.chat_id = chat_id
        self.scheduled_time = scheduled_time
        self.status = status
        self.account_id = account_id
    
    def __eq__(self, other):
        if not isinstance(other, Message):
            return False
        return (self.id == other.id and 
                self.content == other.content and 
                self.chat_id == other.chat_id and 
                self.status == other.status and 
                self.account_id == other.account_id)
    
    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "chat_id": self.chat_id,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "status": self.status,
            "account_id": self.account_id
        }

class Account:
    def __init__(self, id=None, name=None, api_id=None, api_hash=None, phone=None, is_active=True):
        self.id = id
        self.name = name
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.is_active = is_active
    
    def __eq__(self, other):
        if not isinstance(other, Account):
            return False
        return (self.id == other.id and 
                self.name == other.name and 
                self.api_id == other.api_id and 
                self.api_hash == other.api_hash and 
                self.phone == other.phone and 
                self.is_active == other.is_active)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "api_id": self.api_id,
            "api_hash": self.api_hash,
            "phone": self.phone,
            "is_active": self.is_active
        }

# Database servisi için mock
class MockDatabaseService:
    """Database servisinin mock implementasyonu"""
    
    def __init__(self, db_url=None):
        self.db_url = db_url or "sqlite:///:memory:"
        self.running = False
        self.connected = False
        self.messages = {}  # id -> Message
        self.accounts = {}  # id -> Account
        self.last_message_id = 0
        self.last_account_id = 0
        self._connection = None
    
    async def start(self):
        """Database servisini başlatır"""
        self.running = True
        await self.connect()
        return True
    
    async def stop(self):
        """Database servisini durdurur"""
        self.running = False
        await self.disconnect()
        return True
    
    async def connect(self):
        """Veritabanına bağlanır"""
        if self.db_url.startswith("sqlite"):
            self._connection = True  # SQLite in-memory veritabanı
            self.connected = True
            return True
        return False
    
    async def disconnect(self):
        """Veritabanı bağlantısını kapatır"""
        self._connection = None
        self.connected = False
        return True
    
    async def create_tables(self):
        """Tabloları oluşturur"""
        # Mock implementasyon - gerekli değil
        return True
    
    # Message CRUD
    async def create_message(self, message):
        """Yeni mesaj oluşturur"""
        self.last_message_id += 1
        message.id = self.last_message_id
        self.messages[message.id] = message
        return message
    
    async def get_message(self, message_id):
        """Mesajı ID'ye göre alır"""
        return self.messages.get(message_id)
    
    async def update_message(self, message):
        """Mesajı günceller"""
        if message.id in self.messages:
            self.messages[message.id] = message
            return message
        return None
    
    async def delete_message(self, message_id):
        """Mesajı siler"""
        if message_id in self.messages:
            del self.messages[message_id]
            return True
        return False
    
    async def get_messages(self, status=None, limit=100, offset=0):
        """Mesajları listeler"""
        messages = list(self.messages.values())
        
        if status:
            messages = [m for m in messages if m.status == status]
        
        # Sırala (yeniden eskiye)
        if messages and hasattr(messages[0], 'scheduled_time') and all(m.scheduled_time for m in messages):
            messages.sort(key=lambda m: m.scheduled_time, reverse=True)
        
        # Limit ve offset uygula
        return messages[offset:offset+limit]
    
    async def get_pending_scheduled_messages(self):
        """Zamanı gelmiş zamanlanmış mesajları döndürür"""
        now = datetime.datetime.now()
        pending = [
            m for m in self.messages.values() 
            if m.status == "pending" and m.scheduled_time and m.scheduled_time <= now
        ]
        return pending
    
    # Account CRUD
    async def create_account(self, account):
        """Yeni hesap oluşturur"""
        self.last_account_id += 1
        account.id = self.last_account_id
        self.accounts[account.id] = account
        return account
    
    async def get_account(self, account_id):
        """Hesabı ID'ye göre alır"""
        return self.accounts.get(account_id)
    
    async def get_account_by_name(self, name):
        """Hesabı isme göre alır"""
        for account in self.accounts.values():
            if account.name == name:
                return account
        return None
    
    async def update_account(self, account):
        """Hesabı günceller"""
        if account.id in self.accounts:
            self.accounts[account.id] = account
            return account
        return None
    
    async def delete_account(self, account_id):
        """Hesabı siler"""
        if account_id in self.accounts:
            del self.accounts[account_id]
            return True
        return False
    
    async def get_accounts(self, is_active=None):
        """Hesapları listeler"""
        accounts = list(self.accounts.values())
        
        if is_active is not None:
            accounts = [a for a in accounts if a.is_active == is_active]
        
        return accounts
    
    # Yedekleme ve geri yükleme
    async def backup_database(self, backup_path):
        """Veritabanını yedekler"""
        try:
            data = {
                "messages": [m.to_dict() for m in self.messages.values()],
                "accounts": [a.to_dict() for a in self.accounts.values()],
                "backup_time": datetime.datetime.now().isoformat()
            }
            
            with open(backup_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception:
            return False
    
    async def restore_database(self, backup_path):
        """Veritabanını geri yükler"""
        try:
            with open(backup_path, 'r') as f:
                data = json.load(f)
            
            # Verileri temizle
            self.messages = {}
            self.accounts = {}
            
            # Mesajları geri yükle
            for msg_dict in data.get("messages", []):
                msg = Message(
                    id=msg_dict["id"],
                    content=msg_dict["content"],
                    chat_id=msg_dict["chat_id"],
                    scheduled_time=datetime.datetime.fromisoformat(msg_dict["scheduled_time"]) if msg_dict["scheduled_time"] else None,
                    status=msg_dict["status"],
                    account_id=msg_dict["account_id"]
                )
                self.messages[msg.id] = msg
                if msg.id > self.last_message_id:
                    self.last_message_id = msg.id
            
            # Hesapları geri yükle
            for acc_dict in data.get("accounts", []):
                acc = Account(
                    id=acc_dict["id"],
                    name=acc_dict["name"],
                    api_id=acc_dict["api_id"],
                    api_hash=acc_dict["api_hash"],
                    phone=acc_dict["phone"],
                    is_active=acc_dict["is_active"]
                )
                self.accounts[acc.id] = acc
                if acc.id > self.last_account_id:
                    self.last_account_id = acc.id
            
            return True
        except Exception:
            return False

@pytest.fixture
def db_service():
    """Test için DatabaseService instance'ı oluşturur"""
    service = MockDatabaseService()
    return service

# ================== TEMEL FONKSİYONELLİK TESTLERİ ==================

@pytest.mark.asyncio
async def test_service_lifecycle(db_service):
    """Database servisinin yaşam döngüsünü test eder"""
    # Başlangıçta servisin çalışmadığını doğrula
    assert db_service.running == False
    
    # Servisi başlat
    result = await db_service.start()
    assert result == True
    assert db_service.running == True
    assert db_service.connected == True
    
    # Servisi durdur
    result = await db_service.stop()
    assert result == True
    assert db_service.running == False
    assert db_service.connected == False

@pytest.mark.asyncio
async def test_message_crud(db_service):
    """Mesaj CRUD işlemlerini test eder"""
    # Servisi başlat
    await db_service.start()
    
    # Test verisi oluştur
    now = datetime.datetime.now()
    future = now + datetime.timedelta(minutes=30)
    
    message = Message(
        content="Test mesajı",
        chat_id=123456789,
        scheduled_time=future,
        status="pending",
        account_id=1
    )
    
    # Mesaj oluştur
    created = await db_service.create_message(message)
    assert created.id is not None
    assert created.content == "Test mesajı"
    
    # Mesajı al
    retrieved = await db_service.get_message(created.id)
    assert retrieved == created
    
    # Mesajı güncelle
    retrieved.status = "sent"
    updated = await db_service.update_message(retrieved)
    assert updated.status == "sent"
    
    # Mesajları listele
    messages = await db_service.get_messages()
    assert len(messages) == 1
    assert messages[0].status == "sent"
    
    # Mesajı sil
    deleted = await db_service.delete_message(created.id)
    assert deleted == True
    
    # Silinen mesajın artık olmadığını doğrula
    empty = await db_service.get_message(created.id)
    assert empty is None
    
    # Servisi durdur
    await db_service.stop()

@pytest.mark.asyncio
async def test_account_crud(db_service):
    """Hesap CRUD işlemlerini test eder"""
    # Servisi başlat
    await db_service.start()
    
    # Test hesabı oluştur
    account = Account(
        name="test_account",
        api_id="12345678",
        api_hash="test_api_hash",
        phone="+901234567890",
        is_active=True
    )
    
    # Hesap oluştur
    created = await db_service.create_account(account)
    assert created.id is not None
    assert created.name == "test_account"
    
    # Hesabı al
    retrieved = await db_service.get_account(created.id)
    assert retrieved == created
    
    # İsme göre hesabı al
    by_name = await db_service.get_account_by_name("test_account")
    assert by_name == created
    
    # Hesabı güncelle
    retrieved.is_active = False
    updated = await db_service.update_account(retrieved)
    assert updated.is_active == False
    
    # Hesapları listele
    accounts = await db_service.get_accounts()
    assert len(accounts) == 1
    assert accounts[0].is_active == False
    
    # Sadece aktif hesapları listele
    active_accounts = await db_service.get_accounts(is_active=True)
    assert len(active_accounts) == 0
    
    # Hesabı sil
    deleted = await db_service.delete_account(created.id)
    assert deleted == True
    
    # Silinen hesabın artık olmadığını doğrula
    empty = await db_service.get_account(created.id)
    assert empty is None
    
    # Servisi durdur
    await db_service.stop()

# ================== ZAMANLANMIŞ MESAJ TESTLERİ ==================

@pytest.mark.asyncio
async def test_scheduled_messages(db_service):
    """Zamanlanmış mesajların işlenmesini test eder"""
    # Servisi başlat
    await db_service.start()
    
    # Geçmiş, şimdi ve gelecek için mesajlar oluştur
    now = datetime.datetime.now()
    past = now - datetime.timedelta(minutes=10)
    future = now + datetime.timedelta(minutes=10)
    
    # Geçmiş mesaj (zamanı gelmiş)
    past_message = Message(
        content="Geçmiş mesaj",
        chat_id=123456789,
        scheduled_time=past,
        status="pending",
        account_id=1
    )
    
    # Gelecek mesaj (zamanı gelmemiş)
    future_message = Message(
        content="Gelecek mesaj",
        chat_id=123456789,
        scheduled_time=future,
        status="pending",
        account_id=1
    )
    
    # Mesajları oluştur
    await db_service.create_message(past_message)
    await db_service.create_message(future_message)
    
    # Zamanı gelmiş mesajları al
    pending_messages = await db_service.get_pending_scheduled_messages()
    
    # Sadece geçmiş mesajın gelmesi gerekiyor
    assert len(pending_messages) == 1
    assert pending_messages[0].content == "Geçmiş mesaj"
    
    # Servisi durdur
    await db_service.stop()

# ================== YEDEKLEME VE GERİ YÜKLEME TESTLERİ ==================

@pytest.mark.asyncio
async def test_backup_restore(db_service):
    """Yedekleme ve geri yükleme işlemlerini test eder"""
    # Servisi başlat
    await db_service.start()
    
    # Test verilerini oluştur
    account = Account(
        name="yedek_test_hesap",
        api_id="12345678",
        api_hash="test_api_hash",
        phone="+901234567890"
    )
    
    message = Message(
        content="Yedek test mesajı",
        chat_id=123456789,
        scheduled_time=datetime.datetime.now(),
        status="sent",
        account_id=1
    )
    
    # Verileri kaydet
    await db_service.create_account(account)
    await db_service.create_message(message)
    
    # Geçici bir yedek dosyası oluştur
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_file:
        backup_path = tmp_file.name
    
    try:
        # Yedekle
        backup_result = await db_service.backup_database(backup_path)
        assert backup_result == True
        
        # Verileri temizle
        await db_service.stop()
        db_service = MockDatabaseService()
        await db_service.start()
        
        # Temizlendiğini doğrula
        assert len(await db_service.get_accounts()) == 0
        assert len(await db_service.get_messages()) == 0
        
        # Geri yükle
        restore_result = await db_service.restore_database(backup_path)
        assert restore_result == True
        
        # Geri yüklenen verileri kontrol et
        accounts = await db_service.get_accounts()
        assert len(accounts) == 1
        assert accounts[0].name == "yedek_test_hesap"
        
        messages = await db_service.get_messages()
        assert len(messages) == 1
        assert messages[0].content == "Yedek test mesajı"
    
    finally:
        # Geçici dosyayı temizle
        if os.path.exists(backup_path):
            os.unlink(backup_path)
        
        # Servisi durdur
        await db_service.stop()

# ================== PERFORMANS TESTLERİ ==================

@pytest.mark.asyncio
async def test_bulk_message_operations(db_service):
    """Toplu mesaj işlemlerinin performansını test eder"""
    # Servisi başlat
    await db_service.start()
    
    # Çok sayıda mesaj oluştur
    message_count = 1000
    now = datetime.datetime.now()
    
    # Toplu mesaj oluşturma işlemi
    start_time = datetime.datetime.now()
    
    for i in range(message_count):
        message = Message(
            content=f"Performans testi mesajı {i+1}",
            chat_id=123456789,
            scheduled_time=now + datetime.timedelta(minutes=i),
            status="pending",
            account_id=1
        )
        await db_service.create_message(message)
    
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Makul bir sürede tamamlanmalı
    assert duration < 5.0, f"Toplu mesaj oluşturma çok uzun sürdü: {duration:.2f} saniye"
    
    # Tüm mesajların oluşturulduğunu doğrula
    messages = await db_service.get_messages(limit=message_count)
    assert len(messages) == message_count
    
    # Servisi durdur
    await db_service.stop()

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 