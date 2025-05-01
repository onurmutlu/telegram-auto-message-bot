from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, create_engine, text, func, BigInteger, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class Group(Base):
    __tablename__ = 'groups'
    
    group_id = Column(BigInteger, primary_key=True)
    name = Column(String)
    username = Column(String, nullable=True)  # Grubun kullanıcı adı
    description = Column(String, nullable=True)  # Grup açıklaması
    join_date = Column(DateTime, default=func.now())
    last_message = Column(DateTime)
    message_count = Column(Integer, default=0)
    member_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    last_error = Column(DateTime)
    is_active = Column(Boolean, default=True)
    permanent_error = Column(Boolean, default=False)
    is_target = Column(Boolean, default=False)
    retry_after = Column(DateTime)
    is_admin = Column(Boolean, default=False)  # Bizim admin olduğumuz grup mu?
    is_public = Column(Boolean, default=True)  # Grup public mi private mi?
    invite_link = Column(String, nullable=True)  # Grubun davet linki
    source = Column(String, nullable=True)  # Grup kaynağı (discover, manual, etc.)
    last_active = Column(DateTime, default=func.now())  # Son aktivite zamanı
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # İlişkiler
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    analytics = relationship("GroupAnalytics", back_populates="group", cascade="all, delete-orphan")

class DebugBotUser(Base):
    __tablename__ = 'debug_bot_users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    access_level = Column(String)
    first_seen = Column(DateTime, default=datetime.now)
    last_seen = Column(DateTime, default=datetime.now)
    is_developer = Column(Boolean, server_default=text('false'))
    is_superuser = Column(Boolean, server_default=text('false'))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class UserGroupRelation(Base):
    __tablename__ = 'user_group_relation'
    
    user_id = Column(BigInteger, ForeignKey('debug_bot_users.user_id'), primary_key=True)
    group_id = Column(BigInteger, ForeignKey('groups.group_id'), primary_key=True)
    joined_at = Column(DateTime, default=func.now())
    last_seen = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Setting(Base):
    __tablename__ = 'settings'
    
    key = Column(String, primary_key=True)
    value = Column(String)
    description = Column(String)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

# Kullanıcı modeli
class TelegramUser(Base):
    __tablename__ = 'telegram_users'
    
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_bot = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    language_code = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    first_seen = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # İlişkiler
    group_memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")

# Grup üyeliği için ayrı bir tablo
class GroupMember(Base):
    __tablename__ = 'group_members'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('telegram_users.user_id'), nullable=False)
    group_id = Column(BigInteger, ForeignKey('groups.group_id'), nullable=False)
    joined_at = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, default=func.now())
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    admin_rights = Column(String, nullable=True)  # JSON formatında admin yetkileri
    title = Column(String, nullable=True)  # Admin/üye başlığı
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # İlişkiler
    user = relationship("TelegramUser", back_populates="group_memberships")
    group = relationship("Group", back_populates="members")
    
    # Unique constraint eklendi
    __table_args__ = (
        UniqueConstraint('user_id', 'group_id', name='unique_user_group'),
    )

# Grup analitiği için tablo
class GroupAnalytics(Base):
    __tablename__ = 'group_analytics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(BigInteger, ForeignKey('groups.group_id'), nullable=False)
    date = Column(DateTime, default=func.now())
    member_count = Column(Integer, default=0)
    message_count = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    engagement_rate = Column(Integer, default=0)  # Mesaj sayısı / üye sayısı
    growth_rate = Column(Integer, default=0)  # Günlük büyüme oranı
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # İlişkiler
    group = relationship("Group", back_populates="analytics")

# Data Mining için güçlendirilmiş tablo
class DataMining(Base):
    __tablename__ = 'data_mining'
    
    mining_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('telegram_users.user_id'), nullable=True)
    telegram_id = Column(BigInteger, nullable=True)
    group_id = Column(BigInteger, ForeignKey('groups.group_id'), nullable=True)
    type = Column(String)  # Mining tipi (user, group, message, etc.)
    source = Column(String)  # Veri kaynağı
    data = Column(String)  # JSON formatında veri
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

# Mesajları izlemek için tablo
class MessageTracking(Base):
    __tablename__ = 'message_tracking'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(BigInteger, nullable=False)
    group_id = Column(BigInteger, ForeignKey('groups.group_id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('telegram_users.user_id'), nullable=True)
    sent_at = Column(DateTime, default=func.now())
    content = Column(String, nullable=True)
    content_type = Column(String, default="text")  # Mesaj tipi (text, photo, video, etc.)
    is_outgoing = Column(Boolean, default=False)  # Bizim gönderdiğimiz mesaj mı?
    is_reply = Column(Boolean, default=False)  # Yanıt mı?
    reply_to_message_id = Column(Integer, nullable=True)  # Yanıt verilen mesaj
    forwards = Column(Integer, default=0)  # Kaç kez iletildi
    views = Column(Integer, default=0)  # Görüntülenme sayısı
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())