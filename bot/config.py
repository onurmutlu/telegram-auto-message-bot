class Config:
    def __init__(self, config_dict=None):
        self._config = config_dict or {}
        # Telegram ayarları için varsayılan değerler
        self.telegram = {
            'api_id': self._config.get('api_id', None),
            'api_hash': self._config.get('api_hash', None),
            'bot_token': self._config.get('bot_token', None),
            'phone': self._config.get('phone', None),
            'username': self._config.get('username', None),
            'session_name': self._config.get('session_name', 'telegram_session')
        }
        
    def get(self, key, default=None):
        """
        Yapılandırma değerini döndürür.
        
        Args:
            key: Yapılandırma anahtarı
            default: Varsayılan değer (anahtar bulunamazsa)
            
        Returns:
            Yapılandırma değeri veya varsayılan değer
        """
        return self._config.get(key, default)
        
    def set(self, key, value):
        """
        Yapılandırma değerini ayarlar.
        
        Args:
            key: Yapılandırma anahtarı
            value: Yapılandırma değeri
        """
        self._config[key] = value
        
    def __getitem__(self, key):
        return self._config[key]
        
    def __setitem__(self, key, value):
        self._config[key] = value
        
    def __contains__(self, key):
        return key in self._config
        
    def __str__(self):
        return str(self._config)
        
    def __repr__(self):
        return f"Config({self._config})"
        
    def get_setting(self, key, default=None):
        """
        Yapılandırma ayarını döndürür. Bu metot get() metoduyla aynı işlevi görür,
        ancak bazı servislerin beklediği arayüz uyumluluğu için eklenmiştir.
        
        Args:
            key: Yapılandırma anahtarı
            default: Varsayılan değer (anahtar bulunamazsa)
            
        Returns:
            Yapılandırma değeri veya varsayılan değer
        """
        return self.get(key, default) 