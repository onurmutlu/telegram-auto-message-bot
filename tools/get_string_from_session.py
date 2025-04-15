import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession

# API kimlik bilgileri
API_ID = int(os.getenv("API_ID", "23692263"))
API_HASH = os.getenv("API_HASH", "ff5d6053b266f78d1293f9343f40e77e")

# Session dizini - runtime/sessions altında tutmak daha düzenli
SESSION_DIR = "runtime/sessions"
SESSION_FILES = ["anon", "telegram_session", "bot_session"]

def main():
    """Mevcut session dosyalarından StringSession oluştur"""
    print(f"API ID: {API_ID}")
    print(f"API HASH: {API_HASH[:5]}...{API_HASH[-5:]}")
    
    # Session dizinin var olduğundan emin ol
    os.makedirs(SESSION_DIR, exist_ok=True)
    
    # Eski session dizini (geçici çözüm için)
    old_session_dir = "session"
    if os.path.exists(old_session_dir):
        # Eski dizindeki session dosyalarını tara
        for filename in os.listdir(old_session_dir):
            if filename.endswith(".session"):
                session_name = filename.replace(".session", "")
                SESSION_FILES.append(session_name)
                # runtime/sessions dizinine kopyala (taşıma değil, güvenli olsun)
                old_path = os.path.join(old_session_dir, filename)
                new_path = os.path.join(SESSION_DIR, filename)
                if not os.path.exists(new_path):
                    import shutil
                    shutil.copy2(old_path, new_path)
                    print(f"Session dosyası taşındı: {old_path} -> {new_path}")
    
    for session_name in set(SESSION_FILES):  # Tekrarları önlemek için set
        session_path = os.path.join(SESSION_DIR, session_name)
        
        if os.path.exists(f"{session_path}.session"):
            print(f"\nSession dosyası bulundu: {session_path}.session")
            try:
                # Disk tabanlı yükle ve string olarak kaydet
                client = TelegramClient(session_path, API_ID, API_HASH)
                
                # Oturumu aç ve string olarak al
                with client:
                    session_string = StringSession.save(client.session)
                    print(f"\n{session_name} için StringSession:\n{session_string}\n")
                    print(f"Bu stringi .env dosyasında SESSION_STRING olarak kaydedebilirsiniz.")
                    
                    # Veya SQLite'a doğrudan kaydet
                    import sqlite3
                    try:
                        # Veritabanı dizininin var olduğundan emin ol
                        os.makedirs("data", exist_ok=True)
                        
                        conn = sqlite3.connect("data/users.db")
                        cursor = conn.cursor()
                        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                            key TEXT PRIMARY KEY, 
                            value TEXT
                        )''')
                        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                                    ("session_string", session_string))
                        conn.commit()
                        conn.close()
                        print(f"StringSession veritabanına kaydedildi!")
                    except Exception as e:
                        print(f"Veritabanına kaydederken hata: {e}")
                
            except Exception as e:
                print(f"Session dosyası işlenirken hata: {e}")
        else:
            print(f"Session dosyası bulunamadı: {session_path}.session")
    
    print("\n✅ İşlem tamamlandı! Session bilgileri runtime/sessions dizininde tutulmaktadır.")

if __name__ == "__main__":
    main() 