from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlmodel import Field, Relationship
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.group import GroupMember

class User(BaseModel, table=True):
    """Telegram kullanıcılarını temsil eden model"""
    __tablename__ = "users"
    
    user_id: int = Field(unique=True, index=True)
    username: Optional[str] = Field(default=None, index=True)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = Field(default=True)
    
    # İstatistikler
    last_activity_at: Optional[datetime] = Field(default=None, alias="last_activity") # last_activity -> last_activity_at olarak değiştirildi ve alias eklendi
    message_count: int = Field(default=0)
    
    # Relationships
    groups: List["GroupMember"] = Relationship(back_populates="user")
    
    def full_name(self) -> str:
        """Kullanıcının tam adını döndürür"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"User {self.user_id}"
            
    def __repr__(self) -> str:
        return f"<User {self.full_name()} ({self.user_id})>"