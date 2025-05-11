try:
    from app.models.base import BaseModel
    from app.models.user import User
    from app.models.group import Group, GroupMember
    from app.models.message import Message, MessageStatus, MessageType
    from app.models.message_template import MessageTemplate
except ImportError:
    # Göreceli importlar
    from .base import BaseModel
    from .user import User
    from .group import Group, GroupMember
    from .message import Message, MessageStatus, MessageType
    from .message_template import MessageTemplate

# SQLModel/SQLAlchemy için tüm modelleri dışa aktar
__all__ = [
    "BaseModel",
    "User",
    "Group",
    "GroupMember",
    "Message",
    "MessageStatus",
    "MessageType",
    "MessageTemplate"
] 