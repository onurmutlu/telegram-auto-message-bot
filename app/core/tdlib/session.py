import asyncio
import logging
import os
import time
import json
import sqlite3
from telethon.sessions import StringSession, MemorySession
from app.core.config import settings
from telethon import TelegramClient
import psycopg2
from telethon.sessions.sqlite import SQLiteSession
from telethon.crypto import AuthKey
from telethon.tl.types import (
    InputPhoto, InputDocument, PeerUser, PeerChat, PeerChannel
)

# TDLib kullanılabilirlik kontrolü
TDLIB_AVAILABLE = False
try:
    import tdlib
    from app.core.tdlib.client import TDLibClient
    TDLIB_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("TDLib başarıyla import edildi ve kullanılabilir")
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("TDLib import edilemedi, alternatif Telethon kullanılacak")

class PostgresSession(SQLiteSession):
    """
    PostgreSQL tabanlı Telethon oturum yöneticisi.
    SQLite yerine PostgreSQL kullanarak Telethon oturumlarını saklar.
    """
    
    def __init__(self, session_id=None):
        """
        PostgreSQL tabanlı oturum başlatma
        Args:
            session_id: Oturum kimliği. Varsayılan olarak settings.SESSION_NAME kullanılır.
        """
        super().__init__(session_id)
        
        # Name özelliğini ekleyelim
        self.name = session_id or ""
        
        # PostgreSQL bağlantı bilgileri
        self.db_conn = None
        self.db_cursor = None
        
        # PostgreSQL bağlantı parametreleri
        self.db_host = settings.POSTGRES_SERVER
        self.db_port = settings.POSTGRES_PORT
        self.db_name = settings.POSTGRES_DB
        self.db_user = settings.POSTGRES_USER
        self.db_pass = settings.POSTGRES_PASSWORD
        
        # Tablo adı prefix'i (her session_id için benzersiz)
        self.table_prefix = f"telethon_{self.filename.split('/')[-1].replace('.session', '')}"
        
        # Auth key için veri tipi kontrolü
        if hasattr(self, '_auth_key') and self._auth_key and hasattr(self._auth_key, 'key'):
            if isinstance(self._auth_key.key, memoryview):
                # memoryview'i bytes'a çevir
                self._auth_key.key = bytes(self._auth_key.key)
        
        # Varlıklar için sözlük (entities) - set yerine dict kullan
        self._entities = {}  # id -> hash, username, phone, name
        self._entities_by_username = {}  # username -> id
        self._entities_by_phone = {}  # phone -> id
        self._entities_by_name = {}  # name -> id
        
        # Gönderilen dosyalar için sözlük
        self._sent_files = {}
        
        # Update state için sözlük
        self._update_states = {}
        
        # Bağlantıyı aç ve tabloları oluştur
        self._connect()
        self._create_tables()
        
        # Verileri yükle
        self._load_session()
    
    def _connect(self):
        """PostgreSQL veritabanına bağlan"""
        try:
            self.db_conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_pass
            )
            # Otomatik commit özelliğini kapatalım, transaction kontrolüne sahip olalım
            self.db_conn.autocommit = False
            self.db_cursor = self.db_conn.cursor()
            logger.info(f"PostgreSQL bağlantısı başarılı: {self.db_host}:{self.db_port}/{self.db_name}")
        except Exception as e:
            logger.error(f"PostgreSQL bağlantı hatası: {e}")
            raise
    
    def _create_tables(self):
        """Gerekli PostgreSQL tablolarını oluştur"""
        try:
            # Version tablosu
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_prefix}_version (
                    version INTEGER PRIMARY KEY
                )
            """)
            
            # Ana oturum tablosu
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_prefix}_sessions (
                    dc_id INTEGER PRIMARY KEY,
                    server_address TEXT,
                    port INTEGER,
                    auth_key BYTEA,
                    takeout_id INTEGER
                )
            """)
            
            # Varlık tablosu (entity store)
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_prefix}_entities (
                    id BIGINT PRIMARY KEY,
                    hash BIGINT NOT NULL,
                    username TEXT,
                    phone TEXT,
                    name TEXT,
                    date TIMESTAMP
                )
            """)
            
            # Güncellenen ID'ler tablosu
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_prefix}_update_state (
                    id INTEGER PRIMARY KEY,
                    pts INTEGER,
                    qts INTEGER,
                    date INTEGER,
                    seq INTEGER
                )
            """)
            
            # Sent files tablosu
            self.db_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_prefix}_sent_files (
                    md5_digest BYTEA,
                    file_size INTEGER,
                    type INTEGER,
                    id BIGINT,
                    hash BIGINT,
                    PRIMARY KEY (md5_digest, file_size, type)
                )
            """)
            
            # Version bilgisini kontrol et
            self.db_cursor.execute(f"SELECT version FROM {self.table_prefix}_version")
            version_record = self.db_cursor.fetchone()
            
            if not version_record:
                # Version bilgisini ekle
                self.db_cursor.execute(
                    f"INSERT INTO {self.table_prefix}_version VALUES (%s)", 
                    (7,)
                )
            
            # Değişiklikleri kaydet
            self.db_conn.commit()
            logger.info(f"PostgreSQL tabloları başarıyla oluşturuldu: {self.table_prefix}_*")
        except Exception as e:
            logger.error(f"PostgreSQL tabloları oluşturulurken hata: {e}")
            self.db_conn.rollback()
            raise
    
    def _load_session(self):
        """PostgreSQL'den oturum verilerini yükle"""
        try:
            # Oturum verilerini sorgula
            self.db_cursor.execute(f"SELECT * FROM {self.table_prefix}_sessions")
            session_data = self.db_cursor.fetchone()
            
            if session_data:
                self._dc_id, self._server_address, self._port, key, self._takeout_id = session_data
                
                # Auth_key bytes olarak kullanmak için
                if isinstance(key, memoryview):
                    key = bytes(key)
                
                self._auth_key = AuthKey(data=key)
                logger.info(f"PostgreSQL'den oturum verileri yüklendi (DC: {self._dc_id})")
            
            # Varlıkları (entities) yükle
            self.db_cursor.execute(f"SELECT * FROM {self.table_prefix}_entities")
            entities = self.db_cursor.fetchall()
            
            # _entities sözlüğü olarak tanımla (list veya set değil)
            self._entities = {}
            
            for entity_data in entities:
                entity_id, entity_hash, username, phone, name, date = entity_data
                
                # Entity bilgisini _entities sözlüğüne ekle
                self._entities[entity_id] = {
                    'hash': entity_hash,
                    'username': username,
                    'phone': phone,
                    'name': name
                }
                
                # İndeks sözlüklerini güncelle
                if username:
                    self._entities_by_username[username.lower()] = entity_id
                if phone:
                    self._entities_by_phone[phone] = entity_id
                if name:
                    self._entities_by_name[name.lower()] = entity_id
            
            # Gönderilen dosyaları yükle
            self.db_cursor.execute(f"SELECT * FROM {self.table_prefix}_sent_files")
            sent_files = self.db_cursor.fetchall()
            
            # _sent_files sözlük olarak tanımla
            self._sent_files = {}
            
            for file_data in sent_files:
                md5_digest, file_size, file_type, file_id, file_hash = file_data
                
                # md5_digest bytes olarak kullanmak için
                if isinstance(md5_digest, memoryview):
                    md5_digest = bytes(md5_digest)
                
                self._sent_files[(md5_digest, file_size, file_type)] = (file_id, file_hash)
            
            # Update state bilgilerini yükle
            self.db_cursor.execute(f"SELECT * FROM {self.table_prefix}_update_state")
            update_states = self.db_cursor.fetchall()
            
            # _update_states sözlük olarak tanımla
            self._update_states = {}
            
            for state_data in update_states:
                state_id, pts, qts, date, seq = state_data
                self._update_states[state_id] = (pts, qts, date, seq)
            
            logger.info(f"PostgreSQL'den tüm veriler başarıyla yüklendi")
        except Exception as e:
            logger.error(f"PostgreSQL'den veri yüklenirken hata: {e}")
    
    def _update_session_table(self):
        """Oturum tablosunu güncelle"""
        try:
            # Önce mevcut verileri temizle
            self.db_cursor.execute(f"DELETE FROM {self.table_prefix}_sessions")
            
            # Auth key verisi
            auth_key_data = b'' if not self._auth_key else self._auth_key.key
            
            # memoryview'i bytes'a çevir
            if isinstance(auth_key_data, memoryview):
                auth_key_data = bytes(auth_key_data)
            
            # Yeni verileri ekle
            self.db_cursor.execute(
                f"INSERT INTO {self.table_prefix}_sessions VALUES (%s, %s, %s, %s, %s)",
                (self._dc_id, self._server_address, self._port,
                 auth_key_data,
                 self._takeout_id)
            )
            
            self.db_conn.commit()
        except Exception as e:
            logger.error(f"Oturum tablosu güncellenirken hata: {e}")
            self.db_conn.rollback()
            raise
    
    def _update_entities(self, rows):
        """Varlık (entity) kayıtlarını güncelle"""
        try:
            # Mevcut kayıtları sil
            self.db_cursor.execute(f"DELETE FROM {self.table_prefix}_entities")
            
            # Yeni kayıtları ekle
            if rows:
                now = int(time.time())
                rows = [(i, h, u, p, n, now) for i, h, u, p, n in rows]
                
                # PostgreSQL'de parametre gösterimi ? yerine %s ile yapılır
                insert_query = f"INSERT INTO {self.table_prefix}_entities VALUES (%s, %s, %s, %s, %s, %s)"
                self.db_cursor.executemany(insert_query, rows)
            
            self.db_conn.commit()
        except Exception as e:
            logger.error(f"Varlıklar güncellenirken hata: {e}")
            self.db_conn.rollback()
            raise
    
    def _update_sent_files(self, rows):
        """Gönderilen dosya kayıtlarını güncelle"""
        try:
            # Mevcut kayıtları sil
            self.db_cursor.execute(f"DELETE FROM {self.table_prefix}_sent_files")
            
            # Yeni kayıtları ekle
            if rows:
                # memoryview kontrolü
                clean_rows = []
                for row in rows:
                    md5_digest, file_size, file_type, file_id, file_hash = row
                    
                    # Binary verileri bytes'a dönüştür
                    if isinstance(md5_digest, memoryview):
                        md5_digest = bytes(md5_digest)
                    
                    clean_rows.append((md5_digest, file_size, file_type, file_id, file_hash))
                
                # PostgreSQL'de parametre gösterimi ? yerine %s ile yapılır
                insert_query = f"INSERT INTO {self.table_prefix}_sent_files VALUES (%s, %s, %s, %s, %s)"
                self.db_cursor.executemany(insert_query, clean_rows)
            
            self.db_conn.commit()
        except Exception as e:
            logger.error(f"Gönderilen dosyalar güncellenirken hata: {e}")
            self.db_conn.rollback()
            raise
    
    def _update_state(self, rows):
        """Durum kayıtlarını güncelle"""
        try:
            # Mevcut kayıtları sil
            self.db_cursor.execute(f"DELETE FROM {self.table_prefix}_update_state")
            
            # Yeni kayıtları ekle
            if rows:
                # PostgreSQL'de parametre gösterimi ? yerine %s ile yapılır
                insert_query = f"INSERT INTO {self.table_prefix}_update_state VALUES (%s, %s, %s, %s, %s)"
                self.db_cursor.executemany(insert_query, rows)
            
            self.db_conn.commit()
        except Exception as e:
            logger.error(f"Durum kayıtları güncellenirken hata: {e}")
            self.db_conn.rollback()
            raise
    
    def save(self):
        """Oturum verilerini PostgreSQL'e kaydet"""
        try:
            logger.info("PostgreSQL oturum verileri kaydediliyor...")
            
            # Oturum tablosunu güncelle
            self._update_session_table()
            
            # Entities veri tipi kontrolü ve düzeltme
            if isinstance(self._entities, set):
                logger.warning("_entities bir set olarak tanımlanmış, dict'e dönüştürülüyor")
                entity_dict = {}
                for entity in self._entities:
                    # Entity ID'sini belirle (normal bir entity objesi veya dict olabilir)
                    if isinstance(entity, dict) and 'id' in entity:
                        entity_id = entity['id']
                    elif hasattr(entity, 'id'):
                        entity_id = entity.id
                    else:
                        # Entity ID belirlenemezse, bu entity'yi atla
                        continue
                        
                    # Entity bilgilerini oluştur
                    entity_dict[entity_id] = {
                        'hash': getattr(entity, 'hash', 0),
                        'username': getattr(entity, 'username', None),
                        'phone': getattr(entity, 'phone', None),
                        'name': getattr(entity, 'name', None)
                    }
                
                # Set yerine dict kullan
                self._entities = entity_dict
                logger.info(f"_entities başarıyla dict'e dönüştürüldü ({len(self._entities)} adet entity)")
            
            # Varlıkları güncelle
            try:
                rows = [(i, d['hash'], d['username'], d['phone'], d['name'])
                    for i, d in self._entities.items()]
                self._update_entities(rows)
            except Exception as e:
                logger.error(f"Varlıklar güncellenirken hata: {e}")
            
            # Gönderilen dosyaları güncelle
            try:
                rows = [(*key, value[0], value[1])
                    for key, value in self._sent_files.items()]
                self._update_sent_files(rows)
            except Exception as e:
                logger.error(f"Gönderilen dosyalar güncellenirken hata: {e}")
            
            # Durum bilgilerini güncelle
            try:
                rows = [(x, *y) for x, y in self._update_states.items()]
                self._update_state(rows)
            except Exception as e:
                logger.error(f"Durum bilgileri güncellenirken hata: {e}")
            
            logger.info("PostgreSQL oturum verileri başarıyla kaydedildi")
        except Exception as e:
            logger.error(f"PostgreSQL verileri kaydedilirken hata: {e}")
            self.db_conn.rollback()
            raise
        
    def close(self):
        """Veritabanı bağlantısını kapat"""
        try:
            if self.db_cursor:
                self.db_cursor.close()
            
            if self.db_conn:
                self.db_conn.close()
                logger.info("PostgreSQL bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"PostgreSQL bağlantısı kapatılırken hata: {e}")
    
    def delete(self):
        """Oturum verilerini sil"""
        try:
            # Tüm tabloları sil
            tables = [
                f"{self.table_prefix}_sessions",
                f"{self.table_prefix}_entities",
                f"{self.table_prefix}_sent_files",
                f"{self.table_prefix}_update_state",
                f"{self.table_prefix}_version"
            ]
            
            for table in tables:
                self.db_cursor.execute(f"DROP TABLE IF EXISTS {table}")
            
            self.db_conn.commit()
            logger.info(f"PostgreSQL oturum verileri silindi: {self.table_prefix}_*")
        except Exception as e:
            logger.error(f"PostgreSQL oturum verileri silinirken hata: {e}")
            self.db_conn.rollback()
            raise

def migrate_sqlite_to_postgres(sqlite_path, session_name=None):
    """
    SQLite oturum dosyasındaki verileri PostgreSQL'e aktarır
    Args:
        sqlite_path: SQLite .session dosyasının yolu
        session_name: Oluşturulacak PostgreSQL oturumunun adı
    
    Returns:
        bool: Başarılı ise True, değilse False
    """
    if not session_name:
        session_name = os.path.basename(sqlite_path).replace('.session', '')
    
    logger.info(f"Telethon oturum verilerini SQLite -> PostgreSQL'e aktarma: {sqlite_path} -> {session_name}")
    
    try:
        # SQLite bağlantısı
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        
        # PostgreSQL oturumu
        postgres_session = PostgresSession(session_name)
        
        # Version bilgisini kontrol et
        sqlite_cursor.execute("SELECT version FROM version")
        version = sqlite_cursor.fetchone()
        if not version:
            logger.error("SQLite oturum dosyasında version bilgisi bulunamadı")
            return False
        
        # Sessions tablosunu kontrol et ve aktarma işlemini yapana kadar 
        # telethon client tarafından değiştirilmemesi için kilitle
        try:
            sqlite_cursor.execute("BEGIN IMMEDIATE TRANSACTION")
            
            # Oturum verilerini al
            sqlite_cursor.execute("SELECT * FROM sessions")
            session_data = sqlite_cursor.fetchone()
            
            # Oturum verilerini PostgreSQL'e aktar
            if session_data:
                # PostgreSQL'deki verileri temizle
                postgres_session.db_cursor.execute(f"DELETE FROM {postgres_session.table_prefix}_sessions")
                
                # Yeni verileri ekle
                postgres_session.db_cursor.execute(
                    f"INSERT INTO {postgres_session.table_prefix}_sessions VALUES (%s, %s, %s, %s, %s)",
                    (session_data['dc_id'], session_data['server_address'], 
                     session_data['port'], bytes(session_data['auth_key']), 
                     session_data['takeout_id'] if 'takeout_id' in session_data.keys() else None)
                )
                
                # Oturum verilerini belleğe kaydet
                postgres_session._dc_id = session_data['dc_id']
                postgres_session._server_address = session_data['server_address']
                postgres_session._port = session_data['port']
                postgres_session._auth_key = AuthKey(data=bytes(session_data['auth_key']))
                postgres_session._takeout_id = session_data.get('takeout_id')
                
                logger.info(f"PostgreSQL oturum verileri aktarıldı: DC {session_data['dc_id']}")
            
            # Entity verilerini aktarma
            sqlite_cursor.execute("SELECT * FROM entities")
            entities = sqlite_cursor.fetchall()
            
            if entities:
                # PostgreSQL'deki verileri temizle
                postgres_session.db_cursor.execute(f"DELETE FROM {postgres_session.table_prefix}_entities")
                
                # Entity verilerini ekle
                for entity in entities:
                    postgres_session.db_cursor.execute(
                        f"INSERT INTO {postgres_session.table_prefix}_entities VALUES (%s, %s, %s, %s, %s, %s)",
                        (entity['id'], entity['hash'], entity['username'], 
                         entity['phone'], entity['name'], time.time())
                    )
                    
                    # Belleğe de kaydet
                    postgres_session._entities[entity['id']] = {
                        'hash': entity['hash'],
                        'username': entity['username'],
                        'phone': entity['phone'],
                        'name': entity['name']
                    }
                    
                    # İndeksleri de güncelle
                    if entity['username']:
                        postgres_session._entities_by_username[entity['username'].lower()] = entity['id']
                    if entity['phone']:
                        postgres_session._entities_by_phone[entity['phone']] = entity['id']
                    if entity['name']:
                        postgres_session._entities_by_name[entity['name'].lower()] = entity['id']
            
                logger.info(f"{len(entities)} varlık (entity) PostgreSQL'e aktarıldı")
                
            # Sent files verilerini al
            sqlite_cursor.execute("SELECT * FROM sent_files")
            sent_files = sqlite_cursor.fetchall()
            
            if sent_files:
                # PostgreSQL'deki verileri temizle
                postgres_session.db_cursor.execute(f"DELETE FROM {postgres_session.table_prefix}_sent_files")
                
                # Sent files verilerini ekle
                for sent_file in sent_files:
                    postgres_session.db_cursor.execute(
                        f"INSERT INTO {postgres_session.table_prefix}_sent_files VALUES (%s, %s, %s, %s, %s)",
                        (bytes(sent_file['md5_digest']), sent_file['file_size'], 
                         sent_file['type'], sent_file['id'], sent_file['hash'])
                    )
                    
                    # Belleğe de kaydet
                    key = (bytes(sent_file['md5_digest']), sent_file['file_size'], sent_file['type'])
                    postgres_session._sent_files[key] = (sent_file['id'], sent_file['hash'])
                    
                logger.info(f"{len(sent_files)} gönderilmiş dosya PostgreSQL'e aktarıldı")
            
            # Update state verilerini al
            try:
                sqlite_cursor.execute("SELECT * FROM update_state")
                update_states = sqlite_cursor.fetchall()
                
                if update_states:
                    # PostgreSQL'deki verileri temizle
                    postgres_session.db_cursor.execute(f"DELETE FROM {postgres_session.table_prefix}_update_state")
                    
                    # Update state verilerini ekle
                    for state in update_states:
                        postgres_session.db_cursor.execute(
                            f"INSERT INTO {postgres_session.table_prefix}_update_state VALUES (%s, %s, %s, %s, %s)",
                            (state['id'], state['pts'], state['qts'], state['date'], state['seq'])
                        )
                        
                        # Belleğe de kaydet
                        postgres_session._update_states[state['id']] = (
                            state['pts'], state['qts'], state['date'], state['seq']
                        )
                        
                    logger.info(f"{len(update_states)} durum (state) kaydı PostgreSQL'e aktarıldı")
            except Exception as e:
                logger.warning(f"Update state tablosu bulunamadı veya aktarım hatası: {e}")
                
            # Transaction'ı tamamla
            postgres_session.db_conn.commit()
            
            logger.info(f"Oturum verileri başarıyla SQLite -> PostgreSQL'e aktarıldı: {sqlite_path} -> {session_name}")
            return True
            
        finally:
            # SQLite transaction'ı tamamla
            sqlite_conn.commit()
            sqlite_conn.close()
    except Exception as e:
        logger.error(f"SQLite -> PostgreSQL aktarımı sırasında hata: {e}")
        return False

# Bellek tabanlı geçici oturum oluşturucu
def create_memory_session(session_path=None):
    """Bellek tabanlı geçici oturum oluşturur. Yeniden başlatma sonrası kaybolur."""
    logger.info("Bellek tabanlı oturum (MemorySession) oluşturuluyor")
    memory_session = MemorySession()
    
    # TelegramClient oluşturup kontrol edelim
    try:
        api_id = settings.API_ID
        api_hash = settings.API_HASH
        client = TelegramClient(memory_session, api_id, api_hash)
        
        # Asenkron kontrol yapalım
        async def check_session():
            await client.connect()
            is_authorized = await client.is_user_authorized()
            if not is_authorized:
                logger.warning("MemorySession oturumu yetkili değil, yeni giriş yapmanız gerekecek")
            return is_authorized
            
        # Asenkron kontrolü çalıştıralım
        loop = asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else asyncio.new_event_loop()
        is_authorized = loop.run_until_complete(check_session())
        
        logger.info(f"Bellek tabanlı oturum durumu: {'Yetkili' if is_authorized else 'Yetkisiz'}")
    except Exception as e:
        logger.error(f"Bellek tabanlı oturum kontrolü sırasında hata: {e}")
        
    return memory_session

# String tabanlı oturum oluşturucu
def create_string_session(session_string=None):
    """String tabanlı oturum oluşturur."""
    logger.info("String tabanlı oturum (StringSession) oluşturuluyor")
    string_session = StringSession(session_string)
    
    # TelegramClient oluşturup kontrol edelim
    if session_string:
        try:
            api_id = settings.API_ID
            api_hash = settings.API_HASH
            client = TelegramClient(string_session, api_id, api_hash)
            
            # Asenkron kontrol yapalım
            async def check_session():
                await client.connect()
                is_authorized = await client.is_user_authorized()
                if not is_authorized:
                    logger.warning("StringSession oturumu yetkili değil, yeni giriş yapmanız gerekecek")
                return is_authorized
                
            # Asenkron kontrolü çalıştıralım
            loop = asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else asyncio.new_event_loop()
            is_authorized = loop.run_until_complete(check_session())
            
            logger.info(f"String tabanlı oturum durumu: {'Yetkili' if is_authorized else 'Yetkisiz'}")
        except Exception as e:
            logger.error(f"String tabanlı oturum kontrolü sırasında hata: {e}")
    
    return string_session

# Postgres tabanlı oturum oluşturucu
def create_postgres_session(session_name=None):
    """PostgreSQL tabanlı oturum oluşturur."""
    if not session_name:
        session_name = settings.SESSION_NAME

    logger.info(f"PostgreSQL tabanlı oturum oluşturuluyor: {session_name}")
    
    # SQLite oturumundan verileri aktarma kontrolü
    sqlite_session_path = os.path.join(settings.SESSIONS_DIR, f"{session_name}.session")
    if os.path.exists(sqlite_session_path):
        logger.info(f"SQLite oturum dosyası bulundu: {sqlite_session_path}")
        
        # Verileri aktarma işlemi
        try:
            # PostgreSQL oturum oluştur
            session = PostgresSession(session_name)
            
            # Oturum verileri var mı kontrol et
            if not session._auth_key:
                # Verileri SQLite'den aktarmayı dene
                logger.info(f"PostgreSQL oturumunda auth_key bulunamadı, SQLite verileri aktarılıyor...")
                if migrate_sqlite_to_postgres(sqlite_session_path, session_name):
                    # Başarılı aktarımdan sonra yeni bir PostgreSQL oturumu oluştur
                    session.close()
                    session = PostgresSession(session_name)
            
            # TelegramClient oluşturup oturumu kontrol edelim
            try:
                api_id = settings.API_ID
                api_hash = settings.API_HASH
                client = TelegramClient(session, api_id, api_hash)
                
                # Asenkron kontrol yapalım
                async def check_session():
                    await client.connect()
                    is_authorized = await client.is_user_authorized()
                    if not is_authorized:
                        logger.warning("PostgreSQL oturumu yetkili değil, yeni giriş yapmanız gerekecek")
                    return is_authorized
                    
                # Asenkron kontrolü çalıştıralım
                loop = asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else asyncio.new_event_loop()
                is_authorized = loop.run_until_complete(check_session())
                
                logger.info(f"PostgreSQL oturum durumu: {'Yetkili' if is_authorized else 'Yetkisiz'}")
            except Exception as e:
                logger.error(f"PostgreSQL oturum kontrolü sırasında hata: {e}")
            
            return session
        except Exception as e:
            logger.error(f"PostgreSQL tabanlı oturum oluşturulurken hata: {e}")
            logger.warning("Alternatif olarak bellek tabanlı oturuma geçiliyor...")
            return create_memory_session()
    else:
        logger.warning(f"SQLite oturum dosyası bulunamadı: {sqlite_session_path}")
        logger.warning("Yeni bir PostgreSQL oturumu oluşturulacak, ancak oturum açmanız gerekebilir.")
        
        try:
            # PostgreSQL tabanlı oturum oluştur
            session = PostgresSession(session_name)
            
            # TelegramClient oluşturup oturumu kontrol edelim
            try:
                api_id = settings.API_ID
                api_hash = settings.API_HASH
                client = TelegramClient(session, api_id, api_hash)
                
                # Asenkron kontrol yapalım
                async def check_session():
                    await client.connect()
                    is_authorized = await client.is_user_authorized()
                    if not is_authorized:
                        logger.warning("Yeni PostgreSQL oturumu yetkili değil, giriş yapmanız gerekecek")
                    return is_authorized
                    
                # Asenkron kontrolü çalıştıralım
                loop = asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else asyncio.new_event_loop()
                is_authorized = loop.run_until_complete(check_session())
                
                logger.info(f"Yeni PostgreSQL oturum durumu: {'Yetkili' if is_authorized else 'Yetkisiz'}")
            except Exception as e:
                logger.error(f"Yeni PostgreSQL oturum kontrolü sırasında hata: {e}")
            
            return session
        except Exception as e:
            logger.error(f"PostgreSQL tabanlı oturum oluşturulurken hata: {e}")
            logger.warning("Alternatif olarak bellek tabanlı oturuma geçiliyor...")
            return create_memory_session()

# Varsayılan dosya tabanlı oturum oluşturucu
def create_session(session_name=None):
    """Dosya tabanlı oturum oluşturur."""
    if not session_name:
        session_name = settings.SESSION_NAME

    # Oturum dosyasının tam yolu
    session_path = os.path.join(settings.SESSIONS_DIR, f"{session_name}")
    
    logger.info(f"Telethon oturumu başlatılıyor: {session_path}")
    return session_path 

# Otomatik oturum başlatma ve avantajlı fonksiyonu
def initialize_client(session=None, auto_auth=True):
    """
    TelegramClient oluşturur ve otomatik giriş yapar
    
    Args:
        session: Oturum nesnesi (None ise PostgresSession oluşturulur)
        auto_auth: Otomatik giriş yapılıp yapılmayacağı
        
    Returns:
        TelegramClient: Oluşturulan ve bağlanan istemci
    """
    try:
        # Oturum sağlanmamışsa PostgreSQL oturumu oluştur
        if not session:
            try:
                session = create_postgres_session()
                logger.info(f"PostgreSQL oturumu başarıyla oluşturuldu")
            except Exception as e:
                logger.error(f"PostgreSQL oturumu oluşturulamadı: {e}")
                logger.warning("Memory oturumuna geçiliyor...")
                try:
                    session = create_memory_session()
                    logger.info("Memory oturumu başarıyla oluşturuldu")
                except Exception as e:
                    logger.error(f"Memory oturumu da oluşturulamadı: {e}")
                    logger.critical("Hiçbir oturum türü oluşturulamadı, işlem durduruluyor")
                    raise RuntimeError("Oturum oluşturulamadı") from e
        
        # Session'ın name özelliği var mı kontrol edelim
        if not hasattr(session, 'name') and hasattr(session, 'filename'):
            # Özellik yoksa ekleyelim
            session.name = session.filename.split('/')[-1].replace('.session', '')
            logger.info(f"Session name özelliği otomatik oluşturuldu: {session.name}")
        
        # TelegramClient oluştur
        try:
            api_id = settings.API_ID
            api_hash = settings.API_HASH
            client = TelegramClient(session, api_id, api_hash)
            logger.info(f"TelegramClient başarıyla oluşturuldu")
        except Exception as e:
            logger.error(f"TelegramClient oluşturulurken hata: {e}")
            raise RuntimeError("TelegramClient oluşturulamadı") from e
        
        # Otomatik giriş yapılsın mı?
        if auto_auth:
            # auto_login'i doğrudan çağırmadan bir tasarım deseni kullanacağız
            # Bu şekilde event loop sorununu aşacağız
            client._auto_auth_required = True
        
        return client
    except Exception as e:
        logger.critical(f"TelegramClient başlatma sırasında beklenmeyen hata: {e}")
        raise

# TDLib durumunu kontrol eden ve buna göre istemci oluşturan fonksiyon
def get_telegram_client(use_tdlib=True, session=None, auto_auth=True):
    """
    TDLib veya Telethon istemcisi oluşturur
    
    Args:
        use_tdlib: TDLib kullanılıp kullanılmayacağı (mevcutsa)
        session: Oturum nesnesi
        auto_auth: Otomatik giriş yapılıp yapılmayacağı
        
    Returns:
        client: TDLib veya Telethon istemcisi
    """
    try:
        # Global TDLIB_AVAILABLE değişkenini kontrol et
        global TDLIB_AVAILABLE
        
        # TDLib kullanma seçeneği etkinleştirilmiş mi?
        tdlib_enabled = False
        
        try:
            # settings'ten tdlib kullanımını kontrol et
            if hasattr(settings, 'USE_TDLIB'):
                tdlib_enabled = settings.USE_TDLIB
        except Exception as e:
            logger.warning(f"USE_TDLIB ayarı kontrol edilirken hata: {e}")
        
        # TDLib kullanmayı deneyelim
        if use_tdlib and tdlib_enabled and TDLIB_AVAILABLE:
            try:
                # TDLib import kontrolü (tekrar kontrol)
                import importlib.util
                spec = importlib.util.find_spec('tdlib')
                
                if spec is not None:
                    # TDLib istemcisi oluştur
                    try:
                        import tdlib
                        from app.core.tdlib.client import TDLibClient
                        
                        logger.info("TDLib istemcisi oluşturuluyor...")
                        client = TDLibClient()
                        
                        # Otomatik giriş
                        if auto_auth:
                            try:
                                client.login()
                                logger.info("TDLib istemcisi başarıyla giriş yaptı")
                            except Exception as e:
                                logger.error(f"TDLib istemcisi ile giriş sırasında hata: {e}")
                                logger.warning("Telethon istemcisine geçiliyor...")
                                return initialize_client(session=session, auto_auth=auto_auth)
                            
                        logger.info("TDLib istemcisi başarıyla oluşturuldu")
                        return client
                    except Exception as e:
                        logger.error(f"TDLib istemcisi oluşturulurken hata: {e}")
                        logger.warning("Telethon istemcisine geçiliyor...")
                else:
                    logger.warning("TDLib modülü bulunamadı, Telethon istemcisine geçiliyor...")
            except Exception as e:
                logger.error(f"TDLib kullanımı sırasında hata: {e}")
                logger.warning("Telethon istemcisine geçiliyor...")
        else:
            if use_tdlib:
                # TDLib neden kullanılmadığı açıklanıyor
                if not tdlib_enabled:
                    logger.info("settings.USE_TDLIB ayarı aktif değil, Telethon kullanılıyor")
                elif not TDLIB_AVAILABLE:
                    logger.info("TDLib modülü yüklü değil, Telethon kullanılıyor")
            else:
                logger.info("Telethon istemcisi tercih edildi")
        
        # Telethon istemcisi oluştur
        logger.info("Telethon istemcisi oluşturuluyor...")
        return initialize_client(session=session, auto_auth=auto_auth)
    except Exception as e:
        logger.critical(f"Telegram istemcisi oluşturulurken beklenmeyen hata: {e}")
        # Son çare olarak basit Telethon istemcisi oluşturmayı deneyelim
        try:
            # MemorySession kullanarak bir istemci oluştur
            memory_session = MemorySession()
            client = TelegramClient(memory_session, 
                                   settings.API_ID if hasattr(settings, 'API_ID') else 0, 
                                   settings.API_HASH if hasattr(settings, 'API_HASH') else '')
            logger.warning("Acil durum Telethon istemcisi oluşturuldu (MemorySession), oturum kalıcı olmayacak!")
            return client
        except Exception as e2:
            logger.critical(f"Son çare Telethon istemcisi oluşturulamadı: {e2}")
            raise RuntimeError("Telegram istemcisi oluşturulamadı") from e 