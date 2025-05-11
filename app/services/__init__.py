"""
# ============================================================================ #
# Dosya: __init__.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/__init__.py
# İşlev: Servisler modülü için başlatma dosyası.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

# Bu modülü aktif et
__all__ = [
    'ServiceWrapper', 
    'ServiceManager', 
    'ServiceFactory',
    'BaseService', 
    'UserService', 
    'GroupService', 
    'MessageService'
]

# Kullanılan sınıfları içe aktar
try:
    from app.services.service_wrapper import ServiceWrapper
    from app.services.service_manager import ServiceManager
    from app.services.service_factory import ServiceFactory
    from app.services.base_service import BaseService, ConfigAdapter
    from app.services.user_service import UserService
    from app.services.group_service import GroupService
    from app.services.message_service import MessageService
except ImportError:
    # Doğrudan içe aktarma yapalım (göreceli import)
    from .service_wrapper import ServiceWrapper
    from .service_manager import ServiceManager
    from .service_factory import ServiceFactory
    from .base_service import BaseService, ConfigAdapter
    from .user_service import UserService
    from .group_service import GroupService
    from .message_service import MessageService 