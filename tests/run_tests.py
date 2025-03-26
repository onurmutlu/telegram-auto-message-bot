"""
Tüm testleri çalıştıran script
"""
import os
import sys
import pytest
import argparse
from colorama import Fore, Style, init

# Colorama başlat
init(autoreset=True)

def run_tests(verbose=False, failfast=False, specific_test=None):
    """
    Testleri çalıştırır
    
    Args:
        verbose: Ayrıntılı çıktı
        failfast: İlk hatada dur
        specific_test: Belirli bir test dosyasını çalıştır
    """
    print(f"{Fore.CYAN}=" * 60)
    print(f"{Fore.CYAN}TELEGRAM AUTO MESSAGE BOT v3.3 - TEST SUITE")
    print(f"{Fore.CYAN}=" * 60)
    
    # Testler dizinini al
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Proje kök dizinini Python yoluna ekle
    sys.path.insert(0, os.path.abspath(os.path.join(tests_dir, '..')))
    
    # Pytest argümanları
    pytest_args = []
    
    # Verbose mod
    if verbose:
        pytest_args.append('-v')
        
    # Failfast
    if failfast:
        pytest_args.append('-xvs')
        
    # Belirli bir test
    if specific_test:
        if not specific_test.startswith('test_'):
            specific_test = f'test_{specific_test}'
        if not specific_test.endswith('.py'):
            specific_test = f'{specific_test}.py'
            
        test_path = os.path.join(tests_dir, specific_test)
        if os.path.exists(test_path):
            pytest_args.append(test_path)
        else:
            print(f"{Fore.RED}HATA: Test dosyası bulunamadı: {test_path}")
            return 1
    else:
        # Tüm testleri çalıştır
        pytest_args.append(tests_dir)
    
    # Testleri çalıştır
    print(f"{Fore.YELLOW}Testler çalıştırılıyor...\n")
    result = pytest.main(pytest_args)
    
    # Sonucu göster
    if result == 0:
        print(f"\n{Fore.GREEN}✅ Tüm testler başarıyla geçti!")
    else:
        print(f"\n{Fore.RED}❌ Bazı testler başarısız oldu!")
    
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Telegram Auto Message Bot Test Runner')
    parser.add_argument('-v', '--verbose', action='store_true', help='Ayrıntılı çıktı göster')
    parser.add_argument('-f', '--failfast', action='store_true', help='İlk hatada dur')
    parser.add_argument('-t', '--test', help='Belirli bir test dosyasını çalıştır')
    
    args = parser.parse_args()
    
    # Testleri çalıştır
    sys.exit(run_tests(args.verbose, args.failfast, args.test))