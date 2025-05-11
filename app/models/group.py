from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlmodel import Field, Relationship
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.message import Message

class Group(BaseModel, table=True):
    """Telegram gruplarını temsil eden model"""
    __tablename__ = "groups"
    
    # Veritabanında var olan alanlar
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(unique=True, index=True)
    name: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    is_target: bool = Field(default=False)
    is_public: bool = Field(default=True)
    member_count: Optional[int] = Field(default=0)
    message_count: Optional[int] = Field(default=0)
    error_count: Optional[int] = Field(default=0)
    join_date: Optional[datetime] = Field(default_factory=datetime.utcnow)
    last_message: Optional[datetime] = None
    last_active: Optional[datetime] = Field(default_factory=datetime.utcnow)
    last_error: Optional[str] = None
    permanent_error: bool = Field(default=False)
    retry_after: Optional[datetime] = None
    invite_link: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    # İlişkiler
    members: List["GroupMember"] = Relationship(back_populates="group", sa_relationship_kwargs={"lazy": "selectin"})
    messages: List["Message"] = Relationship(back_populates="group", sa_relationship_kwargs={"primaryjoin": "Group.group_id==foreign(Message.group_id)", "lazy": "selectin"})
    
    def __repr__(self) -> str:
        return f"<Group {self.group_id}: {self.name or 'Adsız'}>"


class GroupMember(BaseModel, table=True):
    """Grup üyeliklerini temsil eden model (User-Group many-to-many ilişkisi)"""
    __tablename__ = "group_members"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.user_id", index=True)
    group_id: Optional[int] = Field(default=None, foreign_key="groups.group_id", index=True)
    
    # Üyelik bilgileri
    joined_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    is_admin: bool = Field(default=False)
    is_bot: bool = Field(default=False)
    
    # Relationships
    user: Optional["User"] = Relationship(back_populates="groups")
    group: Optional["Group"] = Relationship(back_populates="members")
    
    def __repr__(self) -> str:
        return f"<GroupMember user={self.user_id} group={self.group_id}>" 