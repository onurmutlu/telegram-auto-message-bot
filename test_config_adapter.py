#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Config Adapter için birim testleri
"""

import unittest
from config_helper import ConfigAdapter, ConfigDict, ConfigWrapper, get_config_value

class TestConfigHelper(unittest.TestCase):
    """Config Helper modülü için birim testleri"""
    
    def test_config_dict(self):
        """ConfigDict sınıfının testleri"""
        # Basit config
        config_dict = ConfigDict({
            'key1': 'value1',
            'key2': 123,
            'nested': {
                'inner_key': 'inner_value',
                'another_key': 456
            }
        })
        
        # Basit anahtar testi
        self.assertEqual(config_dict.get_setting('key1'), 'value1')
        self.assertEqual(config_dict.get_setting('key2'), 123)
        self.assertEqual(config_dict.get_setting('nonexistent', 'default'), 'default')
        
        # İç içe anahtar testi
        self.assertEqual(config_dict.get_setting('nested.inner_key'), 'inner_value')
        self.assertEqual(config_dict.get_setting('nested.another_key'), 456)
        self.assertEqual(config_dict.get_setting('nested.nonexistent', 'nested_default'), 'nested_default')
        self.assertEqual(config_dict.get_setting('nonexistent.key', 'deep_default'), 'deep_default')
    
    def test_config_wrapper(self):
        """ConfigWrapper sınıfının testleri"""
        # get metoduna sahip mock sınıf
        class MockConfig:
            def __init__(self):
                self.settings = {
                    'key1': 'mock_value1',
                    'key2': 789
                }
                self.some_attribute = "test attribute"
                
            def get(self, key, default=None):
                return self.settings.get(key, default)
        
        mock_config = MockConfig()
        config_wrapper = ConfigWrapper(mock_config)
        
        # get_setting metodu testi
        self.assertEqual(config_wrapper.get_setting('key1'), 'mock_value1')
        self.assertEqual(config_wrapper.get_setting('key2'), 789)
        self.assertEqual(config_wrapper.get_setting('nonexistent', 'mock_default'), 'mock_default')
        
        # Öznitelik aktarımı testi
        self.assertEqual(config_wrapper.some_attribute, "test attribute")
    
    def test_config_adapter(self):
        """ConfigAdapter sınıfının testleri"""
        # Dictionary test
        dict_config = {'test': 'dict_value'}
        adapted_dict = ConfigAdapter.adapt_config(dict_config)
        self.assertIsInstance(adapted_dict, ConfigDict)
        self.assertEqual(adapted_dict.get_setting('test'), 'dict_value')
        
        # None değeri testi
        none_adapted = ConfigAdapter.adapt_config(None)
        self.assertIsInstance(none_adapted, ConfigDict)
        self.assertEqual(none_adapted.get_setting('any_key', 'none_default'), 'none_default')
        
        # get_setting metodu olan sınıf testi
        class ConfigWithGetSetting:
            def get_setting(self, key, default=None):
                if key == 'special_key':
                    return 'special_value'
                return default
                
        config_with_get_setting = ConfigWithGetSetting()
        adapted_with_get_setting = ConfigAdapter.adapt_config(config_with_get_setting)
        self.assertIs(adapted_with_get_setting, config_with_get_setting)
        self.assertEqual(adapted_with_get_setting.get_setting('special_key'), 'special_value')
        
        # get metodu olan sınıf testi
        class ConfigWithGet:
            def get(self, key, default=None):
                if key == 'get_key':
                    return 'get_value'
                return default
                
        config_with_get = ConfigWithGet()
        adapted_with_get = ConfigAdapter.adapt_config(config_with_get)
        self.assertIsInstance(adapted_with_get, ConfigWrapper)
        self.assertEqual(adapted_with_get.get_setting('get_key'), 'get_value')
    
    def test_get_config_value(self):
        """get_config_value yardımcı fonksiyonunun testleri"""
        # Dictionary
        dict_config = {'direct_key': 'direct_value'}
        self.assertEqual(get_config_value(dict_config, 'direct_key'), 'direct_value')
        self.assertEqual(get_config_value(dict_config, 'missing', 'dict_default'), 'dict_default')
        
        # get_setting metoduna sahip sınıf
        class GetSettingClass:
            def get_setting(self, key, default=None):
                if key == 'setting_key':
                    return 'setting_value'
                return default
                
        get_setting_obj = GetSettingClass()
        self.assertEqual(get_config_value(get_setting_obj, 'setting_key'), 'setting_value')
        self.assertEqual(get_config_value(get_setting_obj, 'missing', 'setting_default'), 'setting_default')
        
        # get metoduna sahip sınıf
        class GetClass:
            def get(self, key, default=None):
                if key == 'get_method_key':
                    return 'get_method_value'
                return default
                
        get_obj = GetClass()
        self.assertEqual(get_config_value(get_obj, 'get_method_key'), 'get_method_value')
        self.assertEqual(get_config_value(get_obj, 'missing', 'get_default'), 'get_default')
        
        # Öznitelik olarak
        class AttrClass:
            def __init__(self):
                self.attr_key = 'attr_value'
                
        attr_obj = AttrClass()
        self.assertEqual(get_config_value(attr_obj, 'attr_key'), 'attr_value')
        self.assertEqual(get_config_value(attr_obj, 'missing', 'attr_default'), 'attr_default')
        
        # None değeri
        self.assertEqual(get_config_value(None, 'any_key', 'none_default'), 'none_default')

if __name__ == '__main__':
    unittest.main() 