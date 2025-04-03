"""
# ============================================================================ #
# Dosya: test_user_db.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/test_user_db.py
# İşlev: Telegram bot bileşeni
#
# Build: 2025-04-01-00:07:55
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu test modülü, user_db için birim testleri içerir:
# - Temel işlevsellik testleri
# - Sınır koşulları ve hata durumları
# - Mock nesnelerle izolasyon
# 
# Kullanım: python -m pytest tests/test_user_db.py -v
#
# ============================================================================ #
"""

import pytest
import os
import tempfile
from pathlib import Path
import sqlite3
import sys

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# İçe aktarmayı düzelt
from database.user_db import UserDatabase

@pytest.fixture
def temp_db():
    """Geçici test veritabanı oluşturur"""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / 'test_users.db'
    db = UserDatabase(db_path)
    yield db
    db.close()
    # Temizlik
    if os.path.exists(db_path):
        os.remove(db_path)

def test_user_add(temp_db):
    """Kullanıcı ekleme testi"""
    user_id = 12345
    username = "test_user"
    
    # Kullanıcı ekle
    temp_db.add_user(user_id, username)
    
    # Kullanıcı var mı?
    users = temp_db.get_all_users()
    assert len(users) == 1
    assert users[0][0] == user_id
    assert users[0][1] == username

def test_invite_user(temp_db):
    """Kullanıcı davet işaretleme testi"""
    user_id = 12345
    username = "test_user"
    
    # Kullanıcı ekle
    temp_db.add_user(user_id, username)
    
    # Davet edildi olarak işaretle
    temp_db.mark_as_invited(user_id)
    
    # Davet edilmiş mi?
    assert temp_db.is_invited(user_id) == True
    
def test_error_groups(temp_db):
    """Hata veren grupları yönetme testi"""
    # Hata kaydı ekle
    group_id = 98765
    group_title = "Test Error Group"
    error_reason = "Test Error"
    
    # Hata grubu ekle
    temp_db.add_error_group(group_id, group_title, error_reason, retry_hours=8)
    
    # Hata gruplarını getir
    error_groups = temp_db.get_error_groups()
    assert len(error_groups) == 1
    assert error_groups[0][0] == group_id
    
    # Hata gruplarını temizle
    cleared = temp_db.clear_all_error_groups()
    assert cleared == 1
    
    # Tekrar kontrol et
    error_groups = temp_db.get_error_groups()
    assert len(error_groups) == 0