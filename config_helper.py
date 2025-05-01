#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Config Helper - Config nesnesi ile sözlük yapısındaki config nesnelerini uyumlu hale getiren yardımcı sınıf
"""

from typing import Any, Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)

class ConfigAdapter:
    """
    Farklı config yapılarını uyumlu hale getiren adaptör sınıfı.
    Dict türünden config nesnelerine get_setting metodu ekler.
    """
    
    @staticmethod
    def adapt_config(config: Any) -> Any:
        """
        Config nesnesini uyumlu hale getirir
        
        Args:
            config: Orijinal config nesnesi (dict veya Config sınıfı)
            
        Returns:
            Uyumlu hale getirilmiş config nesnesi
        """
        # Eğer config None ise boş dict döndür
        if config is None:
            return ConfigDict({})
            
        # Eğer config bir dict ise ConfigDict'e çevir    
        if isinstance(config, dict):
            return ConfigDict(config)
            
        # Eğer get_setting metoduna sahipse orijinal config'i döndür
        if hasattr(config, 'get_setting'):
            return config
            
        # Eğer get metoduna sahipse ama get_setting yoksa, ConfigWrapper ile sar
        if hasattr(config, 'get'):
            return ConfigWrapper(config)
            
        # Değiştirilemeyen bir config nesnesi, olduğu gibi döndür 
        logger.warning(f"Config nesnesi ({type(config)}) uyumlu değil ve adapte edilemedi")
        return config


class ConfigDict(dict):
    """
    Dict türünden config nesnesi için get_setting metodunu ekleyen wrapper sınıf
    """
    
    def __init__(self, config_dict: Dict):
        super().__init__(config_dict)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Yapılandırma ayarını döndürür.
        
        Args:
            key: Yapılandırma anahtarı (nokta ile ayırarak iç içe değerlere erişilebilir)
            default: Varsayılan değer (anahtar bulunamazsa)
            
        Returns:
            Yapılandırma değeri veya varsayılan değer
        """
        # Nokta içeren anahtarlar için (örn: 'telegram.api_id')
        if '.' in key:
            parts = key.split('.')
            current = self
            try:
                for part in parts[:-1]:
                    if part in current and isinstance(current[part], dict):
                        current = current[part]
                    else:
                        return default
                
                last_part = parts[-1]
                if last_part in current:
                    return current[last_part]
                else:
                    return default
            except (KeyError, TypeError):
                return default
        
        # Basit anahtarlar için normal get metodunu kullan
        return self.get(key, default)


class ConfigWrapper:
    """
    get metodu olan ancak get_setting metodu olmayan config nesnelerini saran sınıf
    """
    
    def __init__(self, config: Any):
        """
        ConfigWrapper sınıfının başlatıcısı
        
        Args:
            config: get metoduna sahip config nesnesi
        """
        self._config = config
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Yapılandırma ayarını döndürür.
        
        Args:
            key: Yapılandırma anahtarı
            default: Varsayılan değer (anahtar bulunamazsa)
            
        Returns:
            Yapılandırma değeri veya varsayılan değer
        """
        # Nokta ile ayrılmış anahtarları desteklemez, doğrudan get metodunu kullanır
        if hasattr(self._config, 'get'):
            return self._config.get(key, default)
        return default
    
    def __getattr__(self, name: str) -> Any:
        """
        Bilinmeyen özniteliklere erişim orijinal config nesnesine aktarılır
        
        Args:
            name: Öznitelik adı
            
        Returns:
            Öznitelik değeri
        """
        return getattr(self._config, name)


# Helper fonksiyon
def get_config_value(config: Any, key: str, default: Any = None) -> Any:
    """
    Herhangi bir config nesnesinden değer okuyan yardımcı fonksiyon
    
    Args:
        config: Config nesnesi (herhangi bir tür)
        key: Yapılandırma anahtarı
        default: Varsayılan değer
        
    Returns:
        Yapılandırma değeri veya varsayılan değer
    """
    # Config None ise direkt default dön
    if config is None:
        return default
        
    # get_setting metodu varsa kullan
    if hasattr(config, 'get_setting'):
        return config.get_setting(key, default)
    
    # get metodu varsa kullan    
    if hasattr(config, 'get'):
        return config.get(key, default)
    
    # dict ise [] operatörü ile dene    
    if isinstance(config, dict):
        try:
            return config[key]
        except KeyError:
            return default
    
    # Son çare olarak attribute olarak dene        
    try:
        return getattr(config, key, default)
    except (AttributeError, TypeError):
        return default 