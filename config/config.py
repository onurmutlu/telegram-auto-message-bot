# Bu dosya sadece settings.py'daki Config sınıfını içe aktarır

from .settings import Config

# Gerekirse ek yapılandırma fonksiyonları buraya eklenebilir
def get_default_config():
    """Varsayılan yapılandırmayı döndürür."""
    return Config()

# Config sınıfını bulun ve load_config metodunu güncelleyin

class Config:
    # ...diğer kodlar...
    
    # Metodu sınıfa uygun şekilde değiştirin
    @classmethod
    def load_config(cls):
        """
        Yapılandırma yükler ve döndürür.
        
        Returns:
            Config: Doldurulmuş yapılandırma nesnesi
        """
        # Mevcut metodun içeriğini koruyun, sadece self -> cls olarak değiştirin
        config = cls()  # self.__class__() yerine cls() kullanın
        # ... diğer kod ...
        return config