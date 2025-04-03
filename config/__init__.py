# Bu dosya, "from config.config import Config" ifadesini düzgün çalıştırır

# settings.py'daki Config sınıfını yeniden dışa aktarın
from .settings import Config

# Bu sayede "from config.config import Config" yerine 
# "from config import Config" şeklinde import edilebilir