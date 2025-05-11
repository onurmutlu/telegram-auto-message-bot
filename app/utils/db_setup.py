import sqlite3
import json
from datetime import datetime, timedelta
from colorama import Fore, Style
from typing import List, Dict, Optional
import os
import logging
import asyncio
import time
# Logger configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
class Database:
    def __init__(self, db_path: str = 'data/users.db'):
        """
        Veritabanı sınıfını başlatır.
        
        Args:
            db_path: Veritabanı dosya yolu
        """
        self.db_path = db_path
        
        # Dizin kontrolü
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Veritabanı dizini oluşturuldu: {db_dir}")
            except Exception as e:
                logger.error(f"Dizin oluşturma hatası: {str(e)}")
                raise RuntimeError(f"Veritabanı dizini oluşturulamadı: {str(e)}")
        
        # Bağlantı kurma
        try:
            self.conn = sqlite3.connect(db_path, timeout=30)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # SQLite optimizasyonları
            self.cursor.execute("PRAGMA journal_mode=WAL")
            self.cursor.execute("PRAGMA busy_timeout=10000")
            
            # Başarılı bağlantı testi
            self.cursor.execute("SELECT 1")
            logger.info(f"Veritabanı bağlantısı kuruldu: {db_path}")
            
            # Temel tabloları oluştur
            self._create_tables()
            
        except Exception as e:
            logger.error(f"Veritabanı bağlantı hatası: {str(e)}")
            # KRITIK: Bağlantıyı None olarak ayarlama!
            # self.conn = None  
            # self.cursor = None
            raise RuntimeError(f"Veritabanı bağlantısı kurulamadı: {str(e)}")
        
    async def init_db(self):
        """Veritabanını başlatır ve gerekli tabloları oluşturur"""
        try:
            # Tabloları oluştur
            self._create_tables()
            
            self.conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging modu
            self.conn.execute("PRAGMA busy_timeout=5000")  # 5 saniye timeout
            
            print(f"{Fore.GREEN}Veritabanı başarıyla başlatıldı{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}Veritabanı başlatma hatası: {str(e)}{Style.RESET_ALL}")
            raise
            
    def _create_tables(self):
        """Gerekli tabloları oluşturur"""
        # Gruplar tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                member_count INTEGER DEFAULT 0,
                last_message DATETIME,
                message_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                last_error DATETIME,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Kullanıcılar tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                group_id INTEGER,
                is_blocked BOOLEAN DEFAULT 0,
                last_message DATETIME,
                message_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(group_id)
            )
        ''')
        
        # Mesajlar tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                content TEXT,
                sent_at DATETIME,
                status TEXT,
                error_message TEXT,
                FOREIGN KEY (group_id) REFERENCES groups(group_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # İndeksler
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_groups_active ON groups(is_active)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_groups_last_message ON groups(last_message)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_group ON users(group_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(is_blocked)')
        
        self.conn.commit()
        
    async def get_target_groups(self):
        """Tüm hedef grupları getirir"""
        self.cursor.execute('''
            SELECT * FROM groups
        ''')
        groups = self.cursor.fetchall()
        return [{
            'group_id': row[0],
            'name': row[1],
            'join_date': row[2],
            'last_message': row[3],
            'message_count': row[4],
            'member_count': row[5],
            'error_count': row[6],
            'last_error': row[7],
            'is_active': bool(row[8]),
            'retry_after': row[9]
        } for row in groups]
        
    async def add_target_group(self, group_id: int, name: str, member_count: int = 0):
        """Hedef grubu veritabanına ekler veya günceller"""
        try:
            # İlk olarak grubun var olup olmadığını kontrol et
            self.cursor.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
            exists = self.cursor.fetchone()
            
            if exists:
                # Mevcut grup kaydını güncelle
                self.cursor.execute('''
                    UPDATE groups
                    SET name = ?, member_count = ?, updated_at = ?
                    WHERE group_id = ?
                ''', (name, member_count, datetime.now(), group_id))
                logger.debug(f"Grup güncellendi: {name} (ID: {group_id})")
            else:
                # Yeni grup ekle
                self.cursor.execute('''
                    INSERT INTO groups (group_id, name, member_count, join_date, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                ''', (group_id, name, member_count, datetime.now(), datetime.now(), datetime.now()))
                logger.info(f"Yeni grup eklendi: {name} (ID: {group_id})")
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Grup eklenirken hata: {str(e)}")
            return False
        
    async def update_group_stats(self, group_id: int, last_message: datetime = None, message_count: int = 1):
        """Grup istatistiklerini günceller"""
        self.cursor.execute('''
            UPDATE groups 
            SET last_message = ?, 
                message_count = message_count + ?,
                updated_at = ?
            WHERE group_id = ?
        ''', (last_message or datetime.now(), message_count, datetime.now(), group_id))
        self.conn.commit()
        
    async def mark_group_inactive(self, group_id: int, error_message: str = None, retry_time=None, permanent: bool = False):
        """
        Grubu devre dışı bırakır
        
        Args:
            group_id: Grup ID
            error_message: Hata mesajı
            retry_time: Yeniden deneme zamanı (default: şu andan 24 saat sonrası)
            permanent: Kalıcı olarak devre dışı bırak (admin hatası vb. için)
        """
        try:
            # Varsayılan retry_time şimdiden 24 saat sonrası
            if retry_time is None and not permanent:
                retry_time = datetime.now() + timedelta(hours=24)
            
            # Kalıcı olarak devre dışı bırakılacaksa retry_time NULL olmalı
            retry_time_str = retry_time.strftime('%Y-%m-%d %H:%M:%S') if retry_time and not permanent else None
            
            # Şu an için retry_time belirlenmemişse (permanent=True durumu)
            permanent_flag = 1 if permanent else 0
            
            # Kilit sorununu çözmek için 3 kez deneme ekleyin
            for attempt in range(3):
                try:
                    self.cursor.execute('''
                        UPDATE groups 
                        SET is_active = 0,
                            error_count = error_count + 1,
                            last_error = ?,
                            retry_after = ?,
                            permanent_error = ?,
                            updated_at = ?
                        WHERE group_id = ?
                    ''', (error_message or "Bilinmeyen hata", retry_time_str, permanent_flag, datetime.now(), group_id))
                    
                    self.conn.commit()
                    
                    if permanent:
                        logger.warning(f"Grup {group_id} kalıcı olarak devre dışı bırakıldı: {error_message}")
                    else:
                        logger.info(f"Grup {group_id} şu tarihe kadar devre dışı bırakıldı: {retry_time}")
                    
                    return True
                    
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) and attempt < 2:
                        logger.warning(f"Veritabanı kilitli, {attempt+1}/3 deneme...")
                        await asyncio.sleep(1)  # 1 saniye bekle ve tekrar dene
                    else:
                        raise
            
            logger.error(f"Veritabanı kilidi nedeniyle grup {group_id} devre dışı bırakılamadı")
            return False
            
        except Exception as e:
            logger.error(f"Grup devre dışı bırakılırken hata: {str(e)}")
            return False
        
    async def reactivate_group(self, group_id):
        """Grubu tekrar aktif eder"""
        self.cursor.execute('''
            UPDATE groups 
            SET is_active = 1,
                retry_after = NULL,
                updated_at = ?
            WHERE group_id = ?
        ''', (datetime.now(), group_id))
        self.conn.commit()
        
    async def get_group_stats(self, group_id: int) -> Optional[Dict]:
        """Grup istatistiklerini getirir"""
        self.cursor.execute('SELECT * FROM groups WHERE group_id = ?', (group_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                'group_id': row[0],
                'name': row[1],
                'member_count': row[2],
                'last_message': row[3],
                'message_count': row[4],
                'error_count': row[5],
                'last_error': row[6],
                'is_active': row[7],
                'created_at': row[8],
                'updated_at': row[9]
            }
        return None
        
    async def remove_target_group(self, group_id: int):
        """Hedef grubu veri tabanından tamamen kaldırır"""
        try:
            self.cursor.execute('''
                DELETE FROM groups WHERE group_id = ?
            ''', (group_id,))
            self.conn.commit()
            logger.info(f"Grup {group_id} veritabanından kaldırıldı")
            return True
        except Exception as e:
            logger.error(f"Grup kaldırılırken hata: {str(e)}")
            return False

    async def get_active_groups(self):
        """
        Aktif grupları ve süresi dolan devre dışı grupları getirir
        """
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.cursor.execute('''
                SELECT * FROM groups 
                WHERE is_active = 1 
                   OR (retry_after IS NOT NULL AND retry_after <= ? AND permanent_error = 0)
            ''', (current_time,))
            
            groups = self.cursor.fetchall()
            result = []
            
            for group in groups:
                # Sütun isimleri bağlama göre değişebilir, doğru indeksleri kullanın
                group_dict = {
                    'group_id': group[0],
                    'name': group[1],
                    'join_date': group[2],
                    'last_message': group[3],
                    'message_count': group[4],
                    'member_count': group[5],
                    'error_count': group[6],
                    'last_error': group[7],
                    'is_active': bool(group[8]),
                    'retry_after': group[9],
                    'permanent_error': bool(group[10]) if len(group) > 10 else False
                }
                result.append(group_dict)
                
                # Eğer retry_after süresi geçmiş ve devre dışı bir grupsa aktifleştir
                if not group_dict['is_active'] and group_dict['retry_after'] and datetime.strptime(group_dict['retry_after'], '%Y-%m-%d %H:%M:%S') <= datetime.now():
                    await self.reactivate_group(group_dict['group_id'])
            
            return result
        except Exception as e:
            logger.error(f"Aktif grupları getirirken hata: {str(e)}")
            return []

    async def add_discovered_group(self, group_id: int, name: str, member_count: int = 0, 
                              is_active: bool = True, is_target: bool = True):
        """
        Keşfedilen grubu veritabanına ekler veya günceller
        
        Args:
            group_id: Grup ID
            name: Grup adı
            member_count: Grup üye sayısı
            is_active: Grup aktif mi?
            is_target: Hedef grup mu? (üye toplamak veya mesaj göndermek için)
        """
        try:
            # İlk olarak grubun var olup olmadığını kontrol et
            self.cursor.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
            exists = self.cursor.fetchone()
            
            if exists:
                # Mevcut grup kaydını güncelle
                self.cursor.execute('''
                    UPDATE groups
                    SET name = ?, member_count = ?, is_active = ?, is_target = ?, updated_at = ?
                    WHERE group_id = ?
                ''', (name, member_count, int(is_active), int(is_target), datetime.now(), group_id))
            else:
                # Yeni grup ekle
                self.cursor.execute('''
                    INSERT INTO groups 
                    (group_id, name, join_date, member_count, is_active, is_target, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    group_id, name, datetime.now(), member_count, 
                    int(is_active), int(is_target), datetime.now(), datetime.now()
                ))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Grup eklenirken hata: {str(e)}")
            return False

    async def get_all_target_groups(self):
        """
        Veritabanından tüm hedef grupları getirir
        """
        try:
            # Düzeltildi: "title" yerine "name" kullanılıyor
            self.cursor.execute('''
                SELECT group_id, name, member_count
                FROM groups 
                WHERE is_target = 1
            ''')
            
            result = []
            for row in self.cursor.fetchall():
                result.append({
                    'group_id': row[0],
                    'name': row[1],  # Anahtar adı bununla uyumlu olmalı
                    'member_count': row[2]
                })
                
            return result
        except Exception as e:
            logger.error(f"Hedef gruplar alınırken hata: {str(e)}")
            return []

    def close(self):
        """Veritabanı bağlantısını kapatır"""
        if self.conn:
            self.conn.close()

    def create_tables(self):
        """Gerekli tabloları oluşturur"""
        try:
            # Users tablosu - Kalıcı kullanıcı kaydı için
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                source_group TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_invited TIMESTAMP,
                invite_count INTEGER DEFAULT 0,
                is_bot INTEGER DEFAULT 0,
                is_replied INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Üye-grup ilişki tablosu
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                group_id INTEGER,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id)
            )
            ''')
            
            # Davet geçmişi tablosu
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS invite_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                response TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            ''')
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Tablo oluşturma hatası: {str(e)}")
            return False
            
    def add_or_update_user(self, user_data):
        """
        Kullanıcıyı veritabanına ekler veya günceller
        
        Args:
            user_data: dict - Kullanıcı verisi
                {user_id, username, first_name, last_name, source_group, is_bot}
        """
        try:
            # Kullanıcının mevcut olup olmadığını kontrol et
            user_id = user_data['user_id']
            self.cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
            exists = self.cursor.fetchone()
            
            now = datetime.now()
            
            if exists:
                # Mevcut kullanıcıyı güncelle, ama bazı alanları korumak için önce verileri al
                self.cursor.execute('SELECT invite_count, last_invited, status FROM users WHERE user_id = ?', (user_id,))
                db_data = self.cursor.fetchone()
                
                # SQL sorgusu hazırla, sadece temel bilgileri güncelle
                self.cursor.execute('''
                    UPDATE users
                    SET username = COALESCE(?, username),
                        first_name = COALESCE(?, first_name),
                        last_name = COALESCE(?, last_name),
                        source_group = COALESCE(?, source_group),
                        is_bot = ?,
                        updated_at = ?
                    WHERE user_id = ?
                ''', (
                    user_data.get('username'),
                    user_data.get('first_name'),
                    user_data.get('last_name'),
                    user_data.get('source_group'),
                    int(user_data.get('is_bot', 0)),
                    now,
                    user_id
                ))
                
                # Kullanıcı-grup ilişkisini ekle (varsa)
                if 'group_id' in user_data:
                    self._add_user_group_relation(user_id, user_data['group_id'])
                    
            else:
                # Yeni kullanıcı ekle
                self.cursor.execute('''
                    INSERT INTO users
                    (user_id, username, first_name, last_name, source_group, is_bot, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    user_data.get('username'),
                    user_data.get('first_name'),
                    user_data.get('last_name'),
                    user_data.get('source_group'),
                    int(user_data.get('is_bot', 0)),
                    now,
                    now
                ))
                
                # Kullanıcı-grup ilişkisini ekle (varsa)
                if 'group_id' in user_data:
                    self._add_user_group_relation(user_id, user_data['group_id'])
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Kullanıcı ekleme/güncelleme hatası: {str(e)}")
            return False

    def _add_user_group_relation(self, user_id, group_id):
        """
        Kullanıcının grup ilişkisini ekler
        """
        try:
            now = datetime.now()
            self.cursor.execute('''
                INSERT OR IGNORE INTO user_groups
                (user_id, group_id, join_date)
                VALUES (?, ?, ?)
            ''', (user_id, group_id, now))
            return True
        except Exception as e:
            logger.error(f"Kullanıcı-grup ilişkisi ekleme hatası: {str(e)}")
            return False
            
    def mark_user_invited(self, user_id):
        """
        Kullanıcının davet edildiğini işaretler
        """
        try:
            now = datetime.now()
            self.cursor.execute('''
                UPDATE users
                SET last_invited = ?,
                    invite_count = invite_count + 1,
                    updated_at = ?
                WHERE user_id = ?
            ''', (now, now, user_id))
            
            # Ayrıca davet geçmişine ekle
            self.cursor.execute('''
                INSERT INTO invite_history
                (user_id, sent_at, status)
                VALUES (?, ?, ?)
            ''', (user_id, now, 'sent'))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Kullanıcının davet durumu güncellenemedi: {str(e)}")
            return False
            
    def get_users_for_invite(self, limit=50, cooldown_hours=24):
        """Davet edilecek kullanıcıları getirir"""
        try:
            now = datetime.now()
            cooldown = now - timedelta(hours=cooldown_hours)
            
            # 'id' yerine 'user_id' sütununu kullan
            self.cursor.execute('''
                SELECT user_id, username, first_name, last_name
                FROM users 
                WHERE (last_invited IS NULL OR last_invited < ?) 
                  AND is_bot = 0
                  AND status = 'active'
                ORDER BY RANDOM()
                LIMIT ?
            ''', (cooldown, limit))
            
            users = []
            for row in self.cursor.fetchall():
                users.append({
                    'user_id': row[0],
                    'username': row[1],
                    'first_name': row[2],
                    'last_name': row[3]
                })
                
            return users
        except Exception as e:
            logger.error(f"get_users_for_invite error: {str(e)}")
            return []

    def execute_with_retry(self, query, params=None, max_retries=3):
        """Kilitlenme durumlarında yeniden deneme mekanizması"""
        for attempt in range(max_retries):
            try:
                self.cursor.execute(query, params or ())
                self.conn.commit()
                return True
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries-1:
                    # Artan bekleme süresi ile tekrar dene
                    time.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    # Son denemede veya farklı bir hata durumunda
                    raise
        return False

def setup_profile_tables(db_path='data/users.db'):
    """Profil tablolarını kurar."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Kullanıcı profil tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            gender_guess TEXT,
            gender_confidence REAL DEFAULT 0.0,
            age_range TEXT,
            demographic_group TEXT,
            communication_style TEXT,
            segment TEXT,
            interests TEXT,
            messages_analyzed INTEGER DEFAULT 0,
            last_message_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Kullanıcı mesajları tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_text TEXT,
            chat_id INTEGER,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            analyzed BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''')
        
        # Kullanıcı tercihleri tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'tr',
            theme TEXT DEFAULT 'default',
            notification_enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''')
        
        conn.commit()
        print(f"{Fore.GREEN}Kullanıcı profil tabloları başarıyla oluşturuldu{Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"{Fore.RED}Kullanıcı profil tabloları oluşturma hatası: {str(e)}{Style.RESET_ALL}")
        return False
    finally:
        conn.close()

def setup_group_tables(db_path='data/users.db'):
    """Grup tablolarını kurar."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Grup tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            member_count INTEGER DEFAULT 0,
            last_activity TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
        ''')
        
        # İs_active sütunu mevcut değilse ekle
        try:
            cursor.execute("ALTER TABLE groups ADD COLUMN is_active INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            # Sütun zaten var, hata görmezden gelinebilir
            pass
            
        conn.commit()
        print("Grup tabloları başarıyla oluşturuldu")
    except Exception as e:
        print(f"Grup tabloları oluşturulurken hata: {str(e)}")
    finally:
        conn.close()

def upgrade_database():
    """
    Veritabanı şemasını en son versiyona yükseltir.
    """
    from database.schema import TABLES, MIGRATIONS, DB_SCHEMA_VERSION
    import sqlite3
    import os
    
    db_path = os.environ.get('DB_PATH', 'runtime/database/users.db')
    
    # Veritabanı dizininin varlığını kontrol et
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    # Veritabanı bağlantısı oluştur
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # Şema versiyonu tablosu
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Mevcut şema versiyonunu kontrol et
        cursor = conn.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
        row = cursor.fetchone()
        current_version = row['version'] if row else '0.0'
        
        print(f"Mevcut veritabanı şema versiyonu: {current_version}")
        print(f"Hedef veritabanı şema versiyonu: {DB_SCHEMA_VERSION}")
        
        # Eğer güncel değilse tabloları oluştur ve migrasyonları uygula
        if current_version != DB_SCHEMA_VERSION:
            print("Veritabanı şeması güncelleniyor...")
            
            # Tabloları oluştur
            for table_sql in TABLES:
                conn.execute(table_sql)
                
            # Migrasyonları uygula
            for migration_sql in MIGRATIONS:
                conn.executescript(migration_sql)
                
            # Şema versiyonunu güncelle
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (DB_SCHEMA_VERSION,))
            conn.commit()
            
            print(f"Veritabanı başarıyla {DB_SCHEMA_VERSION} versiyonuna güncellendi.")
        else:
            print("Veritabanı şeması zaten güncel.")
            
    except Exception as e:
        print(f"Veritabanı güncellenirken hata: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade_database()