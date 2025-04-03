"""
Dashboard modülleri için paket.
Tüm modül fonksiyonlarını buradan içe aktarıp erişimi kolaylaştırır.
"""

# Genel ayarlar modülü
from bot.utils.dashboard.general_settings import (
    api_settings,
    debug_settings,
    log_settings
)

# Mesaj ayarları modülü
from bot.utils.dashboard.message_settings import (
    set_message_interval,
    manage_message_templates,
    response_settings
)

# Grup ayarları modülü
from bot.utils.dashboard.group_settings import (
    manage_groups,
    target_groups,
    admin_groups,
    reset_error_groups,
    member_collection_settings
)

# Davet ayarları modülü
from bot.utils.dashboard.invite_settings import (
    manage_invite_templates,
    manage_super_users,
    invite_frequency
)

# Rate limiter ayarları modülü
from bot.utils.dashboard.rate_limiter_settings import (
    api_rate_limits,
    wait_times,
    error_behaviors
)

# Veritabanı ayarları modülü
from bot.utils.dashboard.database_settings import (
    db_stats,
    optimize_db,
    export_data,
    backup_restore
)

# Şablon düzenleyici modülü
from bot.utils.dashboard.template_editor import template_editor

__all__ = [
    'api_settings', 'debug_settings', 'log_settings',
    'set_message_interval', 'manage_message_templates', 'response_settings',
    'manage_groups', 'target_groups', 'admin_groups', 'reset_error_groups', 'member_collection_settings',
    'manage_invite_templates', 'manage_super_users', 'invite_frequency',
    'api_rate_limits', 'wait_times', 'error_behaviors',
    'db_stats', 'optimize_db', 'export_data', 'backup_restore',
    'template_editor'
]