#!/usr/bin/env python3
import os
import time
import sys
import json
import sqlite3
import requests
import threading
from datetime import datetime
from colorama import init, Fore, Back, Style

# Colorama başlat
init(autoreset=True)

def clear_screen():
    """Terminal ekranını temizler."""
    os.system('clear' if os.name == 'posix' else 'cls')

def get_db_stats():
    """Veritabanından istatistikleri alır."""
    try:
        db_path = os.environ.get('DB_PATH', 'runtime/database/users.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Toplam kullanıcı sayısı
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Son 24 saatte eklenen kullanıcılar
        cursor.execute("SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-1 day')")
        new_users = cursor.fetchone()[0]
        
        # Debug bot kullanıcıları (tablo varsa)
        debug_bot_users = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM debug_bot_users")
            debug_bot_users = cursor.fetchone()[0]
        except:
            pass
        
        conn.close()
        return {
            'total_users': total_users,
            'new_users': new_users,
            'debug_bot_users': debug_bot_users
        }
    except Exception as e:
        return {'error': str(e)}

def get_logs(limit=10):
    """Son log kayıtlarını alır."""
    try:
        log_path = 'runtime/logs/bot.log'
        with open(log_path, 'r') as f:
            logs = f.readlines()
        return logs[-limit:]
    except:
        return ["Loglar okunamadı"]

def get_service_status():
    """Servislerin durumunu kontrol eder."""
    try:
        # Socket veya HTTP isteği ile bot durumunu kontrol edebilirsiniz
        # Örnek olarak basit bir kontrol yapıyoruz
        services = {
            'message_service': {
                'running': True,
                'last_activity': datetime.now().strftime("%H:%M:%S"),
                'messages_sent': 0,
                'messages_received': 0
            },
            'dm_service': {
                'running': True,
                'last_activity': datetime.now().strftime("%H:%M:%S"),
                'processed_dms': 0,
                'invites_sent': 0
            },
            'reply_service': {
                'running': True,
                'last_activity': datetime.now().strftime("%H:%M:%S"),
                'replies_sent': 0
            }
        }
        
        # Bot session dosyasının varlığını kontrol et
        session_path = os.environ.get('SESSION_PATH', 'runtime/sessions/bot_session.session')
        services['telegram_client'] = {
            'connected': os.path.exists(session_path),
            'session_size': os.path.getsize(session_path) if os.path.exists(session_path) else 0
        }
        
        return services
    except Exception as e:
        return {'error': str(e)}

def display_dashboard():
    """Ana dashboard görüntüsünü hazırlar."""
    while True:
        clear_screen()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Header
        print(f"{Fore.CYAN}{Style.BRIGHT}╔══════════════════════════════════════════════════════════╗")
        print(f"{Fore.CYAN}{Style.BRIGHT}║{Fore.YELLOW} TELEGRAM BOT MONITOR {Fore.WHITE}- Aktif İzleme Paneli         {Fore.CYAN}║")
        print(f"{Fore.CYAN}{Style.BRIGHT}╚══════════════════════════════════════════════════════════╝")
        
        # Zaman bilgisi
        print(f"\n{Fore.GREEN}⏱️  Son güncelleme: {Fore.WHITE}{now}\n")
        
        # Veritabanı istatistikleri
        db_stats = get_db_stats()
        print(f"{Fore.MAGENTA}{Style.BRIGHT}📊 VERİTABANI İSTATİSTİKLERİ")
        if 'error' not in db_stats:
            print(f"{Fore.MAGENTA}╔════════════════════════════════╗")
            print(f"{Fore.MAGENTA}║ {Fore.WHITE}Toplam kullanıcı: {Fore.YELLOW}{db_stats['total_users']:<10} {Fore.MAGENTA}║")
            print(f"{Fore.MAGENTA}║ {Fore.WHITE}Son 24s yeni:    {Fore.YELLOW}{db_stats['new_users']:<10} {Fore.MAGENTA}║")
            print(f"{Fore.MAGENTA}║ {Fore.WHITE}Debug kullanıcı: {Fore.YELLOW}{db_stats['debug_bot_users']:<10} {Fore.MAGENTA}║")
            print(f"{Fore.MAGENTA}╚════════════════════════════════╝")
        else:
            print(f"{Fore.RED}Veritabanı hatası: {db_stats['error']}")
        
        # Servis durumu
        services = get_service_status()
        print(f"\n{Fore.BLUE}{Style.BRIGHT}🔄 SERVİS DURUMU")
        if 'error' not in services:
            print(f"{Fore.BLUE}╔════════════════════════════════╗")
            for service, status in services.items():
                if isinstance(status, dict) and 'running' in status:
                    running = status['running']
                    last_activity = status.get('last_activity', 'Bilinmiyor')
                    status_color = Fore.GREEN if running else Fore.RED
                    status_text = "✅ Aktif" if running else "❌ Durduruldu"
                    print(f"{Fore.BLUE}║ {Fore.WHITE}{service:<15}: {status_color}{status_text:<10} {Fore.YELLOW}{last_activity} {Fore.BLUE}║")
            
            # Telegram client durumu ayrı göster
            if 'telegram_client' in services:
                tc = services['telegram_client']
                tc_status = "✅ Bağlandı" if tc.get('connected') else "❌ Bağlantı Yok"
                tc_color = Fore.GREEN if tc.get('connected') else Fore.RED
                print(f"{Fore.BLUE}║ {Fore.WHITE}telegram_client{Fore.BLUE}: {tc_color}{tc_status:<10} {Fore.YELLOW}{tc.get('session_size', 0)} bytes {Fore.BLUE}║")
                
            print(f"{Fore.BLUE}╚════════════════════════════════╝")
        else:
            print(f"{Fore.RED}Servis durumu alınamadı: {services['error']}")
        
        # Son loglar
        print(f"\n{Fore.CYAN}{Style.BRIGHT}📜 SON LOGLAR")
        logs = get_logs(5)
        print(f"{Fore.CYAN}╔════════════════════════════════════════════════════╗")
        for log in logs:
            log = log.strip()
            if "ERROR" in log:
                print(f"{Fore.CYAN}║ {Fore.RED}{log[:60]}... {Fore.CYAN}║")
            elif "WARNING" in log:
                print(f"{Fore.CYAN}║ {Fore.YELLOW}{log[:60]}... {Fore.CYAN}║")
            elif "INFO" in log:
                print(f"{Fore.CYAN}║ {Fore.GREEN}{log[:60]}... {Fore.CYAN}║")
            else:
                print(f"{Fore.CYAN}║ {Fore.WHITE}{log[:60]}... {Fore.CYAN}║")
        print(f"{Fore.CYAN}╚════════════════════════════════════════════════════╝")
        
        # Bot komut durumu - gruplara giden mesajları kontrol et
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}✉️ MESAJ DURUMU")
        
        # Son mesaj izleme
        # Bu kısmı gerçek duruma göre güncelleyebilirsiniz
        print(f"{Fore.YELLOW}⚠️ Son 10 dakikada mesaj gönderilmedi!")
        print(f"{Fore.YELLOW}⚠️ Son 10 dakikada özel mesaj gönderilmedi!")
        print(f"{Fore.YELLOW}⁉️ Olası sorunlar için kontrol listesini görmek için SORUN GİDERME bölümüne bakın\n")
        
        # Sorun giderme
        print(f"{Fore.RED}{Style.BRIGHT}🔍 SORUN GİDERME")
        print(f"{Fore.WHITE}1. API izinleri kontrol edildi mi? {Fore.YELLOW}(https://my.telegram.org)")
        print(f"{Fore.WHITE}2. Hesap engellenmiş olabilir mi? {Fore.YELLOW}(Diğer hesapla test edin)")
        print(f"{Fore.WHITE}3. Gruba gerçekten erişim var mı? {Fore.YELLOW}(Grup ID'leri doğru mu?)")
        print(f"{Fore.WHITE}4. Rate limit kontrolü yapın {Fore.YELLOW}(Çok fazla istek olabilir)")
        print(f"{Fore.WHITE}5. SESSION dosyası geçerli mi? {Fore.YELLOW}(Yeniden oluşturmayı deneyin)")
        
        # Komutlar
        print(f"\n{Fore.GREEN}{Style.BRIGHT}📋 MEVCUT KOMUTLAR")
        print(f"{Fore.GREEN}• {Fore.WHITE}Test mesajı gönder: {Fore.YELLOW}python tools/send_test_message.py")
        print(f"{Fore.GREEN}• {Fore.WHITE}Grupları listele: {Fore.YELLOW}python tools/list_groups.py")
        print(f"{Fore.GREEN}• {Fore.WHITE}Session temizle: {Fore.YELLOW}python tools/clear_session.py")
        print(f"{Fore.GREEN}• {Fore.WHITE}Kullanıcı listele: {Fore.YELLOW}python tools/list_users.py")
        
        # Alt bilgi
        print(f"\n{Fore.WHITE}{Style.DIM}Çıkmak için Ctrl+C tuşlarına basın. Her 5 saniyede güncellenir...")
        
        # 5 saniye bekle
        time.sleep(5)

if __name__ == "__main__":
    try:
        display_dashboard()
    except KeyboardInterrupt:
        print(f"\n{Fore.GREEN}Monitör kapatıldı.")
        sys.exit(0)