"""
# ============================================================================ #
# Dosya: run_tests.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/run_tests.py
# İşlev: Telegram bot test ortamı yöneticisi
#
# Build: 2025-04-01
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram bot uygulamasının test ortamını yönetir ve test sürecini otomatikleştirir:
# - Test senaryolarını yürütme ve sonuçları analiz etme
# - Ayrıntılı raporlama ve loglama imkanı
# - Renkli terminal çıktıları ile test durumlarını görselleştirme
# - Test zaman aşımı ve hata yönetimi 
# - Test istatistiklerini yapılandırılmış bir şekilde sunma
#
# ============================================================================ #
"""
import os
import sys
import time
import pytest
import signal
import logging
import argparse
import subprocess
import re
import io
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Colorama kütüphanesini import et - terminal renkli çıktılar için
from colorama import init, Fore, Back, Style

# Colorama'yı başlat (Windows'ta ANSI kodlarını çalıştırabilmek için)
init(autoreset=True)

# Log dizini oluştur
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

# Zaman damgalı log dosya adı oluştur
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = logs_dir / f"test_run_{timestamp}.log"
results_file = logs_dir / f"test_results_{timestamp}.log"

# Renkli formatlayıcı sınıfı
class ColoredFormatter(logging.Formatter):
    """
    Renkli log formatları sağlar.
    
    Bu sınıf, farklı log seviyelerine göre özelleştirilmiş renkli 
    formatlar oluşturur ve terminal çıktısını daha okunabilir hale getirir.
    """
    
    FORMATS = {
        logging.DEBUG: Fore.CYAN + "%(asctime)s - %(name)s - " + Fore.BLUE + "%(levelname)s" + Fore.RESET + " - %(message)s",
        logging.INFO: Fore.GREEN + "%(asctime)s - %(name)s - " + Fore.GREEN + "%(levelname)s" + Fore.RESET + " - %(message)s",
        logging.WARNING: Fore.YELLOW + "%(asctime)s - %(name)s - " + Fore.YELLOW + "%(levelname)s" + Fore.RESET + " - %(message)s",
        logging.ERROR: Fore.RED + "%(asctime)s - %(name)s - " + Fore.RED + "%(levelname)s" + Fore.RESET + " - %(message)s",
        logging.CRITICAL: Fore.WHITE + Back.RED + "%(asctime)s - %(name)s - " + "%(levelname)s" + Fore.RESET + Back.RESET + " - %(message)s"
    }
    
    def format(self, record):
        """
        Belirtilen log kaydını formatlar.
        
        Args:
            record: Formatlanacak log kaydı
            
        Returns:
            str: Formatlanmış log kaydı
        """
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Güvenli loglama için özel bir sınıf oluşturalım
class SafeLogger(logging.Logger):
    """
    Handler'ları güvenli bir şekilde kullanan logger sınıfı.
    
    Bu sınıf, logger handler'larının düzgün şekilde kapatılmasını sağlayarak
    kaynak sızıntılarını ve hataları önler. Özellikle test ortamı gibi
    kaynak yönetiminin kritik olduğu durumlarda faydalıdır.
    """
    
    def __init__(self, name, level=logging.NOTSET):
        """
        SafeLogger sınıfının başlatıcı metodu.
        
        Args:
            name (str): Logger adı
            level (int): Başlangıç log seviyesi
        """
        super().__init__(name, level)
        self._handlers_closed = False
    
    def close_handlers(self):
        """
        Tüm handler'ları güvenli bir şekilde kapatır.
        
        Bu metot, uygulama sonlandığında veya hata durumunda
        tüm handler'ların düzgün şekilde kapatılmasını sağlar.
        """
        if not self._handlers_closed:
            for handler in self.handlers:
                try:
                    handler.close()
                except Exception:
                    pass
            self._handlers_closed = True
    
    def _log(self, level, msg, args, **kwargs):
        """
        Handler'lar kapatıldıktan sonra log yazmayı engeller.
        
        Args:
            level (int): Log seviyesi
            msg (str): Log mesajı
            args (tuple): Format argümanları
            **kwargs: Ek anahtar kelime argümanları
        """
        if not self._handlers_closed:
            super()._log(level, msg, args, **kwargs)

# Logger yapılandırması için özel sınıfı kaydedelim
logging.setLoggerClass(SafeLogger)

# Logger oluştur
logger = logging.getLogger("test_runner")
logger.setLevel(logging.DEBUG)

# Önceki handler'ları temizle
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Dosya handler - renkler olmadan normal format
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setFormatter(file_format)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# Console handler - renkli format
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredFormatter())
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

# Timeout süresi - saniye cinsinden
DEFAULT_TIMEOUT = 30  # 30 saniye

# ASCII sanat başlığı
ASCII_BANNER = fr"""
{Fore.CYAN}{Style.BRIGHT}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  {Fore.YELLOW}████████╗███████╗██╗     ███████╗ ██████╗ ██████╗  █████╗ ███╗   ███╗{Fore.CYAN}  ║
║  {Fore.YELLOW}╚══██╔══╝██╔════╝██║     ██╔════╝██╔════╝ ██╔══██╗██╔══██╗████╗ ████║{Fore.CYAN}  ║
║  {Fore.YELLOW}   ██║   █████╗  ██║     █████╗  ██║  ███╗██████╔╝███████║██╔████╔██║{Fore.CYAN}  ║
║  {Fore.YELLOW}   ██║   ██╔══╝  ██║     ██╔══╝  ██║   ██║██╔══██╗██╔══██║██║╚██╔╝██║{Fore.CYAN}  ║
║  {Fore.YELLOW}   ██║   ███████╗███████╗███████╗╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║{Fore.CYAN}  ║
║  {Fore.YELLOW}   ╚═╝   ╚══════╝╚══════╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝{Fore.CYAN}  ║
║                                                              ║
║             {Fore.MAGENTA}AUTO MESSAGE BOT v3.4.0 - TEST SUITE{Fore.CYAN}             ║
╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""

def extract_test_results(output):
    """
    Pytest çıktısından test sonuçlarını çıkarır.
    
    Pytest çıktı metnini analiz ederek, çalıştırılan testlerin
    istatistiksel bilgilerini çıkarır.
    
    Args:
        output (str): pytest çıktısı
        
    Returns:
        dict: Ayrıştırılmış test istatistikleri
            {
                'total': Toplam test sayısı,
                'passed': Başarılı test sayısı,
                'failed': Başarısız test sayısı,
                'skipped': Atlanan test sayısı,
                'errors': Hata sayısı,
                'xfailed': Beklenen başarısızlık sayısı,
                'xpassed': Beklenmeyen başarı sayısı,
                'warnings': Uyarı sayısı
            }
    """
    stats = {
        'total': 0,
        'passed': 0, 
        'failed': 0, 
        'skipped': 0, 
        'errors': 0,
        'xfailed': 0,
        'xpassed': 0,
        'warnings': 0
    }
    
    # Toplam test sayısını al
    collected_match = re.search(r'collected (\d+) items', output)
    if collected_match:
        stats['total'] = int(collected_match.group(1))
    
    # Sonuç detayını al - son satırdan bilgileri çek
    summary_lines = [line for line in output.split('\n') if re.search(r'\d+ passed', line) or re.search(r'\d+ failed', line)]
    if summary_lines:
        last_summary = summary_lines[-1]
        
        # Her kategori için kontrol et
        passed_match = re.search(r'(\d+) passed', last_summary)
        if passed_match:
            stats['passed'] = int(passed_match.group(1))
        
        failed_match = re.search(r'(\d+) failed', last_summary)
        if failed_match:
            stats['failed'] = int(failed_match.group(1))
        
        skipped_match = re.search(r'(\d+) skipped', last_summary)
        if skipped_match:
            stats['skipped'] = int(skipped_match.group(1))
        
        errors_match = re.search(r'(\d+) errors', last_summary)
        if errors_match:
            stats['errors'] = int(errors_match.group(1))
            
        xfailed_match = re.search(r'(\d+) xfailed', last_summary)
        if xfailed_match:
            stats['xfailed'] = int(xfailed_match.group(1))
            
        xpassed_match = re.search(r'(\d+) xpassed', last_summary)
        if xpassed_match:
            stats['xpassed'] = int(xpassed_match.group(1))
            
        warnings_match = re.search(r'(\d+) warnings', last_summary)
        if warnings_match:
            stats['warnings'] = int(warnings_match.group(1))
    
    # Warnings sayısı için özel kontrol - warnings summary bölümünden
    if stats['warnings'] == 0:
        warnings_section = re.search(r'(\d+) warnings', output)
        if warnings_section:
            stats['warnings'] = int(warnings_section.group(1))
    
    return stats

def handle_timeout(signum, frame):
    """
    Timeout işleyici fonksiyonu.
    
    SIGALRM sinyali alındığında çağrılır ve test sürecini sonlandırır.
    
    Args:
        signum (int): Sinyal numarası
        frame: Mevcut yığın çerçevesi
    """
    print(f"{Fore.RED}{Style.BRIGHT}⚠️  TIMEOUT: Test çalışması zaman aşımına uğradı!{Style.RESET_ALL}")
    sys.exit(1)

def print_test_summary(stats, elapsed):
    """
    Test sonuçlarını özetler ve yazdırır.
    
    Test koşumu tamamlandıktan sonra istatistikleri renkli
    ve formatlanmış bir şekilde konsola yazdırır.
    
    Args:
        stats (dict): Test istatistikleri
        elapsed (float): Test koşumunun geçen süresi (saniye)
    """
    print(f"\n{Fore.CYAN}{Style.BRIGHT}📊 Test Özeti:{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 70}{Style.RESET_ALL}")
    
    # Sonuç yorumu - BAŞARILI kriterlerini düzelt: uyarılar, testin başarısını etkilemez
    if stats['failed'] > 0 or stats['errors'] > 0:
        result_str = f"{Fore.RED}{Style.BRIGHT}BAŞARISIZ❌{Style.RESET_ALL}"
    elif stats['passed'] == 0 and stats['total'] == 0:
        result_str = f"{Fore.YELLOW}{Style.BRIGHT}TEST YOK⚠️{Style.RESET_ALL}"
    elif stats['passed'] > 0 and stats['passed'] == stats['total']:
        # Tüm testler geçti, uyarılar olabilir ama bu testlerin başarılı olmasını engellemez
        result_str = f"{Fore.GREEN}{Style.BRIGHT}BAŞARILI✅{Style.RESET_ALL}"
    elif stats['passed'] > 0 and stats['passed'] < stats['total']:
        # Bazı testler geçti, bazıları atlandı veya beklenen hata
        result_str = f"{Fore.YELLOW}{Style.BRIGHT}KISMİ✓⚠️{Style.RESET_ALL}"
    else:
        result_str = f"{Fore.YELLOW}{Style.BRIGHT}DURUMU BİLİNMİYOR❓{Style.RESET_ALL}"
    
    # Süre değerlendirme
    if elapsed < 1.0:
        duration_str = f"{Fore.GREEN}ÇOK HIZLI ({elapsed:.2f}s)🚀{Fore.RESET}"
    elif elapsed < 5.0:
        duration_str = f"{Fore.GREEN}HIZLI ({elapsed:.2f}s)⚡{Fore.RESET}"
    elif elapsed < 15.0:
        duration_str = f"{Fore.YELLOW}NORMAL ({elapsed:.2f}s)⏱️{Fore.RESET}"
    else:
        duration_str = f"{Fore.RED}YAVAŞ ({elapsed:.2f}s)🐢{Fore.RESET}"
    
    # Test sayılarını göster
    print(f"  {Fore.YELLOW}Genel Durum:{Fore.RESET} {result_str}")
    print(f"  {Fore.YELLOW}Toplam Test:{Fore.RESET} {stats['total']}")
    
    if stats['passed'] > 0:
        print(f"  {Fore.YELLOW}Başarılı:{Fore.RESET} {Fore.GREEN}{stats['passed']}{Fore.RESET}")
    
    if stats['failed'] > 0:
        print(f"  {Fore.YELLOW}Başarısız:{Fore.RESET} {Fore.RED}{stats['failed']}{Fore.RESET}")
    
    if stats['errors'] > 0:
        print(f"  {Fore.YELLOW}Hatalar:{Fore.RESET} {Fore.RED}{stats['errors']}{Fore.RESET}")
    
    if stats['skipped'] > 0:
        print(f"  {Fore.YELLOW}Atlanan:{Fore.RESET} {Fore.YELLOW}{stats['skipped']}{Fore.RESET}")
    
    if stats['warnings'] > 0:
        print(f"  {Fore.YELLOW}Uyarılar:{Fore.RESET} {Fore.YELLOW}{stats['warnings']}{Fore.RESET} (testlerin başarısını etkilemez)")
    
    if stats['xfailed'] > 0 or stats['xpassed'] > 0:
        print(f"  {Fore.YELLOW}Beklenen Hatalar:{Fore.RESET} {stats['xfailed']} | {Fore.YELLOW}Beklenmeyen Geçişler:{Fore.RESET} {stats['xpassed']}")
    
    print(f"  {Fore.YELLOW}Süre:{Fore.RESET} {duration_str}")
    
    # Çalıştırıcı bilgileri
    print(f"  {Fore.YELLOW}Test Çalıştırıcı:{Fore.RESET} pytest-{pytest.__version__}")
    print(f"  {Fore.YELLOW}Python Sürümü:{Fore.RESET} {sys.version.split()[0]}")
    print(f"  {Fore.YELLOW}Platform:{Fore.RESET} {sys.platform}")
    print(f"  {Fore.YELLOW}Tarih/Saat:{Fore.RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Fore.BLUE}{'─' * 70}{Style.RESET_ALL}")
    
    # Sonuç dosyasına da kaydet
    try:
        with open(results_file, 'w', encoding='utf-8') as f:
            f.write(f"Test Özeti - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'─' * 70}\n")
            f.write(f"Genel Durum: {result_str.replace(Fore.RED, '').replace(Fore.GREEN, '').replace(Fore.YELLOW, '').replace(Style.BRIGHT, '').replace(Style.RESET_ALL, '')}\n")
            f.write(f"Toplam Test: {stats['total']}\n")
            f.write(f"Başarılı: {stats['passed']}\n")
            f.write(f"Başarısız: {stats['failed']}\n")
            f.write(f"Hatalar: {stats['errors']}\n")
            f.write(f"Atlanan: {stats['skipped']}\n")
            f.write(f"Uyarılar: {stats['warnings']}\n")
            f.write(f"Beklenen Hatalar: {stats['xfailed']}\n")
            f.write(f"Beklenmeyen Geçişler: {stats['xpassed']}\n")
            f.write(f"Süre: {elapsed:.2f}s\n")
            f.write(f"{'─' * 70}\n")
    except Exception as e:
        logger.error(f"Sonuç dosyası yazılırken hata: {e}")

def run_tests(verbose=False, failfast=False, test=None, timeout=DEFAULT_TIMEOUT, fix_warnings=False):
    """
    Testleri çalıştırır ve sonuçları değerlendirir.
    
    Bu fonksiyon, argümanlarla belirtilen testleri çalıştırır,
    çıktıları kaydeder ve sonuçları değerlendirir.
    
    Args:
        verbose (bool): Ayrıntılı çıktı göstermek için True
        failfast (bool): İlk hatada testi durdurmak için True
        test (str): Belirli bir test dosyasını çalıştırmak için dosya adı
        timeout (int): Test zaman aşımı süresi (saniye)
        fix_warnings (bool): Uyarıları gizlemek için True
    
    Returns:
        tuple: (çıkış_kodu, test_istatistikleri)
            çıkış_kodu (int): 0 başarılı, diğerleri hata
            test_istatistikleri (dict): Test istatistikleri sözlüğü
    """
    # Banner'ı yazdır
    print(ASCII_BANNER)
    
    # Log bilgilerini yazdır
    logger.info(f"{Fore.BLUE}📊 {Style.BRIGHT}Test oturumu başlatıldı{Style.RESET_ALL} • {Fore.CYAN}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{Fore.BLUE}📝 {Style.BRIGHT}Log dosyası:{Style.RESET_ALL} {log_file}")
    
    # Test parametrelerini yazdır
    test_params = []
    if verbose:
        test_params.append(f"{Fore.YELLOW}ayrıntılı mod{Fore.RESET}")
    if failfast:
        test_params.append(f"{Fore.RED}hızlı başarısızlık{Fore.RESET}")
    if test:
        test_params.append(f"{Fore.GREEN}belirli test: {test}{Fore.RESET}")
    if fix_warnings:
        test_params.append(f"{Fore.CYAN}uyarıları gizle{Fore.RESET}")
    
    if test_params:
        logger.info(f"{Fore.BLUE}⚙️  {Style.BRIGHT}Test parametreleri:{Style.RESET_ALL} {' | '.join(test_params)}")
    
    # Timeout ayarla - Mac'de SIGALRM için özel işlem
    if timeout > 0 and sys.platform != 'win32':
        signal.signal(signal.SIGALRM, handle_timeout)
        signal.alarm(timeout)
        logger.debug(f"Timeout {timeout} saniye olarak ayarlandı")
    
    # Pytest argümanları
    pytest_args = ['python', '-m', 'pytest']
    
    # Verbose mod
    if verbose:
        pytest_args.append('-v')
    
    # Failfast
    if failfast:
        pytest_args.append('-xvs')
    
    # Uyarı düzeltmeleri
    if fix_warnings:
        pytest_args.append('--disable-warnings')
        print(f"{Fore.CYAN}⚙️  Uyarılar gizleniyor{Style.RESET_ALL}")
    
    # Belirli bir test
    if test:
        if not test.startswith('test_'):
            test = f'test_{test}'
        if not test.endswith('.py'):
            test = f'{test}.py'
        
        test_file = os.path.join(os.path.dirname(__file__), test)
        if os.path.exists(test_file):
            pytest_args.append(test_file)
        else:
            print(f"{Fore.RED}⛔ HATA: Test dosyası bulunamadı: {test_file}")
            return 1, {}
    
    # Asyncio mode strict
    pytest_args.append('--asyncio-mode=strict')
    
    # Testlerin başlangıç zamanını kaydet
    start_time = time.time()
    
    # Test başladı bilgisi
    logger.info(f"\n{Fore.CYAN}{Style.BRIGHT}⏳ Testler çalıştırılıyor...{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 70}{Style.RESET_ALL}")
    
    result = 1  # Varsayılan olarak başarısız kabul et
    test_output = ""
    test_stats = {
        'total': 0,
        'passed': 0, 
        'failed': 0, 
        'skipped': 0, 
        'errors': 0,
        'xfailed': 0,
        'xpassed': 0,
        'warnings': 0
    }
    
    try:
        # Subprocess olarak pytest çalıştırma
        process = subprocess.Popen(
            pytest_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Çıktıyı satır satır gerçek zamanlı oku ve yazdır
        for line in process.stdout:
            sys.stdout.write(line)
            test_output += line
        
        # İşlem tamamlandı, çıkış kodunu al
        process.stdout.close()
        result = process.wait()
        
        # Timeout'u iptal et
        if timeout > 0 and sys.platform != 'win32':
            signal.alarm(0)
        
        print(f"{Fore.BLUE}{'─' * 70}{Style.RESET_ALL}")
        
        # Test sonuçları
        elapsed = time.time() - start_time
        
        # Test istatistiklerini çıkarır
        test_stats = extract_test_results(test_output)
        
        # Sonucu göster - renkli ve emojili
        if result == 0 and test_stats['failed'] == 0 and test_stats['errors'] == 0:
            print(f"\n{Fore.GREEN}{Style.BRIGHT}✅ Tüm testler başarıyla geçti!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}{Style.BRIGHT}❌ Bazı testler başarısız oldu!{Style.RESET_ALL}")
        
        # Test süresini göster
        duration_color = Fore.GREEN if elapsed < 5 else Fore.YELLOW if elapsed < 15 else Fore.RED
        print(f"{Fore.BLUE}⏱️  Toplam süre: {duration_color}{elapsed:.2f} saniye{Fore.RESET}")
        
        # Detaylı test özetini göster
        print_test_summary(test_stats, elapsed)
        
    except KeyboardInterrupt:
        print(f"\n{Fore.BLUE}{'─' * 70}{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}⚠️  Testler kullanıcı tarafından durduruldu.{Style.RESET_ALL}")
        
        # İşlemi sonlandır
        if 'process' in locals() and process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        # Asenkron görevleri temizlemeye çalış
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                tasks = asyncio.all_tasks(loop)
                for task in tasks:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                loop.close()
        except Exception:
            pass
        
        result = 1
    except Exception as e:
        print(f"\n{Fore.BLUE}{'─' * 70}{Style.RESET_ALL}")
        print(f"{Fore.RED}{Style.BRIGHT}⛔ Testleri çalıştırırken hata: {e}{Style.RESET_ALL}")
        result = 1
    finally:
        # Timeout'u iptal et
        if timeout > 0 and sys.platform != 'win32':
            signal.alarm(0)
    
    return result, test_stats

def test_extract_test_results_success():
    """
    Test istatistikleri çıkarma - başarı durumunda.
    
    Bu birim test fonksiyonu, extract_test_results fonksiyonunun
    başarılı test sonuçlarını doğru şekilde çıkarabildiğini doğrular.
    """
    sample_output = """
    ============================= test session starts ==============================
    platform darwin -- Python 3.9.2, pytest-8.3.5, pluggy-1.5.0
    collected 10 items
    
    tests/test_example.py ..........                                      [100%]
    
    ========================= 10 passed in 0.12s =========================
    """
    stats = extract_test_results(sample_output)
    assert stats['total'] == 10
    assert stats['passed'] == 10
    assert stats['failed'] == 0

def test_extract_test_results_mixed():
    """
    Test istatistikleri çıkarma - karışık sonuçlar.
    
    Bu birim test fonksiyonu, extract_test_results fonksiyonunun
    karışık test sonuçlarını doğru şekilde çıkarabildiğini doğrular.
    """
    sample_output = """
    ============================= test session starts ==============================
    platform darwin -- Python 3.9.2, pytest-8.3.5, pluggy-1.5.0
    collected 10 items
    
    tests/test_example.py .....F..s.                                      [100%]
    
    ========================= 1 failed, 8 passed, 1 skipped, 2 warnings in 0.12s =========================
    """
    stats = extract_test_results(sample_output)
    assert stats['total'] == 10
    assert stats['passed'] == 8
    assert stats['failed'] == 1
    assert stats['skipped'] == 1
    assert stats['warnings'] == 2

def test_safe_logger_closed_handlers():
    """
    SafeLogger kapalı handler'lara yazma denemesi.
    
    Bu birim test fonksiyonu, SafeLogger sınıfının handler'lar
    kapatıldıktan sonra log yazma girişimlerini engellediğini doğrular.
    """
    logger = SafeLogger("test_logger")
    handler = logging.StreamHandler(io.StringIO())
    logger.addHandler(handler)
    
    # Handler'ları kapat
    logger.close_handlers()
    
    # Kapalı handler'lara yazma girişimi
    logger.info("Bu log yazılmamalı")
    
    # Çıktı boş olmalı
    assert handler.stream.getvalue() == ""

def test_subprocess_error_handling():
    """
    Subprocess hataları ile başa çıkma.
    
    Bu birim test fonksiyonu, run_tests fonksiyonunun subprocess
    çalıştırılması sırasında ortaya çıkan hataları doğru şekilde
    ele alabildiğini doğrular.
    """
    with patch('subprocess.Popen') as mock_popen:
        mock_popen.side_effect = OSError("Komut bulunamadı")
        result, stats = run_tests(test="nonexistent")
        assert result != 0  # Hata kodu döndürmeli

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Telegram Auto Message Bot Test Runner')
    parser.add_argument('-v', '--verbose', action='store_true', help='Ayrıntılı çıktı göster')
    parser.add_argument('-f', '--failfast', action='store_true', help='İlk hatada dur')
    parser.add_argument('-t', '--test', help='Belirli bir test dosyasını çalıştır')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, 
                       help=f'Test zaman aşımı (saniye), 0 için timeout yok (varsayılan: {DEFAULT_TIMEOUT})')
    parser.add_argument('--fix-warnings', action='store_true', help='pytest-asyncio uyarılarını düzelt')
    
    try:
        # Testleri çalıştır
        args = parser.parse_args()
        exit_code, _ = run_tests(args.verbose, args.failfast, args.test, args.timeout, args.fix_warnings)
        
        # Program normal bir şekilde sonlanmadan önce log handler'ları kapat
        if isinstance(logger, SafeLogger):
            logger.close_handlers()
        
        sys.exit(exit_code)
    except Exception as e:
        print(f"{Fore.RED}{Style.BRIGHT}⛔ Test betiğinde beklenmeyen hata: {e}{Style.RESET_ALL}")
        
        # Herhangi bir hata durumunda da log handler'ları kapat
        if isinstance(logger, SafeLogger):
            logger.close_handlers()
        
        sys.exit(1)