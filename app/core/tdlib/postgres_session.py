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

logger = logging.getLogger(__name__)

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
        self.table_prefix = f"telethon_{self.name}"
        
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
                self._auth_key = AuthKey(data=key)
                logger.info(f"PostgreSQL'den oturum verileri yüklendi (DC: {self._dc_id})")
            
            # Varlıkları (entities) yükle
            self.db_cursor.execute(f"SELECT * FROM {self.table_prefix}_entities")
            entities = self.db_cursor.fetchall()
            
            for entity_data in entities:
                entity_id, entity_hash, username, phone, name, date = entity_data
                self._entities[entity_id] = {
                    'hash': entity_hash,
                    'username': username,
                    'phone': phone,
                    'name': name
                }
                
                if username:
                    self._entities_by_username[username.lower()] = entity_id
                if phone:
                    self._entities_by_phone[phone] = entity_id
                if name:
                    self._entities_by_name[name.lower()] = entity_id
            
            # Gönderilen dosyaları yükle
            self.db_cursor.execute(f"SELECT * FROM {self.table_prefix}_sent_files")
            sent_files = self.db_cursor.fetchall()
            
            for file_data in sent_files:
                md5_digest, file_size, file_type, file_id, file_hash = file_data
                self._sent_files[(md5_digest, file_size, file_type)] = (file_id, file_hash)
            
            # Update state bilgilerini yükle
            self.db_cursor.execute(f"SELECT * FROM {self.table_prefix}_update_state")
            update_states = self.db_cursor.fetchall()
            
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
            
            # Yeni verileri ekle
            self.db_cursor.execute(
                f"INSERT INTO {self.table_prefix}_sessions VALUES (%s, %s, %s, %s, %s)",
                (self._dc_id, self._server_address, self._port,
                 self._auth_key.key if self._auth_key else b'',
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
                # PostgreSQL'de parametre gösterimi ? yerine %s ile yapılır
                insert_query = f"INSERT INTO {self.table_prefix}_sent_files VALUES (%s, %s, %s, %s, %s)"
                self.db_cursor.executemany(insert_query, rows)
            
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
            
            # Varlıkları güncelle
            rows = [(i, d['hash'], d['username'], d['phone'], d['name'])
                   for i, d in self._entities.items()]
            self._update_entities(rows)
            
            # Gönderilen dosyaları güncelle
            rows = [(*key, value[0], value[1])
                   for key, value in self._sent_files.items()]
            self._update_sent_files(rows)
            
            # Durum bilgilerini güncelle
            rows = [(x, *y) for x, y in self._update_states.items()]
            self._update_state(rows)
            
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
    return memory_session

# String tabanlı oturum oluşturucu
def create_string_session(session_string=None):
    """String tabanlı oturum oluşturur."""
    logger.info("String tabanlı oturum (StringSession) oluşturuluyor")
    string_session = StringSession(session_string)
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